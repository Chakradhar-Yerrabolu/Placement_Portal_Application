import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from dotenv import load_dotenv

# Load .env for local development. On PythonAnywhere, set secrets in WSGI instead.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth


db = SQLAlchemy()
migrate = Migrate()
oauth = OAuth()


def normalize_database_url(url):
    """Normalize Neon PostgreSQL URLs for psycopg 3 and require TLS."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    parts = urlsplit(url)
    if parts.scheme.startswith("postgresql"):
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.setdefault("sslmode", "require")
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url


def create_app():
    app = Flask(__name__)
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    raw_database_url = os.environ.get("DATABASE_URL", "").strip()
    database_url = normalize_database_url(raw_database_url)
    is_production = os.environ.get("APP_ENV", "").lower() == "production" or bool(raw_database_url)
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if is_production and (not secret_key or secret_key == "replace-with-a-long-random-secret"):
        raise RuntimeError("Set a unique, strong SECRET_KEY in the production environment before starting the app.")

    app.config["SECRET_KEY"] = secret_key or "local-development-only-change-me"
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url or f"sqlite:///{instance_dir / 'site.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = is_production
    db.init_app(app)
    migrate.init_app(app, db)

    # Google OpenID Connect verifies that the registering student controls the email.
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    with app.app_context():
        from . import auth  # noqa: F401
        from . import models  # noqa: F401
        # Explicit opt-in for first-time schema creation. Use Flask-Migrate for future changes.
        if (not raw_database_url) or os.environ.get("AUTO_CREATE_TABLES", "").lower() in {"1", "true", "yes"}:
            db.create_all()

    return app
