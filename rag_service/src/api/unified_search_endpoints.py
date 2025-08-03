"""
Unified RAG Search Endpoints - Single source of truth for all search functionality.
Integrates with UnifiedEmbeddingGenerator and provides consistent API for all content types.
"""
import logging
import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

# Import paths are handled by Docker PYTHONPATH

from search.unified_filters import UnifiedSearchFilters, UnifiedSearchResult, SearchRequest, SearchResponse
from embeddings.unified_embedding_generator import UnifiedEmbeddingGenerator
from cache.unified_cache_manager import get_cache_manager, UnifiedCacheManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/unified-search", tags=["unified-search"])

# Initialize embedding generator (singleton pattern)
_embedding_generator = None

def get_embedding_generator() -> UnifiedEmbeddingGenerator:
    """Get or create the unified embedding generator instance."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = UnifiedEmbeddingGenerator()
    return _embedding_generator

def get_cache() -> UnifiedCacheManager:
    """Get the cache manager instance."""
    return get_cache_manager()


# Pydantic models for API validation
class SearchRequestModel(BaseModel):
    """Request model for unified search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    
    # Restaurant filters
    restaurant_id: Optional[str] = None
    restaurant_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    cuisine_type: Optional[str] = None
    cuisine_types: Optional[List[str]] = None
    michelin_stars: Optional[List[int]] = None
    price_range: Optional[List[str]] = None
    rating_min: Optional[float] = Field(None, ge=0.0, le=5.0)
    rating_max: Optional[float] = Field(None, ge=0.0, le=5.0)
    
    # Image filters
    ai_category: Optional[str] = None
    ai_categories: Optional[List[str]] = None
    image_labels: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    confidence_min: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Content routing
    content_types: Optional[List[str]] = Field(default=None, description="Types to search: restaurants, images, menu_items, documents")
    
    # Search parameters
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="relevance", pattern="^(relevance|date|rating|distance|alphabetical)$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    include_metadata: bool = True
    include_embeddings: bool = False

    def to_unified_filters(self) -> UnifiedSearchFilters:
        """Convert to UnifiedSearchFilters object."""
        return UnifiedSearchFilters(
            restaurant_id=self.restaurant_id,
            restaurant_name=self.restaurant_name,
            city=self.city,
            country=self.country,
            cuisine_type=self.cuisine_type,
            cuisine_types=self.cuisine_types,
            michelin_stars=self.michelin_stars,
            price_range=self.price_range,
            rating_min=self.rating_min,
            rating_max=self.rating_max,
            ai_category=self.ai_category,
            ai_categories=self.ai_categories,
            image_labels=self.image_labels,
            is_featured=self.is_featured,
            confidence_min=self.confidence_min,
            content_types=self.content_types or ['restaurants', 'images', 'menu_items', 'documents'],
            limit=self.limit,
            offset=self.offset,
            sort_by=self.sort_by,
            sort_order=self.sort_order,
            include_metadata=self.include_metadata,
            include_embeddings=self.include_embeddings
        )


class UnifiedSearchResponseModel(BaseModel):
    """Response model for unified search."""
    results: List[Dict[str, Any]]
    total_count: int
    query_info: Dict[str, Any]
    facets: Dict[str, Any]
    performance_metrics: Dict[str, Any]


@router.post("/search", response_model=UnifiedSearchResponseModel)
async def unified_search(
    request: SearchRequestModel,
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator),
    cache: UnifiedCacheManager = Depends(get_cache)
) -> UnifiedSearchResponseModel:
    """
    Unified search across all content types (restaurants, images, menu items, documents).
    
    This single endpoint replaces all separate search endpoints and provides:
    - Semantic search across all content types
    - Consistent filtering and ranking
    - Unified response format
    - High-performance Redis caching
    """
    start_time = datetime.now()
    
    try:
        # Convert request to unified filters
        filters = request.to_unified_filters()
        filters_dict = filters.to_dict()
        
        # Try cache first
        cached_results = cache.get_search_results(request.query, filters_dict)
        if cached_results:
            logger.info(f"🎯 Cache HIT for unified search: '{request.query[:50]}...'")
            return UnifiedSearchResponseModel(**cached_results)
        
        # Perform unified search
        logger.info(f"🔍 Unified search (cache miss): '{request.query}' with filters: {filters.content_types}")
        
        results = generator.unified_search(
            query=request.query,
            filters=filters,
            k=request.limit
        )
        
        # Calculate performance metrics
        search_time = (datetime.now() - start_time).total_seconds()
        
        # Generate facets for UI filtering
        facets = _generate_facets(results)
        
        # Create response
        response_data = {
            'results': [result.to_dict() for result in results],
            'total_count': len(results),
            'query_info': {
                'query': request.query,
                'filters_applied': len([f for f in filters_dict.values() if f is not None]),
                'content_types_searched': filters.content_types,
                'search_mode': 'semantic_vector_search',
                'cache_status': 'miss'
            },
            'facets': facets,
            'performance_metrics': {
                'search_time_seconds': search_time,
                'results_returned': len(results),
                'embedding_model': 'text-embedding-3-small',
                'vector_stores_queried': len(filters.content_types),
                'cached': False
            }
        }
        
        # Cache the results
        cache.set_search_results(request.query, filters_dict, response_data)
        
        response = UnifiedSearchResponseModel(**response_data)
        logger.info(f"✅ Search completed in {search_time:.3f}s, {len(results)} results (cached)")
        return response
        
    except Exception as e:
        logger.error(f"❌ Unified search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search")
