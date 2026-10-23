# Data persistence and recovery

The browser never writes the system of record. The FastAPI backend commits account, student, guardian, enrollment, class, attendance, holiday, setting, audit, and SMS data to the configured MySQL database. The PWA service worker caches static application files only; it does not queue offline attendance. Browser storage and Vercel's temporary function filesystem are not used for records.

## Before collecting real information

1. Use one persistent managed MySQL service, TLS, an application-specific database account, and a region approved by the college. Keep credentials in the host's encrypted environment settings, never in Git or frontend code.
2. Apply Alembic migrations to the same database the deployed API uses. Bootstrap the `Admin` account once from a secure terminal. Do not keep the bootstrap password in the application's runtime environment.
3. Enable provider-managed backups and verify their retention and restoration features. Schedule a separate encrypted export to college-controlled storage. Keep at least one copy independent of the database provider and restrict access to the designated administrator.
4. Restore a backup into an isolated test database and verify login, class roster, attendance totals, and audit records. Record the date and outcome of each restore drill.
5. Monitor database capacity, errors, backup jobs, and the API. Document who may restore data and how changes during an outage will be reconciled.

No system can honestly guarantee zero loss in every outage or accidental deletion. A free single-node database with one disaster-recovery backup has a greater recovery gap than a paid high-availability plan with point-in-time restore. Select a recovery target and retention policy with the college before real student records are entered.

## Portable backup example

From a trusted machine with MySQL client tools and database access, run `mysqldump --single-transaction --routines --triggers --set-gtid-purged=OFF -h <host> -P <port> -u <backup-user> -p <database> > backup.sql`. This prompts for the password without putting it in the command line. Encrypt the resulting file, transfer it to restricted storage, and delete any unencrypted temporary copy. The backup account needs only the privileges required for export.

Restore **only to an isolated test database first** with `mysql -h <host> -P <port> -u <restore-user> -p <test-database> < backup.sql`. Confirm the record counts and application flows before a real recovery. Follow the managed provider's TLS instructions for both commands.
