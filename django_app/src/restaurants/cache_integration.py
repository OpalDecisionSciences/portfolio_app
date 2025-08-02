"""
Django Cache Integration for Unified Search System.
Provides Django-specific caching utilities that integrate with UnifiedCacheManager.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

# Add shared modules to path
shared_path = Path(__file__).parent.parent.parent.parent / 'shared' / 'src'
sys.path.insert(0, str(shared_path))

try:
    from cache.unified_cache_manager import get_cache_manager, UnifiedCacheManager
except ImportError:
    # Fallback for development
    class MockCacheManager:
        def get_search_results(self, query: str, filters: dict) -> Optional[dict]:
            return None
        
        def set_search_results(self, query: str, filters: dict, results: dict):
            pass
        
        def get_suggestions(self, query: str, suggestion_type: str) -> Optional[dict]:
            return None
        
        def set_suggestions(self, query: str, suggestions: dict, suggestion_type: str):
            pass
        
        def invalidate_search_cache(self):
            pass
    
    def get_cache_manager():
        return MockCacheManager()

logger = logging.getLogger(__name__)


class DjangoCacheIntegration:
    """
    Django-specific cache integration that extends UnifiedCacheManager 
    with Django model awareness and ORM optimizations.
    """
    
    def __init__(self):
        """Initialize Django cache integration."""
        self.cache_manager = get_cache_manager()
        self.restaurant_cache = {}  # Local cache for restaurant data
    
    def get_cached_search_results(self, query: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached search results with Django-specific enhancements.
        
        Args:
            query: Search query string
            filters: Search filters dictionary
            
        Returns:
            Cached search results with Django data or None if not found
        """
        try:
            # Normalize filters for consistent caching
            normalized_filters = self._normalize_filters(filters)
            
            # Try cache
            cached_results = self.cache_manager.get_search_results(query, normalized_filters)
            if cached_results:
                logger.info(f"🎯 Django cache HIT for search: '{query[:50]}...'")
                return cached_results
            
            return None
            
        except Exception as e:
            logger.warning(f"Django cache retrieval error: {e}")
            return None
    
    def cache_search_results(self, query: str, filters: Dict[str, Any], results: Dict[str, Any]):
        """
        Cache search results with Django-specific metadata.
        
        Args:
            query: Search query string
            filters: Search filters dictionary
            results: Search results to cache
        """
        try:
            # Normalize filters
            normalized_filters = self._normalize_filters(filters)
            
            # Add Django-specific cache metadata
            cached_results = {
                **results,
                'django_cached_at': datetime.now().isoformat(),
                'django_enhanced': True,
                'restaurant_cache_size': len(self.restaurant_cache)
            }
            
            # Cache the results
            self.cache_manager.set_search_results(query, normalized_filters, cached_results)
            logger.info(f"💾 Django cached search results: '{query[:50]}...' ({len(results.get('results', []))} results)")
            
        except Exception as e:
            logger.warning(f"Django cache storage error: {e}")
    
    def get_cached_restaurant_data(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached restaurant data from local cache or Redis.
        
        Args:
            restaurant_id: Restaurant UUID
            
        Returns:
            Cached restaurant data or None
        """
        # Check local cache first (fastest)
        if restaurant_id in self.restaurant_cache:
            return self.restaurant_cache[restaurant_id]
        
        # Could extend to check Redis here for cross-request caching
        return None
    
    def cache_restaurant_data(self, restaurant_id: str, restaurant_data: Dict[str, Any]):
        """
        Cache restaurant data in local cache.
        
        Args:
            restaurant_id: Restaurant UUID
            restaurant_data: Restaurant data dictionary
        """
        self.restaurant_cache[restaurant_id] = restaurant_data
    
    def get_cached_suggestions(self, query: str) -> Optional[Dict[str, List[str]]]:
        """
        Get cached suggestions with Django model data.
        
        Args:
            query: Partial query string
            
        Returns:
            Cached suggestions or None
        """
        try:
            cached_suggestions = self.cache_manager.get_suggestions(query, 'django_enhanced')
            if cached_suggestions:
                logger.debug(f"🎯 Django cache HIT for suggestions: '{query[:30]}...'")
                return cached_suggestions
            
            return None
            
        except Exception as e:
            logger.warning(f"Django suggestions cache error: {e}")
            return None
    
    def cache_suggestions(self, query: str, suggestions: Dict[str, List[str]]):
        """
        Cache suggestions with Django enhancement metadata.
        
        Args:
            query: Partial query string
            suggestions: Suggestions dictionary
        """
        try:
            # Add Django metadata
            enhanced_suggestions = {
                **suggestions,
                'django_enhanced': True,
                'generated_at': datetime.now().isoformat()
            }
            
            self.cache_manager.set_suggestions(query, enhanced_suggestions, 'django_enhanced')
            logger.debug(f"💾 Django cached suggestions: '{query[:30]}...'")
            
        except Exception as e:
            logger.warning(f"Django suggestions cache storage error: {e}")
    
    def invalidate_restaurant_cache(self, restaurant_id: Optional[str] = None):
        """
        Invalidate restaurant-related cache entries.
        
        Args:
            restaurant_id: Specific restaurant ID to invalidate, or None for all
        """
        try:
            if restaurant_id:
                # Remove from local cache
                self.restaurant_cache.pop(restaurant_id, None)
                logger.info(f"🗑️ Invalidated local cache for restaurant: {restaurant_id}")
            else:
                # Clear all restaurant cache
                self.restaurant_cache.clear()
                logger.info("🗑️ Cleared all restaurant local cache")
            
            # Invalidate Redis cache
            self.cache_manager.invalidate_search_cache()
            
        except Exception as e:
            logger.warning(f"Django cache invalidation error: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get Django-specific cache statistics.
        
        Returns:
            Cache statistics dictionary
        """
        try:
            base_stats = self.cache_manager.get_cache_stats()
            
            django_stats = {
                'django_integration': {
                    'local_restaurant_cache_size': len(self.restaurant_cache),
                    'local_restaurant_cache_keys': list(self.restaurant_cache.keys())[:10],  # First 10 for debugging
                },
                'redis_cache': base_stats
            }
            
            return django_stats
            
        except Exception as e:
            logger.error(f"Django cache stats error: {e}")
            return {
                'error': str(e),
                'django_integration': {
                    'local_restaurant_cache_size': len(self.restaurant_cache)
                }
            }
    
    def _normalize_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize filters for consistent cache key generation.
        
        Args:
            filters: Raw filters dictionary
            
        Returns:
            Normalized filters dictionary
        """
        normalized = {}
        
        # Sort and clean filters for consistent hashing
        for key, value in filters.items():
            if value is not None:
                if isinstance(value, list):
                    # Sort lists for consistent ordering
                    normalized[key] = sorted(value) if value else None
                elif isinstance(value, str):
                    # Strip and lowercase strings
                    normalized[key] = value.strip().lower() if value.strip() else None
                else:
                    normalized[key] = value
        
        return normalized


# Global instance for Django integration
_django_cache = None

def get_django_cache() -> DjangoCacheIntegration:
    """Get or create the Django cache integration instance."""
    global _django_cache
    if _django_cache is None:
        _django_cache = DjangoCacheIntegration()
    return _django_cache