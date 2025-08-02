"""
Advanced Semantic Search Service
Complements existing Django search with AI-powered semantic understanding.
Maintains backward compatibility while adding intelligent query processing.
"""
import logging
import json
import time
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from django.db import models
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Q, F, Count, Avg, Max, Case, When, Value, QuerySet
from django.db.models.functions import Greatest, Coalesce
from django.core.cache import cache
from django.conf import settings
import requests

from .models import Restaurant, RestaurantReview, MenuItem, RestaurantImage
from .search import RestaurantSearchService, ReviewSearchService

logger = logging.getLogger(__name__)


class SearchMethod(Enum):
    """Search method types for routing and fallback."""
    TRADITIONAL = "traditional"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    GEOGRAPHIC = "geographic"


@dataclass
class SearchIntent:
    """Represents analyzed search intent with context."""
    original_query: str
    intent_type: str  # 'location', 'cuisine', 'experience', 'specific'
    entities: Dict[str, str]  # extracted entities
    sentiment: str  # 'positive', 'neutral', 'negative'
    complexity_score: float  # 0.0-1.0
    recommended_method: SearchMethod


@dataclass
class SemanticResult:
    """Enhanced search result with semantic scoring."""
    restaurant: Restaurant
    relevance_score: float
    semantic_score: float
    traditional_score: float
    explanation: str
    matched_features: List[str]


class QueryAnalyzer:
    """
    Analyzes search queries to determine optimal search strategy.
    Routes between traditional and semantic search based on query complexity.
    """
    
    # Simple query patterns that work well with traditional search
    SIMPLE_PATTERNS = [
        r'^[a-zA-Z\s]+$',  # Simple text only
        r'^\w+\s+restaurant$',  # "[cuisine] restaurant"
        r'^\w+\s+in\s+\w+$',  # "[cuisine] in [city]"
        r'^\d+\s+star',  # "3 star restaurants"
    ]
    
    # Complex patterns that benefit from semantic search
    COMPLEX_PATTERNS = [
        r'best.*for.*',  # "best restaurants for date night"
        r'romantic.*dinner',  # "romantic dinner spots"
        r'family.*friendly',  # "family friendly places"
        r'authentic.*experience',  # "authentic Italian experience"
        r'.*atmosphere.*',  # queries about atmosphere
        r'.*ambiance.*',  # queries about ambiance
        r'where.*can.*',  # "where can I find..."
    ]
    
    @classmethod
    def analyze_query(cls, query: str, context: Dict = None) -> SearchIntent:
        """
        Analyze search query to determine intent and optimal search method.
        
        Args:
            query: User search query
            context: Additional context (location, user preferences, etc.)
            
        Returns:
            SearchIntent with routing recommendation
        """
        import re
        
        query_lower = query.lower().strip()
        context = context or {}
        
        # Initialize intent
        intent = SearchIntent(
            original_query=query,
            intent_type='general',
            entities={},
            sentiment='neutral',
            complexity_score=0.0,
            recommended_method=SearchMethod.TRADITIONAL
        )
        
        # Calculate complexity score
        complexity_factors = [
            len(query.split()) > 4,  # Long queries
            any(word in query_lower for word in ['best', 'good', 'great', 'amazing']),  # Quality adjectives
            any(word in query_lower for word in ['romantic', 'cozy', 'atmosphere', 'vibe']),  # Experience words
            any(word in query_lower for word in ['for', 'with', 'near', 'around']),  # Contextual prepositions
            '?' in query,  # Questions
            any(re.search(pattern, query_lower) for pattern in cls.COMPLEX_PATTERNS)  # Complex patterns
        ]
        
        intent.complexity_score = sum(complexity_factors) / len(complexity_factors)
        
        # Extract entities
        intent.entities = cls._extract_entities(query_lower)
        
        # Determine intent type
        if any(word in query_lower for word in ['near', 'in', 'around', 'close']):
            intent.intent_type = 'location'
        elif any(word in query_lower for word in ['italian', 'french', 'chinese', 'japanese', 'mexican']):
            intent.intent_type = 'cuisine'
        elif any(word in query_lower for word in ['romantic', 'date', 'anniversary', 'special']):
            intent.intent_type = 'experience'
        elif len(query.split()) <= 2 and not any(re.search(pattern, query_lower) for pattern in cls.COMPLEX_PATTERNS):
            intent.intent_type = 'specific'
        
        # Determine sentiment
        positive_words = ['best', 'great', 'amazing', 'excellent', 'wonderful', 'fantastic']
        negative_words = ['bad', 'worst', 'terrible', 'awful', 'horrible']
        
        if any(word in query_lower for word in positive_words):
            intent.sentiment = 'positive'
        elif any(word in query_lower for word in negative_words):
            intent.sentiment = 'negative'
        
        # Recommend search method based on analysis
        if intent.complexity_score >= 0.4 or intent.intent_type == 'experience':
            intent.recommended_method = SearchMethod.SEMANTIC
        elif intent.intent_type == 'location' and 'address' in context:
            intent.recommended_method = SearchMethod.GEOGRAPHIC
        elif intent.complexity_score >= 0.2:
            intent.recommended_method = SearchMethod.HYBRID
        else:
            intent.recommended_method = SearchMethod.TRADITIONAL
            
        return intent
    
    @staticmethod
    def _extract_entities(query: str) -> Dict[str, str]:
        """Extract named entities from query."""
        entities = {}
        
        # Simple entity extraction (could be enhanced with NER models)
        cuisine_keywords = {
            'italian': 'Italian', 'french': 'French', 'chinese': 'Chinese',
            'japanese': 'Japanese', 'mexican': 'Mexican', 'indian': 'Indian',
            'thai': 'Thai', 'vietnamese': 'Vietnamese', 'korean': 'Korean'
        }
        
        experience_keywords = {
            'romantic': 'romantic', 'family': 'family-friendly', 'business': 'business',
            'casual': 'casual', 'fine': 'fine-dining', 'quick': 'quick-bite'
        }
        
        for keyword, entity in cuisine_keywords.items():
            if keyword in query:
                entities['cuisine'] = entity
                
        for keyword, entity in experience_keywords.items():
            if keyword in query:
                entities['experience'] = entity
                
        return entities


