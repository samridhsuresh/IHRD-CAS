import re, secrets
from datetime import date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db
from .models import *
from .auth import current_user, require_admin, require_write, admin_write, password_hash, user_dict

router=APIRouter(tags=['management'])

def save(db):
    try: db.commit()
    except IntegrityError: db.rollback();raise HTTPException(409,'Duplicate or referenced record')

def audit(db,u,action,obj,before=None,after=None):
    db.add(AuditLog(actor_id=u.id,action=action,entity=obj.__tablename__,entity_id=obj.id,before=before,after=after))

def teacher_class(db,u,class_id,subject_id=None):
    if u.role=='admin': return
    q=select(TeacherAssignment).where(TeacherAssignment.teacher_id==u.id,TeacherAssignment.class_id==class_id)
    if subject_id is not None: q=q.where(TeacherAssignment.subject_id==subject_id)
    if not db.scalar(q.limit(1)): raise HTTPException(403,'Class or subject not assigned')

def class_data(c):
    return dict(id=c.id,name=c.name,department_id=c.department_id,course_id=c.course_id,semester=c.semester,academic_year=c.academic_year,start_time=c.start_time.isoformat(),grace_minutes=c.grace_minutes,active=c.active)

def roster(db,cid,day):
    return db.scalars(select(Student).join(Enrollment,Enrollment.student_id==Student.id).where(Enrollment.class_id==cid,Enrollment.starts_on<=day,or_(Enrollment.ends_on==None,Enrollment.ends_on>=day),Student.active==True).order_by(Student.roll_number)).all()

class TeacherIn(BaseModel):
    username:str=Field(min_length=3,max_length=80,pattern=r'^[a-zA-Z0-9_.-]+$')
    full_name:str=Field(min_length=2,max_length=160)
    staff_id:str=Field(min_length=1,max_length=60)
    can_manage_students:bool=False
    temporary_password:str|None=Field(default=None,min_length=12,max_length=128)

