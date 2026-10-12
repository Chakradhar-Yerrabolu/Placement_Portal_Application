# Placement Portal 



## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

## Troubleshooting
- `ModuleNotFoundError`: ensure the Web tab points to the virtualenv above and all requirements installed inside it.
- Template/static 404s: confirm the project path and `/static/` mapping.
- Import error: ensure WSGI imports `from run import app as application` and `project_home` points to the folder containing `run.py`.
- Database error: check that `app/instance/` is writable by your account. The app creates this directory automatically when the app starts.


## Google email verification (required for new student registrations)

New student registrations must verify ownership of their email with Google OpenID Connect before the form can be submitted. The callback checks Google's `email_verified` claim and the submitted email must match the verified account. This is email verification; it does not replace the existing password-based student login. Existing accounts are not modified.

### 1. Create Google OAuth credentials

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create/select a project and configure the OAuth consent screen (Google Auth Platform). For an external app in Testing mode, add the intended test accounts.
3. Create an OAuth client ID with application type **Web application**.
4. Add your exact deployment callback to **Authorized redirect URIs**: `https://YOUR_USERNAME.pythonanywhere.com/auth/google/callback` (replace the hostname with your real site). For local testing, also add `http://127.0.0.1:5000/auth/google/callback`. The URI must match exactly.
5. Copy the client ID and client secret. Never commit the secret into source control or put it in a template.

### 2. Configure on PythonAnywhere

In the PythonAnywhere **Web** tab, set environment variables in the WSGI file before importing `run` (replace the placeholder values):

```python
import os
os.environ['GOOGLE_CLIENT_ID'] = 'YOUR_GOOGLE_CLIENT_ID'
os.environ['GOOGLE_CLIENT_SECRET'] = 'YOUR_GOOGLE_CLIENT_SECRET'
os.environ['SECRET_KEY'] = 'REPLACE_WITH_A_LONG_RANDOM_SECRET'

# Keep the existing project path / virtualenv setup and import below.
from run import app as application
```

If your WSGI file already contains the `from run import app as application` line, add the environment settings above that line; do not duplicate the import. Reload the web app after saving. Use HTTPS for the deployed site. Do not share the WSGI file because it contains secrets.

### 3. How the flow works

1. A student selects **Verify email with Google** on the registration page.
2. Google signs the user in and returns the verified email claim.
3. The registration form is prefilled with that verified email and locks the email field.
4. Registration is accepted only if the posted email matches the verified email held in the signed Flask session. The verification marker is cleared after successful registration.

Google OAuth needs internet access and valid client credentials; it cannot be fully tested without credentials and a registered callback URL. If credentials are absent, the site displays a configuration message rather than silently bypassing verification.

### Security note

Set a unique, long `SECRET_KEY` before deployment. This feature does not automatically hash existing student passwords or change company/admin authentication. Review those existing flows separately before production use.


## Email confirmation + environment configuration

The registration flow now has two checks:
1. The student verifies the address using Google OAuth.
2. After submitting the student details, the portal emails a confirmation message. The account is created only after the recipient opens the link and presses **Confirm email and activate account**.

### Email template
The editable Jinja HTML template is at `app/templates/emails/registration_confirmation.html`. It shows the submitted student profile details and a confirmation button/link. Passwords are intentionally never included in the email. The confirmation link opens a page and requires a second button press, which helps prevent email security scanners from activating accounts automatically.

### Local setup with `example.env`
1. Copy `example.env` to `.env`.
2. Fill in `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and SMTP settings.
3. For Gmail SMTP, enable 2-Step Verification and generate a Google **App Password**. Use that App Password as `MAIL_PASSWORD`, not your normal Gmail password.
4. Install dependencies with `pip install -r requirements.txt` and start the app with `python run.py`.

The application loads `.env` when it exists. Do not upload a real `.env` to source control or share it. `example.env` contains placeholders only.

### PythonAnywhere configuration
For deployment, you can either configure the environment variables in the WSGI file before importing the app, or use PythonAnywhere's available environment-variable configuration. Set these variables with your real values:
`SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, and optionally `MAIL_SENDER_NAME`.