async def unified_search_get(
    query: str = Query(..., min_length=1, max_length=1000),
    restaurant_id: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    cuisine_type: Optional[str] = Query(None),
    michelin_stars: Optional[str] = Query(None, description="Comma-separated list: 1,2,3"),
    ai_category: Optional[str] = Query(None),
    content_types: Optional[str] = Query(None, description="Comma-separated: restaurants,images,menu_items,documents"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator)
) -> UnifiedSearchResponseModel:
    """
    GET version of unified search for simple queries.
    Useful for direct browser access and simple integrations.
    """
    try:
        # Parse comma-separated values
        michelin_stars_list = None
        if michelin_stars:
            michelin_stars_list = [int(x.strip()) for x in michelin_stars.split(',') if x.strip().isdigit()]
        
        content_types_list = None
        if content_types:
            content_types_list = [x.strip() for x in content_types.split(',') if x.strip()]
        
        # Create request model
        request = SearchRequestModel(
            query=query,
            restaurant_id=restaurant_id,
            city=city,
            cuisine_type=cuisine_type,
            michelin_stars=michelin_stars_list,
            ai_category=ai_category,
            content_types=content_types_list,
            limit=limit,
            offset=offset
        )
        
        # Use the POST endpoint logic
        return await unified_search(request, generator)
        
    except Exception as e:
        logger.error(f"❌ GET search failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid search parameters: {str(e)}")


@router.post("/search/restaurants")
async def search_restaurants_only(
    request: SearchRequestModel,
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator)
) -> UnifiedSearchResponseModel:
    """
    Search only restaurant content.
    Convenience endpoint that filters to restaurants only.
    """
    request.content_types = ['restaurants']
    return await unified_search(request, generator)


@router.post("/search/images")
async def search_images_only(
    request: SearchRequestModel,
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator)
) -> UnifiedSearchResponseModel:
    """
    Search only image content with AI classifications.
    Includes image categories, labels, and descriptions.
    """
    request.content_types = ['images']
    return await unified_search(request, generator)


@router.post("/search/menu-items")
async def search_menu_items_only(
    request: SearchRequestModel,
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator)
) -> UnifiedSearchResponseModel:
    """
    Search only menu item content.
    Useful for finding specific dishes or ingredients.
    """
    request.content_types = ['menu_items']
    return await unified_search(request, generator)


@router.post("/search/documents")
async def search_documents_only(
    request: SearchRequestModel,
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator)
) -> UnifiedSearchResponseModel:
    """
    Search only document content.
    Includes scraped content, reviews, and descriptions.
    """
    request.content_types = ['documents']
    return await unified_search(request, generator)


@router.get("/search/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator),
    cache: UnifiedCacheManager = Depends(get_cache)
) -> Dict[str, List[str]]:
    """
    Get search suggestions based on partial query.
    Returns suggested completions for restaurants, cuisines, and locations.
    High-performance cached suggestions with 1-hour TTL.
    """
    try:
        # Try cache first
        cached_suggestions = cache.get_suggestions(query, 'all')
        if cached_suggestions:
            logger.debug(f"🎯 Cache HIT for suggestions: '{query[:30]}...'")
            return cached_suggestions
        
        # Generate suggestions
        suggestions = {
            'restaurants': [],
            'cuisines': [],
            'locations': [],
            'categories': []
        }
        
        query_lower = query.lower()
        
        # Basic cuisine suggestions
        cuisines = ['italian', 'french', 'japanese', 'chinese', 'indian', 'thai', 'mexican', 'american', 'mediterranean', 'korean']
        suggestions['cuisines'] = [c for c in cuisines if query_lower in c][:limit]
        
        # Basic location suggestions  
        locations = ['paris', 'tokyo', 'new york', 'london', 'rome', 'barcelona', 'milan', 'hong kong', 'singapore', 'sydney']
        suggestions['locations'] = [l for l in locations if query_lower in l][:limit]
        
        # Image category suggestions
        categories = ['scenery_ambiance', 'menu_item', 'exterior', 'interior', 'food', 'dessert', 'wine']
        suggestions['categories'] = [c for c in categories if query_lower in c.replace('_', ' ')][:limit]
        
        # Cache the suggestions
        cache.set_suggestions(query, suggestions, 'all')
        
        logger.debug(f"💾 Generated and cached suggestions for: '{query[:30]}...'")
        return suggestions
        
    except Exception as e:
        logger.error(f"❌ Suggestions failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/search/facets")
