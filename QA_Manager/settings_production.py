"""
Production settings for QAID Manager packaged application.
This file is used when running the packaged executable.
"""
from pathlib import Path
import os
import sys

from QA_Manager.host_config import build_allowed_hosts, ensure_root_hostname_file, read_hostname

# Determine if running as packaged executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = Path(sys._MEIPASS)  # PyInstaller temp folder (contains templates, static files)
    APP_DIR = Path(os.path.dirname(sys.executable))  # Where the .exe is located
else:
    # Running as normal Python script
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BASE_DIR

# Data directory (where database and uploads are stored)
# This will be in the same folder as the executable
DATA_DIR = APP_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)  # Ensure parent directories exist

# Note: BASE_DIR is NOT overwritten here - it's already set correctly above
# BASE_DIR points to PyInstaller temp folder when frozen, or project root when running as script

# SECURITY WARNING: keep the secret key used in production secret!
# Public prototype: SECRET_KEY must come from the environment (no hardcoded fallback).
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    raise RuntimeError(
        'DJANGO_SECRET_KEY environment variable is required for settings_production.'
    )

# Production defaults to DEBUG=False unless explicitly enabled.
DEBUG = os.environ.get('DJANGO_DEBUG', '').strip().lower() in {'1', 'true', 'yes', 'on'}

# Get hostname from file or environment variable
ensure_root_hostname_file()
HOSTNAME = read_hostname()
ALLOWED_HOSTS = build_allowed_hosts(HOSTNAME)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'QAID_Manager',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'QAID_Manager.middleware.RuntimeBoundSessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'QA_Manager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'QAID_Manager.context_processors.runtime_mode',
            ],
        },
    },
]

WSGI_APPLICATION = 'QA_Manager.wsgi.application'

# Database - stored in data directory
# Convert Path to string for Django compatibility
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(DATA_DIR / 'db.sqlite3'),  # Django requires string path
        'OPTIONS': {
            # Set timeout for database locks (in seconds)
            # If database is locked, wait up to 20 seconds before giving up
            # This helps with concurrent access by allowing SQLite to wait for locks
            'timeout': 20,
            # Use IMMEDIATE transaction mode for better concurrency
            # Acquires write lock at transaction start, reducing lock conflicts
            'transaction_mode': 'IMMEDIATE',
        },
        # Connection pooling settings for better concurrency handling
        'CONN_MAX_AGE': 0,  # Don't keep connections open (SQLite doesn't benefit from connection pooling)
    }
}

# Enable WAL mode for SQLite after database connection
# WAL mode allows multiple readers and one writer simultaneously
# This is done via a signal handler to set PRAGMA after connection
def enable_wal_mode(sender, connection, **kwargs):
    """Enable WAL mode for SQLite to improve concurrent access"""
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            # Enable WAL mode (Write-Ahead Logging) for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")
            # Set synchronous mode to NORMAL (balance between safety and performance)
            cursor.execute("PRAGMA synchronous=NORMAL;")
            # Increase cache size for better performance
            cursor.execute("PRAGMA cache_size=-2000;")  # Negative = KB, positive = pages

# Connect the signal to enable WAL mode when database connection is made
from django.db.backends.signals import connection_created
connection_created.connect(enable_wal_mode)

# Password validation
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = str(DATA_DIR / 'staticfiles')  # Convert to string for Django
STATICFILES_DIRS = [
    str(BASE_DIR / "static"),  # Convert to string
] if not getattr(sys, 'frozen', False) else []

# Media files (uploaded documents, images)
MEDIA_URL = '/media/'
MEDIA_ROOT = str(DATA_DIR / "uploads")  # Convert to string for Django

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
QAID_RUNTIME_SESSION_ID = os.environ.get('QAID_RUNTIME_SESSION_ID', '').strip()
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

_trusted_origins_env = os.environ.get('QAID_CSRF_TRUSTED_ORIGINS', '')
if _trusted_origins_env.strip():
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in _trusted_origins_env.split(',') if origin.strip()
    ]
else:
    # Allow localhost and explicit hostnames configured for this deployment.
    _trusted = []
    for host in ALLOWED_HOSTS:
        if host in {'*', ''}:
            continue
        _trusted.append(f'http://{host}')
    CSRF_TRUSTED_ORIGINS = sorted(set(_trusted))

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# Create necessary directories
(DATA_DIR / 'uploads').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'uploads' / 'dosimeter_files').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'uploads' / 'film_uploads').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'uploads' / 'organization').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'uploads' / 'qa_results').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'staticfiles').mkdir(parents=True, exist_ok=True)

# Logging configuration for production
# When DEBUG=False, errors are logged to console and error log file
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(DATA_DIR / 'error.log'),  # Convert to string
            'formatter': 'verbose',
            'mode': 'a',  # Append mode
            'encoding': 'utf-8',  # UTF-8 encoding for proper error logging
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'ERROR',  # Only log errors in production
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'QAID_Manager': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

