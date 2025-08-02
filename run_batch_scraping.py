#!/usr/bin/env python3
"""
Run comprehensive batch scraping on restaurants from the Michelin CSV 
using the new async comprehensive scraper system
"""

import sys
import json
import time
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

from comprehensive_restaurant_scraper import ComprehensiveRestaurantScraper

async def run_comprehensive_batch(max_restaurants: int = 10):
    """
    Run comprehensive scraping using the new async system
    """
    import signal
    
    print(f"🚀 Starting comprehensive batch scraping for {max_restaurants} restaurants")
    
    # Create scraper instance with production settings
    scraper = ComprehensiveRestaurantScraper(
        output_dir="batch_scraping_results",
        max_concurrent=2,  # Conservative for batch processing
        max_images_per_restaurant=10
    )
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"Received signal {signum} - requesting graceful shutdown")
        scraper.request_shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Process restaurants
    csv_file = "data_pipeline/src/ingestion/michelin_my_maps.csv"
    
    try:
        results = await scraper.process_restaurants_batch(
            csv_file=csv_file,
            max_restaurants=max_restaurants,
            resume=True
        )
        
        print("\n" + "="*60)
        print("COMPREHENSIVE BATCH SCRAPING COMPLETE")
        print("="*60)
        print(f"Total processed: {results['summary']['total_processed']}")
        print(f"Successful: {results['summary']['successful']}")
        print(f"Failed: {results['summary']['failed']}")
        print(f"Partial: {results['summary']['partial']}")
        print(f"Success rate: {results['summary']['success_rate']:.1f}%")
        print("="*60)
        
        # Show detailed results for successful restaurants
        successful_restaurants = [r for r in results['results'] if r.processing_status == 'completed']
        if successful_restaurants:
            print(f"\n✅ Successfully processed restaurants:")
            for result in successful_restaurants[:5]:  # Show first 5
                print(f"   ⭐ {result.name} ({result.michelin_stars}) - {result.cuisine}")
                print(f"      Quality: {result.quality_score:.2f} | Images: {len(result.images)} | Menu items: {len(result.menu_items)}")
            
            if len(successful_restaurants) > 5:
                print(f"   ... and {len(successful_restaurants) - 5} more")
        
        return results
        
    except Exception as e:
        print(f"❌ Batch processing failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Run with asyncio
    asyncio.run(run_comprehensive_batch())