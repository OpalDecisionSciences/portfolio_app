"""
Views for the restaurants app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.db import models
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import Restaurant, Chef, MenuSection, MenuItem, RestaurantReview, ScrapingJob, RestaurantImage
import json
import os
from pathlib import Path
from .forms import RestaurantReviewForm, RestaurantSearchForm
from .recommenders import RestaurantRecommender
import requests
from django.conf import settings
import math


def home_view(request):
    """Enhanced home view with dynamic restaurant showcase and intelligent recommendations."""
    
    # Get featured restaurants with high-quality images
    featured_restaurants = get_featured_restaurant_images(max_results=8)
    
    # Get top Michelin-starred restaurants - enhanced with recommendation scoring for authenticated users
    if request.user.is_authenticated:
        # For authenticated users, get a mix of highly-rated and personalized restaurants
        recommender = RestaurantRecommender()
        try:
            # Get some personalized recommendations
            personalized_recs = recommender._get_enhanced_personalized_recommendations(
                user=request.user, max_results=3
            )
            personalized_restaurant_ids = [rec['restaurant'].id for rec in personalized_recs]
            
            # Combine personalized with top Michelin restaurants, avoiding duplicates
            top_restaurants = Restaurant.objects.filter(
                is_active=True,
                michelin_stars__gte=2
            ).exclude(
                id__in=personalized_restaurant_ids
            ).select_related().prefetch_related('images').order_by(
                '-michelin_stars', '-rating'
            )[:3]
            
            # Add personalized restaurants to the top restaurants
            top_restaurants = list(top_restaurants) + [rec['restaurant'] for rec in personalized_recs]
        except Exception:
            # Fallback to standard approach if recommendation fails
            top_restaurants = Restaurant.objects.filter(
                is_active=True,
                michelin_stars__gte=2
            ).select_related().prefetch_related('images').order_by(
                '-michelin_stars', '-rating'
            )[:6]
    else:
        # For anonymous users, show top restaurants by rating and popularity
        top_restaurants = Restaurant.objects.filter(
            is_active=True,
            michelin_stars__gte=2
        ).select_related().prefetch_related('images').order_by(
            '-michelin_stars', '-rating'
        )[:6]
    
    # Get restaurants with best scenery images for visual showcase
    visual_showcase = RestaurantImage.objects.filter(
        ai_category='scenery_ambiance',
        category_confidence__gte=0.85,
        restaurant__is_active=True,
        restaurant__michelin_stars__gte=1
    ).select_related('restaurant').order_by('-category_confidence')[:12]
    
    # Get restaurant statistics for display
    stats = {
        'total_restaurants': Restaurant.objects.filter(is_active=True).count(),
        'michelin_starred': Restaurant.objects.filter(is_active=True, michelin_stars__gte=1).count(),
        'countries': Restaurant.objects.filter(is_active=True).values('country').distinct().count(),
        'total_images': RestaurantImage.objects.count(),
    }
    
    context = {
        'featured_restaurants': featured_restaurants,
        'top_restaurants': top_restaurants,
        'visual_showcase': visual_showcase,
        'stats': stats,
    }
    
    return render(request, 'home.html', context)


def get_featured_restaurant_images(max_results=12):
    """Get featured restaurant images for home page showcase."""
    return RestaurantImage.objects.filter(
        ai_category='scenery_ambiance',
        category_confidence__gte=0.85,
        restaurant__michelin_stars__gte=2,
        restaurant__is_active=True
    ).select_related('restaurant').order_by(
        '-restaurant__michelin_stars', 
        '-category_confidence'
    )[:max_results]


class RestaurantListView(ListView):
    """List view for restaurants with filtering and pagination."""
    
    model = Restaurant
    template_name = 'restaurants/restaurant_list.html'
    context_object_name = 'restaurants'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Restaurant.objects.filter(is_active=True)
        
        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(city__icontains=search_query) |
                Q(country__icontains=search_query) |
                Q(cuisine_type__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filters with case-insensitive matching
        country = self.request.GET.get('country', '')
        if country:
            queryset = queryset.filter(country__iexact=country)
        
        city = self.request.GET.get('city', '')
        if city:
            queryset = queryset.filter(city__iexact=city)
        
        cuisine = self.request.GET.get('cuisine', '')
        if cuisine:
            queryset = queryset.filter(cuisine_type__iexact=cuisine)
        
        stars = self.request.GET.get('stars', '')
        if stars:
            queryset = queryset.filter(michelin_stars=int(stars))
        
        price_range = self.request.GET.get('price_range', '')
        if price_range:
            queryset = queryset.filter(price_range=price_range)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')
        if sort_by == 'rating':
            queryset = queryset.order_by('-rating', 'name')
        elif sort_by == 'stars':
            queryset = queryset.order_by('-michelin_stars', 'name')
        elif sort_by == 'city':
            queryset = queryset.order_by('city', 'name')
        else:  # default to name
            queryset = queryset.order_by('name')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['countries'] = Restaurant.objects.filter(is_active=True).values_list('country', flat=True).distinct().order_by('country')
        context['cities'] = Restaurant.objects.filter(is_active=True).values_list('city', flat=True).distinct().order_by('city')
        context['cuisines'] = Restaurant.objects.filter(is_active=True).values_list('cuisine_type', flat=True).distinct().order_by('cuisine_type')
        
        # Add current filter values
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'country': self.request.GET.get('country', ''),
            'city': self.request.GET.get('city', ''),
            'cuisine': self.request.GET.get('cuisine', ''),
            'stars': self.request.GET.get('stars', ''),
            'price_range': self.request.GET.get('price_range', ''),
            'sort': self.request.GET.get('sort', 'name'),
        }
        
        return context


class RestaurantDetailView(DetailView):
    """Detail view for a single restaurant."""
    
    model = Restaurant
    template_name = 'restaurants/restaurant_detail.html'
    context_object_name = 'restaurant'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return Restaurant.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.object
        
        # Add related data
        context['chefs'] = restaurant.chefs.all()
        context['menu_sections'] = restaurant.menu_sections.prefetch_related('items').all()
        context['images'] = restaurant.images.all().order_by('order')
        context['reviews'] = restaurant.reviews.filter(is_approved=True).order_by('-created_at')[:5]
        
        # Add categorized images
        context['menu_images'] = restaurant.images.filter(ai_category='menu_item').order_by('-category_confidence')[:6]
        context['ambiance_images'] = restaurant.images.filter(ai_category='scenery_ambiance').order_by('-category_confidence')[:6]
        context['featured_image'] = restaurant.images.filter(is_featured=True).first() or restaurant.images.first()
        
        # Add review form
        if self.request.user.is_authenticated:
            context['review_form'] = RestaurantReviewForm()
        
        # Add statistics
        context['avg_rating'] = restaurant.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
        context['review_count'] = restaurant.reviews.filter(is_approved=True).count()
        
        # Add similar restaurants using recommender
        recommender = RestaurantRecommender()
        user = self.request.user if self.request.user.is_authenticated else None
        similar_restaurants = recommender.get_recommendations(
            user=user,
            restaurant_id=str(restaurant.id),
            max_results=6
        )
        context['similar_restaurants'] = similar_restaurants
        
        # Add document.txt content (restaurant about information)
        document_content = self._get_restaurant_document_content(restaurant)
        if document_content:
            context['document_content'] = document_content
        
        # Add timezone information if available
        timezone_info = self._get_restaurant_timezone_info(restaurant)
        if timezone_info:
            context['timezone_info'] = timezone_info
        
        return context
    
    def _get_restaurant_document_content(self, restaurant):
        """Get document.txt content for restaurant about section."""
        try:
            # Look for document.txt files in restaurant_docs directory
            docs_dir = Path(__file__).resolve().parent.parent.parent / "data_pipeline" / "src" / "scrapers" / "restaurant_docs"
            
            # Create clean filename from restaurant name
            clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in restaurant.name.lower())[:50].strip("_")
            potential_files = [
                docs_dir / f"{clean_name}_document.txt",
                docs_dir / f"{clean_name}.txt",
            ]
            
            # Try to find and read document file
            for doc_file in potential_files:
                if doc_file.exists():
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            return content
            
            # Fallback: generate document content from scraped data if available
            if restaurant.scraped_content:
                return self._generate_about_from_scraped_content(restaurant)
                
        except Exception as e:
            pass  # Silently fail, document content is optional
        
        return None
    
    def _generate_about_from_scraped_content(self, restaurant):
        """Generate about section from existing restaurant data."""
        about_parts = []
        
        if restaurant.name:
            about_parts.append(f"# {restaurant.name}")
        
        if restaurant.cuisine_type:
            about_parts.append(f"\n## Cuisine\n{restaurant.cuisine_type}")
        
        if restaurant.atmosphere:
            about_parts.append(f"\n## Atmosphere\n{restaurant.atmosphere}")
        
        if restaurant.city and restaurant.country:
            about_parts.append(f"\n## Location\n{restaurant.city}, {restaurant.country}")
        
        if restaurant.description:
            about_parts.append(f"\n## About\n{restaurant.description}")
        
        if about_parts:
            return '\n'.join(about_parts)
        
        return None
    
    def _get_restaurant_timezone_info(self, restaurant):
        """Get timezone information for the restaurant."""
        try:
            # Check if restaurant has timezone_info field with JSON data
            if hasattr(restaurant, 'timezone_info') and restaurant.timezone_info:
                try:
                    return json.loads(restaurant.timezone_info)
                except (json.JSONDecodeError, AttributeError):
                    pass
        except Exception:
            pass
        
        return None


@login_required
@require_http_methods(["POST"])
def add_review(request, restaurant_slug):
    """Add a review for a restaurant."""
    restaurant = get_object_or_404(Restaurant, slug=restaurant_slug, is_active=True)
    
    # Check if user has already reviewed this restaurant
    existing_review = RestaurantReview.objects.filter(
        restaurant=restaurant, 
        user=request.user
    ).first()
    
    if existing_review:
        messages.warning(request, "You have already reviewed this restaurant.")
        return redirect('restaurant_detail', slug=restaurant_slug)
    
    form = RestaurantReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.restaurant = restaurant
        review.user = request.user
        review.save()
        
        messages.success(request, "Your review has been submitted and is pending approval.")
        return redirect('restaurant_detail', slug=restaurant_slug)
    else:
        messages.error(request, "Please correct the errors in your review.")
        return redirect('restaurant_detail', slug=restaurant_slug)


def featured_restaurants(request):
    """View for featured restaurants."""
    restaurants = Restaurant.objects.filter(is_active=True, is_featured=True)
    
    context = {
        'restaurants': restaurants,
        'title': 'Featured Restaurants'
    }
    
    return render(request, 'restaurants/featured_restaurants.html', context)


def michelin_starred_restaurants(request):
    """View for Michelin starred restaurants."""
    restaurants = Restaurant.objects.filter(
        is_active=True, 
        michelin_stars__gt=0
    ).order_by('-michelin_stars', 'name')
    
    context = {
        'restaurants': restaurants,
        'title': 'Michelin Starred Restaurants'
    }
    
    return render(request, 'restaurants/michelin_starred.html', context)


def restaurant_search_api(request):
    """Enhanced API endpoint for restaurant search with recommendations and images."""
    query = request.GET.get('q', '')
    location = request.GET.get('location', '')
    cuisine = request.GET.get('cuisine', '')
    price_range = request.GET.get('price_range', '')
    min_stars = request.GET.get('min_stars', '')
    max_results = int(request.GET.get('max_results', 10))
    
    recommender = RestaurantRecommender()
    
    # Build filters
    filters = {}
    if cuisine:
        filters['cuisine'] = cuisine
    if price_range:
        filters['price_range'] = price_range
    if min_stars:
        filters['min_stars'] = int(min_stars)
    
    # Get search results with recommendations
    if query or location or filters:
        search_results = recommender.search_restaurants(
            query=query,
            location=location,
            filters=filters,
            max_results=max_results
        )
    else:
        # Return popular restaurants for empty search
        search_results = recommender._get_popular_restaurants(max_results)
    
    # Format results for API response
    results = []
    for result in search_results:
        restaurant = result['restaurant']
        featured_image = result.get('featured_image')
        
        restaurant_data = {
            'id': str(restaurant.id),
            'name': restaurant.name,
            'city': restaurant.city,
            'country': restaurant.country,
            'cuisine_type': restaurant.cuisine_type,
            'michelin_stars': restaurant.michelin_stars,
            'rating': float(restaurant.rating) if restaurant.rating else None,
            'price_range': restaurant.price_range,
            'url': restaurant.get_absolute_url(),
            'description': restaurant.description[:200] + '...' if len(restaurant.description) > 200 else restaurant.description,
            'image_count': result.get('image_count', 0),
            'match_reasons': result.get('match_reasons', []),
            'relevance_score': result.get('relevance_score', result.get('popularity_score', 0))
        }
        
        # Add featured image data
        if featured_image:
            restaurant_data['featured_image'] = featured_image
        
        results.append(restaurant_data)
    
    return JsonResponse({
        'results': results,
        'total_count': len(results),
        'query': query,
        'location': location,
        'filters': filters
    })


def geocode_address(address):
    """Geocode an address using Google Maps API."""
    google_maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
    if not google_maps_api_key:
        return None
    
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': address,
            'key': google_maps_api_key
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data['status'] == 'OK' and data['results']:
            location = data['results'][0]['geometry']['location']
            return {
                'lat': location['lat'],
                'lng': location['lng'],
                'formatted_address': data['results'][0]['formatted_address']
            }
    except Exception as e:
        print(f"Geocoding error: {e}")
    
    return None


def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points using Haversine formula."""
    R = 6371  # Earth's radius in kilometers
    
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlng/2) * math.sin(dlng/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance


def geographic_search_api(request):
    """Enhanced geographic search with Google Maps integration."""
    address = request.GET.get('address', '')
    query = request.GET.get('q', '')
    max_results = int(request.GET.get('max_results', 10))
    radius_km = float(request.GET.get('radius', 50))  # Default 50km radius
    
    result = {
        'query': query,
        'address': address,
        'results': [],
        'fallback_results': [],
        'message': '',
        'search_type': 'local'
    }
    
    # First try to geocode the address
    geocoded = geocode_address(address) if address else None
    
    if geocoded:
        user_lat = geocoded['lat']
        user_lng = geocoded['lng']
        
        # Find restaurants with coordinates within radius
        restaurants_with_coords = Restaurant.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related().prefetch_related('images')
        
        nearby_restaurants = []
        for restaurant in restaurants_with_coords:
            distance = calculate_distance(
                user_lat, user_lng,
                float(restaurant.latitude), float(restaurant.longitude)
            )
            if distance <= radius_km:
                nearby_restaurants.append({
                    'restaurant': restaurant,
                    'distance': distance
                })
        
        # Sort by distance
        nearby_restaurants.sort(key=lambda x: x['distance'])
        
        # Apply query filter if provided
        if query:
            filtered_restaurants = []
            query_lower = query.lower()
            for item in nearby_restaurants:
                restaurant = item['restaurant']
                if (query_lower in restaurant.name.lower() or
                    (restaurant.cuisine_type and query_lower in restaurant.cuisine_type.lower()) or
                    query_lower in restaurant.city.lower()):
                    filtered_restaurants.append(item)
            nearby_restaurants = filtered_restaurants
        
        # Format results
        for item in nearby_restaurants[:max_results]:
            restaurant = item['restaurant']
            featured_image = get_restaurant_featured_image(restaurant)
            
            result['results'].append({
                'id': str(restaurant.id),
                'name': restaurant.name,
                'city': restaurant.city,
                'country': restaurant.country,
                'cuisine_type': restaurant.cuisine_type,
                'michelin_stars': restaurant.michelin_stars,
                'rating': float(restaurant.rating) if restaurant.rating else None,
                'price_range': restaurant.price_range,
                'url': restaurant.get_absolute_url(),
                'description': restaurant.description[:200] + '...' if len(restaurant.description) > 200 else restaurant.description,
                'distance_km': round(item['distance'], 1),
                'featured_image': featured_image,
                'image_count': restaurant.images.count(),
            })
        
        if result['results']:
            result['message'] = f"Found {len(result['results'])} restaurant{'s' if len(result['results']) != 1 else ''} within {radius_km}km of {geocoded['formatted_address']}"
        else:
            # Fallback: find nearest Michelin restaurants regardless of query
            michelin_restaurants = []
            for restaurant in restaurants_with_coords.filter(michelin_stars__gt=0):
                distance = calculate_distance(
                    user_lat, user_lng,
                    float(restaurant.latitude), float(restaurant.longitude)
                )
                michelin_restaurants.append({
                    'restaurant': restaurant,
                    'distance': distance
                })
            
            michelin_restaurants.sort(key=lambda x: x['distance'])
            
            # Format fallback results
            for item in michelin_restaurants[:max_results]:
                restaurant = item['restaurant']
                featured_image = get_restaurant_featured_image(restaurant)
                
                result['fallback_results'].append({
                    'id': str(restaurant.id),
                    'name': restaurant.name,
                    'city': restaurant.city,
                    'country': restaurant.country,
                    'cuisine_type': restaurant.cuisine_type,
                    'michelin_stars': restaurant.michelin_stars,
                    'rating': float(restaurant.rating) if restaurant.rating else None,
                    'price_range': restaurant.price_range,
                    'url': restaurant.get_absolute_url(),
                    'description': restaurant.description[:200] + '...' if len(restaurant.description) > 200 else restaurant.description,
                    'distance_km': round(item['distance'], 1),
                    'featured_image': featured_image,
                    'image_count': restaurant.images.count(),
                })
            
            if result['fallback_results']:
                result['message'] = f"No restaurants found matching '{query}' near {geocoded['formatted_address']}. Here are the nearest Michelin-starred restaurants:"
                result['search_type'] = 'fallback_nearest_michelin'
            else:
                result['message'] = f"No restaurants found near {geocoded['formatted_address']}. Try expanding your search area or browse our global collection."
                result['search_type'] = 'no_results'
    
    else:
        # Fallback to text-based location search
        if address:
            result['message'] = f"Could not locate '{address}'. Showing restaurants matching this location name:"
        else:
            result['message'] = "Please enter a location to find nearby restaurants."
        
        # Try to find restaurants by city/country name matching the address
        if address:
            restaurants = Restaurant.objects.filter(
                Q(city__icontains=address) | Q(country__icontains=address),
                is_active=True
            ).select_related().prefetch_related('images')
            
            if query:
                restaurants = restaurants.filter(
                    Q(name__icontains=query) |
                    Q(cuisine_type__icontains=query) |
                    Q(description__icontains=query)
                )
            
            # Format results
            for restaurant in restaurants[:max_results]:
                featured_image = get_restaurant_featured_image(restaurant)
                
                result['results'].append({
                    'id': str(restaurant.id),
                    'name': restaurant.name,
                    'city': restaurant.city,
                    'country': restaurant.country,
                    'cuisine_type': restaurant.cuisine_type,
                    'michelin_stars': restaurant.michelin_stars,
                    'rating': float(restaurant.rating) if restaurant.rating else None,
                    'price_range': restaurant.price_range,
                    'url': restaurant.get_absolute_url(),
                    'description': restaurant.description[:200] + '...' if len(restaurant.description) > 200 else restaurant.description,
                    'featured_image': featured_image,
                    'image_count': restaurant.images.count(),
                })
            
            result['search_type'] = 'text_location_match'
    
    return JsonResponse(result)


def get_restaurant_featured_image(restaurant):
    """Helper function to get featured image for a restaurant."""
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


def restaurant_stats_api(request):
    """API endpoint for restaurant statistics."""
    stats = {
        'total_restaurants': Restaurant.objects.filter(is_active=True).count(),
        'michelin_starred': Restaurant.objects.filter(is_active=True, michelin_stars__gt=0).count(),
        'countries': Restaurant.objects.filter(is_active=True).values('country').distinct().count(),
        'cities': Restaurant.objects.filter(is_active=True).values('city').distinct().count(),
        'cuisines': Restaurant.objects.filter(is_active=True).values('cuisine_type').distinct().count(),
        'avg_rating': Restaurant.objects.filter(is_active=True).aggregate(Avg('rating'))['rating__avg'] or 0,
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def restaurant_timezone_status_api(request, restaurant_id):
    """API endpoint to get restaurant's current status in its local timezone."""
    try:
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        
        # Get restaurant's current local time and status
        local_time = restaurant.get_current_local_time()
        open_status = restaurant.is_currently_open()
        
        response_data = {
            'restaurant_name': restaurant.name,
            'location': f"{restaurant.city}, {restaurant.country}",
            'timezone': restaurant.get_timezone_display(),
            'local_time': local_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'local_time_12h': local_time.strftime('%I:%M %p %Z'),
            'is_open': open_status['is_open'],
            'status': open_status['status'],
            'opening_hours': restaurant.opening_hours or 'Not available'
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'error': 'Unable to get restaurant status',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def restaurants_open_now_api(request):
    """API endpoint to get restaurants currently open in their local timezones."""
    try:
        # Get restaurants with timezone info
        restaurants = Restaurant.objects.filter(
            is_active=True,
            timezone_info__isnull=False
        ).exclude(opening_hours='')[:50]  # Limit for performance
        
        open_restaurants = []
        
        for restaurant in restaurants:
            try:
                status = restaurant.is_currently_open()
                if status['is_open'] is True:
                    local_time = restaurant.get_current_local_time()
                    open_restaurants.append({
                        'id': str(restaurant.id),
                        'name': restaurant.name,
                        'location': f"{restaurant.city}, {restaurant.country}",
                        'local_time': local_time.strftime('%H:%M %Z'),
                        'status': status['status'],
                        'michelin_stars': restaurant.michelin_stars,
                        'url': restaurant.get_absolute_url()
                    })
            except Exception:
                continue  # Skip restaurants with invalid data
        
        return JsonResponse({
            'open_restaurants': open_restaurants,
            'count': len(open_restaurants),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'error': 'Unable to get open restaurants',
            'details': str(e)
        }, status=500)


@csrf_exempt
def restaurant_recommendations_api(request):
    """API endpoint for personalized restaurant recommendations."""
    user = request.user if request.user.is_authenticated else None
    restaurant_id = request.GET.get('restaurant_id', '')
    location = request.GET.get('location', '')
    cuisine = request.GET.get('cuisine', '')
    price_range = request.GET.get('price_range', '')
    max_results = int(request.GET.get('max_results', 6))
    
    recommender = RestaurantRecommender()
    
    # Get enhanced recommendations with collaborative filtering
    if user and user.is_authenticated:
        recommendations = recommender._get_enhanced_personalized_recommendations(
            user=user,
            max_results=max_results,
            location=location if location else None,
            cuisine_preference=cuisine if cuisine else None,
            price_range=price_range if price_range else None
        )
    else:
        # Fallback to original method for anonymous users
        recommendations = recommender.get_recommendations(
            user=user,
            restaurant_id=restaurant_id if restaurant_id else None,
            location=location if location else None,
            cuisine_preference=cuisine if cuisine else None,
            price_range=price_range if price_range else None,
            max_results=max_results
        )
    
    # Format results for API response
    results = []
    for rec in recommendations:
        restaurant = rec['restaurant']
        featured_image = rec.get('featured_image')
        
        recommendation_data = {
            'id': str(restaurant.id),
            'name': restaurant.name,
            'city': restaurant.city,
            'country': restaurant.country,
            'cuisine_type': restaurant.cuisine_type,
            'michelin_stars': restaurant.michelin_stars,
            'rating': float(restaurant.rating) if restaurant.rating else None,
            'price_range': restaurant.price_range,
            'url': restaurant.get_absolute_url(),
            'description': restaurant.description[:150] + '...' if len(restaurant.description) > 150 else restaurant.description,
            'image_count': rec.get('image_count', 0),
            'recommendation_score': rec.get('similarity_score', rec.get('preference_score', rec.get('popularity_score', 0))),
            'reasons': rec.get('similar_features', rec.get('recommendation_reasons', rec.get('recommendation_reasons', [])))
        }
        
        # Add featured image data
        if featured_image:
            recommendation_data['featured_image'] = featured_image
        
        results.append(recommendation_data)
    
    return JsonResponse({
        'recommendations': results,
        'total_count': len(results),
        'recommendation_type': 'similar' if restaurant_id else ('personalized' if user else 'popular'),
        'user_authenticated': bool(user)
    })


def restaurant_images_api(request, restaurant_id):
    """API endpoint for restaurant images by category."""
    try:
        restaurant = Restaurant.objects.get(id=restaurant_id, is_active=True)
    except Restaurant.DoesNotExist:
        return JsonResponse({'error': 'Restaurant not found'}, status=404)
    
    category = request.GET.get('category', 'all')  # 'all', 'menu_item', 'scenery_ambiance'
    limit = int(request.GET.get('limit', 20))
    
    # Filter images by category
    images = restaurant.images.all()
    if category == 'menu_item':
        images = images.filter(ai_category='menu_item')
    elif category == 'scenery_ambiance':
        images = images.filter(ai_category='scenery_ambiance')
    elif category == 'featured':
        images = images.filter(Q(is_featured=True) | Q(is_menu_highlight=True) | Q(is_ambiance_highlight=True))
    
    # Order by confidence and limit results
    images = images.order_by('-category_confidence', '-created_at')[:limit]
    
    # Format image data
    image_data = []
    for image in images:
        image_info = {
            'id': str(image.id),
            'url': image.source_url if image.source_url else (image.image.url if image.image else None),
            'caption': image.get_display_name(),
            'ai_category': image.ai_category,
            'ai_labels': image.ai_labels[:5] if image.ai_labels else [],
            'ai_description': image.ai_description,
            'confidence': image.category_confidence,
            'is_featured': image.is_featured,
            'is_menu_highlight': image.is_menu_highlight,
            'is_ambiance_highlight': image.is_ambiance_highlight,
            'width': image.width,
            'height': image.height
        }
        image_data.append(image_info)
    
    return JsonResponse({
        'restaurant_id': str(restaurant.id),
        'restaurant_name': restaurant.name,
        'images': image_data,
        'category': category,
        'total_count': len(image_data),
        'total_images': restaurant.images.count()
    })


@login_required
def scraping_jobs(request):
    """View for scraping job management."""
    jobs = ScrapingJob.objects.all().order_by('-created_at')
    
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'jobs': page_obj,
        'title': 'Scraping Jobs'
    }
    
    return render(request, 'restaurants/scraping_jobs.html', context)


@login_required
def scraping_job_detail(request, job_id):
    """View for scraping job details."""
    job = get_object_or_404(ScrapingJob, id=job_id)
    
    context = {
        'job': job,
        'title': f'Scraping Job: {job.job_name}'
    }
    
    return render(request, 'restaurants/scraping_job_detail.html', context)


def gallery_view(request):
    """Gallery view showing restaurants with image carousels, grouped by restaurant."""
    
    # Build base queryset for restaurants with images
    restaurants = Restaurant.objects.filter(
        is_active=True,
        images__isnull=False
    ).prefetch_related('images').distinct()
    
    # Enhanced filtering with AI labels support  
    category = request.GET.get('category', '')
    if category:
        # Check if it's an AI label or traditional category
        if category in ['scenery_ambiance', 'menu_item', 'uncategorized']:
            restaurants = restaurants.filter(images__ai_category=category)
        else:
            # Filter by AI labels for more granular filtering
            restaurants = restaurants.filter(images__ai_labels__icontains=category)
    
    country = request.GET.get('country', '')
    if country:
        restaurants = restaurants.filter(country=country)
    
    cuisine = request.GET.get('cuisine', '')
    if cuisine:
        restaurants = restaurants.filter(cuisine_type__iexact=cuisine)
    
    # Search with AI labels support
    search_query = request.GET.get('search', '')
    if search_query:
        restaurants = restaurants.filter(
            Q(name__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(images__caption__icontains=search_query) |
            Q(images__ai_category__icontains=search_query) |
            Q(images__ai_labels__icontains=search_query) |
            Q(images__ai_description__icontains=search_query)
        ).distinct()
    
    # Order by restaurants with most images first, then by name
    restaurants = restaurants.annotate(
        image_count=models.Count('images')
    ).order_by('-image_count', 'name')
    
    # Pagination - restaurants per page instead of images
    paginator = Paginator(restaurants, 12)  # 12 restaurants per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate total images for display
    total_images = RestaurantImage.objects.filter(
        restaurant__in=restaurants
    ).count()
    
    # Get improved filter options
    
    # 1. Enhanced Categories: Use top AI labels instead of basic categories
    from collections import Counter
    from itertools import chain
    
    # Get all AI labels and count frequency
    all_labels = RestaurantImage.objects.exclude(ai_labels=[]).values_list('ai_labels', flat=True)
    label_counter = Counter()
    for label_list in all_labels:
        if label_list:  # Ensure it's not empty
            label_counter.update(label_list)
    
    # Get top 15 most common AI labels as categories
    top_ai_labels = [label for label, count in label_counter.most_common(15) if count > 5]
    
    # Add traditional categories as backup
    traditional_categories = ['scenery_ambiance', 'menu_item', 'uncategorized']
    categories = traditional_categories + top_ai_labels
    
    # 2. Clean Countries: Filter out non-countries
    import re
    
    # List of common country name patterns to validate
    valid_country_patterns = [
        r'^[A-Z][a-zA-Z\s]+$',  # Starts with capital, contains only letters and spaces
        r'^[A-Z][a-zA-Z]+(\s[A-Z][a-zA-Z]+)*$'  # Proper country name format
    ]
    
    # Get all countries and clean them
    all_countries = Restaurant.objects.filter(
        is_active=True, 
        images__isnull=False
    ).values_list('country', flat=True).distinct()
    
    # Filter out empty/invalid countries and normalize
    clean_countries = set()  # Use set for automatic deduplication
    for country in all_countries:
        if country and country.strip():  # Not empty
            country = country.strip()
            # Filter out obvious non-countries (contains numbers, too many special chars, etc.)
            if (not re.search(r'\d', country) and  # No numbers
                len(country) > 2 and  # Not too short
                len(country) < 50 and  # Not too long
                not country.startswith('A-') and  # Not postal code
                '-' not in country[:3]):  # Not starting with hyphen prefix
                # Normalize country name: title case
                normalized_country = country.title()
                clean_countries.add(normalized_country)
    
    countries = sorted(list(clean_countries))
    
    # 3. Deduplicated Cuisines: Use set to remove duplicates with case normalization
    cuisine_values = Restaurant.objects.filter(
        is_active=True, 
        images__isnull=False
    ).values_list('cuisine_type', flat=True).distinct().exclude(cuisine_type='')
    
    # Normalize and deduplicate cuisines
    normalized_cuisines = set()
    for cuisine in cuisine_values:
        if cuisine and cuisine.strip():
            # Normalize: title case and strip whitespace
            normalized = cuisine.strip().title()
            normalized_cuisines.add(normalized)
    
    cuisines = sorted(list(normalized_cuisines))
    
    context = {
        'restaurants': page_obj,  # Changed from images to restaurants
        'categories': categories,
        'countries': countries,
        'cuisines': cuisines,
        'current_filters': {
            'category': category,
            'country': country,
            'cuisine': cuisine,
            'search': search_query,
        },
        'total_images': total_images,
        'total_restaurants': restaurants.count(),
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    
    return render(request, 'restaurants/gallery.html', context)


@require_http_methods(["GET"])
def personalized_recommendations_api(request):
    """Enhanced API endpoint specifically for personalized recommendations with collaborative filtering."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    user = request.user
    max_results = int(request.GET.get('max_results', 10))
    location = request.GET.get('location', '')
    cuisine = request.GET.get('cuisine', '')
    price_range = request.GET.get('price_range', '')
    
    recommender = RestaurantRecommender()
    
    try:
        # Get enhanced personalized recommendations
        recommendations = recommender._get_enhanced_personalized_recommendations(
            user=user,
            max_results=max_results,
            location=location if location else None,
            cuisine_preference=cuisine if cuisine else None,
            price_range=price_range if price_range else None
        )
        
        # Format results with enhanced data
        results = []
        for rec in recommendations:
            restaurant = rec['restaurant']
            
            recommendation_data = {
                'id': str(restaurant.id),
                'name': restaurant.name,
                'city': restaurant.city,
                'country': restaurant.country,
                'cuisine_type': restaurant.cuisine_type,
                'michelin_stars': restaurant.michelin_stars,
                'rating': float(restaurant.rating) if restaurant.rating else None,
                'price_range': restaurant.price_range,
                'url': restaurant.get_absolute_url(),
                'description': restaurant.description[:200] + '...' if len(restaurant.description) > 200 else restaurant.description,
                'image_count': rec.get('image_count', 0),
                'total_score': rec.get('total_score', 0),
                'favorites_score': rec.get('favorites_score', 0),
                'profile_score': rec.get('profile_score', 0),
                'collaborative_score': rec.get('collaborative_score', 0),
                'review_score': rec.get('review_score', 0),
                'popularity_score': rec.get('popularity_score', 0),
                'explanation': rec.get('explanation', ''),
                'similar_users_count': rec.get('similar_users_count', 0),
                'is_favorited': rec.get('is_favorited', False)
            }
            
            # Add featured image if available
            featured_image = rec.get('featured_image')
            if featured_image:
                recommendation_data['featured_image'] = featured_image
            
            results.append(recommendation_data)
        
        # Get user's favorites summary
        from accounts.models import UserFavoriteRestaurant
        user_favorites_count = UserFavoriteRestaurant.objects.filter(user=user).count()
        
        return JsonResponse({
            'recommendations': results,
            'total_count': len(results),
            'user_favorites_count': user_favorites_count,
            'recommendation_type': 'enhanced_personalized',
            'algorithm': 'collaborative_filtering_hybrid',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'error': 'Unable to generate personalized recommendations',
            'details': str(e)
        }, status=500)