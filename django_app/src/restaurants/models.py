"""
Restaurant models for the portfolio application.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Restaurant(models.Model):
    """Main restaurant model with comprehensive information."""
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    # Location
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Contact
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Michelin Information
    michelin_stars = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(3)]
    )
    michelin_guide_year = models.IntegerField(null=True, blank=True)
    
    # Rating and Reviews
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    review_count = models.IntegerField(default=0)
    
    # Cuisine and Style
    cuisine_type = models.CharField(max_length=100, blank=True)
    price_range = models.CharField(
        max_length=20,
        choices=[
            ('$', 'Budget'),
            ('$$', 'Moderate'),
            ('$$$', 'Expensive'),
            ('$$$$', 'Very Expensive'),
        ],
        blank=True
    )
    
    # Atmosphere
    atmosphere = models.CharField(max_length=100, blank=True)
    seating_capacity = models.IntegerField(null=True, blank=True)
    has_private_dining = models.BooleanField(default=False)
    
    # Operational
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    opening_hours = models.TextField(blank=True)
    
    # Scraped Data
    original_url = models.URLField(blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    scraped_content = models.TextField(blank=True)
    timezone_info = models.JSONField(null=True, blank=True, help_text="JSON containing timezone and location details")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-michelin_stars', '-rating', 'name']
        indexes = [
            models.Index(fields=['country', 'city']),
            models.Index(fields=['michelin_stars']),
            models.Index(fields=['cuisine_type']),
            models.Index(fields=['is_active', 'is_featured']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.city}, {self.country})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.city}")
        super().save(*args, **kwargs)
    
    def get_timezone_display(self):
        """Get display-friendly timezone information."""
        if self.timezone_info and isinstance(self.timezone_info, dict):
            timezone_name = self.timezone_info.get('local_timezone', '')
            if timezone_name:
                # Format timezone name for display
                return timezone_name.replace('_', ' ').replace('/', ' / ')
        return 'Unknown'
    
    def get_local_time_info(self):
        """Get current local time information for the restaurant."""
        if self.timezone_info and isinstance(self.timezone_info, dict):
            return {
                'timezone': self.timezone_info.get('local_timezone'),
                'country': self.timezone_info.get('country'),
                'city': self.timezone_info.get('city'),
                'utc_offset': self.timezone_info.get('utc_offset')
            }
        return None
    
    def get_current_local_time(self):
        """Get current time in restaurant's local timezone."""
        import pytz
        from django.utils import timezone as django_timezone
        
        if self.timezone_info and self.timezone_info.get('local_timezone'):
            try:
                restaurant_tz = pytz.timezone(self.timezone_info['local_timezone'])
                utc_now = django_timezone.now()
                return utc_now.astimezone(restaurant_tz)
            except Exception:
                pass
        return django_timezone.now()
    
    def is_currently_open(self):
        """
        Check if restaurant is currently open based on local time and operating hours.
        Returns: dict with 'is_open' boolean and 'next_change' datetime if available
        """
        if not self.opening_hours:
            return {'is_open': None, 'status': 'Hours not available', 'next_change': None}
        
        try:
            import json
            from datetime import datetime, time
            
            local_time = self.get_current_local_time()
            current_day = local_time.strftime('%A').lower()
            current_time = local_time.time()
            
            # Parse opening hours (assuming JSON format like {"monday": "09:00-22:00", ...})
            if self.opening_hours.startswith('{'):
                hours_data = json.loads(self.opening_hours)
            else:
                # Parse simple text format if needed
                return {'is_open': None, 'status': 'Hours format not supported', 'next_change': None}
            
            day_hours = hours_data.get(current_day, '')
            
            if not day_hours or day_hours.lower() in ['closed', 'fermé', 'cerrado']:
                return {'is_open': False, 'status': 'Closed today', 'next_change': None}
            
            # Parse time ranges (e.g., "09:00-14:00,19:00-23:00" or "09:00-22:00")
            time_ranges = day_hours.split(',')
            
            for time_range in time_ranges:
                if '-' in time_range:
                    try:
                        start_str, end_str = time_range.strip().split('-')
                        start_time = datetime.strptime(start_str.strip(), '%H:%M').time()
                        end_time = datetime.strptime(end_str.strip(), '%H:%M').time()
                        
                        # Handle overnight hours (e.g., 22:00-02:00)
                        if start_time <= end_time:
                            if start_time <= current_time <= end_time:
                                return {'is_open': True, 'status': f'Open until {end_str}', 'next_change': None}
                        else:
                            # Overnight service
                            if current_time >= start_time or current_time <= end_time:
                                next_close = end_str if current_time >= start_time else end_str
                                return {'is_open': True, 'status': f'Open until {next_close}', 'next_change': None}
                    except ValueError:
                        continue
            
            return {'is_open': False, 'status': 'Currently closed', 'next_change': None}
            
        except Exception as e:
            return {'is_open': None, 'status': 'Unable to determine hours', 'next_change': None}
    
    def get_absolute_url(self):
        return reverse('restaurants:restaurant_detail', kwargs={'slug': self.slug})
    
    @property
    def stars_display(self):
        return '⭐' * self.michelin_stars if self.michelin_stars > 0 else 'No stars'
    
    @property
    def is_michelin_starred(self):
        return self.michelin_stars > 0


