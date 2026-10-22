import csv, io
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import *
from .auth import current_user, admin_write
from .core import teacher_class, StudentIn, save, audit
from .attendance import bulk_aggregate

router=APIRouter(prefix='/reports',tags=['reports'])

@router.get('/class/{class_id}')
def class_report(class_id:int,start:date|None=None,end:date|None=None,subject_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    teacher_class(db,u,class_id,subject_id)
    if not db.get(SchoolClass,class_id):raise HTTPException(404,'Class not found')
    q=select(Student).join(Enrollment,Enrollment.student_id==Student.id).where(Enrollment.class_id==class_id).distinct().order_by(Student.roll_number)
    entries=[]
    students=db.scalars(q).all()
    summaries=bulk_aggregate(db,[s.id for s in students],start,end,subject_id,class_id)
    for s in students:
        a=summaries[s.id]
        entries.append({'student_id':s.id,'admission_number':s.admission_number,'roll_number':s.roll_number,'name':s.full_name,**a})
    return {'class_id':class_id,'start':start,'end':end,'subject_id':subject_id,'items':entries}

@router.get('/class/{class_id}/csv')
def export_csv(class_id:int,start:date|None=None,end:date|None=None,subject_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    data=class_report(class_id,start,end,subject_id,u,db)
    out=io.StringIO();fields=['admission_number','roll_number','name','eligible','attended','absent','late','excused','percentage']
    w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows({k:x[k] for k in fields} for x in data['items'])
    return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="class-{class_id}-attendance.csv"'})

@router.get('/class/{class_id}/pdf')
def export_pdf(class_id:int,start:date|None=None,end:date|None=None,subject_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    data=class_report(class_id,start,end,subject_id,u,db)
    out=io.BytesIO();doc=SimpleDocTemplate(out)
    rows=[['Roll','Student','Eligible','Attended','Absent','Late','%']]
    for x in data['items']: rows.append([x['roll_number'],x['name'][:28],str(x['eligible']),str(x['attended']),str(x['absent']),str(x['late']),str(x['percentage'] if x['percentage'] is not None else '—')])
    t=Table(rows,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#172b52')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#eef2f7')]),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    doc.build([Paragraph('CampusTrack Attendance Report',getSampleStyleSheet()['Title']),Spacer(1,16),t])
    return Response(out.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="class-{class_id}-attendance.pdf"'})

@router.post('/students/import')
async def import_students(file:UploadFile=File(...),class_id:int=0,enrollment_date:date|None=None,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    if not db.get(SchoolClass,class_id):raise HTTPException(400,'Select a valid class')
    content=await file.read(1024*1024+1)
    if len(content)>1024*1024:raise HTTPException(413,'CSV must be under 1 MB')
    try: rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    except UnicodeError:raise HTTPException(400,'CSV must be UTF-8')
    if len(rows)>500:raise HTTPException(400,'Import at most 500 students per file')
    required={'full_name','admission_number','roll_number','guardian_name','guardian_phone'}
    if not rows or not required.issubset(rows[0]):raise HTTPException(400,'Missing required CSV columns')
    errors=[];created=[]
    for i,row in enumerate(rows,2):
        try:
            x=StudentIn(**{k:row[k].strip() for k in required},class_id=class_id,enrollment_date=enrollment_date or date.today())
            created.append(x)
        except Exception as exc:errors.append({'row':i,'error':'Invalid fields or mobile number'})
    existing=set(db.scalars(select(Student.admission_number).where(Student.admission_number.in_([r.admission_number for r in created]))))
    seen=set()
    for i,x in enumerate(created,2):
        if x.admission_number in seen or x.admission_number in existing:errors.append({'row':i,'error':'Duplicate admission number'})
        seen.add(x.admission_number)
    if errors:return {'imported':0,'errors':errors}
    for x in created:
        row=Student(full_name=x.full_name,admission_number=x.admission_number,roll_number=x.roll_number)
        db.add(row);db.flush()
        guardian=Guardian(name=x.guardian_name,phone=x.guardian_phone)
        db.add(guardian);db.flush()
        db.add(StudentGuardian(student_id=row.id,guardian_id=guardian.id))
        db.add(Enrollment(student_id=row.id,class_id=x.class_id,starts_on=x.enrollment_date))
        audit(db,u,'imported',row)
    save(db)
    return {'imported':len(created),'errors':[]}
