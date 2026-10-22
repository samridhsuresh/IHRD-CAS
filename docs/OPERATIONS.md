# Staff guides and operations

## Administrator guide

1. Bootstrap the initial administrator in the backend terminal. Sign in and create departments, courses, classes, and subjects.
2. In Teachers, create each login, privately hand over the one-time password, and assign the class or exact subject. Deactivate the account to revoke its sessions immediately. Reset creates a new temporary password and revokes old sessions.
3. Register students with fictional or institutionally authorized data. CSV imports require five columns: `full_name,admission_number,roll_number,guardian_name,guardian_phone`. An import validates every row first and commits as one batch.
4. Use the student profile to update guardian contact details and transfer classes with an effective date. Past attendance stays attached to the prior class.
5. In Settings, confirm the college's daily versus subject policy, weekend days, late/excused treatment, threshold, and notification switches. Add holidays, closures, and special working days in Academic calendar.
6. Review dashboards, histories, reports, SMS queue, and Audit log. CSV and PDF exports include only authorized class data. Treat exports as confidential.
7. SMS remains simulated until institutional approval, a registered sender/approved DLT templates, and the provider configuration are complete.

## Teacher guide

1. Log in with your username and temporary password, then set a unique password of at least 12 characters.
2. Open Take attendance, choose an assigned class/date and, if required, subject and period. Mark all present, adjust individual statuses and arrival times, then save a draft.
3. Review the roster and finalize. Only finalized sessions count toward percentages and queue parent alerts. Arrival after the configured class start plus grace becomes late and normally counts as attended.
4. If another teacher saves first, CampusTrack asks you to reload instead of overwriting their changes. Ask the administrator to correct a finalized session; the correction appears in the audit log.
5. Use History, Calendar, student profiles, and Reports for assigned classes. Guardian contacts are hidden unless the administrator grants student management permission.

## Backup and recovery

Managed MySQL backups should be enabled at the hosting provider and a restore should be rehearsed on a separate instance. For local development, back up with `mysqldump --single-transaction --routines -u campustrack -p campustrack > campustrack-backup.sql`. Restore only into an empty/recovery database with `mysql -u campustrack -p campustrack < campustrack-backup.sql`, then run migrations and check reports. Encrypt and access restrict backups. Set a retention schedule with the college; do not store real guardians' numbers in public demos or source control.

## Operations

- Keep backend and dependencies patched, restrict admin access, and review failed login/SMS records.
- `python -m app.worker` processes up to 100 queued messages. Schedule it every few minutes in production after provider approval. It simulates sends otherwise. Controlled retries stop after three attempts; inspect failures before requeueing.
- Database timestamps use UTC consistently, and class dates/times use Asia/Kolkata. Monitor app logs and health endpoint `/health`. Never run `uvicorn --reload` in production.
- Draft sessions are not counted. A cancelled session is excluded. Excused and late treatment is configurable.
