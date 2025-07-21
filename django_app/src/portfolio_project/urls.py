"""
URL configuration for portfolio_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from restaurants.views import home_view
from .views import health_check, readiness_check, liveness_check

urlpatterns = [
    # System endpoints
    path('health/', health_check, name='health_check'),
    path('ready/', readiness_check, name='readiness_check'),
    path('alive/', liveness_check, name='liveness_check'),
    
    # Admin (use custom URL for security)
    path(f'{getattr(settings, "ADMIN_URL", "admin")}/', admin.site.urls),
    
    # Application URLs
    path('', home_view, name='home'),
    path('restaurants/', include('restaurants.urls')),
    path('accounts/', include('accounts.urls')),
    path('chat/', include('chat.urls')),
    path('api/', include('api.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin customization
admin.site.site_header = "Portfolio Administration"
admin.site.site_title = "Portfolio Admin"
admin.site.index_title = "Welcome to Portfolio Administration"

# Custom error handlers
handler404 = 'portfolio_project.views.custom_404_view'
handler500 = 'portfolio_project.views.custom_500_view'
handler403 = 'portfolio_project.views.custom_403_view'