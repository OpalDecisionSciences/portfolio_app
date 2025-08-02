#!/usr/bin/env python3
"""
Test the enhanced scraper with a few previously failed sites
"""

import sys
from pathlib import Path

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

from enhanced_restaurant_scraper import scrape_failed_sites_batch

if __name__ == "__main__":
    # Test with a small batch of failed sites
    csv_file = "data_pipeline/src/scrapers/failed_scraping_sites.csv"
    
    print("🚀 Testing enhanced scraper with previously failed sites...")
    
    try:
        results = scrape_failed_sites_batch(
            csv_file=csv_file,
            max_sites=5,  # Test with just 5 sites first
            use_selenium=True
        )
        
        print(f"\n📊 Test Results:")
        print(f"   Total attempted: {results['total_attempted']}")
        print(f"   Successful: {results['successful']}")
        print(f"   Failed: {results['failed']}")
        print(f"   Success rate: {results.get('success_rate', 0):.1f}%")
        
        if results['successful_sites']:
            print(f"\n✅ Successfully scraped sites:")
            for site in results['successful_sites']:
                print(f"   - {site['name']} ({site['quality_score']:.2f} quality, {site['method']})")
        
        if results['still_failed_sites']:
            print(f"\n❌ Still failed sites:")
            for site in results['still_failed_sites'][:3]:  # Show first 3
                print(f"   - {site['name']}: {site['error'][:100]}...")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()