"""
Django settings for school_rfid_project.

School Access & Meal Attendance MVP — RFID-based entry tracking and
class-grouped meal lists. See docs/DATABASE_MODEL.md for the full spec.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-afhelk(rdu+usksn49f-bbmvg@vp3%(=uj(e5tf6dj8s3)x7)^",
)

DEBUG = os.getenv("DEBUG", "True") == "True"

_allowed = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()] or ["*"]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "school_access",
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
    "school_access.middleware.NoCacheAuthMiddleware",
]

ROOT_URLCONF = "school_rfid_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "school_rfid_project.wsgi.application"


# Database — PostgreSQL. Table names match the spec 1:1 (students, classes,
# access_events, etc). They live in the default "public" schema rather than
# a dedicated "school_access" schema: Django's db_table does not split on
# "." into schema+table (it would just quote a literal dotted identifier),
# and a real per-app schema would require a second connection alias plus a
# DATABASE_ROUTERS entry — not worth the complexity for this MVP. Only the
# schema-qualification from the spec's SQL examples is not replicated;
# everything else (columns, constraints, indexes) matches exactly.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "school_rfid"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    },
}


# RFID hardware integration
# Verifies the HMAC-SHA256 signature ESP32 readers attach to scan requests.
CARD_SCAN_API_KEY = os.getenv("CARD_SCAN_API_KEY", "")

# Secret used to derive card_uid_hash / scanned_card_uid_hash at rest.
# Must never be the same value that is deployed onto reader firmware.
CARD_UID_HASH_SECRET = os.getenv("CARD_UID_HASH_SECRET", "")

# Telegram Bot API — used by the `send_daily_report` management command
# (school_access/services/telegram_report.py) to post the daily attendance
# report. Create a bot via @BotFather to get the token; the chat_id is the
# numeric id of the user/group/channel that should receive the report.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "school_access": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "WARNING",
            "propagate": False,
        },
        "django": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