For Gmail, use `MAIL_SERVER=smtp.gmail.com` and `MAIL_PORT=587`. Ensure outbound SMTP is permitted by your account/hosting configuration. Set the Google OAuth callback to the exact HTTPS URL:
`https://YOUR_USERNAME.pythonanywhere.com/auth/google/callback`

If mail sending fails, the pending registration is removed and the app displays an error rather than claiming that the email was sent. Review the PythonAnywhere error log for SMTP diagnostics.


## Production database: Neon PostgreSQL

This version supports **Neon PostgreSQL** (often called Neon Database) using SQLAlchemy + psycopg 3. The app normalizes `postgres://`/`postgresql://` URLs, requires SSL for PostgreSQL connections, enables connection health checks, and does not use the local SQLite file when `DATABASE_URL` is set.

### 1. Create the Neon database

1. Create a project in the Neon Console and create/select a database and role.
2. Open **Connect** and copy the connection string. Prefer the pooled connection string for a web app if Neon offers it.
3. Keep the connection string private. It contains the database password. Use the complete URL in `DATABASE_URL`; it should include `sslmode=require` (the app adds this if it is absent).

Example format only (not real credentials):

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

### 2. Configure PythonAnywhere

Do not upload a real `.env` file or commit secrets. In the PythonAnywhere WSGI configuration file, set environment variables **before** importing `run`:

```python
import os, sys
project_home = '/home/YOUR_USERNAME/placement_portal'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['APP_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'PASTE_A_LONG_RANDOM_SECRET'
os.environ['DATABASE_URL'] = 'PASTE_NEON_CONNECTION_STRING'
os.environ['GOOGLE_CLIENT_ID'] = 'YOUR_GOOGLE_CLIENT_ID'
os.environ['GOOGLE_CLIENT_SECRET'] = 'YOUR_GOOGLE_CLIENT_SECRET'
os.environ['MAIL_SERVER'] = 'smtp.gmail.com'
os.environ['MAIL_PORT'] = '587'
os.environ['MAIL_USERNAME'] = 'your-sending-account@gmail.com'
os.environ['MAIL_PASSWORD'] = 'YOUR_GMAIL_APP_PASSWORD'
os.environ['MAIL_DEFAULT_SENDER'] = 'your-sending-account@gmail.com'
os.environ['MAIL_SENDER_NAME'] = 'Placement Portal'

from run import app as application
```

Keep your existing virtualenv setup and static-file mapping. Replace all placeholders. Never paste real credentials into chat or commit them to source control.

### 3. Create the initial database tables

For a **brand-new, empty Neon database only**, temporarily add this line to the WSGI environment settings before importing the app:

```python
os.environ['AUTO_CREATE_TABLES'] = 'true'
```

Reload once and confirm the app starts and tables are created. Then remove that line (or set it to `false`) and reload again. `create_all()` creates missing tables; it does not alter existing tables or migrate schema changes.

For future model/schema changes, use Flask-Migrate instead of relying on `create_all()`:

```bash
cd ~/placement_portal
source ~/.virtualenvs/placement-portal/bin/activate
export APP_ENV=production
export SECRET_KEY='YOUR_LONG_RANDOM_SECRET'
export DATABASE_URL='YOUR_NEON_CONNECTION_STRING'
flask --app run db init       # run once only if migrations/ does not exist
flask --app run db migrate -m "Initial schema"  # review generated migration before applying
flask --app run db upgrade
```

After creating migrations, keep the `migrations/` folder with your project for future releases. Do not rerun `db init` once that folder exists. For an existing SQLite database with data, do **not** point the app at Neon and assume data has migrated: schema creation does not copy old records. Export/import or run a separately verified migration before switching production traffic.

### 4. Production database notes

- Keep Neon credentials only in the host's environment configuration/WSGI file; restrict access to that file.
- Use a unique `SECRET_KEY`. Production startup intentionally fails if `DATABASE_URL` is configured but the secret is missing or left at the example placeholder.
- Neon PostgreSQL is persistent; your app's local `app/instance/site.db` is not automatically copied to Neon.
- Test registration, confirmation emails, student/company/admin login, job creation, applications, and reports against the new database before announcing the site.
- Take backups/export important records before changing database providers. Check your Neon plan's retention and compute/suspend behavior.
- Flask-Migrate is included for schema migrations. Do not treat `db.create_all()` as a replacement for migrations.
