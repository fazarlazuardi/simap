"""
Django settings for config project.
"""
from pathlib import Path
import environ
import os
import sys
import shutil

env = environ.Env(
    DEBUG=(bool, False)
)

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BASE_DIR / 'apps'))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-simap-key-2026')
DEBUG = env('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['.trycloudflare.com', '127.0.0.1', 'localhost'])
CSRF_TRUSTED_ORIGINS = ['https://*.trycloudflare.com', 'http://127.0.0.1:8000', 'http://localhost:8000']
PUBLIC_HOST_URL = env('PUBLIC_HOST_URL', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'crispy_forms',
    'crispy_bootstrap5',

    'authentication',
    'users',
    'archives',
    'dispositions',
    'agendas',
    'notifications',
    'reports',
    'audit_logs',
    'sppd_service',
    'surat_tugas',
    'internal_meetings.apps.InternalMeetingsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.users.middleware.ActiveUserMiddleware',
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
                'config.context_processors.notification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

db_host = env('DB_HOST', default='127.0.0.1')
if not db_host or db_host == 'localhost':
    db_host = '127.0.0.1'

DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME': env('DB_NAME', default='simap'),
        'USER': env('DB_USER', default='root'),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': db_host,
        'PORT': env('DB_PORT', default='3306'),
        'CONN_MAX_AGE': 300,
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = env('LANGUAGE_CODE', default='id')
TIME_ZONE = env('TIME_ZONE', default='Asia/Jakarta')
USE_I18N = True
USE_TZ = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

LOGIN_URL = 'authentication:login'
LOGIN_REDIRECT_URL = 'users:dashboard'
LOGOUT_REDIRECT_URL = 'authentication:login'

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_ALWAYS_EAGER', default=False)

def _is_redis_available(host='127.0.0.1', port=6379):
    import socket
    try:
        s = socket.create_connection((host, port), timeout=0.3)
        s.close()
        return True
    except Exception:
        return False

if 'test' not in sys.argv and _is_redis_available():
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': env('REDIS_CACHE_URL', default='redis://127.0.0.1:6379/1'),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

WA_GATEWAY_URL = env('WA_GATEWAY_URL', default='')
GOOGLE_DRIVE_FOLDER_ID = env('GOOGLE_DRIVE_FOLDER_ID', default='10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm')
GOOGLE_DRIVE_CREDENTIALS = env('GOOGLE_DRIVE_CREDENTIALS', default=os.path.join(BASE_DIR, 'credentials.json'))
GOOGLE_SHEET_ID = env('GOOGLE_SHEET_ID', default='1WX3-UvF4okkXKRuui9oiTzF6TZFgsdtSyoQR89QyiTc')
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')

SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)

# ------------------------------------------------------------------
# EMAIL CONFIGURATION & GOOGLE DRIVE BACKUP INTEGRATION
# ------------------------------------------------------------------
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='simap@baznas-kabtangerang.or.id')
BACKUP_EMAIL_RECIPIENT = env('BACKUP_EMAIL_RECIPIENT', default='kabupatenbaznastangerang@gmail.com')

