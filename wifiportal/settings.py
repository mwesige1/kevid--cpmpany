"""
Django settings for wifiportal project.
"""

from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ───────────────────────────────────────────
SECRET_KEY    = config('SECRET_KEY')
DEBUG         = config('DEBUG', cast=bool, default=False)
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# ── Redis & Celery ─────────────────────────────────────
REDIS_URL = config('REDIS_URL')

# ── Celery Configuration ───────────────────────────────
CELERY_BROKER_URL        = config('REDIS_URL')
CELERY_RESULT_BACKEND    = config('REDIS_URL')
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE          = 'Africa/Kampala'

# ── MTN MoMo ───────────────────────────────────────────
MTN_BASE_URL         = config('MTN_BASE_URL')
MTN_SUBSCRIPTION_KEY = config('MTN_SUBSCRIPTION_KEY')
MTN_API_USER         = config('MTN_API_USER')
MTN_API_KEY          = config('MTN_API_KEY')
MTN_TARGET_ENV       = config('MTN_TARGET_ENV')
MTN_CALLBACK_URL     = config('MTN_CALLBACK_URL')

# ── Airtel Money ───────────────────────────────────────
AIRTEL_BASE_URL      = config('AIRTEL_BASE_URL')
AIRTEL_CLIENT_ID     = config('AIRTEL_CLIENT_ID')
AIRTEL_CLIENT_SECRET = config('AIRTEL_CLIENT_SECRET')
AIRTEL_CALLBACK_URL  = config('AIRTEL_CALLBACK_URL')

# ── IOTEC Pay ──────────────────────────────────────────
IOTEC_CLIENT_ID     = config('IOTEC_CLIENT_ID')
IOTEC_CLIENT_SECRET = config('IOTEC_CLIENT_SECRET')
IOTEC_WALLET_ID     = config('IOTEC_WALLET_ID')
IOTEC_BASE_URL      = config('IOTEC_BASE_URL',  default='https://pay.iotec.io')
IOTEC_AUTH_URL      = config('IOTEC_AUTH_URL',  default='https://id.iotec.io/connect/token')
IOTEC_CALLBACK_URL  = config('IOTEC_CALLBACK_URL')

# ── Router ─────────────────────────────────────────────
ROUTER_IP       = config('ROUTER_IP')
ROUTER_USER     = config('ROUTER_USER')
ROUTER_PASSWORD = config('ROUTER_PASSWORD')

# ── Africa's Talking ───────────────────────────────────
AT_USERNAME  = config('AT_USERNAME')
AT_API_KEY   = config('AT_API_KEY')
AT_SENDER_ID = config('AT_SENDER_ID', default='')

# ── Installed Apps ─────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third party
    'django_celery_beat',

    # Our custom apps
    'portal',
    'payments',
    'network',
    'dashboard',
    'wifi_sessions',
    'axes',
]

# ── Middleware ─────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wifiportal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wifiportal.wsgi.application'

# ── Database ───────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE'  : 'django.db.backends.postgresql',
        'NAME'    : config('DATABASE_NAME'),
        'USER'    : config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST'    : config('DATABASE_HOST'),
        'PORT'    : config('DATABASE_PORT'),
    }
}

# ── Password Validation ────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ───────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Kampala'
USE_I18N      = True
USE_TZ        = True

# ── Static & Media Files ───────────────────────────────
STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'
MEDIA_URL        = '/media/'
MEDIA_ROOT       = BASE_DIR / 'media'

# WhiteNoise — serves static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Celery Beat Schedule ───────────────────────────────
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'check-expired-sessions': {
        'task'    : 'wifi_sessions.tasks.check_expired_sessions',
        'schedule': 60.0,
    },
    'sync-active-sessions': {
        'task'    : 'wifi_sessions.tasks.sync_active_sessions',
        'schedule': 60.0,
    },
    'restore-router-rules': {
        'task'    : 'wifi_sessions.tasks.restore_router_rules',
        'schedule': crontab(minute='*/5'),
    },
   'check-router-health': {
    'task'    : 'wifi_sessions.tasks.check_router_health',
    'schedule': 60.0,  # Every 60 seconds — keeps dashboard status accurate
    },
}

# ── CSRF ───────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    'https://kevidtechhotspot.com',
    'https://www.kevidtechhotspot.com',
    'http://192.168.88.252:8000',
    'http://192.168.1.9:8000',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://10.0.0.1:8000',
    'http://localhost:8081',
    'http://127.0.0.1:8081',
    'https://reburial-mating-effort.ngrok-free.dev',
    'http://192.168.1.22:8081',

]
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE   = False

# ── Security Headers (production) ─────────────────────
SECURE_BROWSER_XSS_FILTER        = True
SECURE_CONTENT_TYPE_NOSNIFF       = True
X_FRAME_OPTIONS                   = 'DENY'

# ── Logging ────────────────────────────────────────────
LOGGING = {
    'version'                 : 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style' : '{',
        },
    },
    'handlers': {
        'file': {
            'level'    : 'ERROR',
            'class'    : 'logging.FileHandler',
            'filename' : BASE_DIR / 'logs/error.log',
            'formatter': 'verbose',
        },
        'console': {
            'class'    : 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level'   : 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers'  : ['console', 'file'],
            'level'     : 'ERROR',
            'propagate' : False,
        },
    },
}

# ── Django Axes ────────────────────────────────────────
AXES_FAILURE_LIMIT      = 5
AXES_COOLOFF_TIME       = 0.5
AXES_LOCKOUT_TEMPLATE   = None
AXES_RESET_ON_SUCCESS   = True
AXES_ENABLE_ADMIN       = False
AXES_IPWARE_PROXY_COUNT = 1
AXES_LOCKOUT_URL        = '/dashboard/login/?locked=1'

# ── Authentication Backends ────────────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ── Login URL ──────────────────────────────────────────
LOGIN_URL = '/dashboard/login/'
# ── Default Primary Key ────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'