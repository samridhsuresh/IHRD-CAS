from datetime import date
from conftest import login,setup,student

def test_auth_and_permissions(client,admin):
    assert client.get('/api/students').status_code==200
    outsider=__import__('fastapi').testclient.TestClient(__import__('app.main',fromlist=['app']).app)
    assert outsider.get('/api/students').status_code==401
    r=client.post('/api/teachers',json={'username':'teacher1','full_name':'Teacher One','staff_id':'T1'},headers=admin)
    assert r.status_code==200,r.text
    temp=r.json()['temporary_password']
    assert len(temp)>12 and 'password_hash' not in r.text
    teacher=login(client,'teacher1',temp)
    assert client.post('/api/classes',json={},headers=teacher).status_code==403
    assert client.get('/api/auth/me').json()['must_change_password']
    assert client.post('/api/auth/password',json={'old_password':temp,'new_password':'a-new-secure-password'},headers=teacher).status_code==200
    assert client.post('/api/classes',json={},headers=teacher).status_code==403
    assert client.post('/api/teachers',json={},headers=teacher).status_code==403
    assert client.post('/api/students',json={'full_name':'Test Student','admission_number':'X100','roll_number':'1','class_id':1,'enrollment_date':'2026-10-01','guardian_name':'Guardian','guardian_phone':'9876543210'},headers=teacher).status_code==403
    assert client.post('/api/auth/login',json={'username':'student','password':'anything'}).status_code==401

def test_enrollment_attendance_sms_and_conflict(client,admin):
    cls=setup(client,admin)
    s=student(client,admin,cls);assert s.status_code==200,s.text
    sid=s.json()['id']
    assert student(client,admin,cls).status_code==409
    r=client.post('/api/teachers',json={'username':'teacher2','full_name':'Teacher Two','staff_id':'T2'},headers=admin)
    password=r.json()['temporary_password'];tid=r.json()['teacher']['id']
    assert client.post('/api/assignments',json={'teacher_id':tid,'class_id':cls},headers=admin).status_code==200
    teacher=login(client,'teacher2',password)
    assert client.post('/api/auth/password',json={'old_password':password,'new_password':'another-long-password'},headers=teacher).status_code==200
    assert client.get('/api/students').json()['items'][0].get('guardian') is None
    assert client.get('/api/students?class_id=999',headers=teacher).status_code==403
    day='2026-10-22'
    sess=client.post('/api/attendance/sessions',json={'class_id':cls,'day':day},headers=teacher)
    assert sess.status_code==200,sess.text
    sessid=sess.json()['id']
    assert client.post('/api/attendance/sessions',json={'class_id':cls,'day':day},headers=teacher).status_code==409
    payload={'version':1,'records':[{'student_id':sid,'status':'present','arrival_time':'09:18'}],'finalize':True}
    saved=client.put(f'/api/attendance/sessions/{sessid}',json=payload,headers=teacher)
    assert saved.status_code==200,saved.text
    assert saved.json()['records'][0]['status']=='late'
    assert client.put(f'/api/attendance/sessions/{sessid}',json=payload,headers=teacher).status_code==409
    summary=client.get(f'/api/attendance/summary/{sid}').json()
    assert summary['eligible']==1 and summary['attended']==1 and summary['late']==1 and summary['percentage']==100
    admin=login(client)
    messages=client.get('/api/sms/messages').json();assert len(messages)==1 and messages[0]['status']=='queued'
    assert client.post('/api/sms/process',headers=admin).json()['processed']==1
    assert client.get('/api/sms/messages').json()[0]['status']=='simulated'
    corrected=client.put(f'/api/attendance/sessions/{sessid}',json={'version':2,'records':[{'student_id':sid,'status':'absent'}],'finalize':True},headers=admin)
    assert corrected.status_code==200
    assert client.get(f'/api/attendance/summary/{sid}').json()['percentage']==0
    assert any(x['action']=='corrected' for x in client.get('/api/audit').json())
    assert len(client.get('/api/sms/messages').json())==2
    assert client.put(f'/api/attendance/sessions/{sessid}',json={'version':2,'records':[]},headers=admin).status_code==409

def test_calendar_policy_and_transfer_history(client,admin):
    a=setup(client,admin)
    s=student(client,admin,a);sid=s.json()['id']
    b=client.post('/api/classes',json={'name':'BSc CS S2','department_id':1,'course_id':1,'semester':2,'academic_year':'2026-2027','start_time':'09:00'},headers=admin).json()['id']
    holiday=client.post('/api/calendar',json={'day':'2026-10-21','name':'Festival','kind':'holiday'},headers=admin)
    assert holiday.status_code==200
    assert client.post('/api/attendance/sessions',json={'class_id':a,'day':'2026-10-21'},headers=admin).status_code==409
    sess=client.post('/api/attendance/sessions',json={'class_id':a,'day':'2026-10-20'},headers=admin).json()
    client.put(f"/api/attendance/sessions/{sess['id']}",json={'version':1,'records':[{'student_id':sid,'status':'present'}],'finalize':True},headers=admin)
    move=client.post(f'/api/students/{sid}/transfer',json={'class_id':b,'effective_date':'2026-10-22'},headers=admin)
    assert move.status_code==200,move.text
    assert len(move.json()['enrollments'])==2
    assert client.get(f'/api/reports/class/{a}').json()['items'][0]['percentage']==100
    assert client.get(f'/api/reports/class/{b}').json()['items'][0]['percentage'] is None
    assert client.get(f'/api/reports/class/{a}/csv').status_code==200
    assert client.get(f'/api/reports/class/{a}/pdf').status_code==200

