"""
Unified Cache Manager for high-performance caching across all search operations.
Implements intelligent cache invalidation and performance monitoring.
"""
import redis
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import asdict
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class UnifiedCacheManager:
    """
    High-performance cache manager for unified search system.
    Implements multi-tier caching with intelligent invalidation.
    """
    
    def __init__(self):
        """Initialize Redis connections with production-ready configuration."""
        # Primary cache (fast access, shorter TTL)
        self.primary_cache = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_CACHE_DB", 2)),  # Use DB 2 for unified cache
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Secondary cache (longer TTL, fallback)
        self.secondary_cache = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_CACHE_DB_SECONDARY", 3)),  # Use DB 3 for secondary cache
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Cache configuration
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", 1800))  # 30 minutes
        self.search_results_ttl = int(os.getenv("CACHE_SEARCH_TTL", 900))  # 15 minutes
        self.suggestions_ttl = int(os.getenv("CACHE_SUGGESTIONS_TTL", 3600))  # 1 hour
        self.embeddings_ttl = int(os.getenv("CACHE_EMBEDDINGS_TTL", 7200))  # 2 hours
        self.facets_ttl = int(os.getenv("CACHE_FACETS_TTL", 1800))  # 30 minutes
        
        # Performance metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_errors = 0
        
        # Test connections
        self._test_connections()
    
    def _test_connections(self):
        """Test Redis connections and log status."""
        try:
            self.primary_cache.ping()
            logger.info("✅ Primary Redis cache connection established")
        except Exception as e:
            logger.error(f"❌ Primary Redis cache connection failed: {e}")
        
        try:
            self.secondary_cache.ping()
            logger.info("✅ Secondary Redis cache connection established")
        except Exception as e:
            logger.error(f"❌ Secondary Redis cache connection failed: {e}")
    
    def _generate_cache_key(self, prefix: str, data: Union[str, Dict, Any]) -> str:
        """
        Generate consistent cache keys with collision avoidance.
        
        Args:
            prefix: Cache key prefix (e.g., 'search', 'suggestions', 'embeddings')
            data: Data to hash for unique key generation
            
        Returns:
            Unique cache key string
        """
        if isinstance(data, dict):
            # Sort dict keys for consistent hashing
            data_str = json.dumps(data, sort_keys=True)
        elif isinstance(data, str):
            data_str = data
        else:
            data_str = str(data)
        
        # Create hash for uniqueness and collision avoidance
        data_hash = hashlib.sha256(data_str.encode('utf-8')).hexdigest()[:16]
        
        return f"unified_cache:{prefix}:{data_hash}"
    
    def get_search_results(self, query: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached search results with intelligent cache strategy.
        
        Args:
            query: Search query string
            filters: Search filters dictionary
            
        Returns:
            Cached search results or None if not found
        """
        try:
            cache_data = {
                'query': query.lower().strip(),
                'filters': filters,
                'timestamp': datetime.now().strftime('%Y-%m-%d-%H')  # Hour-level cache buckets
            }
            
            cache_key = self._generate_cache_key('search', cache_data)
            
            # Try primary cache first
            result = self.primary_cache.get(cache_key)
            if result:
                self.cache_hits += 1
                logger.debug(f"🎯 Primary cache HIT for search: {query[:50]}...")
                return json.loads(result)
            
            # Try secondary cache as fallback
            result = self.secondary_cache.get(cache_key)
            if result:
                self.cache_hits += 1
                logger.debug(f"🎯 Secondary cache HIT for search: {query[:50]}...")
                
                # Promote to primary cache
                try:
                    self.primary_cache.setex(cache_key, self.search_results_ttl, result)
                except Exception:
                    pass  # Fail silently on promotion errors
                
                return json.loads(result)
            
            self.cache_misses += 1
            logger.debug(f"💨 Cache MISS for search: {query[:50]}...")
            return None
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache retrieval error for search: {e}")
            return None
    
    def set_search_results(self, query: str, filters: Dict[str, Any], results: Dict[str, Any]):
        """
        Cache search results with multi-tier storage.
        
        Args:
            query: Search query string
            filters: Search filters dictionary
            results: Search results to cache
        """
        try:
            cache_data = {
                'query': query.lower().strip(),
                'filters': filters,
                'timestamp': datetime.now().strftime('%Y-%m-%d-%H')
            }
            
            cache_key = self._generate_cache_key('search', cache_data)
            
            # Add cache metadata
            cached_results = {
                **results,
                'cached_at': datetime.now().isoformat(),
                'cache_key': cache_key,
                'query_normalized': query.lower().strip()
            }
            
            serialized_results = json.dumps(cached_results)
            
            # Store in both caches with different TTLs
            self.primary_cache.setex(cache_key, self.search_results_ttl, serialized_results)
            self.secondary_cache.setex(cache_key, self.search_results_ttl * 2, serialized_results)  # Longer TTL for secondary
            
            logger.debug(f"💾 Cached search results: {query[:50]}... ({len(results.get('results', []))} results)")
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache storage error for search: {e}")
    
    def get_suggestions(self, query: str, suggestion_type: str = 'all') -> Optional[Dict[str, List[str]]]:
        """
        Get cached search suggestions.
        
        Args:
            query: Query string for suggestions
            suggestion_type: Type of suggestions ('all', 'restaurants', 'cuisines', etc.)
            
        Returns:
            Cached suggestions or None if not found
        """
        try:
            cache_data = {
                'query': query.lower().strip(),
                'type': suggestion_type,
                'date': datetime.now().strftime('%Y-%m-%d')  # Daily cache buckets for suggestions
            }
            
            cache_key = self._generate_cache_key('suggestions', cache_data)
            
            result = self.primary_cache.get(cache_key)
            if result:
                self.cache_hits += 1
                logger.debug(f"🎯 Cache HIT for suggestions: {query[:30]}...")
                return json.loads(result)
            
            self.cache_misses += 1
            return None
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache retrieval error for suggestions: {e}")
            return None
    
    def set_suggestions(self, query: str, suggestions: Dict[str, List[str]], suggestion_type: str = 'all'):
        """
        Cache search suggestions.
        
        Args:
            query: Query string for suggestions
            suggestions: Suggestions dictionary to cache
            suggestion_type: Type of suggestions
        """
        try:
            cache_data = {
                'query': query.lower().strip(),
                'type': suggestion_type,
                'date': datetime.now().strftime('%Y-%m-%d')
            }
            
            cache_key = self._generate_cache_key('suggestions', cache_data)
            
            cached_suggestions = {
                **suggestions,
                'cached_at': datetime.now().isoformat(),
                'query_normalized': query.lower().strip()
            }
            
            self.primary_cache.setex(cache_key, self.suggestions_ttl, json.dumps(cached_suggestions))
            
            logger.debug(f"💾 Cached suggestions: {query[:30]}...")
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache storage error for suggestions: {e}")
    
    def get_embeddings(self, content_hash: str, content_type: str) -> Optional[bool]:
        """
        Check if embeddings exist for given content hash (deduplication).
        
        Args:
            content_hash: SHA256 hash of content
            content_type: Type of content ('restaurant', 'image', 'menu_item', 'document')
            
        Returns:
            True if embeddings exist, False otherwise, None if cache error
        """
        try:
            cache_key = self._generate_cache_key('embeddings', f"{content_type}:{content_hash}")
            
            result = self.primary_cache.get(cache_key)
            if result is not None:
                self.cache_hits += 1
                return json.loads(result)
            
            self.cache_misses += 1
            return None
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache retrieval error for embeddings: {e}")
            return None
    
    def set_embeddings_exists(self, content_hash: str, content_type: str, exists: bool):
        """
        Cache embeddings existence for deduplication.
        
        Args:
            content_hash: SHA256 hash of content
            content_type: Type of content
            exists: Whether embeddings exist
        """
        try:
            cache_key = self._generate_cache_key('embeddings', f"{content_type}:{content_hash}")
            
            cache_data = {
                'exists': exists,
                'cached_at': datetime.now().isoformat(),
                'content_type': content_type
            }
            
            self.primary_cache.setex(cache_key, self.embeddings_ttl, json.dumps(cache_data))
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache storage error for embeddings: {e}")
    
    def get_facets(self, facet_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached facet data for search filtering.
        
        Args:
            facet_type: Type of facets ('all', 'cuisines', 'locations', etc.)
            
        Returns:
            Cached facets or None if not found
        """
        try:
            cache_data = {
                'type': facet_type,
                'date': datetime.now().strftime('%Y-%m-%d')  # Daily cache for facets
            }
            
            cache_key = self._generate_cache_key('facets', cache_data)
            
            result = self.primary_cache.get(cache_key)
            if result:
                self.cache_hits += 1
                return json.loads(result)
            
            self.cache_misses += 1
            return None
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache retrieval error for facets: {e}")
            return None
    
    def set_facets(self, facet_type: str, facets: Dict[str, Any]):
        """
        Cache facet data.
        
        Args:
            facet_type: Type of facets
            facets: Facets dictionary to cache
        """
        try:
            cache_data = {
                'type': facet_type,
                'date': datetime.now().strftime('%Y-%m-%d')
            }
            
            cache_key = self._generate_cache_key('facets', cache_data)
            
            cached_facets = {
                **facets,
                'cached_at': datetime.now().isoformat(),
                'facet_type': facet_type
            }
            
            self.primary_cache.setex(cache_key, self.facets_ttl, json.dumps(cached_facets))
            
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache storage error for facets: {e}")
    
    def invalidate_cache(self, pattern: str):
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Redis pattern for cache invalidation (e.g., 'unified_cache:search:*')
        """
        try:
            # Get all matching keys
            keys = self.primary_cache.keys(pattern)
            if keys:
                self.primary_cache.delete(*keys)
                logger.info(f"🗑️ Invalidated {len(keys)} primary cache entries matching: {pattern}")
            
            # Also invalidate secondary cache
            keys = self.secondary_cache.keys(pattern)
            if keys:
                self.secondary_cache.delete(*keys)
                logger.info(f"🗑️ Invalidated {len(keys)} secondary cache entries matching: {pattern}")
                
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache invalidation error: {e}")
    
    def invalidate_search_cache(self):
        """Invalidate all search-related cache entries."""
        self.invalidate_cache('unified_cache:search:*')
        self.invalidate_cache('unified_cache:suggestions:*')
        self.invalidate_cache('unified_cache:facets:*')
    
    def invalidate_embeddings_cache(self):
        """Invalidate all embeddings-related cache entries."""
        self.invalidate_cache('unified_cache:embeddings:*')
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache performance statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        try:
            primary_info = self.primary_cache.info()
            secondary_info = self.secondary_cache.info()
            
            # Calculate hit rate
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'performance': {
                    'cache_hits': self.cache_hits,
                    'cache_misses': self.cache_misses,
                    'cache_errors': self.cache_errors,
                    'hit_rate_percentage': round(hit_rate, 2),
                    'total_requests': total_requests
                },
                'primary_cache': {
                    'used_memory': primary_info.get('used_memory_human', 'Unknown'),
                    'connected_clients': primary_info.get('connected_clients', 0),
                    'keyspace_hits': primary_info.get('keyspace_hits', 0),
                    'keyspace_misses': primary_info.get('keyspace_misses', 0),
                    'expired_keys': primary_info.get('expired_keys', 0)
                },
                'secondary_cache': {
                    'used_memory': secondary_info.get('used_memory_human', 'Unknown'),
                    'connected_clients': secondary_info.get('connected_clients', 0),
                    'keyspace_hits': secondary_info.get('keyspace_hits', 0),
                    'keyspace_misses': secondary_info.get('keyspace_misses', 0),
                    'expired_keys': secondary_info.get('expired_keys', 0)
                },
                'configuration': {
                    'search_results_ttl': self.search_results_ttl,
                    'suggestions_ttl': self.suggestions_ttl,
                    'embeddings_ttl': self.embeddings_ttl,
                    'facets_ttl': self.facets_ttl
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'error': str(e),
                'performance': {
                    'cache_hits': self.cache_hits,
                    'cache_misses': self.cache_misses,
                    'cache_errors': self.cache_errors
                }
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check for cache system.
        
        Returns:
            Health check results
        """
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        try:
            # Test primary cache
            test_key = f"health_check:{datetime.now().timestamp()}"
            self.primary_cache.setex(test_key, 10, 'test')
            result = self.primary_cache.get(test_key)
            self.primary_cache.delete(test_key)
            
            health['checks']['primary_cache'] = {
                'status': 'healthy' if result == 'test' else 'unhealthy',
                'latency_ms': 'low'  # Could implement actual latency measurement
            }
            
        except Exception as e:
            health['checks']['primary_cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health['status'] = 'degraded'
        
        try:
            # Test secondary cache
            test_key = f"health_check_secondary:{datetime.now().timestamp()}"
            self.secondary_cache.setex(test_key, 10, 'test')
            result = self.secondary_cache.get(test_key)
            self.secondary_cache.delete(test_key)
            
            health['checks']['secondary_cache'] = {
                'status': 'healthy' if result == 'test' else 'unhealthy',
                'latency_ms': 'low'
            }
            
        except Exception as e:
            health['checks']['secondary_cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            if health['status'] == 'healthy':
                health['status'] = 'degraded'
        
        return health


# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> UnifiedCacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = UnifiedCacheManager()
    return _cache_manager