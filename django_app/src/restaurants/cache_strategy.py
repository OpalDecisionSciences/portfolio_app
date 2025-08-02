"""
Consolidated Cache Strategy for Portfolio Restaurant App.

This module implements a unified approach to caching across all application layers:
- Django default cache for session data, views, templates
- Unified search cache for RAG/search operations  
- Local memory cache for frequently accessed restaurant data
- Cache invalidation strategy across all layers

Cache Architecture:
- Redis DB 0: Django default cache (sessions, view fragments, etc.)
- Redis DB 1: Weather API cache 
- Redis DB 2: Primary unified search cache (15-30min TTL)
- Redis DB 3: Secondary unified search cache (longer TTL, fallback)
- Local Memory: Restaurant object cache (request-scoped)

Performance Targets:
- Search cache hit rate: >80%
- Restaurant data cache hit rate: >90% 
- Average response time: <200ms for cached queries
- Cache invalidation: <5s propagation time
"""
import os
import logging
from typing import Dict, Any, Optional, List
from django.core.cache import cache as django_cache
from django.conf import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConsolidatedCacheStrategy:
    """
    Unified cache management strategy that coordinates all cache layers.
    Provides intelligent cache selection, invalidation, and monitoring.
    """
    
    def __init__(self):
        """Initialize consolidated cache strategy."""
        # Import cache integrations
        try:
            from .cache_integration import get_django_cache
            self.django_cache_integration = get_django_cache()
        except ImportError:
            logger.warning("Django cache integration not available")
            self.django_cache_integration = None
            
        # Cache layer priorities and fallback strategy
        self.cache_layers = {
            'local_memory': {
                'priority': 1,
                'ttl': 300,  # 5 minutes
                'use_for': ['restaurant_data', 'frequent_queries']
            },
            'django_default': {
                'priority': 2, 
                'ttl': 3600,  # 1 hour
                'use_for': ['view_fragments', 'template_cache', 'user_sessions']
            },
            'unified_primary': {
                'priority': 3,
                'ttl': 900,  # 15 minutes  
                'use_for': ['search_results', 'embeddings', 'suggestions']
            },
            'unified_secondary': {
                'priority': 4,
                'ttl': 1800,  # 30 minutes
                'use_for': ['search_fallback', 'long_term_cache']
            }
        }
        
        # Performance monitoring
        self.cache_metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'layer_hits': {layer: 0 for layer in self.cache_layers.keys()},
            'invalidations': 0
        }
    
    def get_cached_data(self, cache_key: str, cache_type: str = 'auto') -> Optional[Any]:
        """
        Get cached data using intelligent cache layer selection.
        
        Args:
            cache_key: Unique cache key
            cache_type: Type hint for cache layer selection
            
        Returns:
            Cached data or None if not found
        """
        self.cache_metrics['total_requests'] += 1
        
        # Auto-select cache layer based on data type
        if cache_type == 'auto':
            cache_type = self._detect_cache_type(cache_key)
        
        # Try cache layers in priority order
        for layer_name, layer_config in sorted(
            self.cache_layers.items(), 
            key=lambda x: x[1]['priority']
        ):
            if cache_type in layer_config['use_for']:
                try:
                    data = self._get_from_layer(layer_name, cache_key)
                    if data is not None:
                        self.cache_metrics['cache_hits'] += 1
                        self.cache_metrics['layer_hits'][layer_name] += 1
                        logger.debug(f"Cache HIT in {layer_name}: {cache_key[:50]}...")
                        return data
                except Exception as e:
                    logger.warning(f"Cache layer {layer_name} error: {e}")
                    continue
        
        self.cache_metrics['cache_misses'] += 1
        logger.debug(f"Cache MISS: {cache_key[:50]}...")
        return None
    
    def set_cached_data(self, cache_key: str, data: Any, cache_type: str = 'auto', ttl: Optional[int] = None):
        """
        Set cached data using intelligent cache layer selection.
        
        Args:
            cache_key: Unique cache key
            data: Data to cache
            cache_type: Type hint for cache layer selection
            ttl: Custom TTL override
        """
        if cache_type == 'auto':
            cache_type = self._detect_cache_type(cache_key)
        
        # Store in appropriate cache layers
        for layer_name, layer_config in self.cache_layers.items():
            if cache_type in layer_config['use_for']:
                try:
                    layer_ttl = ttl or layer_config['ttl']
                    self._set_in_layer(layer_name, cache_key, data, layer_ttl)
                    logger.debug(f"Cached in {layer_name}: {cache_key[:50]}... (TTL: {layer_ttl}s)")
                except Exception as e:
                    logger.warning(f"Cache storage error in {layer_name}: {e}")
    
    def invalidate_cache(self, cache_key: Optional[str] = None, cache_pattern: Optional[str] = None, cache_type: Optional[str] = None):
        """
        Intelligent cache invalidation across all layers.
        
        Args:
            cache_key: Specific key to invalidate
            cache_pattern: Pattern to match for bulk invalidation
            cache_type: Type-based invalidation
        """
        self.cache_metrics['invalidations'] += 1
        
        if cache_key:
            # Invalidate specific key from all layers
            for layer_name in self.cache_layers.keys():
                try:
                    self._invalidate_from_layer(layer_name, cache_key)
                except Exception as e:
                    logger.warning(f"Invalidation error in {layer_name}: {e}")
            
            logger.info(f"🗑️ Invalidated cache key: {cache_key}")
        
        elif cache_pattern:
            # Pattern-based invalidation (mainly for Redis layers)
            try:
                if self.django_cache_integration:
                    self.django_cache_integration.cache_manager.invalidate_cache(cache_pattern)
                logger.info(f"🗑️ Invalidated cache pattern: {cache_pattern}")
            except Exception as e:
                logger.warning(f"Pattern invalidation error: {e}")
        
        elif cache_type:
            # Type-based invalidation
            type_patterns = {
                'search_results': 'unified_cache:search:*',
                'suggestions': 'unified_cache:suggestions:*',
                'restaurant_data': 'restaurant:*',
                'embeddings': 'unified_cache:embeddings:*'
            }
            
            pattern = type_patterns.get(cache_type)
            if pattern:
                self.invalidate_cache(cache_pattern=pattern)
    
    def _detect_cache_type(self, cache_key: str) -> str:
        """
        Detect appropriate cache type based on cache key pattern.
        
        Args:
            cache_key: Cache key to analyze
            
        Returns:
            Detected cache type
        """
        key_lower = cache_key.lower()
        
        if 'search' in key_lower or 'query' in key_lower:
            return 'search_results'
        elif 'suggest' in key_lower:
            return 'suggestions'  
        elif 'restaurant' in key_lower:
            return 'restaurant_data'
        elif 'embed' in key_lower:
            return 'embeddings'
        elif 'view' in key_lower or 'template' in key_lower:
            return 'view_fragments'
        else:
            return 'frequent_queries'
    
    def _get_from_layer(self, layer_name: str, cache_key: str) -> Optional[Any]:
        """Get data from specific cache layer."""
        if layer_name == 'local_memory':
            # Local memory cache (restaurant data)
            if self.django_cache_integration:
                return self.django_cache_integration.get_cached_restaurant_data(cache_key)
            return None
            
        elif layer_name == 'django_default':
            # Django default cache
            return django_cache.get(cache_key)
            
        elif layer_name in ['unified_primary', 'unified_secondary']:
            # Unified search cache
            if self.django_cache_integration:
                # For search results, parse the key to extract query and filters
                if 'search' in cache_key:
                    # This is simplified - in practice, you'd need to parse the key properly
                    return self.django_cache_integration.get_cached_search_results(cache_key, {})
                elif 'suggest' in cache_key:
                    return self.django_cache_integration.get_cached_suggestions(cache_key)
            return None
        
        return None
    
    def _set_in_layer(self, layer_name: str, cache_key: str, data: Any, ttl: int):
        """Set data in specific cache layer."""
        if layer_name == 'local_memory':
            # Local memory cache (restaurant data)
            if self.django_cache_integration:
                self.django_cache_integration.cache_restaurant_data(cache_key, data)
                
        elif layer_name == 'django_default':
            # Django default cache
            django_cache.set(cache_key, data, ttl)
            
        elif layer_name in ['unified_primary', 'unified_secondary']:
            # Unified search cache
            if self.django_cache_integration:
                if 'search' in cache_key:
                    self.django_cache_integration.cache_search_results(cache_key, {}, data)
                elif 'suggest' in cache_key:
                    self.django_cache_integration.cache_suggestions(cache_key, data)
    
    def _invalidate_from_layer(self, layer_name: str, cache_key: str):
        """Invalidate data from specific cache layer."""
        if layer_name == 'local_memory':
            if self.django_cache_integration:
                self.django_cache_integration.invalidate_restaurant_cache(cache_key)
                
        elif layer_name == 'django_default':
            django_cache.delete(cache_key)
            
        elif layer_name in ['unified_primary', 'unified_secondary']:
            if self.django_cache_integration:
                self.django_cache_integration.invalidate_restaurant_cache()
    
    def get_consolidated_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics across all layers.
        
        Returns:
            Consolidated cache statistics
        """
        stats = {
            'consolidated_metrics': self.cache_metrics.copy(),
            'django_default': {},
            'unified_cache': {},
            'recommendations': []
        }
        
        # Add hit rate calculation
        total_requests = self.cache_metrics['total_requests']
        if total_requests > 0:
            hit_rate = (self.cache_metrics['cache_hits'] / total_requests) * 100
            stats['consolidated_metrics']['hit_rate_percentage'] = round(hit_rate, 2)
        
        # Get Django cache stats
        try:
            # Django doesn't provide built-in stats, but we can get basic info
            stats['django_default'] = {
                'backend': settings.CACHES['default']['BACKEND'],
                'location': settings.CACHES['default']['LOCATION'],
                'key_prefix': settings.CACHES['default'].get('KEY_PREFIX', ''),
                'default_timeout': settings.CACHES['default'].get('TIMEOUT', 3600)
            }
        except Exception as e:
            stats['django_default'] = {'error': str(e)}
        
        # Get unified cache stats
        try:
            if self.django_cache_integration:
                stats['unified_cache'] = self.django_cache_integration.get_cache_stats()
        except Exception as e:
            stats['unified_cache'] = {'error': str(e)}
        
        # Add performance recommendations
        hit_rate = stats['consolidated_metrics'].get('hit_rate_percentage', 0)
        if hit_rate < 70:
            stats['recommendations'].append('Consider increasing cache TTL for frequently accessed data')
        if hit_rate < 50:
            stats['recommendations'].append('Cache strategy needs optimization - hit rate too low')
        
        if self.cache_metrics['cache_misses'] > self.cache_metrics['cache_hits'] * 2:
            stats['recommendations'].append('High cache miss ratio - review cache key strategies')
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check for all cache layers.
        
        Returns:
            Health check results
        """
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'layers': {}
        }
        
        # Test Django default cache
        try:
            test_key = f"health_test:{datetime.now().timestamp()}"
            django_cache.set(test_key, 'test', 10)
            result = django_cache.get(test_key)
            django_cache.delete(test_key)
            
            health['layers']['django_default'] = {
                'status': 'healthy' if result == 'test' else 'unhealthy'
            }
        except Exception as e:
            health['layers']['django_default'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health['status'] = 'degraded'
        
        # Test unified cache
        try:
            if self.django_cache_integration:
                unified_health = self.django_cache_integration.cache_manager.health_check()
                health['layers']['unified_cache'] = unified_health
                
                if unified_health.get('status') != 'healthy':
                    health['status'] = 'degraded'
        except Exception as e:
            health['layers']['unified_cache'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health['status'] = 'degraded'
        
        # Test local memory cache
        try:
            if self.django_cache_integration:
                test_restaurant_id = f"test_{datetime.now().timestamp()}"
                test_data = {'name': 'Test Restaurant'}
                
                self.django_cache_integration.cache_restaurant_data(test_restaurant_id, test_data)
                result = self.django_cache_integration.get_cached_restaurant_data(test_restaurant_id)
                
                health['layers']['local_memory'] = {
                    'status': 'healthy' if result == test_data else 'unhealthy'
                }
        except Exception as e:
            health['layers']['local_memory'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        return health


# Global consolidated cache instance
_consolidated_cache = None

def get_consolidated_cache() -> ConsolidatedCacheStrategy:
    """Get or create the consolidated cache strategy instance."""
    global _consolidated_cache
    if _consolidated_cache is None:
        _consolidated_cache = ConsolidatedCacheStrategy()
    return _consolidated_cache