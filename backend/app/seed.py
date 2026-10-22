"""Optional fictional roster. Run only in a blank local development database."""
from datetime import date, time
from sqlalchemy import select
from .db import SessionLocal
from .models import Department,Course,SchoolClass,Student,Guardian,StudentGuardian,Enrollment

def main():
    with SessionLocal() as db:
        if db.scalar(select(Student.id).limit(1)):
            print('Students already exist; no sample records added.');return
        department=Department(name='Sample Computer Science');db.add(department);db.flush()
        course=Course(name='Sample BSc Computer Science',department_id=department.id);db.add(course);db.flush()
        group=SchoolClass(name='Sample CS Semester 1',department_id=department.id,course_id=course.id,semester=1,academic_year='2026-2027',start_time=time(9,0),grace_minutes=10)
        db.add(group);db.flush()
        for i,name in enumerate(['Aarav Nair','Maya Menon','Riya Joseph'],1):
            s=Student(full_name=name,admission_number=f'DEMO-{i:03}',roll_number=f'{i:02}')
            db.add(s);db.flush()
            g=Guardian(name=f'Sample Guardian {i}',phone=f'98765000{i:02d}')
            db.add(g);db.flush()
            db.add(StudentGuardian(student_id=s.id,guardian_id=g.id))
            db.add(Enrollment(student_id=s.id,class_id=group.id,starts_on=date(2026,7,1)))
        db.commit();print('Added three fictional students and one sample class.')
if __name__=='__main__':main()
