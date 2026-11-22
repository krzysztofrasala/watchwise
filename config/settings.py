import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file if present
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    with open(_env_file, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                _v = _v.strip().strip('"').strip("'")
                if _v:  # blank entries (e.g. from .env.example) must not mask defaults
                    os.environ.setdefault(_k.strip(), _v)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', os.environ.get('SECRET_KEY', 'django-insecure-cinescope-secret-key-cinema-2026'))

DEBUG = os.environ.get('DJANGO_DEBUG', 'True' if 'RENDER' not in os.environ else 'False').lower() in ('true', '1')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'movies',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'movies.middleware.LanguageCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

def _parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL environment variable for PostgreSQL / SQLite without external dependencies."""
    from urllib.parse import urlparse, parse_qs, unquote
    parsed = urlparse(url)
    scheme = (parsed.scheme or '').lower()
    if scheme in ('postgres', 'postgresql', 'pgsql'):
        cfg = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or 5432),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
        }
        qs = parse_qs(parsed.query)
        options = {}
        if 'sslmode' in qs and qs['sslmode']:
            options['sslmode'] = qs['sslmode'][0]
        if options:
            cfg['OPTIONS'] = options
        return cfg
    if scheme == 'sqlite':
        db_path = unquote(parsed.path)
        if db_path in ('', '/', ':memory:'):
            name = ':memory:'
        else:
            name = db_path.lstrip('/') if not db_path.startswith('//') else db_path[1:]
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': name,
        }
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }


_database_url = os.environ.get('DATABASE_URL', '').strip()
DATABASES = {
    'default': _parse_database_url(_database_url) if _database_url else {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

SESSION_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year session persistence

if not DEBUG:
    # Production hardening (Render terminates TLS and forwards X-Forwarded-Proto)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SSL_REDIRECT', 'True').lower() in ('true', '1')
    SECURE_REDIRECT_EXEMPT = [r'^healthz/?$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))
    SECURE_CONTENT_TYPE_NOSNIFF = True

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'pl'

TIME_ZONE = 'Europe/Warsaw'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "cinescope-cache",
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
