#!/usr/bin/env python3
"""
Comprehensive Michelin Restaurant Scraper
Scrapes all restaurants from michelin_my_maps.csv using unified_restaurant_scraper.py
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import time

# Add project paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "data_pipeline" / "src" / "scrapers"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from restaurants.models import Restaurant
from unified_restaurant_scraper import scrape_restaurant_unified

class MichelinScraper:
    def __init__(self, csv_path: str, start_row: int = 1, max_restaurants: int = None):
        """
        Initialize the Michelin scraper.
        
        Args:
            csv_path: Path to michelin_my_maps.csv
            start_row: Row to start from (1-based, excluding header)
            max_restaurants: Maximum restaurants to scrape (None for all)
        """
        self.csv_path = csv_path
        self.start_row = start_row
        self.max_restaurants = max_restaurants
        self.results_dir = Path("michelin_scraping_results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Load CSV
        self.df = pd.read_csv(csv_path)
        print(f"📊 Loaded {len(self.df)} restaurants from CSV")
        
        # Stats tracking
        self.total_processed = 0
        self.successful_scrapes = 0
        self.failed_scrapes = 0
        self.start_time = datetime.now()
        
    def scrape_all_restaurants(self):
        """Scrape all restaurants from the CSV."""
        print("🍽️  STARTING COMPREHENSIVE MICHELIN SCRAPING")
        print("=" * 60)
        print(f"📅 Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: Row {self.start_row} to {self.start_row + (self.max_restaurants or len(self.df) - self.start_row + 1)}")
        print("=" * 60)
        
        # Determine range
        end_row = self.start_row + (self.max_restaurants - 1) if self.max_restaurants else len(self.df)
        end_row = min(end_row, len(self.df))
        
        # Process each restaurant
        for idx in range(self.start_row - 1, end_row):  # Convert to 0-based index
            row = self.df.iloc[idx]
            row_num = idx + 1
            
            try:
                self._scrape_single_restaurant(row, row_num)
                self.total_processed += 1
                
                # Progress update every 10 restaurants
                if self.total_processed % 10 == 0:
                    self._print_progress()
                
                # Save intermediate results every 50 restaurants
                if self.total_processed % 50 == 0:
                    self._save_intermediate_results()
                
                # Rate limiting: pause between requests
                time.sleep(3)  # 3 seconds between restaurants
                
            except KeyboardInterrupt:
                print("\\n⚠️  Scraping interrupted by user")
                break
            except Exception as e:
                print(f"❌ Unexpected error processing row {row_num}: {e}")
                self.failed_scrapes += 1
                continue
        
        # Final results
        self._print_final_results()
        self._save_final_results()
    
    def _scrape_single_restaurant(self, row, row_num):
        """Scrape a single restaurant."""
        name = row.get('Name', 'Unknown Restaurant')
        website_url = row.get('WebsiteUrl', '')
        
        if not website_url or pd.isna(website_url):
            print(f"⚠️  Row {row_num}: {name} - No website URL, skipping")
            self.failed_scrapes += 1
            return
        
        print(f"\\n🔄 [{row_num}] Scraping: {name}")
        print(f"   🌐 URL: {website_url}")
        
        try:
            # Use unified scraper
            result = scrape_restaurant_unified(
                url=website_url,
                restaurant_name=name,
                max_images=10,  # Reasonable number for testing
                save_to_db=True,
                multi_page=True
            )
            
            # Check results
            if result.get('scraping_success'):
                print(f"   ✅ Scraping successful")
                
                if result.get('save_to_db_success'):
                    print(f"   ✅ Database save successful")
                    print(f"   📊 Menu sections: {result.get('menu_sections_created', 0)}")
                    print(f"   📊 Menu items: {result.get('menu_items_created', 0)}")
                    print(f"   📊 Images: {result.get('images_integrated', 0)}")
                    print(f"   📄 Document: {'Yes' if result.get('document_txt') else 'No'}")
                    
                    # Check for language translation
                    llm_analysis = result.get('llm_analysis', {})
                    if llm_analysis.get('original_language'):
                        print(f"   🌐 Language: {llm_analysis['original_language']} → English")
                    
                    self.successful_scrapes += 1
                else:
                    print(f"   ⚠️  Database save failed")
                    self.failed_scrapes += 1
            else:
                print(f"   ❌ Scraping failed: {result.get('error', 'Unknown error')}")
                self.failed_scrapes += 1
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.failed_scrapes += 1
    
    def _print_progress(self):
        """Print current progress."""
        elapsed = datetime.now() - self.start_time
        rate = self.total_processed / elapsed.total_seconds() * 60  # per minute
        
        print(f"\\n📈 PROGRESS UPDATE")
        print(f"   Processed: {self.total_processed}")
        print(f"   Successful: {self.successful_scrapes}")
        print(f"   Failed: {self.failed_scrapes}")
        print(f"   Success Rate: {self.successful_scrapes/max(self.total_processed,1)*100:.1f}%")
        print(f"   Rate: {rate:.1f} restaurants/minute")
        print(f"   Elapsed: {elapsed}")
    
    def _save_intermediate_results(self):
        """Save intermediate results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"intermediate_results_{timestamp}.json"
        
        results = {
            "timestamp": timestamp,
            "total_processed": self.total_processed,
            "successful_scrapes": self.successful_scrapes,
            "failed_scrapes": self.failed_scrapes,
            "start_row": self.start_row,
            "elapsed_time": str(datetime.now() - self.start_time)
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Intermediate results saved: {results_file}")
    
    def _print_final_results(self):
        """Print final scraping results."""
        end_time = datetime.now()
        total_time = end_time - self.start_time
        
        print("\\n" + "=" * 60)
        print("🏁 SCRAPING COMPLETED")
        print("=" * 60)
        print(f"📅 Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Total Time: {total_time}")
        print(f"📊 Total Processed: {self.total_processed}")
        print(f"✅ Successful: {self.successful_scrapes}")
        print(f"❌ Failed: {self.failed_scrapes}")
        print(f"📈 Success Rate: {self.successful_scrapes/max(self.total_processed,1)*100:.1f}%")
        
        if self.total_processed > 0:
            avg_time = total_time.total_seconds() / self.total_processed
            print(f"⚡ Average Time: {avg_time:.1f} seconds per restaurant")
    
    def _save_final_results(self):
        """Save final results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"final_results_{timestamp}.json"
        
        results = {
            "scraping_session": {
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "total_time": str(datetime.now() - self.start_time),
                "start_row": self.start_row,
                "max_restaurants": self.max_restaurants
            },
            "results": {
                "total_processed": self.total_processed,
                "successful_scrapes": self.successful_scrapes,
                "failed_scrapes": self.failed_scrapes,
                "success_rate": self.successful_scrapes/max(self.total_processed,1)*100
            }
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Final results saved: {results_file}")

def main():
    """Main function to run the scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Michelin restaurants comprehensively')
    parser.add_argument('--start-row', type=int, default=1, help='Row to start from (1-based)')
    parser.add_argument('--max-restaurants', type=int, help='Maximum restaurants to scrape')
    parser.add_argument('--csv-path', default='data_pipeline/src/ingestion/michelin_my_maps.csv',
                       help='Path to CSV file')
    
    args = parser.parse_args()
    
    # Initialize and run scraper
    scraper = MichelinScraper(
        csv_path=args.csv_path,
        start_row=args.start_row,
        max_restaurants=args.max_restaurants
    )
    
    try:
        scraper.scrape_all_restaurants()
    except KeyboardInterrupt:
        print("\\n⚠️  Scraping interrupted by user")
        scraper._print_final_results()
        scraper._save_final_results()

if __name__ == "__main__":
    main()