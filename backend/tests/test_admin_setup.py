import pytest
from sqlalchemy.exc import IntegrityError

from app.auth import password_hash, valid_password
from app.db import SessionLocal
from app.models import User


def test_only_one_admin_row_can_be_inserted(client):
    with SessionLocal() as db:
        db.add(User(username='another-admin', full_name='Another Admin',
                    role='admin', admin_slot=1, password_hash=password_hash('fictional-secret-123')))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(User).filter(User.role == 'admin').count() == 1


def test_admin_can_set_teacher_temporary_password(client, admin):
    temporary = 'fictional-teacher-secret-123'
    response = client.post('/api/teachers', json={
        'username': 'teacher-custom', 'full_name': 'Teacher Custom',
        'staff_id': 'STAFF-CUSTOM', 'temporary_password': temporary,
    }, headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()['temporary_password'] == temporary
    with SessionLocal() as db:
        teacher = db.query(User).filter_by(username='teacher-custom').one()
        assert teacher.role == 'teacher' and teacher.admin_slot is None
        assert teacher.password_hash != temporary
        assert valid_password(teacher.password_hash, temporary)
        assert teacher.must_change_password
    signed_in = client.post('/api/auth/login', json={
        'username': 'teacher-custom', 'password': temporary,
    })
    assert signed_in.status_code == 200
    assert signed_in.json()['user']['must_change_password']
    assert client.post('/api/teachers', json={
        'username': 'blocked', 'full_name': 'Blocked User', 'staff_id': 'BLOCKED',
    }, headers={'X-CSRF-Token': signed_in.json()['csrf']}).status_code == 403
    assert client.post('/api/auth/login', json={
        'username': 'student', 'password': temporary,
    }).status_code == 401
