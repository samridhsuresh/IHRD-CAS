import getpass, os, sys
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .auth import password_hash

def main():
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.role=='admin')):
            print('An administrator already exists. Bootstrap is disabled.');return 1
        if 'BOOTSTRAP_ADMIN_PASSWORD' in os.environ:
            username=os.environ.get('BOOTSTRAP_ADMIN_USERNAME','Admin').strip()
            full_name=os.environ.get('BOOTSTRAP_ADMIN_FULL_NAME','Admin').strip()
            password=os.environ['BOOTSTRAP_ADMIN_PASSWORD']
            confirm=password
        else:
            username=input('Administrator username: ').strip()
            full_name=input('Full name: ').strip()
            password=getpass.getpass('Password (at least 12 characters): ')
            confirm=getpass.getpass('Confirm password: ')
        if len(username)<3 or len(full_name)<2 or len(password)<12 or password!=confirm:
            print('Invalid input or passwords do not match.');return 1
        db.add(User(username=username,full_name=full_name,password_hash=password_hash(password),role='admin',admin_slot=1))
        try: db.commit()
        except Exception:
            db.rollback()
            print('Administrator bootstrap failed; check that the database is migrated and no administrator exists.');return 1
        print('Administrator created. Remove the bootstrap password from the environment.');return 0
if __name__=='__main__':sys.exit(main())
