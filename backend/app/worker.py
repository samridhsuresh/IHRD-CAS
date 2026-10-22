"""Run from a scheduler; mock delivery by default."""
from sqlalchemy import select, or_
from .db import SessionLocal
from .models import SmsMessage
from .sms import delivery

def main():
    with SessionLocal() as db:
        for message in db.scalars(select(SmsMessage).where(or_(SmsMessage.status=='queued',(SmsMessage.status=='failed')&(SmsMessage.attempts<3))).order_by(SmsMessage.id).limit(100).with_for_update(skip_locked=True)):
            delivery(db,message)
        db.commit()
if __name__=='__main__':main()
