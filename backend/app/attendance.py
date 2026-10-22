from datetime import date, time, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from .db import get_db
from .models import *
from .auth import current_user, require_write
from .core import teacher_class, roster, save, audit

router=APIRouter(prefix='/attendance',tags=['attendance'])
IST=ZoneInfo('Asia/Kolkata')

def setting(db,key,default):
    x=db.get(Setting,key)
    return x.value if x else default

def is_blocked(db,cid,day):
    matching=db.scalars(select(CalendarDay).where(CalendarDay.day==day,or_(CalendarDay.class_id==None,CalendarDay.class_id==cid))).all()
    if any(x.attendance_required or x.kind=='working_day' for x in matching):return False
    if any(x.kind in ('holiday','closure') for x in matching):return True
    return day.weekday() in [int(x) for x in setting(db,'weekend_days','6').split(',')]

def session_dict(db,x,include_records=True):
    out=dict(id=x.id,class_id=x.class_id,subject_id=x.subject_id,day=x.day.isoformat(),label=x.label,state=x.state,version=x.version,cancelled=x.cancelled)
    if include_records:
        out['records']=[dict(id=r.id,student_id=r.student_id,status=r.status,arrival_time=r.arrival_time.isoformat(timespec='minutes') if r.arrival_time else None) for r in db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id==x.id))]
    return out

class SessionIn(BaseModel):
    class_id:int
    day:date
    subject_id:int|None=None
    label:str=Field(default='Daily',min_length=1,max_length=100)

