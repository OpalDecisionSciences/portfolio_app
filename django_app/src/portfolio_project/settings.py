# Django Settings for Portfolio Application
import os
from pathlib import Path
from dotenv import load_dotenv
from decouple import config

# Import security utilities
from .security import (
    get_env_variable, 
    get_env_bool, 
    get_allowed_hosts,
    get_cors_allowed_origins,
    get_database_config,
    get_security_middleware,
    get_production_security_settings,
    get_logging_config,
    validate_production_settings
)

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Validate production settings if not in debug mode
if not get_env_bool('DEBUG', False):
    validation_errors = validate_production_settings()
    if validation_errors:
        raise Exception(f"Production configuration errors: {', '.join(validation_errors)}")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_variable('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_env_bool('DEBUG', False)

ALLOWED_HOSTS = get_allowed_hosts()

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'django_extensions',
    
    # Local apps
    'restaurants',
    'accounts',
    'chat',
    'api',
]

MIDDLEWARE = get_security_middleware()

ROOT_URLCONF = 'portfolio_project.urls'

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

WSGI_APPLICATION = 'portfolio_project.wsgi.application'

# Database
DATABASES = get_database_config()

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# CORS settings
CORS_ALLOWED_ORIGINS = get_cors_allowed_origins()

# Logging configuration
LOGGING = get_logging_config()

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# RAG Service Configuration
RAG_SERVICE_URL = os.getenv('RAG_SERVICE_URL', 'http://localhost:8001')

# Redis Configuration (for chat sessions)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'portfolio_cache',
        'TIMEOUT': CACHE_TIMEOUT_MEDIUM,  # Default 1 hour
    }
}

# Celery Configuration (for background tasks)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Custom settings
PORTFOLIO_DATA_DIR = BASE_DIR / 'data'
PORTFOLIO_SCRAPING_BATCH_SIZE = 10
PORTFOLIO_TOKEN_MANAGEMENT_DIR = BASE_DIR / 'token_management'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Chat Safety Settings
CHAT_MAX_MESSAGE_LENGTH = 1000
CHAT_RATE_LIMIT_MESSAGES = 20
CHAT_RATE_LIMIT_WINDOW = 60  # seconds

# Email Configuration for Password Reset
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Michelin Star Service <noreply@example.com>')

# Account Settings
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_EMAIL_REQUIRED = True

# Create necessary directories
os.makedirs(PORTFOLIO_DATA_DIR, exist_ok=True)
os.makedirs(PORTFOLIO_TOKEN_MANAGEMENT_DIR, exist_ok=True)

# Production Security Settings
# Apply security settings if not in debug mode
if not DEBUG:
    security_settings = get_production_security_settings()
    for key, value in security_settings.items():
        globals()[key] = value

# Additional Security Settings for Production
if not DEBUG:
    # Static files serving security
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    
    # Admin security
    ADMIN_URL = get_env_variable('ADMIN_URL', 'admin')  # Custom admin URL
    
    # Cache security
    if 'default' in CACHES:
        CACHES['default']['KEY_PREFIX'] = get_env_variable('CACHE_PREFIX', 'portfolio')

# Rate limiting configuration
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Import constants for consistency
from .constants import *