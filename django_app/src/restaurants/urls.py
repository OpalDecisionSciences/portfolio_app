"""
URLs for the restaurants app.
"""
from django.urls import path
from . import views

app_name = 'restaurants'

urlpatterns = [
    # Main restaurant views
    path('', views.RestaurantListView.as_view(), name='restaurant_list'),
    path('<slug:slug>/', views.RestaurantDetailView.as_view(), name='restaurant_detail'),
    path('<slug:slug>/review/', views.add_review, name='add_review'),
    
    # Special collections
    path('collections/featured/', views.featured_restaurants, name='featured_restaurants'),
    path('collections/michelin/', views.michelin_starred_restaurants, name='michelin_starred'),
    
    # API endpoints
    path('api/search/', views.restaurant_search_api, name='restaurant_search_api'),
    path('api/recommendations/', views.restaurant_recommendations_api, name='restaurant_recommendations_api'),
    path('api/<uuid:restaurant_id>/images/', views.restaurant_images_api, name='restaurant_images_api'),
    path('api/stats/', views.restaurant_stats_api, name='restaurant_stats_api'),
    
    # Scraping management
    path('admin/scraping/', views.scraping_jobs, name='scraping_jobs'),
    path('admin/scraping/<uuid:job_id>/', views.scraping_job_detail, name='scraping_job_detail'),
]