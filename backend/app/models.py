from datetime import datetime, date, time, timezone
from sqlalchemy import String, Integer, Date, DateTime, Time, Boolean, ForeignKey, UniqueConstraint, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str]=mapped_column(String(160))
    staff_id: Mapped[str|None]=mapped_column(String(60), unique=True, nullable=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(20), default='teacher')
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool]=mapped_column(Boolean, default=False)
    can_manage_students: Mapped[bool]=mapped_column(Boolean, default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class AuthSession(Base):
    __tablename__='auth_sessions'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str]=mapped_column(String(64), unique=True)
    csrf_token: Mapped[str]=mapped_column(String(64))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))

class Department(Base):
    __tablename__='departments'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(120), unique=True)

class Course(Base):
    __tablename__='courses'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(120))
    department_id: Mapped[int]=mapped_column(ForeignKey('departments.id'))
    __table_args__=(UniqueConstraint('name','department_id'),)

class SchoolClass(Base):
    __tablename__='classes'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(120))
    department_id: Mapped[int]=mapped_column(ForeignKey('departments.id'))
    course_id: Mapped[int]=mapped_column(ForeignKey('courses.id'))
    semester: Mapped[int]=mapped_column(Integer)
    academic_year: Mapped[str]=mapped_column(String(20))
    start_time: Mapped[time]=mapped_column(Time)
    grace_minutes: Mapped[int]=mapped_column(Integer, default=10)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    __table_args__=(UniqueConstraint('name','academic_year'),)

class Subject(Base):
    __tablename__='subjects'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(120))
    code: Mapped[str]=mapped_column(String(30), unique=True)

class TeacherAssignment(Base):
    __tablename__='teacher_assignments'
    id: Mapped[int]=mapped_column(primary_key=True)
    teacher_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    class_id: Mapped[int]=mapped_column(ForeignKey('classes.id'))
    subject_id: Mapped[int|None]=mapped_column(ForeignKey('subjects.id'), nullable=True)
    __table_args__=(UniqueConstraint('teacher_id','class_id','subject_id'),)

class Student(Base):
    __tablename__='students'
    id: Mapped[int]=mapped_column(primary_key=True)
    full_name: Mapped[str]=mapped_column(String(160))
    admission_number: Mapped[str]=mapped_column(String(60), unique=True, index=True)
    roll_number: Mapped[str]=mapped_column(String(30))
    email: Mapped[str|None]=mapped_column(String(255), nullable=True)
    notes: Mapped[str|None]=mapped_column(Text, nullable=True)
    active: Mapped[bool]=mapped_column(Boolean, default=True)

class Guardian(Base):
    __tablename__='guardians'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(160))
    phone: Mapped[str]=mapped_column(String(20))
    secondary_phone: Mapped[str|None]=mapped_column(String(20), nullable=True)

class StudentGuardian(Base):
    __tablename__='student_guardians'
    student_id: Mapped[int]=mapped_column(ForeignKey('students.id'), primary_key=True)
    guardian_id: Mapped[int]=mapped_column(ForeignKey('guardians.id'), primary_key=True)
    primary: Mapped[bool]=mapped_column(Boolean, default=True)

class Enrollment(Base):
    __tablename__='enrollments'
    id: Mapped[int]=mapped_column(primary_key=True)
    student_id: Mapped[int]=mapped_column(ForeignKey('students.id'), index=True)
    class_id: Mapped[int]=mapped_column(ForeignKey('classes.id'), index=True)
    starts_on: Mapped[date]=mapped_column(Date)
    ends_on: Mapped[date|None]=mapped_column(Date, nullable=True)
    __table_args__=(Index('ix_enrollment_window','class_id','starts_on','ends_on'),)

class CalendarDay(Base):
    __tablename__='calendar_days'
    id: Mapped[int]=mapped_column(primary_key=True)
    day: Mapped[date]=mapped_column(Date, index=True)
    name: Mapped[str]=mapped_column(String(160))
    kind: Mapped[str]=mapped_column(String(30), default='holiday')
    description: Mapped[str]=mapped_column(Text, default='')
    class_id: Mapped[int|None]=mapped_column(ForeignKey('classes.id'), nullable=True)
    attendance_required: Mapped[bool]=mapped_column(Boolean, default=False)
    __table_args__=(UniqueConstraint('day','class_id','name'),)

class AttendanceSession(Base):
    __tablename__='attendance_sessions'
    id: Mapped[int]=mapped_column(primary_key=True)
    class_id: Mapped[int]=mapped_column(ForeignKey('classes.id'), index=True)
    subject_id: Mapped[int|None]=mapped_column(ForeignKey('subjects.id'), nullable=True)
    day: Mapped[date]=mapped_column(Date, index=True)
    label: Mapped[str]=mapped_column(String(100), default='Daily')
    session_key: Mapped[str]=mapped_column(String(140))
    state: Mapped[str]=mapped_column(String(20), default='draft')
    version: Mapped[int]=mapped_column(Integer, default=1)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    finalized_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    cancelled: Mapped[bool]=mapped_column(Boolean, default=False)
    __table_args__=(UniqueConstraint('class_id','day','session_key'),)

class AttendanceRecord(Base):
    __tablename__='attendance_records'
    id: Mapped[int]=mapped_column(primary_key=True)
    session_id: Mapped[int]=mapped_column(ForeignKey('attendance_sessions.id'), index=True)
    student_id: Mapped[int]=mapped_column(ForeignKey('students.id'), index=True)
    status: Mapped[str]=mapped_column(String(12))
    arrival_time: Mapped[time|None]=mapped_column(Time, nullable=True)
    updated_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    __table_args__=(UniqueConstraint('session_id','student_id'),)

class SmsTemplate(Base):
    __tablename__='sms_templates'
    id: Mapped[int]=mapped_column(primary_key=True)
    kind: Mapped[str]=mapped_column(String(30), unique=True)
    body: Mapped[str]=mapped_column(Text)
    dlt_template_id: Mapped[str|None]=mapped_column(String(100), nullable=True)

class SmsMessage(Base):
    __tablename__='sms_messages'
    id: Mapped[int]=mapped_column(primary_key=True)
    record_id: Mapped[int|None]=mapped_column(ForeignKey('attendance_records.id'), nullable=True)
    student_id: Mapped[int]=mapped_column(ForeignKey('students.id'))
    guardian_id: Mapped[int]=mapped_column(ForeignKey('guardians.id'))
    kind: Mapped[str]=mapped_column(String(30))
    phone: Mapped[str]=mapped_column(String(20))
    body: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(20), default='queued')
    attempts: Mapped[int]=mapped_column(Integer, default=0)
    provider_reference: Mapped[str|None]=mapped_column(String(160), nullable=True)
    error: Mapped[str|None]=mapped_column(String(255), nullable=True)
    dedupe_key: Mapped[str]=mapped_column(String(140), unique=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class SmsDeliveryLog(Base):
    __tablename__='sms_delivery_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    message_id: Mapped[int]=mapped_column(ForeignKey('sms_messages.id'))
    status: Mapped[str]=mapped_column(String(20))
    detail: Mapped[str]=mapped_column(String(255), default='')
    at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class AuditLog(Base):
    __tablename__='audit_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    actor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str]=mapped_column(String(80))
    entity: Mapped[str]=mapped_column(String(80))
    entity_id: Mapped[int]=mapped_column(Integer)
    before: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    after: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class Setting(Base):
    __tablename__='settings'
    key: Mapped[str]=mapped_column(String(80), primary_key=True)
    value: Mapped[str]=mapped_column(String(255))
