"""Generate PostgreSQL migration SQL only (no live DB connection)."""
from config.settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "unused",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
