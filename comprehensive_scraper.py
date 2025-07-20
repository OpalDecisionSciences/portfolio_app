#!/usr/bin/env python3
"""
Comprehensive Restaurant Scraper
Scrapes text, images, analyzes ambiance, chef info, menu, and pricing
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

from enhanced_restaurant_scraper import EnhancedRestaurantScraper
from image_scraper import RestaurantImageScraper

# Setup portfolio paths for token management
sys.path.insert(0, str(Path(__file__).parent / "shared" / "src"))
try:
    from config import setup_portfolio_paths
    setup_portfolio_paths()
    from token_management.token_manager import call_openai_chat
except ImportError:
    # Fallback if token manager not available
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def call_openai_chat(messages, force_model="gpt-4o-mini", response_format=None):
        try:
            response = openai_client.chat.completions.create(
                model=force_model,
                messages=messages,
                response_format=response_format
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None

class ComprehensiveRestaurantScraper:
    """
    Combined scraper for text, images, and AI analysis
    """
    
    def __init__(self, output_dir: str = "comprehensive_scraping_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize scrapers
        self.text_scraper = EnhancedRestaurantScraper()
        self.image_scraper = RestaurantImageScraper(str(self.output_dir / "images"))
        
    def analyze_restaurant_content(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to analyze restaurant content for ambiance, chef, menu, pricing
        """
        content = scraped_data.get('content', '')
        if len(content) < 200:
            return {'analysis_error': 'Insufficient content for analysis'}
        
        analysis_prompt = f"""
        Analyze this restaurant website content and extract detailed information:
        
        Content: {content[:3000]}  # Limit to avoid token overflow
        
        Please provide a comprehensive JSON response with:
        {{
            "restaurant_overview": {{
                "name": "restaurant name",
                "cuisine_type": "cuisine type",
                "location": "city/area if mentioned",
                "price_range": "$ | $$ | $$$ | $$$$",
                "michelin_stars": "number if mentioned, or null"
            }},
            "ambiance_dining": {{
                "atmosphere": "detailed description of atmosphere/ambiance",
                "dining_style": "fine dining/casual/etc",
                "decor_style": "modern/traditional/rustic/etc",
                "special_features": ["unique features", "views", "private rooms"]
            }},
            "chef_team": {{
                "head_chef": "name if mentioned",
                "chef_background": "chef experience/background",
                "cooking_philosophy": "chef's approach/philosophy",
                "awards_recognition": ["any awards or recognition mentioned"]
            }},
            "menu_analysis": {{
                "menu_style": "tasting menu/a la carte/both",
                "signature_dishes": ["dish names if mentioned"],
                "dietary_options": ["vegetarian/vegan/gluten-free options"],
                "seasonal_menu": "yes/no/unknown"
            }},
            "pricing_info": {{
                "menu_prices": ["any specific prices mentioned"],
                "tasting_menu_price": "price if mentioned",
                "wine_pairing": "price if mentioned",
                "value_indicators": ["expensive/moderate/affordable clues"]
            }},
            "dining_experience": {{
                "service_style": "description of service",
                "reservation_required": "yes/no/unknown",
                "dress_code": "formal/smart casual/casual",
                "special_experiences": ["wine tastings/chef table/etc"]
            }}
        }}
        
        Only include information that is clearly stated or strongly implied in the content.
        Use "unknown" or null for information not available.
        """
        
        try:
            response = call_openai_chat(
                messages=[{"role": "user", "content": analysis_prompt}],
                force_model="gpt-4o-mini",
                response_format={"type": "json_object"}
            )
            
            if response:
                return json.loads(response)
            else:
                return {'analysis_error': 'AI analysis failed - no response'}
                
        except Exception as e:
            return {'analysis_error': f'AI analysis failed: {str(e)}'}
    
    def scrape_restaurant_comprehensive(
        self, 
        url: str, 
        restaurant_name: str,
        scrape_images: bool = True,
        max_images: int = 15
    ) -> Dict[str, Any]:
        """
        Comprehensive scraping of a single restaurant
        """
        print(f"🍽️  Starting comprehensive scraping for: {restaurant_name}")
        
        result = {
            'restaurant_name': restaurant_name,
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'scraping_success': False
        }
        
        # Step 1: Scrape text content
        print(f"   📄 Scraping text content...")
        text_data = self.text_scraper.scrape_restaurant(url, use_selenium=True)
        
        if not text_data or text_data.get('quality_score', 0) < 0.2:
            result['text_scraping'] = {'status': 'failed', 'error': 'Low quality or no content'}
            print(f"   ❌ Text scraping failed for {restaurant_name}")
            return result
        
        result['text_scraping'] = {
            'status': 'success',
            'quality_score': text_data.get('quality_score', 0),
            'word_count': text_data.get('word_count', 0),
            'method_used': text_data.get('method_used', 'unknown')
        }
        result['raw_content'] = text_data
        
        # Step 2: AI Analysis
        print(f"   🤖 Analyzing content with AI...")
        ai_analysis = self.analyze_restaurant_content(text_data)
        result['ai_analysis'] = ai_analysis
        
        # Step 3: Scrape images (if enabled)
        if scrape_images:
            print(f"   📸 Scraping images...")
            try:
                image_results = self.image_scraper.scrape_restaurant_images(
                    restaurant_url=url,
                    restaurant_name=restaurant_name,
                    max_images=max_images,
                    enable_ai_categorization=True
                )
                
                result['image_scraping'] = {
                    'status': 'success',
                    'total_images': len(image_results),
                    'successful_images': len([img for img in image_results if img.get('status') == 'completed']),
                    'images': image_results
                }
                print(f"   ✅ Downloaded {len(image_results)} images")
                
            except Exception as e:
                result['image_scraping'] = {
                    'status': 'failed',
                    'error': str(e)
                }
                print(f"   ❌ Image scraping failed: {e}")
        
        result['scraping_success'] = True
        print(f"   ✅ Comprehensive scraping completed for {restaurant_name}")
        return result

