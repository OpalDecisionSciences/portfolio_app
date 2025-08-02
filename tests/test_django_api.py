#!/usr/bin/env python
"""
Test Django API endpoints directly
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
django_path = Path(__file__).parent / "django_app" / "src"
sys.path.insert(0, str(django_path))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

# Load environment variables
from dotenv import load_dotenv

# Clear existing environment variables to avoid conflicts
for key in ['GOOGLE_MAPS_API_KEY', 'OPENWEATHER_API_KEY']:
    if key in os.environ:
        del os.environ[key]

# Load the correct environment file with production keys
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)

django.setup()

from restaurants.models import Restaurant
from restaurants.views import restaurant_location_weather_api
from django.test import RequestFactory
from django.conf import settings
import json

def test_api_endpoint():
    """Test the API endpoint directly."""
    print("🧪 Testing Django API Endpoint")
    print("=" * 50)
    
    # Check environment variables
    print("🔧 Environment Variables:")
    print(f"   OPENWEATHER_API_KEY: {os.getenv('OPENWEATHER_API_KEY', 'Not set')}")
    print(f"   GOOGLE_MAPS_API_KEY: {os.getenv('GOOGLE_MAPS_API_KEY', 'Not set')}")
    print()
    
    # Check Django settings
    print("📋 Django Settings:")
    google_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', 'Not found in settings')
    weather_key = getattr(settings, 'OPENWEATHER_API_KEY', 'Not found in settings')
    print(f"   settings.GOOGLE_MAPS_API_KEY: {google_key}")
    print(f"   settings.OPENWEATHER_API_KEY: {weather_key}")
    print()
    
    # Get a test restaurant
    try:
        restaurant = Restaurant.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).first()
        
        if not restaurant:
            print("❌ No restaurant with coordinates found")
            return
            
        print(f"🏪 Test Restaurant: {restaurant.name}")
        print(f"   ID: {restaurant.id}")
        print(f"   Coordinates: {restaurant.latitude}, {restaurant.longitude}")
        print()
        
        # Create a mock request
        factory = RequestFactory()
        payload = {
            "user_lat": 40.7128,
            "user_lng": -74.0060
        }
        
        request = factory.post(
            f'/restaurants/api/{restaurant.id}/location-weather/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Call the API function directly
        print("📡 Making API Call...")
        response = restaurant_location_weather_api(request, restaurant.id)
        
        print(f"Response Status: {response.status_code}")
        response_data = json.loads(response.content.decode())
        print("Response Data:")
        print(json.dumps(response_data, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_endpoint()