@router.get('/sessions')
def sessions(class_id:int|None=None,start:date|None=None,end:date|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(AttendanceSession).order_by(AttendanceSession.day.desc(),AttendanceSession.id.desc())
    if class_id:teacher_class(db,u,class_id);q=q.where(AttendanceSession.class_id==class_id)
    elif u.role!='admin':q=q.join(TeacherAssignment,TeacherAssignment.class_id==AttendanceSession.class_id).where(TeacherAssignment.teacher_id==u.id).distinct()
    if start:q=q.where(AttendanceSession.day>=start)
    if end:q=q.where(AttendanceSession.day<=end)
    return [session_dict(db,x,False) for x in db.scalars(q.limit(300))]

@router.post('/sessions')
def create_session(data:SessionIn,u:User=Depends(require_write),db:Session=Depends(get_db)):
    teacher_class(db,u,data.class_id,data.subject_id)
    c=db.get(SchoolClass,data.class_id)
    if not c or not c.active:raise HTTPException(400,'Class inactive or missing')
    mode=setting(db,'attendance_mode','daily')
    if mode=='daily' and (data.subject_id is not None or data.label!='Daily'):raise HTTPException(400,'Daily mode requires the Daily session')
    if mode=='subject' and data.subject_id is None:raise HTTPException(400,'Choose an assigned subject')
    if is_blocked(db,data.class_id,data.day):raise HTTPException(409,'Holiday or weekend: add a working day before marking')
    if data.day>datetime.now(IST).date():raise HTTPException(400,'Future attendance is not allowed')
    key='daily' if mode=='daily' else f'{data.subject_id}:{data.label.strip().lower()}'
    if db.scalar(select(AttendanceSession).where(AttendanceSession.class_id==data.class_id,AttendanceSession.day==data.day,AttendanceSession.session_key==key)):
        raise HTTPException(409,'Session already exists')
    x=AttendanceSession(**data.model_dump(),session_key=key,created_by=u.id)
    db.add(x);save(db);audit(db,u,'created',x);db.commit();return session_dict(db,x)

@router.get('/sessions/{id}')
def get_session(id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    x=db.get(AttendanceSession,id)
    if not x:raise HTTPException(404,'Session not found')
    teacher_class(db,u,x.class_id,x.subject_id)
    out=session_dict(db,x)
    out['roster']=[dict(id=s.id,full_name=s.full_name,roll_number=s.roll_number) for s in roster(db,x.class_id,x.day)]
    return out

class MarkIn(BaseModel):
    student_id:int
    status:str=Field(pattern='^(present|absent|late|excused)$')
    arrival_time:time|None=None
class SaveIn(BaseModel):
    version:int
    records:list[MarkIn]
    finalize:bool=False

@router.put('/sessions/{id}')
def save_attendance(id:int,data:SaveIn,u:User=Depends(require_write),db:Session=Depends(get_db)):
    x=db.scalar(select(AttendanceSession).where(AttendanceSession.id==id).with_for_update())
    if not x:raise HTTPException(404,'Session not found')
    teacher_class(db,u,x.class_id,x.subject_id)
    if x.cancelled:raise HTTPException(409,'Session cancelled')
    if x.version!=data.version:raise HTTPException(409,'Another teacher saved changes. Reload before saving')
    if x.state=='finalized' and u.role!='admin':raise HTTPException(403,'Only an administrator can correct finalized attendance')
    expected={s.id for s in roster(db,x.class_id,x.day)}
    incoming={r.student_id for r in data.records}
    if len(incoming)!=len(data.records) or incoming!=expected:raise HTTPException(400,'Submit exactly one record for every enrolled student')
    c=db.get(SchoolClass,x.class_id)
    previous={r.student_id:r for r in db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id==x.id))}
    for item in data.records:
        if item.status in ('absent','excused') and item.arrival_time:
            raise HTTPException(400,'Only present or late students can have arrival times')
        status=item.status
        if item.arrival_time and status=='present':
            threshold=c.start_time.hour*60+c.start_time.minute+c.grace_minutes
            arrived=item.arrival_time.hour*60+item.arrival_time.minute
            if arrived>threshold:status='late'
        old=previous.get(item.student_id)
        before={'status':old.status,'arrival_time':old.arrival_time.isoformat() if old.arrival_time else None} if old else None
        if old:
            if old.status==status and old.arrival_time==item.arrival_time:continue
            old.status=status;old.arrival_time=item.arrival_time;old.updated_by=u.id;old.updated_at=now()
            audit(db,u,'corrected',old,before,{'status':status,'arrival_time':item.arrival_time.isoformat() if item.arrival_time else None})
        else:
            r=AttendanceRecord(session_id=x.id,student_id=item.student_id,status=status,arrival_time=item.arrival_time,updated_by=u.id)
            db.add(r);db.flush();audit(db,u,'marked',r,after={'status':status})
    if data.finalize:
        x.state='finalized';x.finalized_at=now()
    x.version+=1
    audit(db,u,'finalized' if data.finalize else 'saved',x,after={'version':x.version})
    db.flush()
    if x.state=='finalized':
        from .sms import enqueue_session
        enqueue_session(db,x)
    save(db);return session_dict(db,x)

@router.post('/sessions/{id}/cancel')
def cancel_session(id:int,u:User=Depends(require_write),db:Session=Depends(get_db)):
    if u.role!='admin':raise HTTPException(403,'Administrator access required')
    x=db.get(AttendanceSession,id)
    if not x:raise HTTPException(404,'Session not found')
    x.cancelled=True;audit(db,u,'cancelled',x);db.commit();return session_dict(db,x)

@router.get('/roster/{class_id}')
def get_roster(class_id:int,day:date,u:User=Depends(current_user),db:Session=Depends(get_db)):
    teacher_class(db,u,class_id)
    return [{'id':x.id,'full_name':x.full_name,'roll_number':x.roll_number} for x in roster(db,class_id,day)]

