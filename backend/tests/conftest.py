import os
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:///./test_campustrack.sqlite'
os.environ['FRONTEND_ORIGIN']='http://localhost:5173'
from app.db import Base,engine,SessionLocal
from app.models import User
from app.auth import password_hash
from app.main import app
from fastapi.testclient import TestClient
import pytest

@pytest.fixture
def client():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(User(username='admin',full_name='Test Admin',role='admin',password_hash=password_hash('administrator-secret')))
        db.commit()
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)

def login(client,username='admin',password='administrator-secret'):
    res=client.post('/api/auth/login',json={'username':username,'password':password})
    assert res.status_code==200,res.text
    return {'X-CSRF-Token':res.json()['csrf']}

@pytest.fixture
def admin(client):return login(client)

def setup(client,headers):
    dept=client.post('/api/departments',json={'name':'Computer Science'},headers=headers).json()['id']
    course=client.post('/api/courses',json={'name':'BSc CS','department_id':dept},headers=headers).json()['id']
    cls=client.post('/api/classes',json={'name':'BSc CS S1','department_id':dept,'course_id':course,'semester':1,'academic_year':'2026-2027','start_time':'09:00','grace_minutes':10},headers=headers).json()['id']
    return cls

def student(client,headers,cls,admission='C001'):
    return client.post('/api/students',json={'full_name':'Fictional Student','admission_number':admission,'roll_number':'01','class_id':cls,'enrollment_date':'2026-10-01','guardian_name':'Fictional Guardian','guardian_phone':'9876543210'},headers=headers)
