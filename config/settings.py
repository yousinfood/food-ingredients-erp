import os
from pathlib import Path
from urllib.parse import quote

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SUPABASE_PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "dndsfdaqcshavdqdieck").strip()


def _build_supabase_database_url(password: str) -> str:
    return (
        f"postgresql://postgres:{quote(password, safe='')}"
        f"@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres?sslmode=require"
    )


def _resolve_database_url():
    """Railway / 雲端：優先 DATABASE_URL（PostgreSQL）。本機預設 SQLite。"""
    url = os.environ.get("DATABASE_URL", "").strip()
    placeholders = ("YOUR_PASSWORD", "YOUR_PROJECT_REF", "YOUR-PROJECT-REF")
    if url and not any(token in url for token in placeholders):
        return url

    if os.environ.get("USE_POSTGRES", "").strip().lower() not in ("1", "true", "yes"):
        return f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

    db_password = os.environ.get("DB_PASSWORD", "").strip()
    if db_password and db_password not in placeholders:
        return _build_supabase_database_url(db_password)

    return f"sqlite:///{BASE_DIR / 'db.sqlite3'}"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-in-production")
DEBUG = _env_bool("DEBUG", default=True)
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# 本機用 ngrok / Tailscale 在 iPad 測試時（僅 DEBUG）
if DEBUG:
    ALLOWED_HOSTS += ["0.0.0.0"]
    ALLOWED_HOSTS += [
        ".ngrok-free.app",
        ".ngrok.io",
        ".ngrok.app",
    ]
    _extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS_EXTRA", "").strip()
    if _extra_hosts:
        ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(",") if h.strip()]

if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
ALLOWED_HOSTS += [".up.railway.app"]
_extra_allowed = os.environ.get("ALLOWED_HOSTS", "").strip()
if _extra_allowed:
    ALLOWED_HOSTS += [h.strip() for h in _extra_allowed.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS: list[str] = []
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "https://*.ngrok-free.app",
        "https://*.ngrok.io",
        "https://*.ngrok.app",
    ]
    _extra_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS_EXTRA", "").strip()
    if _extra_csrf:
        CSRF_TRUSTED_ORIGINS += [o.strip() for o in _extra_csrf.split(",") if o.strip()]

if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

if RAILWAY_PUBLIC_DOMAIN or _env_bool("USE_NGROK"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.inventory",
    "apps.procurement",
    "apps.sales",
    "apps.production",
    "apps.excel_schema",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.erp_nav",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

_default_db = dj_database_url.parse(
    _resolve_database_url(),
    conn_max_age=600,
    conn_health_checks=True,
)
if _default_db.get("ENGINE") == "django.db.backends.postgresql":
    _default_db.setdefault("OPTIONS", {})
    _default_db["OPTIONS"].setdefault("sslmode", "require")

DATABASES = {"default": _default_db}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
