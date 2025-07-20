from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile and Dashboard
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Favorites
    path('favorites/', views.favorites_view, name='favorites'),
    path('favorites/add/<uuid:restaurant_id>/', views.add_favorite_view, name='add_favorite'),
    path('favorites/remove/<uuid:restaurant_id>/', views.remove_favorite_view, name='remove_favorite'),
    path('favorites/edit/<uuid:favorite_id>/', views.edit_favorite_view, name='edit_favorite'),
    
    # Password Reset
    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password-reset/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
]