@router.get('/teachers')
def teachers(u:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [user_dict(x) for x in db.scalars(select(User).where(User.role=='teacher').order_by(User.full_name))]

@router.post('/teachers')
def teacher_create(data:TeacherIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    temp=data.temporary_password or secrets.token_urlsafe(18)
    x=User(**data.model_dump(exclude={'temporary_password'}),role='teacher',password_hash=password_hash(temp),must_change_password=True)
    db.add(x);save(db);audit(db,u,'created',x);db.commit()
    return {'teacher':user_dict(x),'temporary_password':temp}

class TeacherUpdate(BaseModel):
    full_name:str|None=None
    active:bool|None=None
    can_manage_students:bool|None=None

@router.patch('/teachers/{id}')
def teacher_update(id:int,data:TeacherUpdate,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=db.get(User,id)
    if not x or x.role!='teacher': raise HTTPException(404,'Teacher not found')
    before=user_dict(x)
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(x,k,v)
    if not x.active: db.query(AuthSession).filter(AuthSession.user_id==x.id).delete()
    audit(db,u,'updated',x,before,user_dict(x));save(db)
    return user_dict(x)

@router.post('/teachers/{id}/reset-password')
def reset_teacher(id:int,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=db.get(User,id)
    if not x or x.role!='teacher': raise HTTPException(404,'Teacher not found')
    temp=secrets.token_urlsafe(18);x.password_hash=password_hash(temp);x.must_change_password=True
    db.query(AuthSession).filter(AuthSession.user_id==id).delete()
    audit(db,u,'password_reset',x);db.commit()
    return {'temporary_password':temp}

class DepartmentIn(BaseModel): name:str=Field(min_length=2,max_length=120)
@router.get('/departments')
def departments(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':x.id,'name':x.name} for x in db.scalars(select(Department).order_by(Department.name))]
@router.post('/departments')
def create_department(data:DepartmentIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=Department(**data.model_dump());db.add(x);save(db);audit(db,u,'created',x);db.commit();return {'id':x.id,'name':x.name}

class CourseIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    department_id:int
@router.get('/courses')
def courses(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':x.id,'name':x.name,'department_id':x.department_id} for x in db.scalars(select(Course).order_by(Course.name))]
@router.post('/courses')
def create_course(data:CourseIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    if not db.get(Department,data.department_id): raise HTTPException(400,'Unknown department')
    x=Course(**data.model_dump());db.add(x);save(db);audit(db,u,'created',x);db.commit();return {'id':x.id}

class SubjectIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    code:str=Field(min_length=2,max_length=30)
@router.get('/subjects')
def subjects(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':x.id,'name':x.name,'code':x.code} for x in db.scalars(select(Subject).order_by(Subject.name))]
@router.post('/subjects')
def create_subject(data:SubjectIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=Subject(**data.model_dump());db.add(x);save(db);audit(db,u,'created',x);db.commit();return {'id':x.id}

class ClassIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    department_id:int
    course_id:int
    semester:int=Field(ge=1,le=12)
    academic_year:str=Field(pattern=r'^\d{4}-\d{4}$')
    start_time:time
    grace_minutes:int=Field(default=10,ge=0,le=120)

@router.get('/classes')
def classes(u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(SchoolClass).order_by(SchoolClass.name)
    if u.role!='admin': q=q.join(TeacherAssignment,TeacherAssignment.class_id==SchoolClass.id).where(TeacherAssignment.teacher_id==u.id).distinct()
    return [class_data(c) for c in db.scalars(q)]

@router.post('/classes')
def create_class(data:ClassIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    course=db.get(Course,data.course_id)
    if not course or course.department_id!=data.department_id: raise HTTPException(400,'Course and department mismatch')
    c=SchoolClass(**data.model_dump());db.add(c);save(db);audit(db,u,'created',c);db.commit();return class_data(c)

class ClassPatch(BaseModel):
    name:str|None=None
    start_time:time|None=None
    grace_minutes:int|None=Field(default=None,ge=0,le=120)
    active:bool|None=None
@router.patch('/classes/{id}')
def update_class(id:int,data:ClassPatch,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    c=db.get(SchoolClass,id)
    if not c: raise HTTPException(404,'Class not found')
    before=class_data(c)
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(c,k,v)
    audit(db,u,'updated',c,before,class_data(c));save(db);return class_data(c)

class AssignmentIn(BaseModel):
    teacher_id:int
    class_id:int
    subject_id:int|None=None
@router.get('/assignments')
def assignments(u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(TeacherAssignment)
    if u.role!='admin': q=q.where(TeacherAssignment.teacher_id==u.id)
    return [{'id':x.id,'teacher_id':x.teacher_id,'class_id':x.class_id,'subject_id':x.subject_id} for x in db.scalars(q)]
@router.post('/assignments')
def assign(data:AssignmentIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    t=db.get(User,data.teacher_id)
    if not t or t.role!='teacher' or not t.active or not db.get(SchoolClass,data.class_id): raise HTTPException(400,'Invalid teacher or class')
    if data.subject_id and not db.get(Subject,data.subject_id): raise HTTPException(400,'Invalid subject')
    duplicate=db.scalar(select(TeacherAssignment.id).where(TeacherAssignment.teacher_id==data.teacher_id,TeacherAssignment.class_id==data.class_id,TeacherAssignment.subject_id==data.subject_id))
    if duplicate:raise HTTPException(409,'Assignment already exists')
    x=TeacherAssignment(**data.model_dump());db.add(x);save(db);audit(db,u,'created',x);db.commit();return {'id':x.id}
@router.delete('/assignments/{id}')
def unassign(id:int,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=db.get(TeacherAssignment,id)
    if not x: raise HTTPException(404,'Assignment not found')
    audit(db,u,'removed',x);db.delete(x);db.commit();return {'ok':True}

class StudentIn(BaseModel):
    full_name:str=Field(min_length=2,max_length=160)
    admission_number:str=Field(min_length=2,max_length=60)
    roll_number:str=Field(min_length=1,max_length=30)
    class_id:int
    enrollment_date:date
    guardian_name:str=Field(min_length=2,max_length=160)
    guardian_phone:str
    secondary_phone:str|None=None
    email:str|None=None
    notes:str|None=None
    @field_validator('guardian_phone','secondary_phone')
    @classmethod
    def phone(cls,v):
        if v is None or v=='': return None
        if not re.fullmatch(r'(?:\+91|91)?[6-9]\d{9}|\+[1-9]\d{7,14}',v): raise ValueError('Use a valid mobile number, optionally with country prefix')
        return v

@router.get('/students')
def students(class_id:int|None=None,q:str='',page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=100),u:User=Depends(current_user),db:Session=Depends(get_db)):
    query=select(Student).distinct()
    if u.role!='admin':
        query=query.join(Enrollment,Enrollment.student_id==Student.id).join(TeacherAssignment,TeacherAssignment.class_id==Enrollment.class_id).where(TeacherAssignment.teacher_id==u.id)
    if class_id:
        teacher_class(db,u,class_id)
        if u.role=='admin':query=query.join(Enrollment,Enrollment.student_id==Student.id)
        query=query.where(Enrollment.class_id==class_id,Enrollment.ends_on==None)
    if q: query=query.where(or_(Student.full_name.ilike('%'+q+'%'),Student.admission_number.ilike('%'+q+'%')))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(Student.full_name).offset((page-1)*limit).limit(limit)).all()
    return {'total':total,'items':[student_data(db,x,u) for x in rows]}

def student_data(db,s,u):
    out=dict(id=s.id,full_name=s.full_name,admission_number=s.admission_number,roll_number=s.roll_number,email=s.email,notes=s.notes,active=s.active)
    if u.role=='admin' or u.can_manage_students:
        g=db.scalar(select(Guardian).join(StudentGuardian,StudentGuardian.guardian_id==Guardian.id).where(StudentGuardian.student_id==s.id,StudentGuardian.primary==True))
        out['guardian']=dict(name=g.name,phone=g.phone,secondary_phone=g.secondary_phone) if g else None
    out['enrollments']=[dict(id=e.id,class_id=e.class_id,starts_on=e.starts_on.isoformat(),ends_on=e.ends_on.isoformat() if e.ends_on else None) for e in db.scalars(select(Enrollment).where(Enrollment.student_id==s.id).order_by(Enrollment.starts_on.desc()))]
    return out

@router.post('/students')
def create_student(data:StudentIn,u:User=Depends(require_write),db:Session=Depends(get_db)):
    if u.role!='admin' and not u.can_manage_students: raise HTTPException(403,'Permission required')
    teacher_class(db,u,data.class_id)
    if not db.get(SchoolClass,data.class_id): raise HTTPException(400,'Unknown class')
    if db.scalar(select(Student.id).where(Student.admission_number==data.admission_number)):
        raise HTTPException(409,'Duplicate admission number')
    s=Student(full_name=data.full_name,admission_number=data.admission_number,roll_number=data.roll_number,email=data.email,notes=data.notes)
    db.add(s);db.flush()
    g=Guardian(name=data.guardian_name,phone=data.guardian_phone,secondary_phone=data.secondary_phone)
    db.add(g);db.flush()
    db.add(StudentGuardian(student_id=s.id,guardian_id=g.id))
    db.add(Enrollment(student_id=s.id,class_id=data.class_id,starts_on=data.enrollment_date))
    audit(db,u,'created',s);save(db)
    return student_data(db,s,u)

@router.get('/students/{id}')
def get_student(id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    s=db.get(Student,id)
    if not s: raise HTTPException(404,'Student not found')
    if u.role!='admin':
        allowed=db.scalar(select(Enrollment).join(TeacherAssignment,TeacherAssignment.class_id==Enrollment.class_id).where(Enrollment.student_id==id,TeacherAssignment.teacher_id==u.id).limit(1))
        if not allowed: raise HTTPException(403,'Student outside assigned classes')
    return student_data(db,s,u)

class StudentPatch(BaseModel):
    full_name:str|None=None
    roll_number:str|None=None
    guardian_name:str|None=None
    guardian_phone:str|None=None
    active:bool|None=None
    email:str|None=None
    notes:str|None=None
    @field_validator('guardian_phone')
    @classmethod
    def phone(cls,v):
        if v and not re.fullmatch(r'(?:\+91|91)?[6-9]\d{9}|\+[1-9]\d{7,14}',v): raise ValueError('Invalid phone')
        return v
@router.patch('/students/{id}')
def update_student(id:int,data:StudentPatch,u:User=Depends(require_write),db:Session=Depends(get_db)):
    if u.role!='admin' and not u.can_manage_students: raise HTTPException(403,'Permission required')
    s=db.get(Student,id)
    if not s: raise HTTPException(404,'Student not found')
    if u.role!='admin': get_student(id,u,db)
    before=student_data(db,s,u);changes=data.model_dump(exclude_unset=True)
    g=db.scalar(select(Guardian).join(StudentGuardian,StudentGuardian.guardian_id==Guardian.id).where(StudentGuardian.student_id==id,StudentGuardian.primary==True))
    for k,v in changes.items():
        if k=='guardian_name':g.name=v
        elif k=='guardian_phone':g.phone=v
        else:setattr(s,k,v)
    audit(db,u,'updated',s,before,student_data(db,s,u));save(db);return student_data(db,s,u)

class TransferIn(BaseModel):
    class_id:int
    effective_date:date
@router.post('/students/{id}/transfer')
def transfer(id:int,data:TransferIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    s=db.get(Student,id)
    if not s or not db.get(SchoolClass,data.class_id): raise HTTPException(404,'Student or class not found')
    open_enroll=db.scalars(select(Enrollment).where(Enrollment.student_id==id,Enrollment.ends_on==None).with_for_update()).all()
    if any(e.class_id==data.class_id for e in open_enroll): raise HTTPException(409,'Already enrolled')
    for e in open_enroll:
        if data.effective_date<=e.starts_on: raise HTTPException(400,'Transfer must follow enrollment start')
        e.ends_on=data.effective_date-timedelta(days=1)
    db.add(Enrollment(student_id=id,class_id=data.class_id,starts_on=data.effective_date))
    audit(db,u,'transferred',s,after={'class_id':data.class_id,'effective_date':data.effective_date.isoformat()});save(db)
    return student_data(db,s,u)

class CalendarIn(BaseModel):
    day:date
    name:str=Field(min_length=2,max_length=160)
    kind:str=Field(default='holiday',pattern='^(holiday|closure|exam|working_day)$')
    description:str=''
    class_id:int|None=None
    attendance_required:bool=False
@router.get('/calendar')
def calendar(start:date|None=None,end:date|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(CalendarDay)
    if start:q=q.where(CalendarDay.day>=start)
    if end:q=q.where(CalendarDay.day<=end)
    return [dict(id=x.id,day=x.day.isoformat(),name=x.name,kind=x.kind,description=x.description,class_id=x.class_id,attendance_required=x.attendance_required) for x in db.scalars(q.order_by(CalendarDay.day).limit(500))]
@router.post('/calendar')
def create_day(data:CalendarIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=CalendarDay(**data.model_dump());db.add(x);save(db);audit(db,u,'created',x);db.commit();return {'id':x.id}
@router.patch('/calendar/{id}')
def update_day(id:int,data:CalendarIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=db.get(CalendarDay,id)
    if not x: raise HTTPException(404,'Calendar day not found')
    for k,v in data.model_dump().items():setattr(x,k,v)
    audit(db,u,'updated',x);save(db);return {'id':x.id}
@router.delete('/calendar/{id}')
def remove_day(id:int,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    x=db.get(CalendarDay,id)
    if not x: raise HTTPException(404,'Calendar day not found')
    audit(db,u,'removed',x);db.delete(x);db.commit();return {'ok':True}

@router.get('/settings')
def settings_list(u:User=Depends(require_admin),db:Session=Depends(get_db)):
    out={x.key:x.value for x in db.scalars(select(Setting))}
    return {'attendance_mode':out.get('attendance_mode','daily'),'excused_counts':out.get('excused_counts','false')=='true','late_counts':out.get('late_counts','true')=='true','min_percentage':int(out.get('min_percentage','75')),'weekend_days':out.get('weekend_days','6'),'sms_absent':out.get('sms_absent','true')=='true','sms_late':out.get('sms_late','true')=='true','sms_low':out.get('sms_low','false')=='true'}
class SettingsIn(BaseModel):
    attendance_mode:str=Field(pattern='^(daily|subject)$')
    excused_counts:bool=False
    late_counts:bool=True
    min_percentage:int=Field(default=75,ge=0,le=100)
    weekend_days:str=Field(default='6',pattern=r'^[0-6](,[0-6])*$')
    sms_absent:bool=True
    sms_late:bool=True
    sms_low:bool=False
@router.put('/settings')
def set_settings(data:SettingsIn,u:User=Depends(admin_write),db:Session=Depends(get_db)):
    for k,v in data.model_dump().items():
        x=db.get(Setting,k)
        if x:x.value=str(v).lower() if isinstance(v,bool) else str(v)
        else:db.add(Setting(key=k,value=str(v).lower() if isinstance(v,bool) else str(v)))
    db.add(AuditLog(actor_id=u.id,action='updated',entity='settings',entity_id=0,after=data.model_dump()))
    db.commit();return settings_list(u,db)

@router.get('/audit')
def logs(page:int=Query(1,ge=1),u:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [dict(id=x.id,actor_id=x.actor_id,action=x.action,entity=x.entity,entity_id=x.entity_id,before=x.before,after=x.after,created_at=x.created_at.isoformat()) for x in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset((page-1)*50).limit(50))]
