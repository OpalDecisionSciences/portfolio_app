"""
Signals for the restaurants app with intelligent cache invalidation.
Handles rating updates and cache invalidation for optimal performance.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Avg
from django.core.cache import cache
from .models import Restaurant, RestaurantReview, RestaurantImage, MenuItem

logger = logging.getLogger(__name__)


def get_cache_manager():
    """Get cache manager with fallback for graceful degradation."""
    try:
        from .cache_integration import get_django_cache
        return get_django_cache()
    except ImportError:
        logger.warning("Cache integration not available, skipping cache invalidation")
        return None


def invalidate_restaurant_view_cache():
    """Invalidate view-level cache for restaurant lists."""
    # Invalidate restaurant list caches
    cache_keys = [
        'featured_restaurants_data',
        'michelin_starred_restaurants_data',
    ]
    
    for cache_key in cache_keys:
        cache.delete(cache_key)
        logger.info(f"🗑️ Invalidated view cache: {cache_key}")


@receiver(post_save, sender=RestaurantReview)
def update_restaurant_rating(sender, instance, created, **kwargs):
    """
    Update restaurant rating when a review is added or updated.
    Also invalidates cache for performance.
    """
    if instance.is_approved:
        restaurant = instance.restaurant
        
        # Calculate new average rating
        avg_rating = restaurant.reviews.filter(is_approved=True).aggregate(
            Avg('rating')
        )['rating__avg']
        
        # Update restaurant rating and review count
        restaurant.rating = avg_rating
        restaurant.review_count = restaurant.reviews.filter(is_approved=True).count()
        restaurant.save(update_fields=['rating', 'review_count'])
        
        # Invalidate cache
        _invalidate_restaurant_cache(restaurant, 'review_update')


@receiver(post_delete, sender=RestaurantReview)
def update_restaurant_rating_on_delete(sender, instance, **kwargs):
    """
    Update restaurant rating when a review is deleted.
    Also invalidates cache for performance.
    """
    if instance.is_approved:
        restaurant = instance.restaurant
        
        # Calculate new average rating
        avg_rating = restaurant.reviews.filter(is_approved=True).aggregate(
            Avg('rating')
        )['rating__avg']
        
        # Update restaurant rating and review count
        restaurant.rating = avg_rating
        restaurant.review_count = restaurant.reviews.filter(is_approved=True).count()
        restaurant.save(update_fields=['rating', 'review_count'])
        
        # Invalidate cache
        _invalidate_restaurant_cache(restaurant, 'review_delete')


def _invalidate_restaurant_cache(restaurant, reason):
    """
    Helper function to invalidate restaurant-related cache.
    
    Args:
        restaurant: Restaurant instance
        reason: String describing why cache is being invalidated
    """
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            # Invalidate restaurant-specific cache
            cache_manager.invalidate_restaurant_cache(str(restaurant.id))
            
            # Invalidate search cache (restaurants might appear in search results)
            cache_manager.cache_manager.invalidate_search_cache()
            
            logger.info(f"🗑️ Cache invalidated for restaurant: {restaurant.name} ({restaurant.id}) - {reason}")
        
        # Also clear Django's built-in cache for related views
        cache_keys_to_clear = [
            f'restaurant_detail_{restaurant.slug}',
            f'restaurant_images_{restaurant.id}',
            'restaurant_list',
            'featured_restaurants_data',  # Updated cache key
            'michelin_starred_restaurants_data'  # Updated cache key
        ]
        
        for key in cache_keys_to_clear:
            cache.delete(key)
            
        # Invalidate restaurant view cache specifically
        invalidate_restaurant_view_cache()
            
    except Exception as e:
        logger.error(f"Error invalidating restaurant cache: {e}")


# New signal handlers for comprehensive cache invalidation

@receiver([post_save, post_delete], sender=Restaurant)
def invalidate_restaurant_cache(sender, instance, **kwargs):
    """
    Invalidate cache when restaurant data changes.
    """
    _invalidate_restaurant_cache(instance, 'restaurant_update')


@receiver([post_save, post_delete], sender=RestaurantImage)
def invalidate_image_cache(sender, instance, **kwargs):
    """
    Invalidate cache when restaurant image data changes.
    """
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            # Invalidate restaurant cache (images are part of restaurant data)
            cache_manager.invalidate_restaurant_cache(str(instance.restaurant.id))
            
            # Invalidate image-specific search cache
            cache_manager.cache_manager.invalidate_cache('unified_cache:search:*images*')
            
            logger.info(f"🗑️ Cache invalidated for image: {instance.id} (restaurant: {instance.restaurant.name})")
        
        # Clear Django cache for image-related views
        cache_keys_to_clear = [
            f'restaurant_images_{instance.restaurant.id}',
            f'image_gallery_{instance.ai_category}',
            'semantic_gallery_all',
            'restaurant_gallery'
        ]
        
        for key in cache_keys_to_clear:
            cache.delete(key)
            
    except Exception as e:
        logger.error(f"Error invalidating image cache: {e}")


@receiver([post_save, post_delete], sender=MenuItem)
def invalidate_menu_cache(sender, instance, **kwargs):
    """
    Invalidate cache when menu item data changes.
    """
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            # Invalidate restaurant cache (menu items are part of restaurant data)
            cache_manager.invalidate_restaurant_cache(str(instance.restaurant.id))
            
            # Invalidate menu-specific search cache
            cache_manager.cache_manager.invalidate_cache('unified_cache:search:*menu*')
            
            logger.info(f"🗑️ Cache invalidated for menu item: {instance.name} (restaurant: {instance.restaurant.name})")
        
        # Clear Django cache for menu-related views
        cache_keys_to_clear = [
            f'restaurant_menu_{instance.restaurant.id}',
            f'menu_item_{instance.id}'
        ]
        
        for key in cache_keys_to_clear:
            cache.delete(key)
            
    except Exception as e:
        logger.error(f"Error invalidating menu cache: {e}")


# Bulk operations and monitoring functions

def invalidate_all_search_cache():
    """
    Invalidate all search-related cache entries.
    Use this for bulk operations or maintenance.
    """
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            cache_manager.cache_manager.invalidate_search_cache()
            cache_manager.cache_manager.invalidate_embeddings_cache()
            
        # Clear Django cache
        cache.clear()
        
        logger.info("🗑️ All search cache invalidated")
        
    except Exception as e:
        logger.error(f"Error invalidating all cache: {e}")


def get_cache_invalidation_summary():
    """
    Get summary of cache invalidation activity.
    Useful for monitoring and debugging.
    """
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            stats = cache_manager.get_cache_stats()
            return {
                'cache_errors': stats.get('performance', {}).get('cache_errors', 0),
                'redis_connected': True,
                'last_check': 'now'
            }
        else:
            return {
                'cache_errors': 0,
                'redis_connected': False,
                'last_check': 'now'
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'cache_errors': 'unknown',
            'redis_connected': False,
            'last_check': 'error'
        }