"""
Unified search filters and schemas for consistent parameter handling across all systems.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


@dataclass
class UnifiedSearchFilters:
    """
    Standardized filter parameters used across all search systems:
    - Django views
    - RAG service endpoints  
    - Vector stores
    - Frontend components
    - Database queries
    """
    
    # Restaurant identifiers
    restaurant_id: Optional[str] = None
    restaurant_uuid: Optional[str] = None  # Alias for restaurant_id
    restaurant_name: Optional[str] = None
    restaurant_slug: Optional[str] = None
    
    # Geographic filters
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = None
    
    # Cuisine & Quality filters
    cuisine_type: Optional[str] = None
    cuisine_types: Optional[List[str]] = None  # Multiple cuisines
    michelin_stars: Optional[List[int]] = None  # [1, 2, 3]
    price_range: Optional[List[str]] = None    # ['$', '$$', '$$$', '$$$$']
    rating_min: Optional[float] = None
    rating_max: Optional[float] = None
    
    # Image-specific filters
    ai_category: Optional[str] = None          # 'food', 'interior', 'exterior', 'chef', 'staff', 'ambiance', 'presentation', 'ingredients', 'bar', 'menu_item', 'scenery_ambiance', 'uncategorized'
    ai_categories: Optional[List[str]] = None  # Multiple categories
    image_labels: Optional[List[str]] = None   # ['outdoor', 'romantic', 'pasta']
    image_type: Optional[str] = None           # Legacy support: 'exterior', 'interior', 'food'
    is_featured: Optional[bool] = None
    is_menu_highlight: Optional[bool] = None
    is_ambiance_highlight: Optional[bool] = None
    processing_status: Optional[str] = None    # 'completed', 'pending', 'failed'
    ai_processed: Optional[bool] = None
    
    # Menu item filters
    menu_section: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None  # ['vegetarian', 'vegan', 'gluten-free']
    allergens: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    
    # Document filters
    document_type: Optional[str] = None        # 'scraped_content', 'review', 'description'
    content_quality_min: Optional[float] = None
    
    # Content type routing
    content_types: Optional[List[str]] = None  # ['restaurants', 'images', 'menu_items', 'documents']
    
    # Search behavior
    limit: int = 20
    offset: int = 0
    sort_by: str = 'relevance'                # 'relevance', 'date', 'rating', 'distance', 'alphabetical'
    sort_order: str = 'desc'                  # 'asc', 'desc'
    include_metadata: bool = True
    include_embeddings: bool = False          # For debugging/analysis
    
    # Date filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    
    # Advanced filters
    confidence_min: Optional[float] = None     # Minimum AI confidence score
    has_images: Optional[bool] = None
    has_menu: Optional[bool] = None
    has_reviews: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}
    
    def to_vector_filter(self) -> Dict[str, Any]:
        """Convert to PGVector metadata filter format."""
        vector_filter = {}
        
        # Map fields to vector store metadata keys
        field_mappings = {
            'restaurant_id': 'restaurant_id',
            'restaurant_uuid': 'restaurant_id',  # Alias
            'city': 'city',
            'country': 'country',
            'cuisine_type': 'cuisine_type',
            'michelin_stars': 'michelin_stars',
            'ai_category': 'ai_category',
            'content_type': 'content_type'
        }
        
        for field, metadata_key in field_mappings.items():
            value = getattr(self, field, None)
            if value is not None:
                vector_filter[metadata_key] = value
        
        # Handle list filters
        if self.cuisine_types:
            vector_filter['cuisine_type'] = {'$in': self.cuisine_types}
        
        if self.ai_categories:
            vector_filter['ai_category'] = {'$in': self.ai_categories}
        
        if self.michelin_stars:
            vector_filter['michelin_stars'] = {'$in': self.michelin_stars}
        
        return vector_filter
    
    def to_django_q(self):
        """Convert to Django Q object for database queries."""
        from django.db.models import Q
        
        q_objects = Q()
        
        # Restaurant filters
        if self.restaurant_id or self.restaurant_uuid:
            restaurant_id = self.restaurant_id or self.restaurant_uuid
            q_objects &= Q(restaurant__id=restaurant_id)
        
        if self.restaurant_name:
            q_objects &= Q(restaurant__name__icontains=self.restaurant_name)
        
        if self.city:
            q_objects &= Q(restaurant__city__icontains=self.city)
        
        if self.country:
            q_objects &= Q(restaurant__country__icontains=self.country)
        
        # Cuisine filters
        if self.cuisine_type:
            q_objects &= Q(restaurant__cuisine_type__icontains=self.cuisine_type)
        
        if self.cuisine_types:
            cuisine_q = Q()
            for cuisine in self.cuisine_types:
                cuisine_q |= Q(restaurant__cuisine_type__icontains=cuisine)
            q_objects &= cuisine_q
        
        # Quality filters
        if self.michelin_stars:
            q_objects &= Q(restaurant__michelin_stars__in=self.michelin_stars)
        
        if self.rating_min:
            q_objects &= Q(restaurant__rating__gte=self.rating_min)
        
        if self.rating_max:
            q_objects &= Q(restaurant__rating__lte=self.rating_max)
        
        # Image-specific filters (for RestaurantImage model)
        if self.ai_category:
            q_objects &= Q(ai_category=self.ai_category)
        
        if self.ai_categories:
            q_objects &= Q(ai_category__in=self.ai_categories)
        
        if self.is_featured is not None:
            q_objects &= Q(is_featured=self.is_featured)
        
        if self.is_menu_highlight is not None:
            q_objects &= Q(is_menu_highlight=self.is_menu_highlight)
        
        if self.is_ambiance_highlight is not None:
            q_objects &= Q(is_ambiance_highlight=self.is_ambiance_highlight)
        
        if self.processing_status:
            q_objects &= Q(processing_status=self.processing_status)
        
        if self.ai_processed is not None:
            q_objects &= Q(ai_processed=self.ai_processed)
        
        # Date filters
        if self.created_after:
            q_objects &= Q(created_at__gte=self.created_after)
        
        if self.created_before:
            q_objects &= Q(created_at__lte=self.created_before)
        
        if self.confidence_min:
            q_objects &= Q(category_confidence__gte=self.confidence_min)
        
        return q_objects


@dataclass
class UnifiedSearchResult:
    """
    Standardized search result format returned by all search systems.
    """
    
    # Content identification
    content_type: str                    # 'restaurant', 'image', 'menu_item', 'document'
    content_id: str                      # UUID of the content
    restaurant_id: str                   # Always include restaurant context
    
    # Content data
    title: str
    description: str
    content_preview: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    # Relevance & ranking
    relevance_score: float = 0.0
    embedding_distance: float = 0.0
    
    # Rich metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    restaurant_context: Dict[str, Any] = field(default_factory=dict)
    
    # UX display helpers
    display_category: str = ""           # Human-readable category
    display_tags: List[str] = field(default_factory=list)  # Tags for UI filtering
    
    # Additional context
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        result = {
            'content_type': self.content_type,
            'content_id': self.content_id,
            'restaurant_id': self.restaurant_id,
            'title': self.title,
            'description': self.description,
            'relevance_score': self.relevance_score,
            'display_category': self.display_category,
            'display_tags': self.display_tags,
            'metadata': self.metadata,
            'restaurant_context': self.restaurant_context
        }
        
        # Add optional fields if present
        optional_fields = [
            'content_preview', 'image_url', 'thumbnail_url', 
            'embedding_distance', 'created_at', 'updated_at'
        ]
        
        for field in optional_fields:
            value = getattr(self, field, None)
            if value is not None:
                if isinstance(value, datetime):
                    result[field] = value.isoformat()
                else:
                    result[field] = value
        
        return result


@dataclass 
class SearchRequest:
    """
    Unified search request format for all search endpoints.
    """
    query: str
    filters: UnifiedSearchFilters = field(default_factory=UnifiedSearchFilters)
    options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'filters': self.filters.to_dict(),
            'options': self.options
        }


@dataclass
class SearchResponse:
    """
    Unified search response format for all search endpoints.
    """
    results: List[UnifiedSearchResult]
    total_count: int
    facets: Dict[str, Any] = field(default_factory=dict)
    query_info: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'results': [result.to_dict() for result in self.results],
            'total_count': self.total_count,
            'facets': self.facets,
            'query_info': self.query_info,
            'performance_metrics': self.performance_metrics
        }