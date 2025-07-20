#!/usr/bin/env python3
"""
Run batch scraping on 10 restaurants from the Michelin CSV using our ARM64-fixed scraper
"""

import sys
import json
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add the scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "data_pipeline" / "src" / "scrapers"))

from enhanced_restaurant_scraper import EnhancedRestaurantScraper

def analyze_restaurant_with_openai(content: str, restaurant_name: str) -> Dict[str, Any]:
    """
    Simple analysis using OpenAI directly
    """
    try:
        from openai import OpenAI
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        if not client.api_key or client.api_key == "your-openai-api-key-here":
            return {'analysis_error': 'OpenAI API key not configured'}
        
        prompt = f"""
        Analyze this restaurant website content for {restaurant_name}:
        
        Content: {content[:2000]}
        
        Extract and provide a JSON response with:
        {{
            "restaurant_summary": {{
                "name": "{restaurant_name}",
                "cuisine_type": "identified cuisine type",
                "dining_style": "fine dining/casual/etc",
                "price_level": "$/$$/$$$/$$$$ or unknown"
            }},
            "ambiance": {{
                "atmosphere": "description of atmosphere",
                "decor_style": "modern/traditional/etc",
                "special_features": ["unique features"]
            }},
            "chef_info": {{
                "head_chef": "name if mentioned",
                "chef_background": "background if mentioned",
                "philosophy": "cooking philosophy if mentioned"
            }},
            "menu_highlights": {{
                "signature_dishes": ["dishes mentioned"],
                "menu_style": "tasting/a la carte/both",
                "dietary_options": ["vegetarian/vegan/etc if mentioned"]
            }},
            "pricing_info": {{
                "price_mentions": ["any specific prices found"],
                "value_level": "expensive/moderate/affordable impression"
            }},
            "dining_experience": {{
                "service_style": "service description",
                "reservation_needed": "yes/no/unknown",
                "special_experiences": ["wine pairing/chef table/etc"]
            }}
        }}
        
        Only include information clearly found in the content.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return {'analysis_error': f'Analysis failed: {str(e)}'}

def run_comprehensive_batch():
    """
    Run comprehensive scraping on 10 restaurants from the Michelin CSV
    """
    # Load the CSV file
    csv_file = Path("data_pipeline/src/ingestion/michelin_my_maps.csv")
    
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    print(f"📄 Loading restaurants from: {csv_file}")
    df = pd.read_csv(csv_file)
    
    # Filter to only restaurants with websites and limit to 10
    df_with_websites = df[df['WebsiteUrl'].notna()].head(10)
    
    print(f"🍽️  Found {len(df_with_websites)} restaurants with websites (limited to 10)")
    
    # Initialize scraper
    scraper = EnhancedRestaurantScraper()
    
    # Create output directory
    output_dir = Path("batch_scraping_results")
    output_dir.mkdir(exist_ok=True)
    
    results = []
    successful = 0
    failed = 0
    
    for idx, row in df_with_websites.iterrows():
        restaurant_name = row['Name']
        restaurant_url = row['WebsiteUrl']
        cuisine = row.get('Cuisine', 'Unknown')
        stars = row.get('Award', '0 Stars')
        
        print(f"\n🍽️  [{idx+1}/10] {restaurant_name}")
        print(f"   🌟 {stars} Michelin stars | 🍴 {cuisine}")
        print(f"   🌐 {restaurant_url}")
        
        try:
            # Scrape the restaurant
            scraped_data = scraper.scrape_restaurant(restaurant_url, use_selenium=True)
            
            if scraped_data and scraped_data.get('quality_score', 0) > 0.2:
                print(f"   ✅ Scraped successfully (Quality: {scraped_data.get('quality_score', 0):.2f})")
                
                # Run AI analysis
                print(f"   🤖 Analyzing content...")
                ai_analysis = analyze_restaurant_with_openai(
                    scraped_data.get('content', ''), 
                    restaurant_name
                )
                
                result = {
                    'restaurant_name': restaurant_name,
                    'url': restaurant_url,
                    'michelin_stars': stars,
                    'cuisine_type': cuisine,
                    'scraping_success': True,
                    'scraped_at': datetime.now().isoformat(),
                    'scraping_method': scraped_data.get('method_used', 'unknown'),
                    'quality_score': scraped_data.get('quality_score', 0),
                    'word_count': scraped_data.get('word_count', 0),
                    'ai_analysis': ai_analysis,
                    'raw_content': scraped_data.get('content', '')[:1000],  # First 1000 chars
                    'headings': scraped_data.get('headings', []),
                    'contact_info': scraped_data.get('contact_info', {}),
                    'menu_items': scraped_data.get('menu_items', []),
                    'structured_data': scraped_data.get('structured_data', {})
                }
                
                successful += 1
                
            else:
                print(f"   ❌ Scraping failed - low quality or no content")
                result = {
                    'restaurant_name': restaurant_name,
                    'url': restaurant_url,
                    'michelin_stars': stars,
                    'cuisine_type': cuisine,
                    'scraping_success': False,
                    'error': 'Low quality content or scraping failed'
                }
                failed += 1
            
            results.append(result)
            
            # Save individual result
            safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in restaurant_name)
            result_file = output_dir / f"{safe_name}.json"
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            # Small delay between restaurants
            time.sleep(3)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            result = {
                'restaurant_name': restaurant_name,
                'url': restaurant_url,
                'michelin_stars': stars,
                'cuisine_type': cuisine,
                'scraping_success': False,
                'error': str(e)
            }
            results.append(result)
            failed += 1
    
    # Save batch results
    batch_summary = {
        'batch_info': {
            'total_restaurants': len(results),
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(results) * 100) if results else 0,
            'completed_at': datetime.now().isoformat()
        },
        'restaurants': results
    }
    
    summary_file = output_dir / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump(batch_summary, f, indent=2)
    
    # Print summary
    print(f"\n📊 Batch Scraping Complete!")
    print(f"   Total: {len(results)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Success rate: {successful/len(results)*100:.1f}%")
    print(f"   Results saved to: {output_dir}")
    
    # Show successful restaurants with analysis
    if successful > 0:
        print(f"\n✅ Successfully analyzed restaurants:")
        for result in results:
            if result.get('scraping_success'):
                name = result['restaurant_name']
                stars = result.get('michelin_stars', 0)
                quality = result.get('quality_score', 0)
                words = result.get('word_count', 0)
                
                ai_data = result.get('ai_analysis', {})
                cuisine = ai_data.get('restaurant_summary', {}).get('cuisine_type', 'Unknown')
                dining_style = ai_data.get('restaurant_summary', {}).get('dining_style', 'Unknown')
                
                print(f"   ⭐ {name} ({stars}★) - {cuisine}, {dining_style}")
                print(f"      Quality: {quality:.2f}, Words: {words}")
    
    return batch_summary

if __name__ == "__main__":
    run_comprehensive_batch()