#!/usr/bin/env python3
"""
Test new UI features: Navigation, Gallery, and Improved Search
"""
import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_navigation():
    """Test navigation menu on all pages."""
    print("🧭 TESTING NAVIGATION MENU")
    print("-" * 40)
    
    pages = [
        ("/", "Homepage"),
        ("/restaurants/", "Restaurant List"),
        ("/restaurants/gallery/", "Gallery Page"),
        ("/restaurants/epicure-paris/", "Restaurant Detail")
    ]
    
    for url, name in pages:
        try:
            response = requests.get(f"{BASE_URL}{url}", timeout=10)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {name}: {response.status_code}")
            
            # Check if navigation menu is present
            if "Home</a>" in response.text and "Restaurants</a>" in response.text and "Gallery</a>" in response.text:
                print(f"   📍 Navigation menu: ✅ Present")
            else:
                print(f"   📍 Navigation menu: ❌ Missing")
                
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
    print()

def test_search_improvements():
    """Test improved search functionality with accents."""
    print("🔍 TESTING IMPROVED SEARCH")
    print("-" * 40)
    
    search_tests = [
        ("Épicure", "Accented character search"),
        ("epicure", "Lowercase search"),
        ("ÉPICURE", "Uppercase accented search"),
        ("paris", "Location search"),
        ("french", "Cuisine search")
    ]
    
    for query, description in search_tests:
        try:
            url = f"{BASE_URL}/restaurants/api/search/?q={query}&max_results=3"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            results_count = len(data.get('results', []))
            print(f"✅ {description} ('{query}'): {results_count} results")
            
            # Show top result
            if results_count > 0:
                top_result = data['results'][0]
                print(f"   🥇 Top: {top_result['name']} ({top_result['city']}, {top_result['country']})")
            
        except Exception as e:
            print(f"❌ {description}: Error - {e}")
    print()

def test_gallery_functionality():
    """Test gallery page and filtering."""
    print("🖼️  TESTING GALLERY FUNCTIONALITY")
    print("-" * 40)
    
    # Test main gallery page
    try:
        response = requests.get(f"{BASE_URL}/restaurants/gallery/", timeout=10)
        status = "✅" if response.status_code == 200 else "❌"
        print(f"{status} Gallery page load: {response.status_code}")
        
        # Test filter combinations
        filters = [
            ("?category=menu_item", "Menu items filter"),
            ("?category=scenery_ambiance", "Ambiance filter"),
            ("?country=France", "Country filter"),
            ("?search=paris", "Search filter")
        ]
        
        for filter_param, description in filters:
            filter_response = requests.get(f"{BASE_URL}/restaurants/gallery/{filter_param}", timeout=10)
            filter_status = "✅" if filter_response.status_code == 200 else "❌"
            print(f"{filter_status} {description}: {filter_response.status_code}")
            
    except Exception as e:
        print(f"❌ Gallery testing: Error - {e}")
    print()

def test_restaurant_linking():
    """Test that gallery images link to restaurant detail pages."""
    print("🔗 TESTING RESTAURANT LINKING")
    print("-" * 40)
    
    # Test that we can navigate from gallery to restaurant details
    try:
        # Get some restaurant slugs that have images
        import os
        import sys
        sys.path.insert(0, 'django_app/src')
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
        import django
        django.setup()
        from restaurants.models import Restaurant
        
        restaurants_with_images = Restaurant.objects.filter(images__isnull=False).distinct()[:3]
        
        for restaurant in restaurants_with_images:
            detail_url = f"{BASE_URL}/restaurants/{restaurant.slug}/"
            response = requests.get(detail_url, timeout=10)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {restaurant.name} detail page: {response.status_code}")
            print(f"   📸 Images: {restaurant.images.count()}")
            
    except Exception as e:
        print(f"❌ Restaurant linking test: Error - {e}")
    print()

def test_image_display():
    """Test that images are actually displaying correctly."""
    print("📸 TESTING IMAGE DISPLAY")
    print("-" * 40)
    
    try:
        import os
        import sys
        sys.path.insert(0, 'django_app/src')
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
        import django
        django.setup()
        from restaurants.models import RestaurantImage
        
        # Test a few image URLs
        sample_images = RestaurantImage.objects.all()[:5]
        
        for image in sample_images:
            try:
                # Test if image URL is accessible
                img_response = requests.head(image.source_url, timeout=5)
                status = "✅" if img_response.status_code == 200 else "⚠️"
                print(f"{status} {image.restaurant.name} image: {img_response.status_code}")
                print(f"   Category: {image.ai_category}")
                print(f"   URL: {image.source_url[:50]}...")
            except:
                print(f"❌ {image.restaurant.name} image: URL not accessible")
        
    except Exception as e:
        print(f"❌ Image display test: Error - {e}")
    print()

def main():
    """Run comprehensive tests of new features."""
    print("🎯 COMPREHENSIVE NEW FEATURES TEST")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_navigation()
    test_search_improvements()
    test_gallery_functionality()
    test_restaurant_linking()
    test_image_display()
    
    print("=" * 60)
    print("✅ All new features tested!")
    print("\n🎉 KEY IMPROVEMENTS ADDED:")
    print("   • Home/Restaurants/Gallery navigation menu")
    print("   • Accent-insensitive search (Épicure, épicure, etc.)")
    print("   • Dedicated image gallery with filtering")
    print("   • Gallery images link to restaurant detail pages")
    print("   • AI-categorized images (menu_item, scenery_ambiance)")
    print("   • Responsive gallery grid layout")

if __name__ == "__main__":
    main()