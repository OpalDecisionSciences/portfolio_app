# Django Portfolio Project Views
"""
System-level views for health checks, error handling, and utility endpoints.
"""

import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db import connection
import redis
import os

logger = logging.getLogger(__name__)


@csrf_exempt
@never_cache
@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        JsonResponse: Health status and system information
    """
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'environment': 'production' if not settings.DEBUG else 'development'
        }
        
        # Check database connectivity
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_data['database'] = 'connected'
        except Exception as e:
            health_data['database'] = f'error: {str(e)}'
            health_data['status'] = 'unhealthy'
        
        # Check Redis connectivity
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.ping()
            health_data['redis'] = 'connected'
        except Exception as e:
            health_data['redis'] = f'error: {str(e)}'
            health_data['status'] = 'degraded'
        
        # Check RAG service
        try:
            import requests
            response = requests.get(f"{settings.RAG_SERVICE_URL}/health", timeout=5)
            if response.status_code == 200:
                health_data['rag_service'] = 'connected'
            else:
                health_data['rag_service'] = f'error: HTTP {response.status_code}'
                health_data['status'] = 'degraded'
        except Exception as e:
            health_data['rag_service'] = f'error: {str(e)}'
            health_data['status'] = 'degraded'
        
        # Return appropriate HTTP status
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return JsonResponse(health_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)


@never_cache
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes deployments.
    
    Returns:
        HttpResponse: Simple OK response if ready
    """
    try:
        # Basic readiness checks
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return HttpResponse("OK", content_type="text/plain")
        
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return HttpResponse("NOT READY", status=503, content_type="text/plain")


@never_cache
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for Kubernetes deployments.
    
    Returns:
        HttpResponse: Simple OK response if alive
    """
    return HttpResponse("OK", content_type="text/plain")


def csrf_failure(request, reason=""):
    """
    Custom CSRF failure view with proper error handling.
    
    Args:
        request: The HTTP request
        reason: Reason for CSRF failure
        
    Returns:
        JsonResponse: Error response with CSRF failure details
    """
    logger.warning(f"CSRF failure from {request.META.get('REMOTE_ADDR')}: {reason}")
    
    return JsonResponse({
        'error': 'CSRF verification failed',
        'message': 'Request blocked for security reasons',
        'code': 'csrf_failure'
    }, status=403)


def custom_404_view(request, exception=None):
    """
    Custom 404 handler that returns JSON for API requests.
    
    Args:
        request: The HTTP request
        exception: The exception that caused the 404
        
    Returns:
        JsonResponse or template: Appropriate 404 response
    """
    # For API requests, return JSON
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'code': 'not_found'
        }, status=404)
    
    # For regular requests, use the template
    from django.shortcuts import render
    return render(request, '404.html', status=404)


def custom_500_view(request):
    """
    Custom 500 handler that returns JSON for API requests.
    
    Args:
        request: The HTTP request
        
    Returns:
        JsonResponse or template: Appropriate 500 response
    """
    # For API requests, return JSON
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'code': 'server_error'
        }, status=500)
    
    # For regular requests, use the template
    from django.shortcuts import render
    return render(request, '500.html', status=500)


def custom_403_view(request, exception=None):
    """
    Custom 403 handler that returns JSON for API requests.
    
    Args:
        request: The HTTP request
        exception: The exception that caused the 403
        
    Returns:
        JsonResponse or template: Appropriate 403 response
    """
    # For API requests, return JSON
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'code': 'forbidden'
        }, status=403)
    
    # For regular requests, use the template
    from django.shortcuts import render
    return render(request, '403.html', status=403)