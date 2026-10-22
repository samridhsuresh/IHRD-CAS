# CampusTrack

A private staff attendance application built with React, TypeScript, Vite, Tailwind CSS, FastAPI, SQLAlchemy, Alembic, and MySQL. Students and parents do not have accounts. It has an administrator interface, teacher assignments, student/guardian records, effective-dated enrollment, holiday controls, attendance sessions with optimistic concurrency, reports, audit events, and an SMS outbox with mock delivery by default.

## Start here

- [Windows college lab setup](docs/WINDOWS_SETUP.md)
- [Teacher and administrator guides](docs/OPERATIONS.md)
- [Deployment, security, and cost preparation](docs/DEPLOYMENT.md)
- [Entity relationship diagram](docs/ERD.md)

## Local quick reference

Backend from `backend/`: copy `.env.example` to `.env`, configure local MySQL, install `requirements.txt`, run `python -m alembic upgrade head`, then `python -m app.bootstrap` and `uvicorn app.main:app --reload`. Frontend from `frontend/`: `npm install`, `npm run dev`. Visit `http://localhost:5173`.

To test without MySQL: from `backend/`, run `python -m pytest -q`; the test suite uses a temporary SQLite file and synthetic records. A production MySQL acceptance test remains necessary. The migration was also exercised locally on SQLite. The frontend production build is `npm run build`.

## Important implementation limits

- Real SMS is disabled by default. The generic HTTP adapter needs a provider matching its JSON contract, approved Indian DLT templates, an approved sender, and institutional permission. Provider acceptance is logged, but handset delivery receipts/webhooks are not implemented.
- Login rate limiting is per process memory. For multiple production instances, move counters to a shared store or use edge rate limiting. The frontend bundles routes in one entry chunk rather than lazily loading each page; the measured production JavaScript is about 68 KiB gzip. Lighthouse and ordinary-device browser measurements have not been run.
- Guardian phone values are restricted in API responses by role, but not encrypted at the application field level. Database encryption, backups, restricted operators, and retention policy are deployment responsibilities.
- Calendar entries and histories can be managed, with some admin edits through API even where the UI currently emphasizes create/remove. Per-class holiday scope is supported by the API. The UI does not yet expose every specialist workflow (for example, delivery receipt reconciliation).
- Attendance policy must be configured by the college before use. Historical percentage calculations use finalized, non-cancelled session records, exclude excused sessions by default, and count late as attended by default.

## Performance and security notes

Session tokens use server-side hashed opaque values in HttpOnly cookies. CSRF tokens are returned by `/auth/me` on refresh and sent as a header for mutations. Passwords use Argon2. The service worker caches static assets only, never `/api` responses. Enrollment and attendance changes are audited. Pagination caps student lists at 100 per request. Do not use real student or guardian data in a demo.
