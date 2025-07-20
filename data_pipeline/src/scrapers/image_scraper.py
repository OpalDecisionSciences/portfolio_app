"""
Restaurant Image Scraper with AI-powered categorization and labeling.

This module provides functionality to:
1. Scrape images from restaurant websites
2. Download and save images locally
3. Use OpenAI Vision API to categorize and label images
4. Integrate with the existing scraping pipeline
"""

import os
import time
import logging
import requests
import traceback
import base64
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Tuple, Optional
import json

from PIL import Image
from openai import OpenAI
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import existing scraper components
try:
    from .llm_web_scraper import NewWebsite
except ImportError:
    from llm_web_scraper import NewWebsite

# Setup portfolio paths for cross-component imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "src"))
from config import setup_portfolio_paths
setup_portfolio_paths()

from token_management.token_manager import call_openai_chat
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configuration
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
MIN_IMAGE_SIZE = 200  # Minimum width/height in pixels
MAX_IMAGE_SIZE = 2048  # Maximum width/height for processing
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB max file size
IMAGE_QUALITY = 85  # JPEG quality for saved images

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RestaurantImageScraper:
    """
    Scraper for extracting and categorizing restaurant images.
    """
    
    def __init__(self, save_directory: str = "scraped_images"):
        """
        Initialize the image scraper.
        
        Args:
            save_directory: Directory to save downloaded images
        """
        self.save_directory = Path(save_directory)
        self.save_directory.mkdir(exist_ok=True)
        
        # Image categorization prompts
        self.categorization_prompt = """
        You are an expert at analyzing restaurant images. Please categorize this image and provide detailed labels.
        
        Respond with a JSON object containing:
        {
            "category": "scenery_ambiance" or "menu_item",
            "category_confidence": 0.0-1.0,
            "labels": ["label1", "label2", "label3"],
            "description": "detailed description of what's in the image",
            "description_confidence": 0.0-1.0
        }
        
        Category definitions:
        - "scenery_ambiance": Restaurant exterior, interior, dining rooms, views, atmosphere, ambiance, seating areas, decor
        - "menu_item": Food dishes, beverages, plated items, cooking process, ingredients
        
        Labels should be specific descriptors like:
        - For scenery_ambiance: "mountain views", "outdoor terrace", "romantic lighting", "modern interior", "rustic decor"
        - For menu_item: "pasta dish", "wine glass", "dessert plate", "seafood entree", "artisanal bread"
        
        Be confident in your categorization and provide 3-5 relevant labels.
        """
    
    def get_image_urls_from_website(self, url: str, max_images: int = 20) -> List[str]:
        """
        Extract image URLs from a restaurant website.
        
        Args:
            url: Website URL to scrape
            max_images: Maximum number of images to extract
            
        Returns:
            List of image URLs found on the website
        """
        try:
            website = NewWebsite(url)
            driver = website.driver
            
            # Find all image elements
            img_elements = driver.find_elements(By.TAG_NAME, "img")
            
            image_urls = set()
            
            for img in img_elements:
                if len(image_urls) >= max_images:
                    break
                    
                # Get image source URL
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if not src:
                    continue
                
                # Convert relative URLs to absolute
                img_url = urljoin(url, src)
                
                # Filter out obviously non-food/restaurant images
                if self._is_relevant_image_url(img_url):
                    image_urls.add(img_url)
            
            logger.info(f"Found {len(image_urls)} relevant images on {url}")
            return list(image_urls)[:max_images]
            
        except Exception as e:
            logger.error(f"Error extracting images from {url}: {e}")
            return []
    
    def _is_relevant_image_url(self, img_url: str) -> bool:
        """
        Filter out irrelevant images (icons, logos, ads, etc.).
        
        Args:
            img_url: URL of the image to check
            
        Returns:
            True if the image seems relevant for restaurant content
        """
        img_url_lower = img_url.lower()
        
        # Skip common non-content images
        skip_patterns = [
            'logo', 'icon', 'favicon', 'avatar', 'profile',
            'banner', 'ad', 'advertisement', 'sponsor',
            'social', 'facebook', 'instagram', 'twitter',
            'arrow', 'button', 'nav', 'menu-icon',
            'pixel', 'tracking', 'analytics'
        ]
        
        if any(pattern in img_url_lower for pattern in skip_patterns):
            return False
        
        # Check for supported image formats
        parsed_url = urlparse(img_url)
        path = parsed_url.path.lower()
        
        if not any(path.endswith(fmt) for fmt in SUPPORTED_FORMATS):
            # Some images might not have extensions, so don't completely filter them out
            # unless they clearly aren't images
            if any(ext in path for ext in ['.css', '.js', '.pdf', '.txt', '.xml']):
                return False
        
        return True
    
    def download_image(self, img_url: str, filename: str) -> Optional[Path]:
        """
        Download an image from URL and save it locally.
        
        Args:
            img_url: URL of the image to download
            filename: Local filename to save the image as
            
        Returns:
            Path to the saved image file, or None if download failed
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(img_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Check file size
            if len(response.content) > MAX_FILE_SIZE:
                logger.warning(f"Image too large: {len(response.content)} bytes for {img_url}")
                return None
            
            # Verify it's actually an image and get dimensions
            try:
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                
                # Check minimum size requirements
                if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                    logger.debug(f"Image too small: {width}x{height} for {img_url}")
                    return None
                
                # Resize if too large
                if width > MAX_IMAGE_SIZE or height > MAX_IMAGE_SIZE:
                    img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
                
                # Save the image
                save_path = self.save_directory / filename
                
                # Convert to RGB if necessary (for JPEG saving)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(save_path, 'JPEG', quality=IMAGE_QUALITY)
                
                logger.info(f"Downloaded image: {save_path} ({width}x{height})")
                return save_path
                
            except Exception as e:
                logger.error(f"Error processing image from {img_url}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading image from {img_url}: {e}")
            return None
    
    def categorize_image_with_ai(self, image_path: Path) -> Dict:
        """
        Use OpenAI Vision API to categorize and label an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with categorization results
        """
        try:
            # Read and encode image
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Prepare the vision API request
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.categorization_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "low"  # Use low detail for cost efficiency
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Validate the result structure
            required_fields = ['category', 'category_confidence', 'labels', 'description', 'description_confidence']
            for field in required_fields:
                if field not in result:
                    result[field] = None if field in ['category', 'description'] else 0.0 if 'confidence' in field else []
            
            logger.info(f"AI categorization for {image_path.name}: {result['category']} ({result['category_confidence']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Error categorizing image {image_path}: {e}")
            return {
                'category': 'uncategorized',
                'category_confidence': 0.0,
                'labels': [],
                'description': f"Error during AI analysis: {str(e)}",
                'description_confidence': 0.0
            }
    
    def scrape_restaurant_images(
        self, 
        restaurant_url: str, 
        restaurant_name: str,
        max_images: int = 20,
        enable_ai_categorization: bool = True
    ) -> List[Dict]:
        """
        Complete image scraping pipeline for a restaurant.
        
        Args:
            restaurant_url: URL of the restaurant website
            restaurant_name: Name of the restaurant (for organizing files)
            max_images: Maximum number of images to process
            enable_ai_categorization: Whether to run AI categorization
            
        Returns:
            List of dictionaries containing image information
        """
        logger.info(f"Starting image scraping for {restaurant_name} at {restaurant_url}")
        
        # Clean restaurant name for use in filenames
        clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in restaurant_name.lower())[:50]
        
        # Create restaurant-specific directory
        restaurant_dir = self.save_directory / clean_name
        restaurant_dir.mkdir(exist_ok=True)
        
        # Get image URLs from the website
        image_urls = self.get_image_urls_from_website(restaurant_url, max_images)
        
        if not image_urls:
            logger.warning(f"No images found for {restaurant_name}")
            return []
        
        results = []
        
        for i, img_url in enumerate(image_urls):
            try:
                # Generate filename
                filename = f"{clean_name}_{i+1:03d}.jpg"
                
                # Download the image
                image_path = self.download_image(img_url, restaurant_dir / filename)
                
                if not image_path:
                    results.append({
                        'source_url': img_url,
                        'status': 'failed',
                        'error': 'Download failed'
                    })
                    continue
                
                # Get image metadata
                img = Image.open(image_path)
                width, height = img.size
                file_size = image_path.stat().st_size
                
                image_data = {
                    'source_url': img_url,
                    'local_path': str(image_path),
                    'filename': filename,
                    'width': width,
                    'height': height,
                    'file_size': file_size,
                    'status': 'downloaded'
                }
                
                # Run AI categorization if enabled
                if enable_ai_categorization:
                    try:
                        ai_result = self.categorize_image_with_ai(image_path)
                        image_data.update({
                            'ai_category': ai_result['category'],
                            'category_confidence': ai_result['category_confidence'],
                            'ai_labels': ai_result['labels'],
                            'ai_description': ai_result['description'],
                            'description_confidence': ai_result['description_confidence'],
                            'status': 'completed'
                        })
                    except Exception as e:
                        logger.error(f"AI categorization failed for {filename}: {e}")
                        image_data.update({
                            'ai_category': 'uncategorized',
                            'category_confidence': 0.0,
                            'ai_labels': [],
                            'ai_description': f"AI categorization failed: {str(e)}",
                            'description_confidence': 0.0,
                            'status': 'completed'
                        })
                
                results.append(image_data)
                
                # Small delay to be respectful to OpenAI API
                if enable_ai_categorization:
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing image {img_url}: {e}")
                results.append({
                    'source_url': img_url,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"Completed image scraping for {restaurant_name}. Processed {len(results)} images.")
        return results


def scrape_images_from_csv(csv_path: str, output_dir: str = "scraped_restaurant_images", max_restaurants: int = None):
    """
    Scrape images for restaurants listed in a CSV file.
    
    Args:
        csv_path: Path to CSV file containing restaurant data
        output_dir: Directory to save all scraped images
        max_restaurants: Maximum number of restaurants to process (for testing)
    """
    import pandas as pd
    
    try:
        # Load restaurant data
        df = pd.read_csv(csv_path)
        
        if max_restaurants:
            df = df.head(max_restaurants)
        
        # Initialize scraper
        scraper = RestaurantImageScraper(output_dir)
        
        all_results = []
        
        for idx, row in df.iterrows():
            restaurant_name = row.get('name', f'Restaurant_{idx}')
            restaurant_url = row.get('url', '')
            
            if not restaurant_url:
                logger.warning(f"No URL found for {restaurant_name}")
                continue
            
            try:
                logger.info(f"Processing {idx+1}/{len(df)}: {restaurant_name}")
                
                results = scraper.scrape_restaurant_images(
                    restaurant_url=restaurant_url,
                    restaurant_name=restaurant_name,
                    max_images=15,  # Reasonable number per restaurant
                    enable_ai_categorization=True
                )
                
                # Add restaurant metadata to results
                for result in results:
                    result['restaurant_name'] = restaurant_name
                    result['restaurant_url'] = restaurant_url
                
                all_results.extend(results)
                
                # Save progress periodically
                if (idx + 1) % 5 == 0:
                    progress_file = Path(output_dir) / "scraping_progress.json"
                    with open(progress_file, 'w') as f:
                        json.dump(all_results, f, indent=2)
                
            except Exception as e:
                logger.error(f"Error processing {restaurant_name}: {e}")
                continue
        
        # Save final results
        results_file = Path(output_dir) / "image_scraping_results.json"
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        logger.info(f"Image scraping completed. Results saved to {results_file}")
        
        # Print summary
        total_images = len(all_results)
        successful_images = len([r for r in all_results if r.get('status') == 'completed'])
        
        print(f"\n=== Image Scraping Summary ===")
        print(f"Restaurants processed: {len(df)}")
        print(f"Total images found: {total_images}")
        print(f"Successfully processed: {successful_images}")
        print(f"Success rate: {successful_images/total_images*100:.1f}%" if total_images > 0 else "No images processed")
        
        return all_results
        
    except Exception as e:
        logger.error(f"Error in batch image scraping: {e}")
        raise


if __name__ == "__main__":
    # Example usage
    scraper = RestaurantImageScraper()
    
    # Test with a single restaurant
    test_url = "https://example-restaurant.com"
    test_name = "Test Restaurant"
    
    results = scraper.scrape_restaurant_images(
        restaurant_url=test_url,
        restaurant_name=test_name,
        max_images=5,
        enable_ai_categorization=True
    )
    
    print(f"Scraped {len(results)} images")
    for result in results:
        print(f"- {result.get('filename', 'unknown')}: {result.get('ai_category', 'unknown')} ({result.get('status', 'unknown')})")