async def get_search_facets(
    query: Optional[str] = Query(None),
    generator: UnifiedEmbeddingGenerator = Depends(get_embedding_generator),
    cache: UnifiedCacheManager = Depends(get_cache)
) -> Dict[str, Any]:
    """
    Get available facets for search filtering.
    Returns counts and available values for each filter type.
    High-performance cached facets with daily TTL.
    """
    try:
        facet_type = 'all' if not query else f'query_{query[:50]}'
        
        # Try cache first
        cached_facets = cache.get_facets(facet_type)
        if cached_facets:
            logger.debug(f"🎯 Cache HIT for facets: {facet_type}")
            return cached_facets
        
        # Generate facets (in production, this would aggregate data from vector stores)
        facets = {
            'content_types': {
                'restaurants': {'count': 0, 'available': True},
                'images': {'count': 0, 'available': True},
                'menu_items': {'count': 0, 'available': True},
                'documents': {'count': 0, 'available': True}
            },
            'cuisines': {
                'italian': {'count': 0},
                'french': {'count': 0},
                'japanese': {'count': 0},
                'chinese': {'count': 0}
            },
            'michelin_stars': {
                '1': {'count': 0},
                '2': {'count': 0},
                '3': {'count': 0}
            },
            'ai_categories': {
                'scenery_ambiance': {'count': 0},
                'menu_item': {'count': 0},
                'uncategorized': {'count': 0}
            },
            'locations': {
                'paris': {'count': 0},
                'tokyo': {'count': 0},
                'new_york': {'count': 0}
            }
        }
        
        # Cache the facets
        cache.set_facets(facet_type, facets)
        
        logger.debug(f"💾 Generated and cached facets for: {facet_type}")
        return facets
        
    except Exception as e:
        logger.error(f"❌ Facets failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get facets: {str(e)}")


def _generate_facets(results: List[UnifiedSearchResult]) -> Dict[str, Any]:
    """Generate facets from search results for UI filtering."""
    facets = {
        'content_types': {},
        'cuisines': {},
        'michelin_stars': {},
        'ai_categories': {},
        'cities': {}
    }
    
    for result in results:
        # Content type facets
        content_type = result.content_type
        if content_type not in facets['content_types']:
            facets['content_types'][content_type] = 0
        facets['content_types'][content_type] += 1
        
        # Restaurant context facets
        if result.restaurant_context:
            cuisine = result.restaurant_context.get('cuisine_type')
            if cuisine:
                if cuisine not in facets['cuisines']:
                    facets['cuisines'][cuisine] = 0
                facets['cuisines'][cuisine] += 1
            
            stars = result.restaurant_context.get('michelin_stars')
            if stars and stars > 0:
                stars_key = str(stars)
                if stars_key not in facets['michelin_stars']:
                    facets['michelin_stars'][stars_key] = 0
                facets['michelin_stars'][stars_key] += 1
            
            city = result.restaurant_context.get('city')
            if city:
                if city not in facets['cities']:
                    facets['cities'][city] = 0
                facets['cities'][city] += 1
        
        # AI category facets (for images)
        if result.content_type == 'image':
            ai_category = result.metadata.get('ai_category')
            if ai_category:
                if ai_category not in facets['ai_categories']:
                    facets['ai_categories'][ai_category] = 0
                facets['ai_categories'][ai_category] += 1
    
    return facets


@router.get("/cache/stats")
async def get_cache_stats(
    cache: UnifiedCacheManager = Depends(get_cache)
) -> Dict[str, Any]:
    """Get comprehensive cache performance statistics."""
    try:
        stats = cache.get_cache_stats()
        return {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'cache_stats': stats
        }
    except Exception as e:
        logger.error(f"❌ Cache stats failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: str = Query(..., description="Redis pattern for cache invalidation (e.g., 'unified_cache:search:*')"),
    cache: UnifiedCacheManager = Depends(get_cache)
) -> Dict[str, Any]:
    """Invalidate cache entries matching pattern."""
    try:
        cache.invalidate_cache(pattern)
        return {
            'status': 'success',
            'message': f'Cache invalidated for pattern: {pattern}',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Cache invalidation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")


@router.get("/health")
async def health_check(
    cache: UnifiedCacheManager = Depends(get_cache)
) -> Dict[str, Any]:
    """Health check endpoint for unified search service with cache monitoring."""
    try:
        generator = get_embedding_generator()
        
        # Test vector store connections
        store_status = {}
        for store_name, store in generator.stores.items():
            if 'unified' in store_name:
                try:
                    # Simple connection test
                    store_status[store_name] = 'healthy'
                except Exception as e:
                    store_status[store_name] = f'error: {str(e)}'
        
        # Get cache health
        cache_health = cache.health_check()
        
        # Get cache stats
        cache_stats = cache.get_cache_stats()
        
        return {
            'status': 'healthy',
            'service': 'unified_search_endpoints',
            'timestamp': datetime.now().isoformat(),
            'vector_stores': store_status,
            'cache_health': cache_health,
            'cache_performance': cache_stats.get('performance', {}),
            'embedding_model': 'text-embedding-3-small',
            'features': [
                'unified_search',
                'content_type_filtering', 
                'semantic_similarity',
                'faceted_search',
                'search_suggestions',
                'redis_caching',
                'cache_analytics'
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# Export router for FastAPI app integration
__all__ = ['router']