class SemanticSearchService:
    """
    Advanced semantic search service that complements traditional search.
    Integrates with RAG service for natural language understanding.
    """
    
    def __init__(self):
        self.rag_service_url = getattr(settings, 'RAG_SERVICE_URL', 'http://rag:8001')
        self.cache_timeout = 1800  # 30 minutes
        self.fallback_enabled = True
        
    def search_restaurants(
        self,
        query: str,
        context: Dict = None,
        filters: Dict = None,
        limit: int = 20,
        force_method: SearchMethod = None
    ) -> Dict:
        """
        Main semantic search entry point with intelligent routing.
        
        Args:
            query: Search query
            context: Search context (location, user prefs, etc.)
            filters: Additional filters
            limit: Maximum results
            force_method: Force specific search method (for testing)
            
        Returns:
            Enhanced search results with semantic scoring
        """
        start_time = time.time()
        context = context or {}
        filters = filters or {}
        
        try:
            # Analyze query to determine optimal search method
            intent = QueryAnalyzer.analyze_query(query, context)
            method = force_method or intent.recommended_method
            
            logger.info(f"Semantic search: query='{query}' method={method.value} complexity={intent.complexity_score}")
            
            # Route to appropriate search method
            if method == SearchMethod.SEMANTIC:
                results = self._semantic_search(query, intent, filters, limit)
            elif method == SearchMethod.HYBRID:
                results = self._hybrid_search(query, intent, filters, limit)
            elif method == SearchMethod.GEOGRAPHIC and 'location' in context:
                results = self._geographic_semantic_search(query, context['location'], filters, limit)
            else:
                results = self._enhanced_traditional_search(query, intent, filters, limit)
            
            # Add metadata
            results.update({
                'search_method': method.value,
                'intent_analysis': {
                    'type': intent.intent_type,
                    'complexity': intent.complexity_score,
                    'entities': intent.entities,
                    'sentiment': intent.sentiment
                },
                'response_time_ms': round((time.time() - start_time) * 1000, 2),
                'semantic_enhanced': method in [SearchMethod.SEMANTIC, SearchMethod.HYBRID]
            })
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            if self.fallback_enabled:
                return self._fallback_search(query, filters, limit)
            raise
    
    def _semantic_search(self, query: str, intent: SearchIntent, filters: Dict, limit: int) -> Dict:
        """Pure semantic search using RAG service."""
        try:
            # Get semantic results from RAG service
            rag_results = self._query_rag_service(query, 'restaurants', filters)
            
            # Convert to Django objects and enhance
            restaurant_ids = [r.get('id') for r in rag_results.get('results', [])]
            restaurants = Restaurant.objects.filter(
                id__in=restaurant_ids,
                status='active'
            ).select_related().prefetch_related(
                'images', 'chefs', 'menu_sections__items'
            )
            
            # Create semantic results with scoring
            semantic_results = []
            for restaurant in restaurants:
                rag_result = next((r for r in rag_results['results'] if r['id'] == str(restaurant.id)), {})
                
                semantic_result = SemanticResult(
                    restaurant=restaurant,
                    relevance_score=rag_result.get('relevance_score', 0.0),
                    semantic_score=rag_result.get('semantic_score', 0.0),
                    traditional_score=0.0,
                    explanation=rag_result.get('explanation', ''),
                    matched_features=rag_result.get('matched_features', [])
                )
                semantic_results.append(semantic_result)
            
            # Sort by relevance
            semantic_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return {
                'results': [r.restaurant for r in semantic_results[:limit]],
                'semantic_results': semantic_results[:limit],
                'total_count': len(semantic_results),
                'source': 'semantic_rag',
                'facets': self._generate_semantic_facets(semantic_results)
            }
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def _hybrid_search(self, query: str, intent: SearchIntent, filters: Dict, limit: int) -> Dict:
        """Hybrid search combining traditional and semantic approaches."""
        try:
            # Get traditional results
            traditional_results = RestaurantSearchService.search_restaurants(
                query=query,
                limit=limit * 2,  # Get more for blending
                **filters
            )
            
            # Get semantic enhancement from RAG
            semantic_enhancement = self._query_rag_service(
                query, 'restaurants', filters, max_results=limit
            )
            
            # Blend results with weighted scoring
            blended_results = self._blend_search_results(
                traditional_results['restaurants'],
                semantic_enhancement.get('results', []),
                intent
            )
            
            return {
                'results': blended_results[:limit],
                'total_count': len(blended_results),
                'traditional_count': len(traditional_results['restaurants']),
                'semantic_count': len(semantic_enhancement.get('results', [])),
                'source': 'hybrid',
                'facets': traditional_results.get('facets', {})
            }
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    def _geographic_semantic_search(self, query: str, location: str, filters: Dict, limit: int) -> Dict:
        """Geographic search enhanced with semantic understanding."""
        try:
            # Use existing geographic API as base
            from .views import geographic_search_api
            from django.http import HttpRequest
            
            # Create mock request for geographic API
            request = HttpRequest()
            request.GET = {
                'address': location,
                'q': query,
                'max_results': str(limit * 2)
            }
            
            geographic_results = geographic_search_api(request)
            
            # Enhance with semantic analysis if query is complex
            if len(query.split()) > 2:
                enhanced_results = self._enhance_with_semantics(
                    geographic_results.json()['results'], query
                )
                return {
                    'results': enhanced_results[:limit],
                    'total_count': len(enhanced_results),
                    'source': 'geographic_semantic'
                }
            
            return geographic_results.json()
            
        except Exception as e:
            logger.error(f"Geographic semantic search failed: {e}")
            raise
    
    def _enhanced_traditional_search(self, query: str, intent: SearchIntent, filters: Dict, limit: int) -> Dict:
        """Enhanced traditional search with intent-based optimization."""
        try:
            # Use existing traditional search but optimize based on intent
            search_params = filters.copy()
            
            # Apply intent-based enhancements
            if intent.entities.get('cuisine'):
                search_params['cuisine_type'] = intent.entities['cuisine']
            
            if intent.entities.get('experience'):
                # Map experience to filters
                experience_mapping = {
                    'romantic': {'atmosphere__icontains': 'romantic'},
                    'family-friendly': {'has_private_dining': True},
                    'fine-dining': {'michelin_stars__gte': 1},
                    'casual': {'price_range__in': ['$', '$$']},
                    'business': {'has_private_dining': True}
                }
                
                if intent.entities['experience'] in experience_mapping:
                    search_params.update(experience_mapping[intent.entities['experience']])
            
            results = RestaurantSearchService.search_restaurants(
                query=query,
                limit=limit,
                **search_params
            )
            
            results['source'] = 'traditional_enhanced'
            results['intent_optimized'] = True
            
            return results
            
        except Exception as e:
            logger.error(f"Enhanced traditional search failed: {e}")
            raise
    
    def _query_rag_service(self, query: str, content_type: str, filters: Dict, max_results: int = None) -> Dict:
        """Query the RAG service for semantic search."""
        try:
            cache_key = f"semantic_search:{hash(query)}:{content_type}:{hash(str(sorted(filters.items())))}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            payload = {
                'query': query,
                'content_type': content_type,
                'max_results': max_results or 20,
                'filters': filters,
                'include_explanations': True
            }
            
            response = requests.post(
                f"{self.rag_service_url}/search/unified",
                json=payload,
                timeout=5.0,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                cache.set(cache_key, result, self.cache_timeout)
                return result
            else:
                logger.warning(f"RAG service returned {response.status_code}: {response.text}")
                return {'results': []}
                
        except requests.RequestException as e:
            logger.error(f"RAG service request failed: {e}")
            return {'results': []}
    
    def _blend_search_results(self, traditional: List, semantic: List, intent: SearchIntent) -> List:
        """Blend traditional and semantic results with intelligent weighting."""
        try:
            # Convert semantic results to restaurant objects if needed
            semantic_ids = [r.get('id') if isinstance(r, dict) else str(r.id) for r in semantic]
            traditional_ids = [str(r.id) for r in traditional]
            
            # Create scoring weights based on intent
            weights = {
                'traditional': 0.7 if intent.complexity_score < 0.3 else 0.4,
                'semantic': 0.3 if intent.complexity_score < 0.3 else 0.6
            }
            
            # Score and rank results
            restaurant_scores = {}
            
            # Score traditional results
            for i, restaurant in enumerate(traditional):
                restaurant_id = str(restaurant.id)
                traditional_score = (len(traditional) - i) / len(traditional)
                restaurant_scores[restaurant_id] = {
                    'restaurant': restaurant,
                    'traditional_score': traditional_score,
                    'semantic_score': 0.0,
                    'final_score': traditional_score * weights['traditional']
                }
            
            # Add semantic scores
            for i, semantic_result in enumerate(semantic):
                restaurant_id = semantic_result.get('id') if isinstance(semantic_result, dict) else str(semantic_result.id)
                semantic_score = (len(semantic) - i) / len(semantic)
                
                if restaurant_id in restaurant_scores:
                    restaurant_scores[restaurant_id]['semantic_score'] = semantic_score
                    restaurant_scores[restaurant_id]['final_score'] += semantic_score * weights['semantic']
                else:
                    # Restaurant only in semantic results
                    try:
                        restaurant = Restaurant.objects.get(id=restaurant_id, status='active')
                        restaurant_scores[restaurant_id] = {
                            'restaurant': restaurant,
                            'traditional_score': 0.0,
                            'semantic_score': semantic_score,
                            'final_score': semantic_score * weights['semantic']
                        }
                    except Restaurant.DoesNotExist:
                        continue
            
            # Sort by final score
            sorted_results = sorted(
                restaurant_scores.values(),
                key=lambda x: x['final_score'],
                reverse=True
            )
            
            return [r['restaurant'] for r in sorted_results]
            
        except Exception as e:
            logger.error(f"Result blending failed: {e}")
            return traditional  # Fallback to traditional results
    
    def _enhance_with_semantics(self, geographic_results: List, query: str) -> List:
        """Enhance geographic results with semantic analysis."""
        try:
            if not geographic_results:
                return []
            
            # Get restaurant objects
            restaurant_ids = [r['id'] for r in geographic_results if 'id' in r]
            restaurants = Restaurant.objects.filter(id__in=restaurant_ids, status='active')
            
            # Query semantic service for enhanced understanding
            semantic_data = self._query_rag_service(query, 'restaurants', {})
            semantic_scores = {
                r['id']: r.get('relevance_score', 0.0) 
                for r in semantic_data.get('results', [])
            }
            
            # Combine geographic and semantic scores
            enhanced_results = []
            for restaurant in restaurants:
                restaurant_id = str(restaurant.id)
                geographic_score = 1.0  # All geographic results are equally valid
                semantic_score = semantic_scores.get(restaurant_id, 0.0)
                
                # Weight: 70% geographic relevance, 30% semantic relevance
                combined_score = (geographic_score * 0.7) + (semantic_score * 0.3)
                
                enhanced_results.append({
                    'restaurant': restaurant,
                    'combined_score': combined_score,
                    'geographic_score': geographic_score,
                    'semantic_score': semantic_score
                })
            
            # Sort by combined score
            enhanced_results.sort(key=lambda x: x['combined_score'], reverse=True)
            
            return [r['restaurant'] for r in enhanced_results]
            
        except Exception as e:
            logger.error(f"Semantic enhancement failed: {e}")
            return [Restaurant.objects.get(id=r['id']) for r in geographic_results if 'id' in r]
    
    def _generate_semantic_facets(self, semantic_results: List[SemanticResult]) -> Dict:
        """Generate facets based on semantic analysis."""
        try:
            facets = {
                'experiences': {},
                'matched_features': {},
                'price_sentiment': {},
                'atmosphere_types': {}
            }
            
            for result in semantic_results:
                # Extract experience facets from explanations
                if 'romantic' in result.explanation.lower():
                    facets['experiences']['romantic'] = facets['experiences'].get('romantic', 0) + 1
                if 'family' in result.explanation.lower():
                    facets['experiences']['family'] = facets['experiences'].get('family', 0) + 1
                if 'business' in result.explanation.lower():
                    facets['experiences']['business'] = facets['experiences'].get('business', 0) + 1
                
                # Count matched features
                for feature in result.matched_features:
                    facets['matched_features'][feature] = facets['matched_features'].get(feature, 0) + 1
            
            return facets
            
        except Exception as e:
            logger.error(f"Facet generation failed: {e}")
            return {}
    
    def _fallback_search(self, query: str, filters: Dict, limit: int) -> Dict:
        """Fallback to traditional search when semantic search fails."""
        try:
            logger.info(f"Using fallback search for query: {query}")
            
            results = RestaurantSearchService.search_restaurants(
                query=query,
                limit=limit,
                **filters
            )
            
            results['source'] = 'fallback_traditional'
            results['semantic_failed'] = True
            
            return results
            
        except Exception as e:
            logger.error(f"Fallback search also failed: {e}")
            return {
                'results': [],
                'total_count': 0,
                'error': 'All search methods failed',
                'source': 'error'
            }


# Convenience functions for easy integration
def semantic_search(query: str, **kwargs) -> Dict:
    """Convenience function for semantic search."""
    service = SemanticSearchService()
    return service.search_restaurants(query, **kwargs)


def analyze_search_intent(query: str, context: Dict = None) -> SearchIntent:
    """Convenience function for query analysis."""
    return QueryAnalyzer.analyze_query(query, context)