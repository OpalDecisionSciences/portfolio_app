#!/usr/bin/env python3
"""
Test with logging enabled
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging to show INFO level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "data_pipeline" / "src" / "scrapers"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from unified_restaurant_scraper import scrape_restaurant_unified

def test_with_logging():
    """Test with logging enabled."""
    print("🔧 Testing with logging enabled...")
    
    test_url = 'https://guide.michelin.com/us/en/new-york-state/new-york/restaurant/le-bernardin'
    test_name = 'Le Bernardin Test'
    
    result = scrape_restaurant_unified(
        url=test_url,
        restaurant_name=test_name,
        max_images=1,
        save_to_db=True,
        multi_page=False
    )
    
    print(f"\nFinal results:")
    print(f"Scraping success: {result.get('scraping_success', False)}")
    print(f"Database save success: {result.get('save_to_db_success', False)}")
    
    if result.get('error'):
        print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    test_with_logging()