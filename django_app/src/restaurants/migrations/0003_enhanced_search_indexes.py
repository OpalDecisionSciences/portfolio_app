# Generated migration for enhanced search performance
# Adds composite indexes, full-text search, and trigram indexes

from django.db import migrations, models
from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.indexes import GinIndex, GistIndex
from django.contrib.postgres.fields import ArrayField


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0002_restaurant_timezone_info'),
    ]

    operations = [
        # Enable PostgreSQL trigram extension for fuzzy text search
        TrigramExtension(),
        
        # Full-text search indexes for Restaurant
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS restaurants_restaurant_search_vector "
            "ON restaurants_restaurant USING gin("
            "to_tsvector('english', name || ' ' || COALESCE(description, '') || ' ' || "
            "COALESCE(cuisine_type, '') || ' ' || city || ' ' || country));",
            
            "DROP INDEX IF EXISTS restaurants_restaurant_search_vector;"
        ),
        
        # Trigram indexes for fuzzy search
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS restaurants_restaurant_name_trigram "
            "ON restaurants_restaurant USING gin(name gin_trgm_ops);",
            
            "DROP INDEX IF EXISTS restaurants_restaurant_name_trigram;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS restaurants_restaurant_city_trigram "
            "ON restaurants_restaurant USING gin(city gin_trgm_ops);",
            
            "DROP INDEX IF EXISTS restaurants_restaurant_city_trigram;"
        ),
        
        # Composite indexes for common query patterns
        migrations.AddIndex(
            model_name='restaurant',
            index=models.Index(
                fields=['status', 'michelin_stars', '-rating'],
                name='restaurants_restaurant_search_rank_idx'
            ),
        ),
        
        migrations.AddIndex(
            model_name='restaurant',
            index=models.Index(
                fields=['country', 'city', 'cuisine_type', 'status'],
                name='restaurants_restaurant_location_cuisine_idx'
            ),
        ),
        
        migrations.AddIndex(
            model_name='restaurant',
            index=models.Index(
                fields=['price_range', 'rating', 'status'],
                name='restaurants_restaurant_price_rating_idx'
            ),
        ),
        
        # Geographic search optimization
        migrations.AddIndex(
            model_name='restaurant',
            index=models.Index(
                fields=['latitude', 'longitude'],
                name='restaurants_restaurant_geo_idx'
            ),
        ),
        
        # Review search optimization
        migrations.AddIndex(
            model_name='restaurantreview',
            index=models.Index(
                fields=['restaurant', 'status', '-rating'],
                name='restaurants_review_restaurant_rating_idx'
            ),
        ),
        
        # Full-text search for reviews
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS restaurants_review_content_search "
            "ON restaurants_restaurantreview USING gin("
            "to_tsvector('english', title || ' ' || COALESCE(content, '')));",
            
            "DROP INDEX IF EXISTS restaurants_review_content_search;"
        ),
        
        # Menu item search optimization
        migrations.AddIndex(
            model_name='menuitem',
            index=models.Index(
                fields=['menu_section', 'status', 'price'],
                name='restaurants_menuitem_section_price_idx'
            ),
        ),
        
        # Full-text search for menu items
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS restaurants_menuitem_search "
            "ON restaurants_menuitem USING gin("
            "to_tsvector('english', name || ' ' || COALESCE(description, '')));",
            
            "DROP INDEX IF EXISTS restaurants_menuitem_search;"
        ),
        
        # Image search optimization
        migrations.AddIndex(
            model_name='restaurantimage',
            index=models.Index(
                fields=['restaurant', 'ai_category', 'processing_status'],
                name='restaurants_image_category_idx'
            ),
        ),
        
        # Cart optimization
        migrations.AddIndex(
            model_name='cart',
            index=models.Index(
                fields=['user', 'restaurant', 'cart_status', '-updated_at'],
                name='restaurants_cart_user_restaurant_idx'
            ),
        ),
        
        # Scraping task optimization
        migrations.AddIndex(
            model_name='scrapingtask',
            index=models.Index(
                fields=['status', 'task_type', 'priority', 'created_at'],
                name='restaurants_scrapingtask_queue_idx'
            ),
        ),
    ]