from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from . import auth,core,attendance,sms,reports

app=FastAPI(title='CampusTrack API',version='1.0.0',docs_url=None,redoc_url=None)
@app.middleware('http')
async def security_headers(request: Request, call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control']='no-store, private'
    if settings.secure_cookies:
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin.rstrip('/')],allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Content-Type','X-CSRF-Token'])
for router in (auth.router,core.router,attendance.router,sms.router,reports.router):app.include_router(router,prefix='/api')
@app.get('/health')
def health():return {'status':'ok'}
