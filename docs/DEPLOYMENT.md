# Production deployment preparation

**No deployment or paid resource has been created.** Ask the college to approve provider accounts, costs, privacy procedures, and SMS before going live.

## Suggested topology and current estimate (checked 22 October 2026)

- DigitalOcean App Platform: one Python web service, starting at **US$5/month** for a 1 vCPU / 512 MiB fixed shared container, plus a static frontend component. The static component has no additional component charge within a paid app. [App Platform pricing](https://www.digitalocean.com/pricing/app-platform).
- DigitalOcean Managed MySQL Standard Basic: starting at **US$15.15/month** for 1 GiB / 1 vCPU / 10 GiB storage. [Managed database pricing](https://www.digitalocean.com/pricing/managed-databases).
- Baseline: roughly **US$20.15/month**, before taxes, domains, bandwidth overages, increased compute, SMS, or scheduled job runtime. A scheduled SMS job is billed for execution time and can run no more often than every 15 minutes on App Platform. [Job documentation](https://docs.digitalocean.com/products/app-platform/how-to/manage-jobs/).
- A static-only free tier does not include an always-on Python backend or managed MySQL. Pricing changes; check the provider before purchase.

## Deployment sequence

1. Put the source in a private Git repository. Protect branches and exclude `.env`, real data, and database dumps.
2. Create managed MySQL in the same region as the App Platform web service. Use a dedicated low-privilege database user. Restrict connections to the application as a trusted source and use the private URL/VPC with TLS where supported. Never allow unrestricted internet access to MySQL. [App/database trusted sources](https://docs.digitalocean.com/products/app-platform/how-to/manage-databases/).
3. Create a Python web service with source directory `backend`, build command `pip install -r requirements.txt`, run command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`. No `--reload` in production.
4. Configure runtime secrets: `DATABASE_URL` using `mysql+pymysql://...` and the managed database private endpoint with provider TLS parameters; `FRONTEND_ORIGIN=https://campus.example.edu`; `SECURE_COOKIES=true`; `COOKIE_SAMESITE=lax` if frontend and API are on sibling subdomains under one domain. If the two hosts are cross-site, use `COOKIE_SAMESITE=none` with secure HTTPS cookies and test third-party cookie behavior. Avoid cross-site deployment if possible. Set `SMS_ENABLED=false`, `SMS_COLLEGE_APPROVED=false`.
5. Run `python -m alembic upgrade head` as a controlled release job or an authorized one-off console command **after** the service can reach the database. The build stage cannot connect to a managed database with trusted sources enabled. Run `python -m app.bootstrap` once from a secure console. Do not put the first administrator password into a build log.
6. Create a static frontend component with source directory `frontend`, build command `npm ci && npm run build`, output directory `dist`, and `VITE_API_BASE=https://api.example.edu` at build time. Configure SPA fallback so unknown paths serve `index.html`. Connect `campus.example.edu` to the frontend and `api.example.edu` to the backend. Verify HTTPS, CORS origin, cookies, login after refresh, logout, and permissions in a private test instance using fictional data.
7. Enable managed backups and test restore to a separate instance. Turn on app logs and uptime alerts. Validate the `/health` endpoint, error reports, database connectivity, and usage bills. Schedule security updates and retention reviews.
8. After college SMS approval and provider contract, register the Indian DLT entity/sender and exact templates. Add template bodies and IDs in CampusTrack. Configure `SMS_PROVIDER_URL` (HTTPS), `SMS_API_KEY`, `SMS_SENDER_ID`, and `SMS_DLT_ENTITY_ID`. The generic HTTP adapter sends JSON `{to,message,sender_id,entity_id,template_id}` with bearer authorization; verify that exact contract with the provider in a test account before enabling `SMS_ENABLED=true` and `SMS_COLLEGE_APPROVED=true`.
9. Add a scheduled job with source directory `backend`, command `python -m app.worker`, runtime database/provider environment, and a schedule such as `*/15 * * * *` in `Asia/Kolkata`. It processes at most 100 messages per invocation and retries failures up to three attempts. Confirm whether the provider accepts a message; a `sent` status currently means provider accepted the request, **not confirmed handset delivery**. If the provider supports delivery callbacks, add signed callback verification before calling it delivered.

## Release checks

- Use a private staging database with fictional records; run tests and MySQL migrations there first.
- Verify two teachers cannot overwrite a session, admin correction history, holidays, real phone number validation, PWA install, and mobile browser flow.
- Confirm the chosen processor/storage region and written college privacy policy. Restrict exports and backups.
- Obtain explicit institutional sign-off before any live student records, paid subscription, or real SMS.
