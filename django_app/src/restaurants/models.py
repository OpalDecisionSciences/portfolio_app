"""
Restaurant models for the portfolio application.
"""
from django.db import models
from django.contrib.auth.models import User
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
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
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
    
    def get_absolute_url(self):
        return reverse('restaurant_detail', kwargs={'slug': self.slug})
    
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
    """Restaurant image model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='restaurants/')
    caption = models.CharField(max_length=200, blank=True)
    
    # Image Types
    image_type = models.CharField(
        max_length=50,
        choices=[
            ('exterior', 'Exterior'),
            ('interior', 'Interior'),
            ('food', 'Food'),
            ('chef', 'Chef'),
            ('staff', 'Staff'),
            ('event', 'Event'),
        ],
        default='interior'
    )
    
    # Order and display
    order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['restaurant', 'order', '-created_at']
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.get_image_type_display()}"


class RestaurantReview(models.Model):
    """Restaurant review model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
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