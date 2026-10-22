"""Transactional outbox and opt-in generic HTTP provider adapter.

The real adapter requires institutional approval, DLT details, a template ID,
and a provider endpoint accepting the documented JSON contract.
"""
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import *
from .auth import require_admin, admin_write

router=APIRouter(prefix='/sms',tags=['notifications'])

def queue(db,record,session,student,guardian,kind,body,key):
    existing=db.scalar(select(SmsMessage).where(SmsMessage.dedupe_key==key))
    if existing and existing.status=='cancelled':
        existing.status='queued';existing.attempts=0;existing.body=body;existing.phone=guardian.phone
    elif not existing:
        db.add(SmsMessage(record_id=record.id,student_id=student.id,guardian_id=guardian.id,kind=kind,phone=guardian.phone,body=body,dedupe_key=key))

def enqueue_session(db,session):
    from .attendance import aggregate
    for record in db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id==session.id)):
        student=db.get(Student,record.student_id)
        guardian=db.scalar(select(Guardian).join(StudentGuardian,StudentGuardian.guardian_id==Guardian.id).where(StudentGuardian.student_id==student.id,StudentGuardian.primary==True))
        if not guardian:continue
        for old in db.scalars(select(SmsMessage).where(SmsMessage.record_id==record.id,SmsMessage.status=='queued')):
            if old.kind in ('absent','late') and old.kind!=record.status:old.status='cancelled'
        if record.status in ('absent','late'):
            kind=record.status
            option=db.get(Setting,'sms_'+kind)
            if not option or option.value!='false':
                template=db.scalar(select(SmsTemplate).where(SmsTemplate.kind==kind))
                default=('Dear Parent, your ward {name} was marked absent for {session} on {date}. - CampusTrack' if kind=='absent' else 'Dear Parent, your ward {name} arrived late at {time} on {date}. - CampusTrack')
                body=(template.body if template else default).format(name=student.full_name,session=session.label,date=session.day.strftime('%d-%m-%Y'),time=record.arrival_time.strftime('%I:%M %p') if record.arrival_time else 'an unrecorded time')
                queue(db,record,session,student,guardian,kind,body,f'{session.id}:{student.id}:{guardian.id}:{kind}')
        option=db.get(Setting,'sms_low')
        if option and option.value=='true':
            pct=aggregate(db,student.id,end=session.day)['percentage']
            threshold=int(db.get(Setting,'min_percentage').value) if db.get(Setting,'min_percentage') else 75
            if pct is not None and pct<threshold:
                template=db.scalar(select(SmsTemplate).where(SmsTemplate.kind=='low'))
                default='Dear Parent, your ward {name} currently has {percentage}% attendance as of {date}. - CampusTrack'
                body=(template.body if template else default).format(name=student.full_name,percentage=pct,date=session.day.strftime('%d-%m-%Y'))
                queue(db,record,session,student,guardian,'low',body,f'low:{session.day}:{student.id}:{guardian.id}')

def delivery(db,m):
    if not (settings.sms_enabled and settings.sms_college_approved):
        m.status='simulated';detail='Mock gateway: no SMS transmitted'
    else:
        template=db.scalar(select(SmsTemplate).where(SmsTemplate.kind==m.kind))
        if not all([settings.sms_provider_url.startswith('https://'),settings.sms_api_key,settings.sms_sender_id,settings.sms_dlt_entity_id,template and template.dlt_template_id]):
            m.status='failed';detail='HTTPS provider and approved DLT configuration required'
        else:
            try:
                response=httpx.post(settings.sms_provider_url,headers={'Authorization':'Bearer '+settings.sms_api_key},json={'to':m.phone,'message':m.body,'sender_id':settings.sms_sender_id,'entity_id':settings.sms_dlt_entity_id,'template_id':template.dlt_template_id},timeout=10)
                response.raise_for_status()
                m.status='sent';m.provider_reference=response.json().get('id') if response.headers.get('content-type','').startswith('application/json') else None
                detail='Provider accepted the request; delivery receipt not verified'
            except (httpx.HTTPError,ValueError) as exc:
                m.status='failed';detail=type(exc).__name__
    m.attempts+=1;m.error=detail if m.status=='failed' else None
    db.add(SmsDeliveryLog(message_id=m.id,status=m.status,detail=detail))

@router.get('/messages')
def messages(u:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [dict(id=x.id,kind=x.kind,student_id=x.student_id,phone=x.phone,body=x.body,status=x.status,attempts=x.attempts,error=x.error,created_at=x.created_at.isoformat()) for x in db.scalars(select(SmsMessage).order_by(SmsMessage.id.desc()).limit(250))]

@router.post('/process')
def process(u:User=Depends(admin_write),db:Session=Depends(get_db)):
    pending=db.scalars(select(SmsMessage).where(or_(SmsMessage.status=='queued',(SmsMessage.status=='failed')&(SmsMessage.attempts<3))).order_by(SmsMessage.id).limit(100).with_for_update(skip_locked=True)).all()
    for m in pending:delivery(db,m)
    db.commit();return {'processed':len(pending),'mode':'mock' if not (settings.sms_enabled and settings.sms_college_approved) else 'provider'}

@router.get('/templates')
def templates(u:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [{'id':t.id,'kind':t.kind,'body':t.body,'dlt_template_id':t.dlt_template_id} for t in db.scalars(select(SmsTemplate))]

class TemplateIn(BaseModel):
    kind:str=Field(pattern='^(absent|late|low)$')
    body:str=Field(min_length=10,max_length=1000)
    dlt_template_id:str|None=None

@router.put('/templates')
def update_template(data:TemplateIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    t=db.scalar(select(SmsTemplate).where(SmsTemplate.kind==data.kind))
    if not t:t=SmsTemplate(**data.model_dump());db.add(t)
    else:t.body=data.body;t.dlt_template_id=data.dlt_template_id
    db.flush();db.add(AuditLog(actor_id=u.id,action='updated',entity='sms_templates',entity_id=t.id));db.commit()
    return {'id':t.id,'kind':t.kind,'body':t.body,'dlt_template_id':t.dlt_template_id}
