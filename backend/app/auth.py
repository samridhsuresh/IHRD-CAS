import hashlib, secrets, time
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from .config import settings
from .db import get_db
from .models import User, AuthSession, AuditLog, now

router=APIRouter(prefix='/auth',tags=['authentication'])
ph=PasswordHasher()
_attempts={}

def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def password_hash(s): return ph.hash(s)
def valid_password(hash_value,s):
    try: return ph.verify(hash_value,s)
    except (VerifyMismatchError,VerificationError): return False

def user_dict(u):
    return dict(id=u.id,username=u.username,full_name=u.full_name,role=u.role,active=u.active,staff_id=u.staff_id,must_change_password=u.must_change_password,can_manage_students=u.can_manage_students)

def current_user(request: Request,db:Session=Depends(get_db)):
    token=request.cookies.get('ct_session')
    if not token: raise HTTPException(401,'Please sign in')
    s=db.scalar(select(AuthSession).where(AuthSession.token_hash==digest(token)))
    if not s or s.expires_at<now(): raise HTTPException(401,'Session expired')
    u=db.get(User,s.user_id)
    if not u or not u.active: raise HTTPException(401,'Account inactive')
    request.state.auth_session=s
    return u

def require_admin(u:User=Depends(current_user)):
    if u.role!='admin': raise HTTPException(403,'Administrator access required')
    return u

def require_write(request:Request,u:User=Depends(current_user)):
    s=request.state.auth_session
    supplied=request.headers.get('x-csrf-token','')
    if not supplied or not secrets.compare_digest(supplied,s.csrf_token): raise HTTPException(403,'CSRF token missing or invalid')
    origin=request.headers.get('origin')
    if origin and origin!=settings.frontend_origin.rstrip('/'): raise HTTPException(403,'Origin rejected')
    if u.must_change_password and request.url.path not in ('/api/auth/password','/api/auth/logout'):
        raise HTTPException(403,'Change temporary password first')
    return u

def admin_write(u:User=Depends(require_write)):
    if u.role!='admin': raise HTTPException(403,'Administrator access required')
    return u

class Login(BaseModel):
    username:str
    password:str

@router.post('/login')
def login(data:Login,response:Response,request:Request,db:Session=Depends(get_db)):
    key=(request.client.host if request.client else 'unknown')+':'+data.username.lower()
    recent=[t for t in _attempts.get(key,[]) if t>time.monotonic()-900]
    if len(recent)>=8: raise HTTPException(429,'Too many attempts. Try again later')
    u=db.scalar(select(User).where(User.username==data.username))
    if not u or not u.active or not valid_password(u.password_hash,data.password):
        _attempts[key]=(recent+[time.monotonic()])[-8:]
        raise HTTPException(401,'Invalid username or password')
    _attempts.pop(key,None)
    token=secrets.token_urlsafe(48); csrf=secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=u.id,token_hash=digest(token),csrf_token=csrf,expires_at=now()+timedelta(hours=settings.session_hours)))
    db.commit()
    response.set_cookie('ct_session',token,httponly=True,secure=settings.secure_cookies,samesite=settings.cookie_samesite,max_age=settings.session_hours*3600,path='/api')
    return {'user':user_dict(u),'csrf':csrf}

@router.get('/me')
def me(request:Request,u:User=Depends(current_user)):
    return {**user_dict(u),'csrf':request.state.auth_session.csrf_token}

@router.post('/logout')
def logout(response:Response,request:Request,u:User=Depends(require_write),db:Session=Depends(get_db)):
    db.delete(request.state.auth_session);db.commit()
    response.delete_cookie('ct_session',path='/api')
    return {'ok':True}

class PasswordChange(BaseModel):
    old_password:str
    new_password:str=Field(min_length=12,max_length=128)

@router.post('/password')
def password(data:PasswordChange,request:Request,u:User=Depends(require_write),db:Session=Depends(get_db)):
    if not valid_password(u.password_hash,data.old_password): raise HTTPException(400,'Current password incorrect')
    u.password_hash=password_hash(data.new_password);u.must_change_password=False
    db.add(AuditLog(actor_id=u.id,action='password_changed',entity='user',entity_id=u.id))
    db.commit();return {'ok':True}
