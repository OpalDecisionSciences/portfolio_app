#!/usr/bin/env python3
"""
Health check test for all services in the portfolio application.
Tests Django, RAG service, Redis, and PostgreSQL connectivity.
"""

import os
import sys
import requests
import redis
import time
from pathlib import Path

# Add Django project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "django_app" / "src"))

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio_project.settings")

import django
django.setup()

from django.core.management.color import make_style
from django.db import connection

style = make_style()

def test_django_health():
    """Test Django application health."""
    print(style.HTTP_INFO("Testing Django application health..."))
    
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            
        print(style.SUCCESS("✅ Django application healthy"))
        return True
        
    except Exception as e:
        print(style.ERROR(f"❌ Django health check failed: {e}"))
        return False

def test_redis_connection():
    """Test Redis connection."""
    print(style.HTTP_INFO("Testing Redis connection..."))
    
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        
        # Test basic operations
        r.ping()
        r.set('health_check', 'ok', ex=10)
        result = r.get('health_check')
        
        if result == b'ok':
            print(style.SUCCESS("✅ Redis connection healthy"))
            return True
        else:
            print(style.ERROR("❌ Redis health check failed: invalid response"))
            return False
            
    except Exception as e:
        print(style.ERROR(f"❌ Redis health check failed: {e}"))
        return False

def test_rag_service_health():
    """Test RAG service health."""
    print(style.HTTP_INFO("Testing RAG service health..."))
    
    try:
        rag_url = os.getenv('RAG_SERVICE_URL', 'http://localhost:8001')
        health_url = f"{rag_url}/health"
        
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            print(style.SUCCESS("✅ RAG service healthy"))
            return True
        else:
            print(style.ERROR(f"❌ RAG service health check failed: HTTP {response.status_code}"))
            return False
            
    except requests.exceptions.ConnectionError:
        print(style.WARNING("⚠️  RAG service not accessible (may not be running)"))
        return False
    except Exception as e:
        print(style.ERROR(f"❌ RAG service health check failed: {e}"))
        return False

def test_celery_health():
    """Test Celery worker health."""
    print(style.HTTP_INFO("Testing Celery worker health..."))
    
    try:
        from celery import Celery
        
        app = Celery('portfolio_project')
        app.config_from_object('django.conf:settings', namespace='CELERY')
        
        # Check if workers are available
        inspect = app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            worker_count = len(stats)
            print(style.SUCCESS(f"✅ Celery healthy ({worker_count} workers active)"))
            return True
        else:
            print(style.WARNING("⚠️  No Celery workers found"))
            return False
            
    except Exception as e:
        print(style.ERROR(f"❌ Celery health check failed: {e}"))
        return False

def test_openai_api():
    """Test OpenAI API connectivity."""
    print(style.HTTP_INFO("Testing OpenAI API connectivity..."))
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print(style.WARNING("⚠️  OPENAI_API_KEY not set"))
            return False
            
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Simple API test
        response = client.models.list()
        
        if response.data:
            print(style.SUCCESS("✅ OpenAI API connectivity healthy"))
            return True
        else:
            print(style.ERROR("❌ OpenAI API test failed: no models returned"))
            return False
            
    except Exception as e:
        print(style.ERROR(f"❌ OpenAI API health check failed: {e}"))
        return False

def test_google_maps_api():
    """Test Google Maps API connectivity."""
    print(style.HTTP_INFO("Testing Google Maps API connectivity..."))
    
    try:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            print(style.WARNING("⚠️  GOOGLE_MAPS_API_KEY not set"))
            return False
            
        # Test geocoding API
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address=1600+Amphitheatre+Parkway,+Mountain+View,+CA&key={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK':
                print(style.SUCCESS("✅ Google Maps API connectivity healthy"))
                return True
            else:
                print(style.ERROR(f"❌ Google Maps API error: {data.get('status')}"))
                return False
        else:
            print(style.ERROR(f"❌ Google Maps API health check failed: HTTP {response.status_code}"))
            return False
            
    except Exception as e:
        print(style.ERROR(f"❌ Google Maps API health check failed: {e}"))
        return False

def main():
    """Run all health checks."""
    print(style.HTTP_SUCCESS("🏥 Portfolio Application Health Check Suite"))
    print("=" * 60)
    
    tests = [
        ("Django Application", test_django_health),
        ("Redis Cache", test_redis_connection),
        ("RAG Service", test_rag_service_health),
        ("Celery Workers", test_celery_health),
        ("OpenAI API", test_openai_api),
        ("Google Maps API", test_google_maps_api),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 40)
        result = test_func()
        results.append((test_name, result))
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n" + "=" * 60)
    print(style.HTTP_SUCCESS("📊 Health Check Summary"))
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        if result:
            print(style.SUCCESS(f"✅ {test_name}"))
            passed += 1
        else:
            print(style.ERROR(f"❌ {test_name}"))
    
    total = len(results)
    print(f"\n{passed}/{total} health checks passed")
    
    if passed == total:
        print(style.SUCCESS("🎉 All systems healthy!"))
        return 0
    elif passed >= total * 0.75:
        print(style.WARNING("⚠️  Most systems healthy, review failed checks"))
        return 1
    else:
        print(style.ERROR("❌ Multiple system failures detected"))
        return 2

if __name__ == "__main__":
    exit(main())