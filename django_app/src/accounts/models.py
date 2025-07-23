from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator
from django.utils import timezone
import uuid


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Includes profile information and dining preferences.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="Email address for account notifications and password reset"
    )
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    
    # Profile Information
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True, help_text="City, Country")
    
    # Dining Preferences
    preferred_cuisines = models.JSONField(
        default=list,
        blank=True,
        help_text="User's preferred cuisine types"
    )
    dietary_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text="Dietary restrictions and preferences"
    )
    price_range_preference = models.CharField(
        max_length=20,
        choices=[
            ('budget', 'Budget-friendly ($)'),
            ('moderate', 'Moderate ($$)'),
            ('upscale', 'Upscale ($$$)'),
            ('luxury', 'Luxury ($$$$)'),
            ('any', 'Any price range')
        ],
        default='any',
        blank=True
    )
    
    # Account Settings
    email_verified = models.BooleanField(default=False)
    newsletter_subscription = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Metadata
    profile_completed = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.username
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.username
    
    @property
    def has_complete_profile(self):
        """Check if user has completed their profile."""
        return bool(
            self.first_name and 
            self.last_name and 
            self.location and
            self.preferred_cuisines
        )


class UserFavoriteRestaurant(models.Model):
    """
    User's favorite restaurants with notes and categories.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_restaurants')
    restaurant = models.ForeignKey(
        'restaurants.Restaurant', 
        on_delete=models.CASCADE,
        related_name='user_favorites'
    )
    
    # Favorite details
    category = models.CharField(
        max_length=50,
        choices=[
            ('to_visit', 'Want to Visit'),
            ('visited', 'Visited & Loved'),
            ('special_occasion', 'Special Occasions'),
            ('business_dining', 'Business Dining'),
            ('romantic', 'Romantic Dinners'),
            ('family', 'Family-Friendly'),
            ('quick_bite', 'Quick Bites'),
        ],
        default='to_visit'
    )
    
    personal_rating = models.IntegerField(
        null=True, 
        blank=True,
        choices=[(i, f"{i} Stars") for i in range(1, 6)],
        help_text="Personal rating (1-5 stars)"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Personal notes about this restaurant"
    )
    
    visit_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date of visit (if visited)"
    )
    
    recommended_dishes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended dishes"
    )
    
    # Metadata
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'restaurant']
        ordering = ['-added_at']
        verbose_name = 'Favorite Restaurant'
        verbose_name_plural = 'Favorite Restaurants'
    
    def __str__(self):
        return f"{self.user.get_short_name()}'s favorite: {self.restaurant.name}"


class UserChatHistory(models.Model):
    """
    Store user's chat conversation history for better recommendations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_history')
    
    # Chat session info
    conversation_id = models.CharField(max_length=100, db_index=True)
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank=True)
    
    # Conversation summary
    topics_discussed = models.JSONField(
        default=list,
        help_text="Main topics discussed in this conversation"
    )
    restaurants_mentioned = models.ManyToManyField(
        'restaurants.Restaurant',
        blank=True,
        help_text="Restaurants discussed in this conversation"
    )
    
    # Preferences learned
    preferences_learned = models.JSONField(
        default=dict,
        help_text="User preferences discovered during conversation"
    )
    
    message_count = models.IntegerField(default=0)
    satisfaction_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, f"{i} Stars") for i in range(1, 6)],
        help_text="User's satisfaction with the conversation"
    )
    
    class Meta:
        ordering = ['-session_start']
        verbose_name = 'Chat History'
        verbose_name_plural = 'Chat Histories'
    
    def __str__(self):
        return f"{self.user.get_short_name()}'s chat on {self.session_start.date()}"


class PasswordResetToken(models.Model):
    """
    Custom password reset tokens with enhanced security.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def is_valid(self):
        """Check if token is still valid."""
        return not self.used and timezone.now() < self.expires_at
    
    def __str__(self):
        return f"Password reset for {self.user.email}"