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

from .models import Restaurant, Chef, MenuSection, MenuItem, RestaurantReview, ScrapingJob
from .forms import RestaurantReviewForm, RestaurantSearchForm


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
        
        # Add review form
        if self.request.user.is_authenticated:
            context['review_form'] = RestaurantReviewForm()
        
        # Add statistics
        context['avg_rating'] = restaurant.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
        context['review_count'] = restaurant.reviews.filter(is_approved=True).count()
        
        return context


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
    """API endpoint for restaurant search autocomplete."""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    restaurants = Restaurant.objects.filter(
        Q(name__icontains=query) | 
        Q(city__icontains=query) | 
        Q(cuisine_type__icontains=query),
        is_active=True
    )[:10]
    
    results = []
    for restaurant in restaurants:
        results.append({
            'id': str(restaurant.id),
            'name': restaurant.name,
            'city': restaurant.city,
            'country': restaurant.country,
            'cuisine_type': restaurant.cuisine_type,
            'michelin_stars': restaurant.michelin_stars,
            'url': restaurant.get_absolute_url()
        })
    
    return JsonResponse({'results': results})


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