"""
Admin configuration for restaurant models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Restaurant, Chef, MenuSection, MenuItem, 
    RestaurantImage, RestaurantReview, ScrapingJob
)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'city', 'country', 'michelin_stars', 'cuisine_type', 
        'price_range', 'rating', 'is_active', 'is_featured'
    ]
    list_filter = [
        'michelin_stars', 'cuisine_type', 'price_range', 'country', 
        'is_active', 'is_featured', 'created_at'
    ]
    search_fields = ['name', 'city', 'country', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'stars_display']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'slug', 'description', 'is_active', 'is_featured']
        }),
        ('Location', {
            'fields': ['country', 'city', 'address', 'latitude', 'longitude']
        }),
        ('Contact', {
            'fields': ['phone', 'email', 'website']
        }),
        ('Michelin Information', {
            'fields': ['michelin_stars', 'michelin_guide_year', 'stars_display']
        }),
        ('Rating & Reviews', {
            'fields': ['rating', 'review_count']
        }),
        ('Cuisine & Style', {
            'fields': ['cuisine_type', 'price_range', 'atmosphere']
        }),
        ('Operational', {
            'fields': ['seating_capacity', 'has_private_dining', 'opening_hours']
        }),
        ('Scraped Data', {
            'fields': ['original_url', 'scraped_at', 'scraped_content'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'created_by'],
            'classes': ['collapse']
        }),
    ]
    
    def stars_display(self, obj):
        return obj.stars_display
    stars_display.short_description = 'Stars'


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1
    fields = ['name', 'description', 'price', 'is_vegetarian', 'is_vegan', 'is_available']


@admin.register(MenuSection)
class MenuSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'restaurant', 'order']
    list_filter = ['restaurant']
    search_fields = ['name', 'restaurant__name']
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'price', 'is_vegetarian', 'is_vegan', 'is_available']
    list_filter = ['section__restaurant', 'is_vegetarian', 'is_vegan', 'is_available']
    search_fields = ['name', 'description', 'section__name']


@admin.register(Chef)
class ChefAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'position', 'restaurant', 'years_experience']
    list_filter = ['position', 'restaurant']
    search_fields = ['first_name', 'last_name', 'restaurant__name']
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Name'


@admin.register(RestaurantImage)
class RestaurantImageAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'image_type', 'caption', 'is_featured', 'order']
    list_filter = ['image_type', 'is_featured', 'restaurant']
    search_fields = ['restaurant__name', 'caption']
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.image.url
            )
        return "No image"
    image_thumbnail.short_description = 'Thumbnail'


@admin.register(RestaurantReview)
class RestaurantReviewAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'user', 'rating', 'title', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_featured', 'created_at']
    search_fields = ['restaurant__name', 'user__username', 'title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews approved.')
    approve_reviews.short_description = 'Approve selected reviews'
    
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews disapproved.')
    disapprove_reviews.short_description = 'Disapprove selected reviews'


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    list_display = [
        'job_name', 'status', 'progress_percentage', 'success_rate', 
        'total_urls', 'processed_urls', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['job_name']
    readonly_fields = [
        'id', 'progress_percentage', 'success_rate', 'created_at', 
        'started_at', 'completed_at'
    ]
    
    fieldsets = [
        ('Job Information', {
            'fields': ['job_name', 'status', 'created_by']
        }),
        ('Progress', {
            'fields': [
                'total_urls', 'processed_urls', 'successful_urls', 'failed_urls',
                'progress_percentage', 'success_rate'
            ]
        }),
        ('Results', {
            'fields': ['results', 'error_log'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'started_at', 'completed_at'],
            'classes': ['collapse']
        }),
    ]
    
    def progress_percentage(self, obj):
        return f"{obj.progress_percentage:.1f}%"
    progress_percentage.short_description = 'Progress'
    
    def success_rate(self, obj):
        return f"{obj.success_rate:.1f}%"
    success_rate.short_description = 'Success Rate'