def bulk_aggregate(db,student_ids,start=None,end=None,subject_id=None,class_id=None):
    if not student_ids:return {}
    q=select(AttendanceRecord.student_id,AttendanceRecord.status,func.count()).join(AttendanceSession,AttendanceSession.id==AttendanceRecord.session_id).where(AttendanceRecord.student_id.in_(student_ids),AttendanceSession.state=='finalized',AttendanceSession.cancelled==False).group_by(AttendanceRecord.student_id,AttendanceRecord.status)
    if start:q=q.where(AttendanceSession.day>=start)
    if end:q=q.where(AttendanceSession.day<=end)
    if subject_id:q=q.where(AttendanceSession.subject_id==subject_id)
    if class_id:q=q.where(AttendanceSession.class_id==class_id)
    raw={sid:{'present':0,'absent':0,'late':0,'excused':0} for sid in student_ids}
    for sid,status,count in db.execute(q):raw[sid][status]=count
    excused_counts=setting(db,'excused_counts','false')=='true'
    late_counts=setting(db,'late_counts','true')=='true'
    result={}
    for sid,counts in raw.items():
        eligible=sum(counts.values()) if excused_counts else sum(v for k,v in counts.items() if k!='excused')
        attended=counts['present']+(counts['late'] if late_counts else 0)+(counts['excused'] if excused_counts else 0)
        result[sid]=dict(eligible=eligible,attended=attended,absent=counts['absent'],late=counts['late'],excused=counts['excused'],percentage=round(attended/eligible*100,2) if eligible else None)
    return result

def aggregate(db,student_id,start=None,end=None,subject_id=None,class_id=None):
    return bulk_aggregate(db,[student_id],start,end,subject_id,class_id)[student_id]

@router.get('/summary/{student_id}')
def summary(student_id:int,start:date|None=None,end:date|None=None,subject_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    from .core import get_student
    get_student(student_id,u,db)
    return aggregate(db,student_id,start,end,subject_id)

@router.get('/config')
def attendance_config(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return {'attendance_mode':setting(db,'attendance_mode','daily'),'min_percentage':int(setting(db,'min_percentage','75'))}

@router.get('/dashboard')
def dashboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
    today=datetime.now(IST).date()
    classes= db.scalars(select(SchoolClass).where(SchoolClass.active==True)).all() if u.role=='admin' else db.scalars(select(SchoolClass).join(TeacherAssignment,TeacherAssignment.class_id==SchoolClass.id).where(TeacherAssignment.teacher_id==u.id,SchoolClass.active==True).distinct()).all()
    ids=[c.id for c in classes]
    sessions=db.scalars(select(AttendanceSession).where(AttendanceSession.day==today,AttendanceSession.class_id.in_(ids),AttendanceSession.state=='finalized',AttendanceSession.cancelled==False)).all() if ids else []
    counts={'present':0,'absent':0,'late':0,'excused':0}
    for sess in sessions:
        for status,amount in db.execute(select(AttendanceRecord.status,func.count()).where(AttendanceRecord.session_id==sess.id).group_by(AttendanceRecord.status)):
            counts[status]+=amount
    students=db.scalar(select(func.count()).select_from(Student).where(Student.active==True)) if u.role=='admin' else len({s.id for c in classes for s in roster(db,c.id,today)})
    threshold=int(setting(db,'min_percentage','75'))
    low=[]
    for c in classes:
        students_for_class=roster(db,c.id,today)
        summaries=bulk_aggregate(db,[s.id for s in students_for_class])
        for s in students_for_class:
            a=summaries[s.id]
            if a['percentage'] is not None and a['percentage']<threshold:low.append({'student_id':s.id,'name':s.full_name,'class_id':c.id,'percentage':a['percentage']})
    holidays=db.scalars(select(CalendarDay).where(CalendarDay.day>=today,CalendarDay.kind.in_(['holiday','closure'])).order_by(CalendarDay.day).limit(5)).all()
    return {'students':students,'teachers':db.scalar(select(func.count()).select_from(User).where(User.role=='teacher',User.active==True)) if u.role=='admin' else None,'classes':len(classes),'today':counts,'low_attendance':low[:20],'upcoming_holidays':[{'day':x.day.isoformat(),'name':x.name} for x in holidays],'sms':dict(db.execute(select(SmsMessage.status,func.count()).group_by(SmsMessage.status)).all()) if u.role=='admin' else None}
