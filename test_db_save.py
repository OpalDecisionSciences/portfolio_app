#!/usr/bin/env python3
"""
Test database save functionality with detailed error logging
"""
import os
import sys
import traceback
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "data_pipeline" / "src" / "scrapers"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from restaurants.models import Restaurant
from unified_restaurant_scraper import scrape_restaurant_unified

def test_database_save():
    """Test database save with detailed error handling."""
    print("🔧 Testing database save functionality...")
    
    # Test with a simple URL
    test_url = 'https://guide.michelin.com/us/en/new-york-state/new-york/restaurant/le-bernardin'
    test_name = 'Le Bernardin Test'
    
    try:
        result = scrape_restaurant_unified(
            url=test_url,
            restaurant_name=test_name,
            max_images=1,
            save_to_db=True,
            multi_page=False
        )
        
        print(f"✅ Scraping success: {result.get('scraping_success', False)}")
        print(f"🗄️  Database save success: {result.get('save_to_db_success', False)}")
        
        if result.get('error'):
            print(f"❌ Error: {result['error']}")
        
        if result.get('database_restaurant_id'):
            print(f"🆔 Restaurant ID: {result['database_restaurant_id']}")
        
        # Check if restaurant was actually saved
        if result.get('save_to_db_success'):
            restaurant_id = result.get('database_restaurant_id')
            if restaurant_id:
                try:
                    restaurant = Restaurant.objects.get(id=restaurant_id)
                    print(f"✅ Restaurant found in DB: {restaurant.name}")
                    print(f"   City: {restaurant.city}")
                    print(f"   Country: {restaurant.country}")
                    print(f"   Timezone info: {restaurant.timezone_info}")
                except Restaurant.DoesNotExist:
                    print("❌ Restaurant not found in database despite success flag")
        
        print("\n📊 LLM Analysis Summary:")
        llm_analysis = result.get('llm_analysis', {})
        if llm_analysis.get('restaurant_summary'):
            summary = llm_analysis['restaurant_summary']
            print(f"   Name: {summary.get('name', 'N/A')}")
            print(f"   Cuisine: {summary.get('cuisine', 'N/A')}")
            print(f"   Location: {summary.get('location', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    test_database_save()