#!/usr/bin/env python3
"""
Run the comprehensive restaurant scraper with full functionality
"""

import sys
from pathlib import Path

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

from comprehensive_restaurant_scraper import run_comprehensive_batch_scraping

if __name__ == "__main__":
    print("🚀 Starting Comprehensive Restaurant Scraping with Full Functionality")
    print("   ✅ ARM64 ChromeDriver compatibility")
    print("   ✅ Ethical anti-bot measures")
    print("   ✅ Sophisticated LLM analysis (chef, ambiance, menu)")
    print("   ✅ Image scraping with AI categorization")
    print("   ✅ Translation support")
    print("   ✅ Menu and pricing parsing")
    print("   ✅ Database-ready structured output")
    print()
    
    # Run on 5 restaurants for comprehensive test
    csv_file = "data_pipeline/src/ingestion/michelin_my_maps.csv"
    
    try:
        results = run_comprehensive_batch_scraping(csv_file, max_restaurants=5)
        
        print(f"\n📊 Final Results Summary:")
        summary = results['summary']
        print(f"   🎯 Success Rate: {summary['successful']}/{summary['successful'] + summary['failed']} = {(summary['successful']/(summary['successful'] + summary['failed'])*100) if (summary['successful'] + summary['failed']) > 0 else 0:.1f}%")
        print(f"   📝 Total Content Words: {summary['total_content_words']:,}")
        print(f"   🖼️  Total Images Scraped: {summary['total_images']}")
        
        # Show successful restaurants
        successful_restaurants = [r for r in results['restaurants'] if r.get('scraping_success')]
        
        if successful_restaurants:
            print(f"\n✅ Successfully Analyzed Restaurants:")
            for restaurant in successful_restaurants:
                name = restaurant['restaurant_name']
                quality = restaurant.get('quality_score', 0)
                words = restaurant.get('word_count', 0)
                images = restaurant.get('image_scraping', {}).get('total_images', 0)
                
                print(f"   🍽️  {name}")
                print(f"       Quality: {quality:.2f} | Words: {words} | Images: {images}")
                
                # Show AI analysis if available
                ai_analysis = restaurant.get('comprehensive_ai_analysis', {})
                if ai_analysis.get('restaurant_summary'):
                    summary_data = ai_analysis['restaurant_summary']
                    if isinstance(summary_data, dict):
                        cuisine = summary_data.get('cuisine_type', 'Unknown')
                        atmosphere = summary_data.get('atmosphere', '')
                        print(f"       🍴 Cuisine: {cuisine}")
                        if atmosphere:
                            print(f"       🏛️  Atmosphere: {atmosphere[:80]}...")
                
                # Show menu analysis if available
                if ai_analysis.get('structured_menu'):
                    menu_data = ai_analysis['structured_menu']
                    if isinstance(menu_data, list) and menu_data:
                        print(f"       📋 Menu sections found: {len(menu_data)}")
                
                print()
        
        print("🎉 Comprehensive scraping completed successfully!")
        print("📁 Check the following directories for results:")
        print("   • comprehensive_scraped_data/ - Detailed JSON analysis")
        print("   • comprehensive_scraped_images/ - Downloaded and categorized images")
        print("   • comprehensive_scraping_results/ - Batch summary")
        
    except Exception as e:
        print(f"❌ Comprehensive scraping failed: {e}")
        import traceback
        traceback.print_exc()