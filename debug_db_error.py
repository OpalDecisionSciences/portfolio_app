#!/usr/bin/env python3
"""
Debug specific database save error
"""
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from restaurants.models import Restaurant

def test_restaurant_creation():
    """Test direct restaurant creation to isolate the issue."""
    print("🔧 Testing direct Restaurant model creation...")
    
    try:
        # Test basic restaurant creation
        restaurant_data = {
            'name': 'Test Restaurant',
            'website': 'https://test.com',
            'scraped_content': 'Test content',
            'scraped_at': datetime.now(),
            'city': 'Test City',
            'country': 'Test Country',
            'address': 'Test Address',
        }
        
        print("Creating restaurant with basic data...")
        restaurant = Restaurant.objects.create(**restaurant_data)
        print(f"✅ Basic restaurant created: {restaurant.id}")
        
        # Test with timezone_info
        restaurant_data_with_timezone = {
            'name': 'Test Restaurant 2',
            'website': 'https://test2.com',
            'scraped_content': 'Test content 2',
            'scraped_at': datetime.now(),
            'city': 'Test City 2',
            'country': 'Test Country 2',
            'address': 'Test Address 2',
            'timezone_info': {
                'local_timezone': 'America/New_York',
                'country': 'United States',
                'city': 'New York'
            }
        }
        
        print("Creating restaurant with timezone_info...")
        restaurant2 = Restaurant.objects.create(**restaurant_data_with_timezone)
        print(f"✅ Restaurant with timezone created: {restaurant2.id}")
        
        # Clean up test data
        restaurant.delete()
        restaurant2.delete()
        print("✅ Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Restaurant creation failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_restaurant_creation()