# Production Configuration Files

This directory contains production-ready configuration files that were separated from the development environment.

## Files:

- `settings_production.py` - Production Django settings with security features, logging, rate limiting, and Redis integration
- `security.py` - Security utilities and configuration functions for production deployment
- `constants.py` - Production constants and rate limiting settings
- `.env.production` - Production environment variables with container host names (db, redis, rag)

## Usage:

To use these production configurations in deployment:

1. Copy `settings_production.py` to replace the main `settings.py` file
2. Ensure `security.py` and `constants.py` are in the Django project directory
3. Install production dependencies:
   - django-ratelimit>=3.0.1
   - django-redis>=5.2.0
   - whitenoise>=6.6.0
4. Set up proper environment variables for production
5. Configure logging directories and permissions

## Features Included:

- Enhanced security middleware
- Rate limiting on authentication endpoints
- Redis caching and session management
- Production logging configuration
- CORS and HTTPS security settings
- Environment-based configuration validation

## Development Note:

The main Django application now uses simplified settings for local development without these production dependencies.