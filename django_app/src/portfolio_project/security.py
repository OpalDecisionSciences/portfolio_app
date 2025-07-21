# Django Portfolio Application Security Configuration
"""
Security utilities and validation functions for production deployment.
"""

import os
import secrets
from django.core.exceptions import ImproperlyConfigured
from typing import Any, Optional


def get_env_variable(var_name: str, default: Optional[str] = None) -> str:
    """
    Get environment variable with proper error handling.
    
    Args:
        var_name: Name of the environment variable
        default: Default value if variable is not set
        
    Returns:
        Environment variable value
        
    Raises:
        ImproperlyConfigured: If required variable is missing
    """
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not None:
            return default
        error_msg = f"Set the {var_name} environment variable"
        raise ImproperlyConfigured(error_msg)


def get_env_bool(var_name: str, default: bool = False) -> bool:
    """
    Get boolean environment variable.
    
    Args:
        var_name: Name of the environment variable
        default: Default value if variable is not set
        
    Returns:
        Boolean value
    """
    value = os.environ.get(var_name, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_list(var_name: str, default: Optional[list] = None) -> list:
    """
    Get list from comma-separated environment variable.
    
    Args:
        var_name: Name of the environment variable
        default: Default value if variable is not set
        
    Returns:
        List of values
    """
    value = os.environ.get(var_name, '')
    if not value:
        return default or []
    return [item.strip() for item in value.split(',') if item.strip()]


def generate_secret_key() -> str:
    """
    Generate a cryptographically secure secret key.
    
    Returns:
        Random secret key suitable for Django
    """
    return secrets.token_urlsafe(50)


def validate_production_settings() -> list:
    """
    Validate that all required production settings are configured.
    
    Returns:
        List of validation errors
    """
    errors = []
    
    # Required environment variables for production
    required_vars = [
        'DJANGO_SECRET_KEY',
        'DATABASE_NAME',
        'DATABASE_USER', 
        'DATABASE_PASSWORD',
        'DATABASE_HOST',
        'OPENAI_API_KEY',
    ]
    
    for var in required_vars:
        try:
            value = get_env_variable(var)
            if not value or len(value.strip()) == 0:
                errors.append(f"Environment variable {var} is empty")
        except ImproperlyConfigured:
            errors.append(f"Required environment variable {var} is not set")
    
    # Validate SECRET_KEY length
    try:
        secret_key = get_env_variable('DJANGO_SECRET_KEY')
        if len(secret_key) < 50:
            errors.append("DJANGO_SECRET_KEY should be at least 50 characters long")
    except ImproperlyConfigured:
        pass  # Already caught above
    
    # Check DEBUG is disabled in production
    if get_env_bool('DEBUG', False):
        errors.append("DEBUG should be False in production")
    
    return errors


def get_allowed_hosts() -> list:
    """
    Get allowed hosts with proper defaults for development/production.
    
    Returns:
        List of allowed hosts
    """
    # Production hosts from environment
    production_hosts = get_env_list('ALLOWED_HOSTS')
    
    # Development defaults
    development_hosts = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']
    
    # If DEBUG is True, include development hosts
    if get_env_bool('DEBUG', False):
        return list(set(production_hosts + development_hosts))
    
    # Production mode - only use specified hosts
    if not production_hosts:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS environment variable must be set in production"
        )
    
    return production_hosts


def get_cors_allowed_origins() -> list:
    """
    Get CORS allowed origins with proper defaults.
    
    Returns:
        List of allowed CORS origins
    """
    cors_origins = get_env_list('CORS_ALLOWED_ORIGINS')
    
    # Development defaults
    if get_env_bool('DEBUG', False):
        development_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000", 
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
        return list(set(cors_origins + development_origins))
    
    return cors_origins


def get_database_config() -> dict:
    """
    Get database configuration with security best practices.
    
    Returns:
        Database configuration dictionary
    """
    return {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': get_env_variable('DATABASE_NAME'),
            'USER': get_env_variable('DATABASE_USER'),
            'PASSWORD': get_env_variable('DATABASE_PASSWORD'),
            'HOST': get_env_variable('DATABASE_HOST'),
            'PORT': get_env_variable('DATABASE_PORT', '5432'),
            'OPTIONS': {
                'sslmode': get_env_variable('DATABASE_SSL_MODE', 'prefer'),
            },
            'CONN_MAX_AGE': 60,  # Connection pooling
            'CONN_HEALTH_CHECKS': True,
        }
    }


def get_security_middleware() -> list:
    """
    Get security middleware configuration.
    
    Returns:
        List of middleware classes in correct order
    """
    return [
        'django.middleware.security.SecurityMiddleware',
        'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
        'django.contrib.sessions.middleware.SessionMiddleware',
        'corsheaders.middleware.CorsMiddleware',
        'django.middleware.common.CommonMiddleware', 
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]


def get_production_security_settings() -> dict:
    """
    Get production security settings.
    
    Returns:
        Dictionary of security settings
    """
    return {
        # HTTPS Security
        'SECURE_HSTS_SECONDS': 31536000,  # 1 year
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
        'SECURE_HSTS_PRELOAD': True,
        'SECURE_SSL_REDIRECT': True,
        
        # Cookie Security
        'SESSION_COOKIE_SECURE': True,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'CSRF_COOKIE_SECURE': True,
        'CSRF_COOKIE_HTTPONLY': True,
        'CSRF_COOKIE_SAMESITE': 'Lax',
        
        # Browser Security
        'SECURE_BROWSER_XSS_FILTER': True,
        'SECURE_CONTENT_TYPE_NOSNIFF': True,
        'SECURE_REFERRER_POLICY': 'strict-origin-when-cross-origin',
        'X_FRAME_OPTIONS': 'DENY',
        
        # Additional Security
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    }


def get_logging_config(log_level: str = 'INFO') -> dict:
    """
    Get logging configuration for production.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Logging configuration dictionary
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'level': log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '/var/log/django/django.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'formatter': 'verbose',
            },
            'console': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
            'mail_admins': {
                'level': 'ERROR',
                'class': 'django.utils.log.AdminEmailHandler',
                'include_html': True,
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': log_level,
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file', 'mail_admins'],
                'level': log_level,
                'propagate': False,
            },
            'restaurants': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False,
            },
            'accounts': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False,
            },
            'api': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False,
            },
        },
    }