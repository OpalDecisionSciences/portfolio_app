"""
Views for the restaurants app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Restaurant, Chef, MenuSection, MenuItem, RestaurantReview, ScrapingJob, RestaurantImage
import json
import os
from pathlib import Path
from .forms import RestaurantReviewForm, RestaurantSearchForm
from .recommenders import RestaurantRecommender


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
        
        # Filters
        country = self.request.GET.get('country', '')
        if country:
            queryset = queryset.filter(country=country)
        
        city = self.request.GET.get('city', '')
        if city:
            queryset = queryset.filter(city=city)
        
        cuisine = self.request.GET.get('cuisine', '')
        if cuisine:
            queryset = queryset.filter(cuisine_type=cuisine)
        
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
    
    # Get recommendations
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
    """Gallery view showing all restaurant images with filtering."""
    
    # Get all images with their restaurants
    images = RestaurantImage.objects.select_related('restaurant').filter(
        restaurant__is_active=True
    )
    
    # Filtering
    category = request.GET.get('category', '')
    if category:
        images = images.filter(ai_category=category)
    
    country = request.GET.get('country', '')
    if country:
        images = images.filter(restaurant__country=country)
    
    cuisine = request.GET.get('cuisine', '')
    if cuisine:
        images = images.filter(restaurant__cuisine_type=cuisine)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        images = images.filter(
            Q(restaurant__name__icontains=search_query) |
            Q(restaurant__city__icontains=search_query) |
            Q(caption__icontains=search_query) |
            Q(ai_category__icontains=search_query)
        )
    
    # Order by newest first
    images = images.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(images, 24)  # 24 images per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    categories = RestaurantImage.objects.values_list('ai_category', flat=True).distinct().exclude(ai_category='')
    countries = Restaurant.objects.filter(is_active=True, images__isnull=False).values_list('country', flat=True).distinct()
    cuisines = Restaurant.objects.filter(is_active=True, images__isnull=False).values_list('cuisine_type', flat=True).distinct().exclude(cuisine_type='')
    
    context = {
        'images': page_obj,
        'categories': sorted(categories),
        'countries': sorted(countries),
        'cuisines': sorted(cuisines),
        'current_filters': {
            'category': category,
            'country': country,
            'cuisine': cuisine,
            'search': search_query,
        },
        'total_images': images.count(),
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    
    return render(request, 'restaurants/gallery.html', context)