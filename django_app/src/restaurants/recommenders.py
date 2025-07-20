"""
Restaurant Recommendation System

This module provides content-based and collaborative filtering recommendations
for restaurants based on various features like cuisine, location, price, and ratings.
"""

import math
import unicodedata
from typing import List, Dict, Tuple, Optional
from django.db.models import Q, Count, Avg, F
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import Restaurant, RestaurantReview, RestaurantImage


class RestaurantRecommender:
    """
    Main recommendation engine for restaurants.
    Combines content-based and collaborative filtering approaches.
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour cache
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing accents and converting to lowercase."""
        if not text:
            return ""
        # Remove accents and normalize unicode
        normalized = unicodedata.normalize('NFD', text)
        ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
        return ascii_text.lower().strip()
    
    def get_recommendations(self, 
                          user: Optional[User] = None,
                          restaurant_id: Optional[str] = None,
                          location: Optional[str] = None,
                          cuisine_preference: Optional[str] = None,
                          price_range: Optional[str] = None,
                          max_results: int = 10) -> List[Dict]:
        """
        Get personalized restaurant recommendations.
        
        Args:
            user: User for personalized recommendations
            restaurant_id: Restaurant ID for similar restaurants
            location: Location preference (city or country)
            cuisine_preference: Cuisine type preference
            price_range: Price range preference
            max_results: Maximum number of results to return
            
        Returns:
            List of recommended restaurants with scores and reasons
        """
        cache_key = f"recommendations_{user.id if user else 'anon'}_{restaurant_id}_{location}_{cuisine_preference}_{price_range}_{max_results}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get base queryset
        restaurants = Restaurant.objects.filter(is_active=True).select_related().prefetch_related('images')
        
        if restaurant_id:
            # Similar restaurant recommendations
            recommendations = self._get_similar_restaurants(restaurant_id, max_results)
        elif user and hasattr(user, 'restaurantreview_set'):
            # Personalized recommendations based on user reviews
            recommendations = self._get_personalized_recommendations(user, location, cuisine_preference, price_range, max_results)
        else:
            # Content-based recommendations for anonymous users
            recommendations = self._get_content_based_recommendations(location, cuisine_preference, price_range, max_results)
        
        # Add image data to recommendations
        for rec in recommendations:
            rec['featured_image'] = self._get_featured_image(rec['restaurant'])
            rec['image_count'] = rec['restaurant'].images.count()
        
        cache.set(cache_key, recommendations, self.cache_timeout)
        return recommendations
    
    def search_restaurants(self, 
                         query: str, 
                         location: Optional[str] = None,
                         filters: Optional[Dict] = None,
                         max_results: int = 20) -> List[Dict]:
        """
        Search restaurants with intelligent ranking and recommendations.
        
        Args:
            query: Search query
            location: Location filter
            filters: Additional filters (cuisine, price, stars)
            max_results: Maximum results to return
            
        Returns:
            List of restaurants with relevance scores and images
        """
        if not query and not location and not filters:
            # Return popular restaurants for empty search
            return self._get_popular_restaurants(max_results)
        
        # Build search queryset
        restaurants = Restaurant.objects.filter(is_active=True)
        
        # Text search with accent-insensitive matching
        if query:
            # For better accent-insensitive search, we'll do Python-level filtering
            # on a reasonable subset of restaurants, then apply proper scoring
            normalized_query = self._normalize_text(query)
            
            # Get all restaurants and filter in Python for accent-insensitive search
            all_restaurants = list(restaurants.all())
            matching_restaurants = []
            
            for restaurant in all_restaurants:
                # Check if query matches any field (with accent normalization)
                name_match = (query.lower() in restaurant.name.lower() or 
                             normalized_query in self._normalize_text(restaurant.name))
                city_match = (query.lower() in restaurant.city.lower() or 
                             normalized_query in self._normalize_text(restaurant.city))
                country_match = (query.lower() in restaurant.country.lower() or 
                                normalized_query in self._normalize_text(restaurant.country))
                cuisine_match = (restaurant.cuisine_type and 
                               (query.lower() in restaurant.cuisine_type.lower() or 
                                normalized_query in self._normalize_text(restaurant.cuisine_type)))
                description_match = (restaurant.description and 
                                   (query.lower() in restaurant.description.lower() or 
                                    normalized_query in self._normalize_text(restaurant.description)))
                
                if name_match or city_match or country_match or cuisine_match or description_match:
                    matching_restaurants.append(restaurant)
            
            # Convert back to queryset using IDs
            if matching_restaurants:
                matching_ids = [r.id for r in matching_restaurants]
                restaurants = restaurants.filter(id__in=matching_ids)
            else:
                # No matches found, return empty queryset
                restaurants = restaurants.none()
        
        # Apply filters
        if location:
            restaurants = restaurants.filter(
                Q(city__icontains=location) | Q(country__icontains=location)
            )
        
        if filters:
            if filters.get('cuisine'):
                restaurants = restaurants.filter(cuisine_type__icontains=filters['cuisine'])
            if filters.get('price_range'):
                restaurants = restaurants.filter(price_range=filters['price_range'])
            if filters.get('min_stars'):
                restaurants = restaurants.filter(michelin_stars__gte=filters['min_stars'])
            if filters.get('min_rating'):
                restaurants = restaurants.filter(rating__gte=filters['min_rating'])
        
        # Calculate relevance scores and rank results
        results = []
        for restaurant in restaurants.select_related().prefetch_related('images')[:max_results * 2]:
            score = self._calculate_search_relevance(restaurant, query, location)
            
            results.append({
                'restaurant': restaurant,
                'relevance_score': score,
                'featured_image': self._get_featured_image(restaurant),
                'image_count': restaurant.images.count(),
                'match_reasons': self._get_match_reasons(restaurant, query, location, filters)
            })
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:max_results]
    
    def _get_similar_restaurants(self, restaurant_id: str, max_results: int) -> List[Dict]:
        """Find restaurants similar to the given restaurant."""
        try:
            target_restaurant = Restaurant.objects.get(id=restaurant_id, is_active=True)
        except Restaurant.DoesNotExist:
            return []
        
        # Get all other restaurants
        candidates = Restaurant.objects.filter(
            is_active=True
        ).exclude(id=restaurant_id).select_related().prefetch_related('images')
        
        similarities = []
        for candidate in candidates:
            similarity_score = self._calculate_restaurant_similarity(target_restaurant, candidate)
            if similarity_score > 0.1:  # Minimum similarity threshold
                similarities.append({
                    'restaurant': candidate,
                    'similarity_score': similarity_score,
                    'similar_features': self._get_similarity_reasons(target_restaurant, candidate)
                })
        
        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similarities[:max_results]
    
    def _get_personalized_recommendations(self, user: User, location: str, cuisine: str, price_range: str, max_results: int) -> List[Dict]:
        """Get personalized recommendations based on user's review history."""
        # Get user's reviewed restaurants and preferences
        user_reviews = RestaurantReview.objects.filter(user=user, is_approved=True)
        
        if not user_reviews.exists():
            # Fallback to content-based for new users
            return self._get_content_based_recommendations(location, cuisine, price_range, max_results)
        
        # Analyze user preferences
        preferences = self._analyze_user_preferences(user_reviews)
        
        # Find restaurants matching user preferences
        candidates = Restaurant.objects.filter(is_active=True).exclude(
            id__in=user_reviews.values_list('restaurant_id', flat=True)
        ).select_related().prefetch_related('images')
        
        # Apply preference filters
        if location:
            candidates = candidates.filter(Q(city__icontains=location) | Q(country__icontains=location))
        if cuisine:
            candidates = candidates.filter(cuisine_type__icontains=cuisine)
        if price_range:
            candidates = candidates.filter(price_range=price_range)
        
        recommendations = []
        for candidate in candidates:
            score = self._calculate_user_preference_score(candidate, preferences)
            if score > 0.3:  # Minimum preference threshold
                recommendations.append({
                    'restaurant': candidate,
                    'preference_score': score,
                    'recommendation_reasons': self._get_preference_reasons(candidate, preferences)
                })
        
        # Sort by preference score
        recommendations.sort(key=lambda x: x['preference_score'], reverse=True)
        return recommendations[:max_results]
    
    def _get_content_based_recommendations(self, location: str, cuisine: str, price_range: str, max_results: int) -> List[Dict]:
        """Get content-based recommendations for anonymous users."""
        restaurants = Restaurant.objects.filter(is_active=True).select_related().prefetch_related('images')
        
        # Apply filters
        if location:
            restaurants = restaurants.filter(Q(city__icontains=location) | Q(country__icontains=location))
        if cuisine:
            restaurants = restaurants.filter(cuisine_type__icontains=cuisine)
        if price_range:
            restaurants = restaurants.filter(price_range=price_range)
        
        # Score restaurants based on popularity and quality
        recommendations = []
        for restaurant in restaurants:
            score = self._calculate_popularity_score(restaurant)
            recommendations.append({
                'restaurant': restaurant,
                'popularity_score': score,
                'recommendation_reasons': self._get_popularity_reasons(restaurant)
            })
        
        # Sort by popularity score
        recommendations.sort(key=lambda x: x['popularity_score'], reverse=True)
        return recommendations[:max_results]
    
    def _get_popular_restaurants(self, max_results: int) -> List[Dict]:
        """Get popular restaurants for empty searches."""
        restaurants = Restaurant.objects.filter(
            is_active=True
        ).annotate(
            review_count=Count('reviews'),
            avg_rating=Avg('reviews__rating')
        ).order_by('-michelin_stars', '-avg_rating', '-review_count').select_related().prefetch_related('images')
        
        results = []
        for restaurant in restaurants[:max_results]:
            results.append({
                'restaurant': restaurant,
                'popularity_score': self._calculate_popularity_score(restaurant),
                'featured_image': self._get_featured_image(restaurant),
                'image_count': restaurant.images.count(),
                'match_reasons': ['Popular restaurant', 'Highly rated']
            })
        
        return results
    
    def _calculate_restaurant_similarity(self, restaurant1: Restaurant, restaurant2: Restaurant) -> float:
        """Calculate similarity score between two restaurants."""
        score = 0.0
        
        # Cuisine similarity (40% weight)
        if restaurant1.cuisine_type and restaurant2.cuisine_type:
            if restaurant1.cuisine_type.lower() == restaurant2.cuisine_type.lower():
                score += 0.4
            elif any(word in restaurant2.cuisine_type.lower() for word in restaurant1.cuisine_type.lower().split()):
                score += 0.2
        
        # Location similarity (25% weight)
        if restaurant1.city == restaurant2.city:
            score += 0.15
        if restaurant1.country == restaurant2.country:
            score += 0.1
        
        # Price range similarity (20% weight)
        if restaurant1.price_range and restaurant2.price_range:
            if restaurant1.price_range == restaurant2.price_range:
                score += 0.2
            elif abs(len(restaurant1.price_range) - len(restaurant2.price_range)) <= 1:
                score += 0.1
        
        # Michelin stars similarity (15% weight)
        if restaurant1.michelin_stars and restaurant2.michelin_stars:
            star_diff = abs(restaurant1.michelin_stars - restaurant2.michelin_stars)
            if star_diff == 0:
                score += 0.15
            elif star_diff == 1:
                score += 0.1
            elif star_diff == 2:
                score += 0.05
        
        return min(score, 1.0)
    
    def _calculate_search_relevance(self, restaurant: Restaurant, query: str, location: str) -> float:
        """Calculate search relevance score for a restaurant."""
        score = 0.0
        query_lower = query.lower() if query else ""
        location_lower = location.lower() if location else ""
        
        # Normalize for accent-insensitive comparison
        query_normalized = self._normalize_text(query) if query else ""
        restaurant_name_normalized = self._normalize_text(restaurant.name)
        
        # Exact name match gets highest score (check both original and normalized)
        if query:
            if restaurant.name.lower() == query_lower:
                score += 1.0  # Perfect exact match
            elif restaurant_name_normalized == query_normalized:
                score += 0.98  # Accent-insensitive exact match (e.g., "epicure" = "Épicure") - raised priority
            elif query_lower in restaurant.name.lower():
                score += 0.8  # Substring match with original case
            elif query_normalized in restaurant_name_normalized:
                score += 0.75  # Accent-insensitive substring match
        
        # Location relevance (with accent normalization)
        if location:
            location_normalized = self._normalize_text(location)
            city_normalized = self._normalize_text(restaurant.city)
            country_normalized = self._normalize_text(restaurant.country)
            
            if restaurant.city.lower() == location_lower or city_normalized == location_normalized:
                score += 0.6
            elif location_lower in restaurant.city.lower() or location_normalized in city_normalized:
                score += 0.4
            elif restaurant.country.lower() == location_lower or country_normalized == location_normalized:
                score += 0.3
        
        # Cuisine relevance (with accent normalization)
        if query and restaurant.cuisine_type:
            cuisine_normalized = self._normalize_text(restaurant.cuisine_type)
            if query_lower in restaurant.cuisine_type.lower() or query_normalized in cuisine_normalized:
                score += 0.5
        
        # Quality boosters
        if restaurant.michelin_stars:
            score += restaurant.michelin_stars * 0.1
        
        if restaurant.rating:
            score += (float(restaurant.rating) / 5.0) * 0.2
        
        return min(score, 2.0)  # Cap at 2.0 for sorting
    
    def _calculate_popularity_score(self, restaurant: Restaurant) -> float:
        """Calculate popularity score based on ratings, reviews, and Michelin stars."""
        score = 0.0
        
        # Michelin stars (50% weight)
        if restaurant.michelin_stars:
            score += restaurant.michelin_stars * 0.2  # Max 0.6 for 3 stars
        
        # Rating (30% weight)
        if restaurant.rating:
            score += (float(restaurant.rating) / 5.0) * 0.3
        
        # Review count (20% weight)
        if restaurant.review_count:
            # Logarithmic scale for review count
            score += min(math.log(restaurant.review_count + 1) / 5.0, 0.2)
        
        return score
    
    def _get_featured_image(self, restaurant: Restaurant) -> Optional[Dict]:
        """Get the best featured image for a restaurant."""
        # Priority order: featured -> menu highlight -> ambiance highlight -> any image
        image = (
            restaurant.images.filter(is_featured=True).first() or
            restaurant.images.filter(is_menu_highlight=True).first() or
            restaurant.images.filter(is_ambiance_highlight=True).first() or
            restaurant.images.filter(ai_category='scenery_ambiance').first() or
            restaurant.images.first()
        )
        
        if image:
            return {
                'id': str(image.id),
                'url': image.source_url if image.source_url else (image.image.url if image.image else None),
                'caption': image.get_display_name(),
                'category': image.ai_category,
                'labels': image.ai_labels[:3] if image.ai_labels else [],
            }
        return None
    
    def _analyze_user_preferences(self, user_reviews) -> Dict:
        """Analyze user preferences from their review history."""
        preferences = {
            'cuisines': {},
            'price_ranges': {},
            'locations': {},
            'avg_rating_given': 0,
            'michelin_preference': 0
        }
        
        total_reviews = user_reviews.count()
        high_rated_reviews = user_reviews.filter(rating__gte=4)
        
        # Analyze cuisine preferences
        for review in high_rated_reviews:
            restaurant = review.restaurant
            cuisine = restaurant.cuisine_type
            if cuisine:
                preferences['cuisines'][cuisine] = preferences['cuisines'].get(cuisine, 0) + 1
        
        # Analyze price preferences
        for review in high_rated_reviews:
            price_range = review.restaurant.price_range
            if price_range:
                preferences['price_ranges'][price_range] = preferences['price_ranges'].get(price_range, 0) + 1
        
        # Analyze location preferences
        for review in high_rated_reviews:
            city = review.restaurant.city
            if city:
                preferences['locations'][city] = preferences['locations'].get(city, 0) + 1
        
        # Calculate averages
        preferences['avg_rating_given'] = user_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        preferences['michelin_preference'] = high_rated_reviews.filter(restaurant__michelin_stars__gt=0).count() / max(total_reviews, 1)
        
        return preferences
    
    def _calculate_user_preference_score(self, restaurant: Restaurant, preferences: Dict) -> float:
        """Calculate how well a restaurant matches user preferences."""
        score = 0.0
        
        # Cuisine preference (40% weight)
        if restaurant.cuisine_type and restaurant.cuisine_type in preferences['cuisines']:
            cuisine_score = preferences['cuisines'][restaurant.cuisine_type] / sum(preferences['cuisines'].values())
            score += cuisine_score * 0.4
        
        # Price preference (20% weight)
        if restaurant.price_range and restaurant.price_range in preferences['price_ranges']:
            price_score = preferences['price_ranges'][restaurant.price_range] / sum(preferences['price_ranges'].values())
            score += price_score * 0.2
        
        # Location preference (20% weight)
        if restaurant.city and restaurant.city in preferences['locations']:
            location_score = preferences['locations'][restaurant.city] / sum(preferences['locations'].values())
            score += location_score * 0.2
        
        # Michelin preference (20% weight)
        if restaurant.michelin_stars > 0 and preferences['michelin_preference'] > 0.5:
            score += 0.2
        elif restaurant.michelin_stars == 0 and preferences['michelin_preference'] < 0.3:
            score += 0.1
        
        return min(score, 1.0)
    
    def _get_match_reasons(self, restaurant: Restaurant, query: str, location: str, filters: Dict) -> List[str]:
        """Get reasons why a restaurant matches the search."""
        reasons = []
        
        if query:
            if query.lower() in restaurant.name.lower():
                reasons.append(f"Name matches '{query}'")
            if restaurant.cuisine_type and query.lower() in restaurant.cuisine_type.lower():
                reasons.append(f"Cuisine matches '{query}'")
        
        if location:
            if location.lower() in restaurant.city.lower():
                reasons.append(f"Located in {restaurant.city}")
        
        if restaurant.michelin_stars > 0:
            reasons.append(f"{restaurant.michelin_stars} Michelin star{'s' if restaurant.michelin_stars > 1 else ''}")
        
        if restaurant.rating and restaurant.rating >= 4.0:
            reasons.append(f"Highly rated ({restaurant.rating:.1f}/5)")
        
        return reasons
    
    def _get_similarity_reasons(self, restaurant1: Restaurant, restaurant2: Restaurant) -> List[str]:
        """Get reasons why two restaurants are similar."""
        reasons = []
        
        if restaurant1.cuisine_type == restaurant2.cuisine_type:
            reasons.append(f"Same cuisine ({restaurant1.cuisine_type})")
        
        if restaurant1.city == restaurant2.city:
            reasons.append(f"Same city ({restaurant1.city})")
        
        if restaurant1.price_range == restaurant2.price_range:
            reasons.append(f"Similar price range ({restaurant1.price_range})")
        
        if restaurant1.michelin_stars == restaurant2.michelin_stars and restaurant1.michelin_stars > 0:
            reasons.append(f"Both have {restaurant1.michelin_stars} Michelin star{'s' if restaurant1.michelin_stars > 1 else ''}")
        
        return reasons
    
    def _get_preference_reasons(self, restaurant: Restaurant, preferences: Dict) -> List[str]:
        """Get reasons why a restaurant matches user preferences."""
        reasons = []
        
        if restaurant.cuisine_type in preferences['cuisines']:
            reasons.append(f"You like {restaurant.cuisine_type} cuisine")
        
        if restaurant.price_range in preferences['price_ranges']:
            reasons.append(f"Matches your price preference ({restaurant.price_range})")
        
        if restaurant.city in preferences['locations']:
            reasons.append(f"You've enjoyed restaurants in {restaurant.city}")
        
        if restaurant.michelin_stars > 0 and preferences['michelin_preference'] > 0.5:
            reasons.append("You prefer Michelin-starred restaurants")
        
        return reasons
    
    def _get_popularity_reasons(self, restaurant: Restaurant) -> List[str]:
        """Get reasons why a restaurant is popular."""
        reasons = []
        
        if restaurant.michelin_stars > 0:
            reasons.append(f"{restaurant.michelin_stars} Michelin star{'s' if restaurant.michelin_stars > 1 else ''}")
        
        if restaurant.rating and restaurant.rating >= 4.0:
            reasons.append(f"Highly rated ({restaurant.rating:.1f}/5)")
        
        if restaurant.review_count and restaurant.review_count >= 10:
            reasons.append(f"Popular ({restaurant.review_count} reviews)")
        
        if restaurant.is_featured:
            reasons.append("Featured restaurant")
        
        return reasons