def run_batch_comprehensive_scraping(csv_file: str, max_restaurants: int = 10):
    """
    Run comprehensive scraping on a batch of restaurants
    """
    import pandas as pd
    
    print(f"🚀 Starting comprehensive batch scraping for {max_restaurants} restaurants")
    
    # Load restaurant data
    df = pd.read_csv(csv_file)
    df = df.head(max_restaurants)
    
    # Initialize comprehensive scraper
    scraper = ComprehensiveRestaurantScraper()
    
    batch_results = {
        'batch_info': {
            'total_restaurants': len(df),
            'started_at': datetime.now().isoformat(),
            'csv_source': csv_file
        },
        'restaurants': [],
        'summary': {
            'successful': 0,
            'failed': 0,
            'total_images': 0,
            'total_content_words': 0
        }
    }
    
    for idx, row in df.iterrows():
        restaurant_name = row.get('name', f'Restaurant_{idx}')
        website = row.get('website', '')
        
        if not website:
            print(f"⏭️  Skipping {restaurant_name} - no website")
            continue
        
        try:
            result = scraper.scrape_restaurant_comprehensive(
                url=website,
                restaurant_name=restaurant_name,
                scrape_images=True,
                max_images=15
            )
            
            batch_results['restaurants'].append(result)
            
            # Update summary
            if result.get('scraping_success'):
                batch_results['summary']['successful'] += 1
                batch_results['summary']['total_content_words'] += result.get('raw_content', {}).get('word_count', 0)
                
                image_data = result.get('image_scraping', {})
                if image_data.get('status') == 'success':
                    batch_results['summary']['total_images'] += image_data.get('total_images', 0)
            else:
                batch_results['summary']['failed'] += 1
            
            # Save progress after each restaurant
            progress_file = scraper.output_dir / f"batch_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(progress_file, 'w') as f:
                json.dump(batch_results, f, indent=2)
            
            # Small delay between restaurants
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error processing {restaurant_name}: {e}")
            batch_results['restaurants'].append({
                'restaurant_name': restaurant_name,
                'url': website,
                'scraping_success': False,
                'error': str(e)
            })
            batch_results['summary']['failed'] += 1
    
    # Final results
    batch_results['batch_info']['completed_at'] = datetime.now().isoformat()
    
    # Save final results
    final_file = scraper.output_dir / f"comprehensive_batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w') as f:
        json.dump(batch_results, f, indent=2)
    
    # Print summary
    print(f"\n📊 Batch Scraping Complete!")
    print(f"   Total restaurants: {batch_results['summary']['successful'] + batch_results['summary']['failed']}")
    print(f"   Successful: {batch_results['summary']['successful']}")
    print(f"   Failed: {batch_results['summary']['failed']}")
    print(f"   Success rate: {batch_results['summary']['successful']/(batch_results['summary']['successful'] + batch_results['summary']['failed'])*100:.1f}%")
    print(f"   Total images downloaded: {batch_results['summary']['total_images']}")
    print(f"   Total content words: {batch_results['summary']['total_content_words']:,}")
    print(f"   Results saved to: {final_file}")
    
    return batch_results

if __name__ == "__main__":
    # Run comprehensive scraping on failed sites
    csv_file = "data_pipeline/src/scrapers/failed_scraping_sites.csv"
    
    results = run_batch_comprehensive_scraping(csv_file, max_restaurants=10)