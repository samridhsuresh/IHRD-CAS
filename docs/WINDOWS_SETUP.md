# Windows college lab setup (PowerShell)

## Install tools

1. Install Python 3.12+ from [python.org](https://www.python.org/downloads/windows/) and select **Add Python to PATH**. A user-only installation usually avoids administrator rights.
2. Install Node.js LTS from [nodejs.org](https://nodejs.org/en/download). Choose the user installation if offered.
3. Install [VS Code](https://code.visualstudio.com/download) using its User Installer.
4. Install [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) and remember the root password. This commonly needs administrator privileges. Workbench is optional.
5. Install Git for Windows if you will clone a repository, or unzip the CampusTrack source folder. Ask the lab administrator before installing system software.

Check in PowerShell: `py --version`, `node --version`, `npm --version`, `mysql --version`. If PowerShell blocks activation scripts, use the virtual environment's `python.exe` directly as below.

## Create the database

Open a MySQL terminal (`mysql -u root -p`) and run these SQL statements. Pick a strong password and put it only in your local `.env` file.

```sql
CREATE DATABASE campustrack CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'campustrack'@'localhost' IDENTIFIED BY 'choose-a-strong-unique-password';
GRANT ALL PRIVILEGES ON campustrack.* TO 'campustrack'@'localhost';
```

## Prepare backend

In PowerShell, open the project folder and run:

```powershell
cd .\IHRD-TRACKER\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Replace the database password in `DATABASE_URL` with the one you created. URL-encode special password characters (`@` becomes `%40`, for example). Keep `.env` private and `SMS_ENABLED=false`. Then run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.bootstrap
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`app.seed` is optional and inserts three fictional students. Bootstrap asks you to type the first administrator password. It refuses to create another administrator once one exists. Keep this terminal open.

## Prepare frontend

Open a second PowerShell window:

```powershell
cd .\IHRD-TRACKER\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Sign in as the administrator you bootstrapped. Go to **Teachers**, create a teacher, and copy the one-time password. Sign out, sign in as that teacher, and change the password. Use **Classes & subjects** to create the structure and assign a teacher. The Vite development proxy sends `/api` requests to port 8000. No real SMS is sent.

## Restricted lab computers

If software installation is blocked, use already installed Python and Node if available, ask an administrator to provision MySQL once on a lab server, or work on a personally controlled Windows machine. Do not point an unmanaged lab PC at a real student database. The `venv` folder and npm dependencies can be installed in your user folder without modifying system directories. The automated tests use a temporary SQLite file, so they can run without MySQL, but final production acceptance must run against MySQL.

## Troubleshooting

- `py` not found: reopen PowerShell after installation or use the full path to Python.
- `mysql` not found: use MySQL Command Line Client from Start or add MySQL's `bin` folder to PATH.
- Port already in use: close the previous dev server or choose a different port and update proxy/origin accordingly.
- Migration connection refused: verify MySQL is running, credentials match, and the database exists.
- To run tests: from `backend`, use `.\.venv\Scripts\python.exe -m pytest -q`.
