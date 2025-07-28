#!/usr/bin/env python
"""
Test script for API integrations (Google Maps and OpenWeather)
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables from production config
import os
from pathlib import Path

# Clear existing environment variables to avoid conflicts
for key in ['GOOGLE_MAPS_API_KEY', 'OPENWEATHER_API_KEY']:
    if key in os.environ:
        del os.environ[key]

# Get the absolute path to .env file (which contains production keys)
env_path = Path(__file__).parent / '.env'
print(f"Loading environment from: {env_path}")

if env_path.exists():
    load_dotenv(env_path, override=True)
    print("✓ .env file found and loaded")
else:
    print("❌ .env file not found")
    print(f"Looking for file at: {env_path.absolute()}")

# Debug: Print what was loaded
print("🔧 Environment variables loaded:")
google_key = os.getenv('GOOGLE_MAPS_API_KEY')
weather_key = os.getenv('OPENWEATHER_API_KEY')
print(f"   GOOGLE_MAPS_API_KEY: {'✓ Set' if google_key else '✗ Not set'}")
print(f"   OPENWEATHER_API_KEY: {'✓ Set' if weather_key else '✗ Not set'}")
print(f"   GOOGLE key value: {google_key}")
print(f"   WEATHER key value: {weather_key}")
print()

def test_google_maps_api():
    """Test Google Maps Geocoding API."""
    print("=== TESTING GOOGLE MAPS API ===")
    
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    print(f"DEBUG: API key value: {api_key}")
    print(f"DEBUG: Key starts with 'your-': {api_key.startswith('your-') if api_key else 'N/A'}")
    
    if not api_key or api_key.startswith('your-'):
        print("❌ Google Maps API key not configured")
        return False
    
    print(f"✓ API Key configured: {api_key[:20]}...")
    
    # Test geocoding
    test_address = "Barcelona, Spain"
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': test_address,
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response status from Google: {data.get('status')}")
            
            if data['status'] == 'OK' and data['results']:
                location = data['results'][0]['geometry']['location']
                print(f"✅ Google Maps API working!")
                print(f"   Address: {test_address}")
                print(f"   Lat/Lng: {location['lat']}, {location['lng']}")
                print(f"   Formatted: {data['results'][0]['formatted_address']}")
                return True
            else:
                print(f"❌ Google API returned: {data.get('status')} - {data.get('error_message', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_openweather_api():
    """Test OpenWeather API."""
    print("\n=== TESTING OPENWEATHER API ===")
    
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key or api_key.startswith('your-'):
        print("❌ OpenWeather API key not configured")
        return False
    
    print(f"✓ API Key configured: {api_key[:20]}...")
    
    # Test with Barcelona coordinates (from ABaC restaurant)
    lat, lon = 41.410382, 2.136766
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OpenWeather API working!")
            print(f"   Location: {data.get('name')}, {data.get('sys', {}).get('country')}")
            print(f"   Temperature: {data['main']['temp']}°C")
            print(f"   Description: {data['weather'][0]['description'].title()}")
            print(f"   Humidity: {data['main']['humidity']}%")
            return True
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('message', 'Unknown error')}")
            except:
                pass
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_api_integration():
    """Test both APIs with restaurant data."""
    print("\n=== TESTING FULL API INTEGRATION ===")
    
    # Test restaurant: ABaC in Barcelona
    restaurant_data = {
        'name': 'ABaC',
        'city': 'Barcelona',
        'country': 'Spain',
        'address': 'Avenida del Tibidabo 1, Barcelona, 08022, Spain',
        'latitude': 41.410382,
        'longitude': 2.136766
    }
    
    print(f"Testing with restaurant: {restaurant_data['name']}")
    print(f"Location: {restaurant_data['city']}, {restaurant_data['country']}")
    print(f"Coordinates: {restaurant_data['latitude']}, {restaurant_data['longitude']}")
    
    # Test user location (simulated - New York)
    user_lat, user_lng = 40.7128, -74.0060
    print(f"Simulated user location: {user_lat}, {user_lng} (New York)")
    
    # Calculate distance (simple great circle distance)
    import math
    
    def calculate_distance(lat1, lng1, lat2, lng2):
        R = 6371  # Earth's radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlng/2) * math.sin(dlng/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        return distance
    
    distance_km = calculate_distance(
        user_lat, user_lng,
        restaurant_data['latitude'], restaurant_data['longitude']
    )
    distance_miles = distance_km * 0.621371
    
    print(f"\n📍 DISTANCE CALCULATION:")
    print(f"   Distance: {distance_km:.1f} km ({distance_miles:.1f} miles)")
    
    # Test weather for restaurant location
    print(f"\n🌤️ WEATHER AT RESTAURANT:")
    weather_success = test_openweather_api()
    
    return weather_success

if __name__ == "__main__":
    print("🧪 API Integration Test Suite")
    print("=" * 50)
    
    # Test individual APIs
    maps_success = test_google_maps_api()
    weather_success = test_openweather_api()
    
    # Test full integration
    integration_success = test_api_integration()
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS:")
    print(f"   Google Maps API: {'✅ Working' if maps_success else '❌ Failed'}")
    print(f"   OpenWeather API: {'✅ Working' if weather_success else '❌ Failed'}")
    print(f"   Integration: {'✅ Ready' if maps_success and weather_success else '❌ Issues detected'}")
    
    if maps_success and weather_success:
        print("\n🎉 All APIs are working correctly!")
        print("   Ready for production testing.")
    else:
        print("\n⚠️  Some APIs have issues. Check configuration.")