def test_policy_modes_and_validation(client,admin):
    c=setup(client,admin)
    assert student(client,admin,c,'C002').status_code==200
    assert client.post('/api/students',json={'full_name':'X','admission_number':'C003'},headers=admin).status_code==422
    assert client.put('/api/settings',json={'attendance_mode':'subject','min_percentage':75,'weekend_days':'6'},headers=admin).status_code==200
    assert client.post('/api/attendance/sessions',json={'class_id':c,'day':'2026-10-22'},headers=admin).status_code==400
    subject=client.post('/api/subjects',json={'name':'Mathematics','code':'MTH101'},headers=admin).json()['id']
    created=client.post('/api/attendance/sessions',json={'class_id':c,'day':'2026-10-22','subject_id':subject,'label':'Period 1'},headers=admin)
    assert created.status_code==200,created.text
    other=client.post('/api/subjects',json={'name':'Physics','code':'PHY101'},headers=admin).json()['id']
    assert client.post('/api/attendance/sessions',json={'class_id':c,'day':'2026-10-22','subject_id':other,'label':'Period 1'},headers=admin).status_code==200
    sid=client.get('/api/students').json()['items'][0]['id']
    saved=client.put(f"/api/attendance/sessions/{created.json()['id']}",json={'version':1,'records':[{'student_id':sid,'status':'excused'}],'finalize':True},headers=admin)
    assert saved.status_code==200
    assert client.get(f'/api/attendance/summary/{sid}').json()['percentage'] is None

def test_teacher_scope_revocation_and_csrf(client,admin):
    first=setup(client,admin)
    second=client.post('/api/classes',json={'name':'Other class','department_id':1,'course_id':1,'semester':1,'academic_year':'2026-2027','start_time':'09:00'},headers=admin).json()['id']
    teacher=client.post('/api/teachers',json={'username':'scope1','full_name':'Scoped Teacher','staff_id':'S1'},headers=admin).json()
    client.post('/api/assignments',json={'teacher_id':teacher['teacher']['id'],'class_id':first},headers=admin)
    token=login(client,'scope1',teacher['temporary_password'])
    client.post('/api/auth/password',json={'old_password':teacher['temporary_password'],'new_password':'very-secret-password'},headers=token)
    assert client.get('/api/classes').json()[0]['id']==first
    assert client.get(f'/api/attendance/roster/{second}?day=2026-10-22').status_code==403
    assert client.post('/api/auth/logout').status_code==403
    admin=login(client)
    assert client.patch(f"/api/teachers/{teacher['teacher']['id']}",json={'active':False},headers=admin).status_code==200
    assert client.get('/api/auth/me').json()['role']=='admin'
    assert client.post('/api/auth/login',json={'username':'scope1','password':'very-secret-password'}).status_code==401

def test_csv_import_is_atomic_and_sms_waits_for_finalization(client,admin):
    cls=setup(client,admin)
    data='full_name,admission_number,roll_number,guardian_name,guardian_phone\nDemo Alpha,A01,1,Guardian Alpha,9876543210\nDemo Beta,A02,2,Guardian Beta,123\n'
    result=client.post(f'/api/reports/students/import?class_id={cls}&enrollment_date=2026-10-01',files={'file':('roster.csv',data,'text/csv')},headers=admin)
    assert result.status_code==200 and result.json()['imported']==0
    assert client.get('/api/students').json()['total']==0
    good=data.replace('123','9876543211')
    assert client.post(f'/api/reports/students/import?class_id={cls}&enrollment_date=2026-10-01',files={'file':('roster.csv',good,'text/csv')},headers=admin).json()['imported']==2
    session=client.post('/api/attendance/sessions',json={'class_id':cls,'day':'2026-10-22'},headers=admin).json()
    students=client.get('/api/students').json()['items']
    marks=[{'student_id':s['id'],'status':'absent'} for s in students]
    assert client.put(f"/api/attendance/sessions/{session['id']}",json={'version':1,'records':marks},headers=admin).status_code==200
    assert client.get('/api/sms/messages').json()==[]
    assert client.put(f"/api/attendance/sessions/{session['id']}",json={'version':2,'records':marks,'finalize':True},headers=admin).status_code==200
    assert len(client.get('/api/sms/messages').json())==2
    marks[0]['status']='present'
    assert client.put(f"/api/attendance/sessions/{session['id']}",json={'version':3,'records':marks,'finalize':True},headers=admin).status_code==200
    assert sorted(x['status'] for x in client.get('/api/sms/messages').json())==['cancelled','queued']