class Chef(models.Model):
    """Chef model for restaurant staff."""
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    biography = models.TextField(blank=True)
    
    # Professional Information
    position = models.CharField(
        max_length=100,
        choices=[
            ('head_chef', 'Head Chef'),
            ('executive_chef', 'Executive Chef'),
            ('sous_chef', 'Sous Chef'),
            ('pastry_chef', 'Pastry Chef'),
            ('chef_de_partie', 'Chef de Partie'),
        ]
    )
    
    # Experience
    years_experience = models.IntegerField(null=True, blank=True)
    awards = models.TextField(blank=True)
    
    # Media
    photo = models.ImageField(upload_to='chefs/', blank=True)
    
    # Relationships
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='chefs')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['restaurant', 'position', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_position_display()}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class MenuSection(models.Model):
    """Menu section model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_sections')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['restaurant', 'order', 'name']
        unique_together = ['restaurant', 'name']
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class MenuItem(models.Model):
    """Menu item model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(MenuSection, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.CharField(max_length=20, blank=True)
    
    # Dietary Information
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    allergens = models.TextField(blank=True)
    
    # Availability
    is_available = models.BooleanField(default=True)
    is_signature = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['section', 'name']
    
    def __str__(self):
        return f"{self.section.name} - {self.name}"


class RestaurantImage(models.Model):
    """Enhanced restaurant image model with AI-powered categorization and labeling."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='images')
    
    # Image Storage
    image = models.ImageField(upload_to='restaurants/', blank=True)
    source_url = models.URLField(blank=True, help_text="Original URL where the image was scraped from")
    
    # Manual metadata
    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    
    # AI-Powered Categorization
    ai_category = models.CharField(
        max_length=50,
        choices=[
            ('scenery_ambiance', 'Scenery/Ambiance/Dining'),
            ('menu_item', 'Menu Item'),
            ('uncategorized', 'Uncategorized'),
        ],
        default='uncategorized',
        help_text="AI-determined primary category"
    )
    
    # AI-Generated Labels and Descriptions
    ai_labels = models.JSONField(
        default=list, 
        blank=True,
        help_text="AI-generated descriptive labels (e.g., ['mountain views', 'outdoor terrace', 'romantic lighting'])"
    )
    ai_description = models.TextField(
        blank=True,
        help_text="AI-generated detailed description of what's in the image"
    )
    
    # Confidence Scores (0.0 to 1.0)
    category_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI confidence score for category classification"
    )
    description_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI confidence score for description accuracy"
    )
    
    # Legacy Image Types (keeping for backwards compatibility)
    image_type = models.CharField(
        max_length=50,
        choices=[
            ('exterior', 'Exterior'),
            ('interior', 'Interior'),
            ('food', 'Food'),
            ('chef', 'Chef'),
            ('staff', 'Staff'),
            ('event', 'Event'),
            ('scenery', 'Scenery'),
            ('dining_room', 'Dining Room'),
            ('ambiance', 'Ambiance'),
        ],
        default='interior'
    )
    
    # Processing Status
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(blank=True)
    
    # Image Quality and Metadata
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True, help_text="File size in bytes")
    
    # Order and display
    order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_menu_highlight = models.BooleanField(default=False, help_text="Is this a standout menu item image?")
    is_ambiance_highlight = models.BooleanField(default=False, help_text="Is this a standout ambiance/scenery image?")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['restaurant', 'order', '-created_at']
        indexes = [
            models.Index(fields=['restaurant', 'ai_category']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['is_featured', 'is_menu_highlight', 'is_ambiance_highlight']),
        ]
    
    def __str__(self):
        if self.ai_category and self.ai_category != 'uncategorized':
            return f"{self.restaurant.name} - {self.get_ai_category_display()}"
        return f"{self.restaurant.name} - {self.get_image_type_display()}"
    
    @property
    def is_scenery_ambiance(self):
        """Check if this image is categorized as scenery/ambiance."""
        return self.ai_category == 'scenery_ambiance'
    
    @property
    def is_menu_item(self):
        """Check if this image is categorized as a menu item."""
        return self.ai_category == 'menu_item'
    
    @property
    def primary_labels(self):
        """Get the first 3 AI labels as primary descriptors."""
        return self.ai_labels[:3] if self.ai_labels else []
    
    @property
    def is_high_confidence(self):
        """Check if the AI categorization has high confidence (>0.8)."""
        return self.category_confidence > 0.8
    
    def get_display_name(self):
        """Get a human-readable display name for the image."""
        if self.ai_labels:
            return ", ".join(self.primary_labels).title()
        elif self.caption:
            return self.caption
        else:
            return self.get_ai_category_display() or self.get_image_type_display()


class RestaurantReview(models.Model):
    """Restaurant review model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Review Content
    title = models.CharField(max_length=200)
    content = models.TextField()
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review Details
    visit_date = models.DateField(null=True, blank=True)
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['restaurant', 'user']
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.user.username} ({self.rating}/5)"


