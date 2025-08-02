#!/usr/bin/env python3
"""
Test with detailed error reporting
"""
import os
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "data_pipeline" / "src" / "scrapers"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from unified_restaurant_scraper import scrape_restaurant_unified

def test_with_error_details():
    """Test with detailed error reporting."""
    print("🔧 Testing with detailed error reporting...")
    
    test_url = 'https://guide.michelin.com/us/en/new-york-state/new-york/restaurant/le-bernardin'
    test_name = 'Le Bernardin Test'
    
    result = scrape_restaurant_unified(
        url=test_url,
        restaurant_name=test_name,
        max_images=1,
        save_to_db=True,
        multi_page=False
    )
    
    print(f"Scraping success: {result.get('scraping_success', False)}")
    print(f"Database save success: {result.get('save_to_db_success', False)}")
    
    if result.get('error'):
        print(f"❌ Error: {result['error']}")
    
    if result.get('traceback'):
        print(f"📋 Traceback: {result['traceback']}")
    
    # Check LLM analysis
    llm_analysis = result.get('llm_analysis', {})
    print(f"\n📊 LLM Analysis:")
    print(f"  Keys: {list(llm_analysis.keys())}")
    
    summary = llm_analysis.get('restaurant_summary')
    if summary:
        print(f"  Summary keys: {list(summary.keys())}")
        print(f"  Name: {summary.get('name', 'N/A')}")
        print(f"  Location: {summary.get('location', 'N/A')}")
    else:
        print("  No restaurant summary found")

if __name__ == "__main__":
    test_with_error_details()