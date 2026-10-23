from app.config import settings
from app.db import SessionLocal
from app.models import Guardian, SmsDeliveryLog, SmsMessage, SmsTemplate, Student
from app.sms import delivery
from conftest import setup


def test_opted_in_provider_receives_approved_template_once(client, monkeypatch):
    """Exercise the real adapter contract without transmitting an SMS."""
    monkeypatch.setattr(settings, 'sms_enabled', True)
    monkeypatch.setattr(settings, 'sms_college_approved', True)
    monkeypatch.setattr(settings, 'sms_provider_url', 'https://sms.example.invalid/send')
    monkeypatch.setattr(settings, 'sms_api_key', 'synthetic-test-key')
    monkeypatch.setattr(settings, 'sms_sender_id', 'TESTSMS')
    monkeypatch.setattr(settings, 'sms_dlt_entity_id', 'synthetic-entity')
    sent = []

    class Accepted:
        headers = {'content-type': 'application/json'}

        def raise_for_status(self):
            pass

        def json(self):
            return {'id': 'provider-test-reference'}

    def fake_post(url, *, headers, json, timeout):
        sent.append((url, headers, json, timeout))
        return Accepted()

    monkeypatch.setattr('app.sms.httpx.post', fake_post)
    with SessionLocal() as db:
        student = Student(full_name='Fictional Student', admission_number='SMS-TEST',
                          roll_number='1')
        guardian = Guardian(name='Fictional Guardian', phone='+919876543210')
        db.add_all([student, guardian])
        db.flush()
        db.add(SmsTemplate(kind='absent', body='Approved fictional test',
                           dlt_template_id='synthetic-template'))
        db.flush()
        message = SmsMessage(student_id=student.id, guardian_id=guardian.id, kind='absent',
                             phone='+919876543210', body='Approved fictional test',
                             dedupe_key='synthetic-test:1', status='queued', attempts=0)
        db.add(message)
        db.flush()
        delivery(db, message)
        db.commit()
        assert message.status == 'sent'
        assert message.provider_reference == 'provider-test-reference'
        assert db.query(SmsDeliveryLog).filter_by(message_id=message.id).count() == 1

    assert len(sent) == 1
    url, headers, payload, timeout = sent[0]
    assert url == 'https://sms.example.invalid/send'
    assert headers['Authorization'] == 'Bearer synthetic-test-key'
    assert payload == {
        'to': '+919876543210', 'message': 'Approved fictional test',
        'sender_id': 'TESTSMS', 'entity_id': 'synthetic-entity',
        'template_id': 'synthetic-template',
    }
    assert timeout == 10


def test_guardian_mobile_is_normalized_for_delivery(client, admin):
    cls = setup(client, admin)
    created = client.post('/api/students', json={
        'full_name': 'Synthetic Student', 'admission_number': 'MOBILE-1',
        'roll_number': '1', 'class_id': cls, 'enrollment_date': '2026-10-01',
        'guardian_name': 'Synthetic Guardian',
        'guardian_phone': '+91 98765 43210',
    }, headers=admin)
    assert created.status_code == 200, created.text
    assert created.json()['guardian']['phone'] == '+919876543210'
    assert client.patch(f"/api/students/{created.json()['id']}",
                        json={'guardian_phone': ''}, headers=admin).status_code == 422
