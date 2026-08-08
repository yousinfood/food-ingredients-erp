import os
from pathlib import Path
from urllib.parse import quote

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=False)

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


def _detect_local_lan_ips() -> list[str]:
    """本機區域網 IP（iPad 同 Wi‑Fi 測試用，僅 DEBUG 載入 settings 時呼叫）。"""
    import socket
    import subprocess

    found: set[str] = set()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    for iface in ("en0", "en1", "en2", "bridge0"):
        try:
            out = subprocess.check_output(
                ["ipconfig", "getifaddr", iface],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if out:
                found.add(out)
        except (OSError, subprocess.CalledProcessError):
            continue
    return sorted(ip for ip in found if ip and not ip.startswith("127."))


SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-in-production")
DEBUG = _env_bool("DEBUG", default=True)
# Local dev often hits remote PostgreSQL (~2s); production (DEBUG=False) keeps 1s P0 timeout.
CUSTOMER_SEARCH_TIMEOUT_MS = int(
    os.environ.get("CUSTOMER_SEARCH_TIMEOUT_MS", "5000" if DEBUG else "1000")
)
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
CLOUDFLARE_TUNNEL_HOSTNAME = os.environ.get("CLOUDFLARE_TUNNEL_HOSTNAME", "").strip()

DEV_LAN_IP = os.environ.get("DEV_LAN_IP", "192.168.0.165").strip()

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "192.168.0.165"]

# 本機用 ngrok / Tailscale / 區域網 在 iPad 測試時（僅 DEBUG）
if DEBUG:
    ALLOWED_HOSTS += [
        ".ngrok-free.app",
        ".ngrok.io",
        ".ngrok.app",
        ".trycloudflare.com",
    ]
    if DEV_LAN_IP and DEV_LAN_IP not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(DEV_LAN_IP)
    _extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS_EXTRA", "").strip()
    if _extra_hosts:
        ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(",") if h.strip()]
    for ip in _detect_local_lan_ips():
        if ip not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(ip)

if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
if CLOUDFLARE_TUNNEL_HOSTNAME:
    ALLOWED_HOSTS.append(CLOUDFLARE_TUNNEL_HOSTNAME)
ALLOWED_HOSTS += [".up.railway.app"]
_extra_allowed = os.environ.get("ALLOWED_HOSTS", "").strip()
if _extra_allowed:
    ALLOWED_HOSTS += [h.strip() for h in _extra_allowed.split(",") if h.strip()]

ALLOWED_HOSTS = list(dict.fromkeys(h for h in ALLOWED_HOSTS if h))

CSRF_TRUSTED_ORIGINS: list[str] = []
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "https://*.ngrok-free.app",
        "https://*.ngrok.io",
        "https://*.ngrok.app",
        "https://*.trycloudflare.com",
    ]
    _extra_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS_EXTRA", "").strip()
    if _extra_csrf:
        CSRF_TRUSTED_ORIGINS += [o.strip() for o in _extra_csrf.split(",") if o.strip()]
    _dev_port = os.environ.get("DJANGO_DEV_PORT", "8000").strip() or "8000"
    _csrf_lan_ips = dict.fromkeys(
        [DEV_LAN_IP, "192.168.0.165", "127.0.0.1", "localhost", *_detect_local_lan_ips()]
    )
    for ip in _csrf_lan_ips:
        if ip:
            CSRF_TRUSTED_ORIGINS.append(f"http://{ip}:{_dev_port}")

if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")
if CLOUDFLARE_TUNNEL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{CLOUDFLARE_TUNNEL_HOSTNAME}")

if RAILWAY_PUBLIC_DOMAIN or _env_bool("USE_NGROK") or _env_bool("USE_CLOUDFLARE_TUNNEL"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool(
        "SECURE_SSL_REDIRECT",
        default=not bool(RAILWAY_PUBLIC_DOMAIN),
    )
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
    "apps.deliveries",
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

MEDIA_URL = os.environ.get("MEDIA_URL", "media/").strip() or "media/"
_media_root_env = os.environ.get("MEDIA_ROOT", "").strip()
MEDIA_ROOT = Path(_media_root_env) if _media_root_env else BASE_DIR / "media"

WHITENOISE_MIMETYPES = {
    ".webmanifest": "application/manifest+json",
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Google「產品資料」→ Product 自動同步（接單讀商品前）
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_SHEETS_PRODUCT_CSV_URL = os.environ.get("GOOGLE_SHEETS_PRODUCT_CSV_URL", "").strip()
GOOGLE_SHEETS_CUSTOMER_CSV_URL = os.environ.get("GOOGLE_SHEETS_CUSTOMER_CSV_URL", "").strip()
PRODUCT_SHEET_SYNC_INTERVAL_SECONDS = int(
    os.environ.get("PRODUCT_SHEET_SYNC_INTERVAL_SECONDS", "15")
)
CUSTOMER_SHEET_SYNC_INTERVAL_SECONDS = int(
    os.environ.get("CUSTOMER_SHEET_SYNC_INTERVAL_SECONDS", "15")
)

# Google Sheet 客戶 webhook（Apps Script POST → ERP）
GOOGLE_SHEET_WEBHOOK_TOKEN = os.environ.get("GOOGLE_SHEET_WEBHOOK_TOKEN", "").strip()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

# Log full tracebacks for 500 errors to stdout (Railway deploy logs).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps.inventory.services.product_webhook_sync": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.inventory.views_product_sync_webhook": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
