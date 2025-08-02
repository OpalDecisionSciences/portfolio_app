"""
Advanced search functionality for restaurants with optimized queries.
Utilizes PostgreSQL full-text search, trigram matching, and composite indexes.
"""
from django.db import models
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Q, F, Count, Avg, Max, Case, When, Value
from django.db.models.functions import Greatest, Coalesce
from typing import Dict, List, Optional, Tuple
import logging

from .models import Restaurant, RestaurantReview, MenuItem

logger = logging.getLogger(__name__)


class RestaurantSearchService:
    """
    High-performance restaurant search with multiple ranking algorithms.
    """
    
    @staticmethod
    def search_restaurants(
        query: str = "",
        city: str = "",
        country: str = "",
        cuisine_type: str = "",
        price_range: str = "",
        min_rating: float = 0.0,
        min_michelin_stars: int = 0,
        has_availability: bool = False,
        lat: float = None,
        lng: float = None,
        radius_km: float = 10.0,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """
        Advanced restaurant search with multiple ranking factors.
        
        Args:
            query: Text search query
            city: Filter by city
            country: Filter by country  
            cuisine_type: Filter by cuisine
            price_range: Filter by price ($, $$, $$$, $$$$)
            min_rating: Minimum rating threshold
            min_michelin_stars: Minimum Michelin stars
            has_availability: Filter restaurants with availability
            lat: Latitude for geographic search
            lng: Longitude for geographic search
            radius_km: Search radius in kilometers
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            Dict with 'restaurants', 'total_count', 'facets'
        """
        
        # Base queryset with optimized prefetching
        queryset = Restaurant.objects.select_related(
            'parent_group'
        ).prefetch_related(
            'images', 'chefs', 'menu_sections__items'
        ).filter(
            is_active=True  # Only active restaurants
        )
        
        # Text search with full-text search and trigram similarity
        if query:
            # Create search vector for full-text search
            search_vector = SearchVector(
                'name', weight='A'
            ) + SearchVector(
                'description', weight='B'
            ) + SearchVector(
                'cuisine_type', weight='B'
            ) + SearchVector(
                'city', weight='C'
            ) + SearchVector(
                'country', weight='C'
            )
            
            search_query = SearchQuery(query, config='english')
            
            # Trigram similarity for fuzzy matching
            name_similarity = TrigramSimilarity('name', query)
            city_similarity = TrigramSimilarity('city', query)
            cuisine_similarity = TrigramSimilarity('cuisine_type', query)
            
            # Combined relevance score
            queryset = queryset.annotate(
                search_rank=SearchRank(search_vector, search_query),
                name_similarity=name_similarity,
                city_similarity=city_similarity,
                cuisine_similarity=cuisine_similarity,
                combined_similarity=Greatest(
                    'name_similarity',
                    'city_similarity', 
                    'cuisine_similarity'
                )
            ).filter(
                Q(search_rank__gt=0.1) | Q(combined_similarity__gt=0.3)
            )
        
        # Geographic filtering
        if lat is not None and lng is not None:
            # Haversine distance calculation
            queryset = queryset.extra(
                select={
                    'distance': '''
                        6371 * acos(
                            cos(radians(%s)) * cos(radians(latitude)) *
                            cos(radians(longitude) - radians(%s)) +
                            sin(radians(%s)) * sin(radians(latitude))
                        )
                    '''
                },
                select_params=[lat, lng, lat]
            ).filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).extra(
                where=['6371 * acos(cos(radians(%s)) * cos(radians(latitude)) * cos(radians(longitude) - radians(%s)) + sin(radians(%s)) * sin(radians(latitude))) <= %s'],
                params=[lat, lng, lat, radius_km]
            )
        
        # Location filters
        if city:
            queryset = queryset.filter(city__icontains=city)
        if country:
            queryset = queryset.filter(country__icontains=country)
            
        # Cuisine filter
        if cuisine_type:
            queryset = queryset.filter(cuisine_type__icontains=cuisine_type)
            
        # Price range filter
        if price_range:
            queryset = queryset.filter(price_range=price_range)
            
        # Rating filter
        if min_rating > 0:
            queryset = queryset.filter(rating__gte=min_rating)
            
        # Michelin stars filter
        if min_michelin_stars > 0:
            queryset = queryset.filter(michelin_stars__gte=min_michelin_stars)
        
        # Add computed fields for ranking
        queryset = queryset.annotate(
            # Review metrics
            review_score=Coalesce('rating', Value(0.0)),
            review_volume=Coalesce('review_count', Value(0)),
            
            # Michelin bonus
            michelin_bonus=Case(
                When(michelin_stars__gte=3, then=Value(3.0)),
                When(michelin_stars__gte=2, then=Value(2.0)),
                When(michelin_stars__gte=1, then=Value(1.0)),
                default=Value(0.0),
                output_field=models.FloatField()
            ),
            
            # Featured bonus
            featured_bonus=Case(
                When(is_featured=True, then=Value(0.5)),
                default=Value(0.0),
                output_field=models.FloatField()
            ),
            
            # Recent review activity
            recent_reviews_count=Count(
                'reviews',
                filter=Q(reviews__created_at__gte=models.functions.Now() - models.DurationField(days=30))
            )
        )
        
        # Calculate final ranking score
        if query:
            # With search query: combine relevance and quality
            queryset = queryset.annotate(
                final_score=(
                    F('search_rank') * 2.0 +
                    F('combined_similarity') * 1.5 +
                    F('review_score') / 5.0 +
                    F('michelin_bonus') * 0.8 +
                    F('featured_bonus') * 0.3 +
                    (F('recent_reviews_count') * 0.1)
                )
            ).order_by('-final_score', '-michelin_stars', '-review_score')
        else:
            # Without search query: quality-based ranking
            queryset = queryset.annotate(
                final_score=(
                    F('review_score') / 5.0 * 2.0 +
                    F('michelin_bonus') * 1.5 +
                    F('featured_bonus') * 0.5 +
                    (F('recent_reviews_count') * 0.1)
                )
            ).order_by('-final_score', '-michelin_stars', '-review_score', 'name')
        
        # Get total count before pagination
        total_count = queryset.count()
        
        # Apply pagination
        restaurants = list(queryset[offset:offset + limit])
        
        # Generate search facets for filtering
        facets = RestaurantSearchService._generate_facets(
            city=city, country=country, cuisine_type=cuisine_type,
            price_range=price_range, min_rating=min_rating
        )
        
        return {
            'restaurants': restaurants,
            'total_count': total_count,
            'facets': facets,
            'has_more': total_count > (offset + limit)
        }
    
    @staticmethod
    def _generate_facets(city="", country="", cuisine_type="", price_range="", min_rating=0.0) -> Dict:
        """Generate search facets for filtering."""
        
        base_queryset = Restaurant.objects.filter(is_active=True)
        
        # Apply current filters to facet generation
        if city:
            base_queryset = base_queryset.filter(city__icontains=city)
        if country:
            base_queryset = base_queryset.filter(country__icontains=country)
        if cuisine_type:
            base_queryset = base_queryset.filter(cuisine_type__icontains=cuisine_type)
        if price_range:
            base_queryset = base_queryset.filter(price_range=price_range)
        if min_rating > 0:
            base_queryset = base_queryset.filter(rating__gte=min_rating)
        
        return {
            'cuisines': list(
                base_queryset.exclude(cuisine_type="")
                .values('cuisine_type')
                .annotate(count=Count('id'))
                .order_by('-count')[:20]
            ),
            'cities': list(
                base_queryset.values('city', 'country')
                .annotate(count=Count('id'))
                .order_by('-count')[:20]
            ),
            'price_ranges': list(
                base_queryset.exclude(price_range="")
                .values('price_range')
                .annotate(count=Count('id'))
                .order_by('price_range')
            ),
            'michelin_levels': list(
                base_queryset.filter(michelin_stars__gt=0)
                .values('michelin_stars')
                .annotate(count=Count('id'))
                .order_by('-michelin_stars')
            )
        }
    
    @staticmethod
    def search_menu_items(
        restaurant_id: str,
        query: str = "",
        category: str = "",
        max_price: float = None,
        limit: int = 20
    ) -> List[MenuItem]:
        """
        Search menu items within a restaurant.
        """
        
        queryset = MenuItem.objects.select_related(
            'menu_section', 'menu_section__restaurant'
        ).filter(
            menu_section__restaurant_id=restaurant_id,
            status='available'
        )
        
        if query:
            # Full-text search on menu items
            search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
            search_query = SearchQuery(query, config='english')
            
            queryset = queryset.annotate(
                search_rank=SearchRank(search_vector, search_query),
                name_similarity=TrigramSimilarity('name', query)
            ).filter(
                Q(search_rank__gt=0.1) | Q(name_similarity__gt=0.3)
            ).order_by('-search_rank', '-name_similarity')
        
        if category:
            queryset = queryset.filter(menu_section__name__icontains=category)
            
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)
        
        return list(queryset.order_by('menu_section__order', 'order')[:limit])
    
    @staticmethod
    def get_restaurant_suggestions(query: str, limit: int = 5) -> List[Dict]:
        """
        Get autocomplete suggestions for restaurant search.
        """
        if len(query) < 2:
            return []
        
        # Name suggestions
        name_suggestions = Restaurant.objects.filter(
            is_active=True,
            name__icontains=query
        ).annotate(
            similarity=TrigramSimilarity('name', query)
        ).filter(
            similarity__gt=0.3
        ).order_by('-similarity', '-michelin_stars')[:limit]
        
        suggestions = []
        for restaurant in name_suggestions:
            suggestions.append({
                'type': 'restaurant',
                'id': str(restaurant.id),
                'name': restaurant.name,
                'city': restaurant.city,
                'country': restaurant.country,
                'michelin_stars': restaurant.michelin_stars,
                'similarity': restaurant.similarity
            })
        
        return suggestions


class ReviewSearchService:
    """
    Search service for restaurant reviews.
    """
    
    @staticmethod
    def search_reviews(
        restaurant_id: str = None,
        query: str = "",
        min_rating: int = 1,
        max_rating: int = 5,
        limit: int = 20,
        offset: int = 0
    ) -> Dict:
        """
        Search restaurant reviews with full-text search.
        """
        
        queryset = RestaurantReview.objects.select_related(
            'restaurant', 'user'
        ).filter(
            status='published'
        )
        
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        
        if query:
            search_vector = SearchVector('title', weight='A') + SearchVector('content', weight='B')
            search_query = SearchQuery(query, config='english')
            
            queryset = queryset.annotate(
                search_rank=SearchRank(search_vector, search_query)
            ).filter(
                search_rank__gt=0.1
            ).order_by('-search_rank', '-created_at')
        else:
            queryset = queryset.order_by('-created_at')
        
        # Rating filter
        queryset = queryset.filter(
            rating__gte=min_rating,
            rating__lte=max_rating
        )
        
        total_count = queryset.count()
        reviews = list(queryset[offset:offset + limit])
        
        return {
            'reviews': reviews,
            'total_count': total_count,
            'has_more': total_count > (offset + limit)
        }