# Django Portfolio Application Constants
"""
Central location for all application constants to avoid magic numbers
and ensure consistency across the codebase.
"""

# Pagination
DEFAULT_PAGE_SIZE = 20
LARGE_PAGE_SIZE = 50
SMALL_PAGE_SIZE = 10

# Rate Limiting
LOGIN_RATE_LIMIT = '5/m'  # 5 attempts per minute
PASSWORD_RESET_RATE_LIMIT = '3/h'  # 3 requests per hour
API_RATE_LIMIT_ANON = '100/h'  # Anonymous users
API_RATE_LIMIT_USER = '1000/h'  # Authenticated users
CHAT_RATE_LIMIT = '20/m'  # Chat messages per minute

# File Upload Limits
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGES_PER_RESTAURANT = 20
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

# Cache Timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 300  # 5 minutes
CACHE_TIMEOUT_MEDIUM = 3600  # 1 hour
CACHE_TIMEOUT_LONG = 86400  # 24 hours
CACHE_TIMEOUT_RECOMMENDATIONS = 3600  # 1 hour for recommendations

# API Timeouts
RAG_SERVICE_TIMEOUT = 30  # seconds
OPENAI_API_TIMEOUT = 60  # seconds
EXTERNAL_API_TIMEOUT = 10  # seconds

# Scraping Configuration
SCRAPING_BATCH_SIZE = 10
MAX_SCRAPING_RETRIES = 3
SCRAPING_DELAY = 2  # seconds between requests

# User Preferences
MIN_PASSWORD_LENGTH = 8
MAX_FAVORITES_PER_USER = 500
DEFAULT_RECOMMENDATIONS_COUNT = 10

# Restaurant Data
MICHELIN_STAR_CHOICES = [
    (0, 'No Stars'),
    (1, '1 Star'),
    (2, '2 Stars'),
    (3, '3 Stars'),
]

PRICE_RANGE_CHOICES = [
    ('budget', 'Budget-friendly ($)'),
    ('moderate', 'Moderate ($$)'),
    ('upscale', 'Upscale ($$$)'),
    ('luxury', 'Luxury ($$$$)'),
    ('any', 'Any price range'),
]

FAVORITE_CATEGORIES = [
    ('to_visit', 'Want to Visit'),
    ('visited', 'Visited & Loved'),
    ('special_occasion', 'Special Occasions'),
    ('business_dining', 'Business Dining'),
    ('romantic', 'Romantic Dinners'),
    ('family', 'Family-Friendly'),
    ('quick_bite', 'Quick Bites'),
]

# Collaborative Filtering
SIMILARITY_THRESHOLD = 0.15  # Minimum similarity for recommendations
MAX_SIMILAR_USERS = 10
RECOMMENDATION_WEIGHTS = {
    'favorites_score': 0.35,
    'profile_score': 0.25,
    'review_score': 0.20,
    'collaborative_score': 0.15,
    'popularity_score': 0.05,
}

CATEGORY_WEIGHTS = {
    'visited': 1.0,
    'special_occasion': 0.9,
    'business_dining': 0.8,
    'romantic': 0.8,
    'to_visit': 0.7,
    'family': 0.7,
    'quick_bite': 0.6,
}

# AI Image Classification
IMAGE_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7
MAX_CLASSIFICATION_RETRIES = 2

# Token Management
TOKEN_USAGE_THRESHOLD_HIGH = 80  # Percentage
TOKEN_USAGE_THRESHOLD_MEDIUM = 60  # Percentage
MODEL_SWITCH_THRESHOLD = 75  # Switch to cheaper model at this usage

# Session Management
SESSION_EXPIRE_SECONDS = 3600  # 1 hour
REMEMBER_ME_EXPIRE_SECONDS = 30 * 24 * 3600  # 30 days

# Security
PASSWORD_RESET_TIMEOUT = 86400  # 24 hours
CSRF_FAILURE_VIEW = 'portfolio_project.views.csrf_failure'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Logging
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Development vs Production
DEVELOPMENT_ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']

# Database
DATABASE_CONN_MAX_AGE = 60  # seconds
DATABASE_CONN_HEALTH_CHECKS = True

# Static Files
STATIC_FILES_MAX_AGE = 31536000  # 1 year for static files
MEDIA_FILES_MAX_AGE = 3600  # 1 hour for media files