class ScrapingJob(models.Model):
    """Model to track scraping jobs."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Job Information
    job_name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    
    # Progress Tracking
    total_urls = models.IntegerField(default=0)
    processed_urls = models.IntegerField(default=0)
    successful_urls = models.IntegerField(default=0)
    failed_urls = models.IntegerField(default=0)
    
    # Results
    results = models.JSONField(default=dict, blank=True)
    error_log = models.TextField(blank=True)
    
    # Metadata
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.job_name} - {self.status}"
    
    @property
    def progress_percentage(self):
        if self.total_urls == 0:
            return 0
        return (self.processed_urls / self.total_urls) * 100
    
    @property
    def success_rate(self):
        if self.processed_urls == 0:
            return 0
        return (self.successful_urls / self.processed_urls) * 100


class ImageScrapingJob(models.Model):
    """Model to track image scraping jobs."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Job Information
    job_name = models.CharField(max_length=200)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, null=True, blank=True)
    source_urls = models.JSONField(default=list, help_text="List of URLs to scrape images from")
    
    # Job Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    
    # Progress Tracking
    total_images_found = models.IntegerField(default=0)
    images_processed = models.IntegerField(default=0)
    images_downloaded = models.IntegerField(default=0)
    images_categorized = models.IntegerField(default=0)
    images_failed = models.IntegerField(default=0)
    
    # Configuration
    max_images_per_url = models.IntegerField(default=20, help_text="Maximum images to scrape per URL")
    min_image_size = models.IntegerField(default=200, help_text="Minimum image size in pixels")
    enable_ai_categorization = models.BooleanField(default=True)
    
    # Results and Errors
    results = models.JSONField(default=dict, blank=True)
    error_log = models.TextField(blank=True)
    
    # Metadata
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='image_scraping_jobs'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.restaurant:
            return f"Image scraping: {self.restaurant.name} - {self.status}"
        return f"{self.job_name} - {self.status}"
    
    @property
    def progress_percentage(self):
        if self.total_images_found == 0:
            return 0
        return (self.images_processed / self.total_images_found) * 100
    
    @property
    def success_rate(self):
        if self.images_processed == 0:
            return 0
        return (self.images_downloaded / self.images_processed) * 100
    
    @property
    def categorization_rate(self):
        if self.images_downloaded == 0:
            return 0
        return (self.images_categorized / self.images_downloaded) * 100


class ScrapingBacklogTask(models.Model):
    """PostgreSQL-based scraping backlog task model for async processing."""
    
    TASK_TYPE_CHOICES = [
        ('text', 'Text Scraping'),
        ('images', 'Image Scraping'),
        ('comprehensive', 'Comprehensive Scraping'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    url = models.URLField()
    restaurant_name = models.CharField(max_length=255)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, db_index=True)
    
    # Priority and retry logic
    priority = models.PositiveIntegerField(default=1, db_index=True)
    max_retries = models.PositiveIntegerField(default=3)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_messages = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_attempt = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Optional restaurant association
    restaurant = models.ForeignKey(
        Restaurant, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='backlog_tasks'
    )
    
    class Meta:
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority', 'created_at']),
            models.Index(fields=['task_type', 'status']),
            models.Index(fields=['retry_count', 'max_retries', 'status']),
        ]
    
    def __str__(self):
        return f"{self.task_type} - {self.restaurant_name} ({self.status})"
    
    @property
    def can_retry(self):
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status != 'completed'
    
    def mark_failed(self, error_message: str):
        """Mark task as failed and increment retry count."""
        from django.utils import timezone
        
        self.retry_count += 1
        self.error_messages.append(f"{timezone.now().isoformat()}: {error_message}")
        self.last_attempt = timezone.now()
        
        if self.retry_count >= self.max_retries:
            self.status = 'failed'
        else:
            self.status = 'pending'  # Allow retry
        
        self.save()
    
    def mark_completed(self):
        """Mark task as completed."""
        from django.utils import timezone
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


