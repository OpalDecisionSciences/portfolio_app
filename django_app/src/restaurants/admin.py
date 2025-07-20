"""
Admin configuration for restaurant models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Restaurant, Chef, MenuSection, MenuItem, 
    RestaurantImage, RestaurantReview, ScrapingJob, ImageScrapingJob
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
    list_display = [
        'restaurant', 'get_display_name', 'ai_category', 'category_confidence', 
        'processing_status', 'is_featured', 'is_menu_highlight', 'is_ambiance_highlight'
    ]
    list_filter = [
        'ai_category', 'processing_status', 'image_type', 'is_featured', 
        'is_menu_highlight', 'is_ambiance_highlight', 'restaurant'
    ]
    search_fields = ['restaurant__name', 'caption', 'ai_description', 'ai_labels']
    readonly_fields = [
        'id', 'image_thumbnail', 'source_url', 'category_confidence', 
        'description_confidence', 'width', 'height', 'file_size',
        'created_at', 'updated_at', 'processed_at'
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['restaurant', 'image', 'image_thumbnail', 'caption', 'alt_text']
        }),
        ('AI Categorization', {
            'fields': [
                'ai_category', 'category_confidence', 'ai_labels', 
                'ai_description', 'description_confidence'
            ]
        }),
        ('Processing', {
            'fields': ['processing_status', 'processing_error', 'processed_at']
        }),
        ('Display Options', {
            'fields': [
                'is_featured', 'is_menu_highlight', 'is_ambiance_highlight', 
                'order', 'image_type'
            ]
        }),
        ('Technical Details', {
            'fields': ['source_url', 'width', 'height', 'file_size'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    actions = ['reprocess_with_ai', 'mark_as_menu_highlight', 'mark_as_ambiance_highlight']
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 5px;" />',
                obj.image.url
            )
        elif obj.source_url:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 5px;" />',
                obj.source_url
            )
        return "No image"
    image_thumbnail.short_description = 'Preview'
    
    def get_display_name(self, obj):
        return obj.get_display_name()
    get_display_name.short_description = 'Display Name'
    
    def category_confidence(self, obj):
        if obj.category_confidence > 0:
            color = 'green' if obj.category_confidence > 0.8 else 'orange' if obj.category_confidence > 0.5 else 'red'
            return format_html(
                '<span style="color: {};">{:.1%}</span>',
                color, obj.category_confidence
            )
        return '-'
    category_confidence.short_description = 'AI Confidence'
    
    def reprocess_with_ai(self, request, queryset):
        from .tasks import process_image_ai_categorization
        
        count = 0
        for image in queryset:
            if image.processing_status != 'processing':
                process_image_ai_categorization.delay(image.id)
                count += 1
        
        self.message_user(request, f'{count} images queued for AI reprocessing.')
    reprocess_with_ai.short_description = 'Reprocess selected images with AI'
    
    def mark_as_menu_highlight(self, request, queryset):
        updated = queryset.update(is_menu_highlight=True, is_ambiance_highlight=False)
        self.message_user(request, f'{updated} images marked as menu highlights.')
    mark_as_menu_highlight.short_description = 'Mark as menu highlights'
    
    def mark_as_ambiance_highlight(self, request, queryset):
        updated = queryset.update(is_ambiance_highlight=True, is_menu_highlight=False)
        self.message_user(request, f'{updated} images marked as ambiance highlights.')
    mark_as_ambiance_highlight.short_description = 'Mark as ambiance highlights'


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


@admin.register(ImageScrapingJob)
class ImageScrapingJobAdmin(admin.ModelAdmin):
    list_display = [
        'job_name', 'restaurant', 'status', 'progress_percentage', 'success_rate', 
        'categorization_rate', 'images_processed', 'images_downloaded', 'created_at'
    ]
    list_filter = ['status', 'enable_ai_categorization', 'created_at']
    search_fields = ['job_name', 'restaurant__name']
    readonly_fields = [
        'id', 'progress_percentage', 'success_rate', 'categorization_rate',
        'created_at', 'started_at', 'completed_at'
    ]
    
    fieldsets = [
        ('Job Information', {
            'fields': ['job_name', 'restaurant', 'source_urls', 'status', 'created_by']
        }),
        ('Configuration', {
            'fields': ['max_images_per_url', 'min_image_size', 'enable_ai_categorization']
        }),
        ('Progress Tracking', {
            'fields': [
                'total_images_found', 'images_processed', 'images_downloaded', 
                'images_categorized', 'images_failed', 'progress_percentage', 
                'success_rate', 'categorization_rate'
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
    
    actions = ['restart_failed_jobs']
    
    def progress_percentage(self, obj):
        return f"{obj.progress_percentage:.1f}%"
    progress_percentage.short_description = 'Progress'
    
    def success_rate(self, obj):
        return f"{obj.success_rate:.1f}%"
    success_rate.short_description = 'Success Rate'
    
    def categorization_rate(self, obj):
        return f"{obj.categorization_rate:.1f}%"
    categorization_rate.short_description = 'AI Categorized'
    
    def restart_failed_jobs(self, request, queryset):
        from .tasks import scrape_restaurant_images_task
        
        restarted = 0
        for job in queryset.filter(status='failed'):
            # Reset job status
            job.status = 'pending'
            job.error_log = ''
            job.save()
            
            # Restart the task
            if job.restaurant:
                scrape_restaurant_images_task.delay(
                    job_id=str(job.id),
                    restaurant_id=str(job.restaurant.id),
                    max_images_per_url=job.max_images_per_url
                )
            elif job.source_urls:
                scrape_restaurant_images_task.delay(
                    job_id=str(job.id),
                    urls_list=job.source_urls,
                    max_images_per_url=job.max_images_per_url
                )
            restarted += 1
        
        self.message_user(request, f'{restarted} failed jobs restarted.')
    restart_failed_jobs.short_description = 'Restart selected failed jobs'