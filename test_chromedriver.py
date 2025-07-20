#!/usr/bin/env python3
"""
Test script to verify ARM64 ChromeDriver setup
"""

import sys
from pathlib import Path

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

try:
    from enhanced_restaurant_scraper import EnhancedRestaurantScraper
    
    print("✅ Successfully imported EnhancedRestaurantScraper")
    
    # Test scraper initialization
    scraper = EnhancedRestaurantScraper()
    print("✅ Successfully initialized scraper")
    
    # Test simple website scraping
    test_url = "https://www.example.com"
    print(f"🧪 Testing scraping with: {test_url}")
    
    result = scraper.scrape_restaurant(test_url, use_selenium=True)
    
    if result:
        print("✅ Scraping test successful!")
        print(f"   - Method used: {result.get('method_used', 'unknown')}")
        print(f"   - Content length: {result.get('content_length', 0)} chars")
        print(f"   - Quality score: {result.get('quality_score', 0):.2f}")
    else:
        print("❌ Scraping test failed - no content returned")
    
except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()