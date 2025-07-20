"""
Comprehensive Restaurant Scraper
Combines enhanced ARM64 compatibility, ethical anti-bot measures, sophisticated LLM analysis,
image scraping, translation, and comprehensive data extraction.
"""

import os
import time
import random
import logging
import requests
import traceback
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from datetime import datetime, timedelta
import hashlib
import base64
from io import BytesIO

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# BeautifulSoup for HTML parsing
from bs4 import BeautifulSoup, Comment

# Image processing
from PIL import Image
import pandas as pd

# Setup portfolio paths for cross-component imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "src"))

try:
    from config import setup_portfolio_paths
    setup_portfolio_paths()
    from token_management.token_manager import call_openai_chat, get_token_usage_summary, init_token_manager
except ImportError:
    pass

# Import templates and utilities
try:
    from .templates import (
        summary_prompt,
        structured_menu_prompt,
        cleaning_prompt,
        get_summary_prompt,
        get_structured_menu_user_prompt,
        get_translation_prompt,
        multi_restaurant_check_prompt
    )
    from .scrape_utils import detect_language, translate_text
    from .llm_web_scraper import NewWebsite
except ImportError:
    from templates import (
        summary_prompt,
        structured_menu_prompt,
        cleaning_prompt,
        get_summary_prompt,
        get_structured_menu_user_prompt,
        get_translation_prompt,
        multi_restaurant_check_prompt
    )
    try:
        from scrape_utils import detect_language, translate_text
    except ImportError:
        def detect_language(text): return "en"
        def translate_text(text, source_lang, target_lang): return text
    from llm_web_scraper import NewWebsite

# OpenAI setup for fallback
try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    openai_client = None

logger = logging.getLogger(__name__)

# Configuration constants
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
MIN_IMAGE_SIZE = 200
MAX_IMAGE_SIZE = 2048
MAX_FILE_SIZE = 5 * 1024 * 1024
IMAGE_QUALITY = 85

class EthicalScrapingError(Exception):
    """Custom exception for ethical scraping violations."""
    pass

class ComprehensiveRestaurantScraper:
    """
    Comprehensive restaurant scraper combining all functionality:
    - ARM64 ChromeDriver compatibility
    - Ethical anti-bot measures
    - Sophisticated LLM analysis using templates
    - Image scraping with AI categorization
    - Translation support
    - Menu and pricing parsing
    - Database integration ready
    """
    
    def __init__(self, 
                 token_dir: Optional[Path] = None,
                 image_output_dir: str = "comprehensive_scraped_images",
                 text_output_dir: str = "comprehensive_scraped_data"):
        """
        Initialize the comprehensive scraper.
        """
        # Initialize token manager
        if token_dir is None:
            token_dir = Path(__file__).parent.parent.parent.parent / "shared" / "token_management"
        
        try:
            init_token_manager(token_dir)
            logger.info(f"Token manager initialized with directory: {token_dir}")
        except Exception as e:
            logger.warning(f"Token manager initialization failed: {e}")
        
        # Setup directories
        self.image_output_dir = Path(image_output_dir)
        self.image_output_dir.mkdir(exist_ok=True)
        self.text_output_dir = Path(text_output_dir)
        self.text_output_dir.mkdir(exist_ok=True)
        
        # Ethical scraping setup
        self.session = requests.Session()
        self.robots_cache = {}
        self.rate_limits = {}
        self.failed_attempts = {}
        
        # User agent rotation for ethical diversity
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        
        # Configure session with ethical defaults
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # ARM64-compatible Chrome options
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument('--window-size=1920,1080')
        
        # ARM64 ChromeDriver path
        self.chromedriver_path = "/Users/iamai/.wdm/drivers/chromedriver/mac64/138.0.7204.157/chromedriver-mac-arm64/chromedriver"
        
        logger.info("Comprehensive restaurant scraper initialized with full functionality")
    
    def check_robots_txt(self, base_url: str, path: str = '/') -> bool:
        """Check if scraping is allowed by robots.txt."""
        try:
            parsed_url = urlparse(base_url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            if base_domain in self.robots_cache:
                robot_parser = self.robots_cache[base_domain]
            else:
                robot_parser = RobotFileParser()
                robot_parser.set_url(urljoin(base_domain, '/robots.txt'))
                try:
                    robot_parser.read()
                    self.robots_cache[base_domain] = robot_parser
                except Exception as e:
                    logger.warning(f"Could not read robots.txt for {base_domain}: {e}")
                    return True
            
            user_agent = self.session.headers.get('User-Agent', '*')
            can_fetch = robot_parser.can_fetch(user_agent, path)
            
            if not can_fetch:
                logger.info(f"Robots.txt disallows scraping {path} on {base_domain}")
            
            return can_fetch
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt: {e}")
            return True
    
    def respect_rate_limit(self, domain: str, min_delay: float = 1.0, max_delay: float = 3.0):
        """Implement respectful rate limiting between requests."""
        current_time = time.time()
        
        if domain in self.rate_limits:
            last_request_time = self.rate_limits[domain]
            time_since_last = current_time - last_request_time
            
            failure_count = self.failed_attempts.get(domain, 0)
            extra_delay = min(failure_count * 2, 10)
            
            required_delay = random.uniform(min_delay, max_delay) + extra_delay
            
            if time_since_last < required_delay:
                sleep_time = required_delay - time_since_last
                logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)
        
        self.rate_limits[domain] = current_time
    
    def get_with_selenium(self, url: str, wait_time: int = 10) -> Optional[str]:
        """Use Selenium WebDriver with ARM64 compatibility for JavaScript-heavy sites."""
        driver = None
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            self.respect_rate_limit(domain, min_delay=2.0, max_delay=5.0)
            
            # Initialize ARM64-compatible Chrome driver
            service = Service(self.chromedriver_path)
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            
            # Set random user agent
            user_agent = random.choice(self.user_agents)
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            
            # Navigate to page
            driver.get(url)
            
            # Wait for page load
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for dynamic content
            time.sleep(random.uniform(2, 4))
            
            # Handle loading indicators
            try:
                WebDriverWait(driver, 5).until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "loading"))
                )
            except TimeoutException:
                pass
            
            # Scroll to trigger lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            page_source = driver.page_source
            logger.info(f"Successfully loaded {url} with Selenium ({len(page_source)} chars)")
            return page_source
            
        except Exception as e:
            logger.error(f"Selenium failed for {url}: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Error closing driver: {e}")
    
    def get_with_requests(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with intelligent retry logic."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        self.respect_rate_limit(domain)
        
        for attempt in range(max_retries + 1):
            try:
                self.session.headers['User-Agent'] = random.choice(self.user_agents)
                
                if attempt > 0:
                    delay = random.uniform(2, 5) * attempt
                    logger.info(f"Retry attempt {attempt} for {url} after {delay:.1f}s delay")
                    time.sleep(delay)
                
                response = self.session.get(url, timeout=30, allow_redirects=True)
                
                if response.status_code == 200:
                    if domain in self.failed_attempts:
                        del self.failed_attempts[domain]
                    return response
                elif response.status_code == 429:
                    wait_time = 60 + random.uniform(10, 30)
                    logger.warning(f"Rate limited by {domain}, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                elif response.status_code in [403, 406, 503]:
                    logger.warning(f"Potential bot detection ({response.status_code}) for {url}")
                    break
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed for {url}: {e}")
                self.failed_attempts[domain] = self.failed_attempts.get(domain, 0) + 1
        
        return None
    
    def extract_structured_data(self, html: str, url: str) -> Dict[str, Any]:
        """Extract structured data from HTML (JSON-LD, microdata, etc.)."""
        structured_data = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') in ['Restaurant', 'LocalBusiness', 'FoodEstablishment']:
                        structured_data.update({
                            'name': data.get('name', ''),
                            'description': data.get('description', ''),
                            'address': data.get('address', {}),
                            'telephone': data.get('telephone', ''),
                            'opening_hours': data.get('openingHours', []),
                            'price_range': data.get('priceRange', ''),
                            'cuisine': data.get('servesCuisine', []),
                            'rating': data.get('aggregateRating', {}),
                        })
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug(f"Could not parse JSON-LD: {e}")
            
            # Extract Open Graph metadata
            og_data = {}
            for og_tag in soup.find_all('meta', property=lambda x: x and x.startswith('og:')):
                property_name = og_tag.get('property', '').replace('og:', '')
                content = og_tag.get('content', '')
                if property_name and content:
                    og_data[property_name] = content
            
            if og_data:
                structured_data['open_graph'] = og_data
            
            # Extract basic meta information
            title_tag = soup.find('title')
            if title_tag:
                structured_data['page_title'] = title_tag.get_text().strip()
            
            description_meta = soup.find('meta', attrs={'name': 'description'})
            if description_meta:
                structured_data['meta_description'] = description_meta.get('content', '').strip()
            
        except Exception as e:
            logger.warning(f"Error extracting structured data from {url}: {e}")
        
        return structured_data
    
    def clean_and_extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """Clean HTML and extract meaningful restaurant content."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
                element.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Extract main content areas
            content_selectors = [
                'main', '[role="main"]', '.main-content', '#main-content',
                '.content', '#content', '.page-content', '.restaurant-info',
                '.about', '.description', '.menu', '.story'
            ]
            
            main_content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    main_content = ' '.join([elem.get_text(strip=True) for elem in elements])
                    break
            
            # If no main content found, use body
            if not main_content:
                body = soup.find('body')
                if body:
                    main_content = body.get_text(separator=' ', strip=True)
            
            # Extract specific restaurant information
            restaurant_info = {
                'content': main_content,
                'headings': [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3'])],
                'contact_info': self._extract_contact_info(soup),
                'menu_items': self._extract_menu_content(soup),
                'opening_hours': self._extract_hours(soup),
            }
            
            # Get word count for quality assessment
            word_count = len(main_content.split())
            restaurant_info['word_count'] = word_count
            restaurant_info['quality_score'] = min(word_count / 100, 1.0)
            
            return restaurant_info
            
        except Exception as e:
            logger.error(f"Error cleaning content from {url}: {e}")
            return {'content': '', 'word_count': 0, 'quality_score': 0.0}
    
    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract contact information from soup."""
        contact_info = {}
        
        # Look for phone numbers
        phone_patterns = [
            r'\+?[\d\s\-\(\)]{10,}',
            r'tel:[\+\d\-\(\)\s]+',
        ]
        
        text = soup.get_text()
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            if matches:
                contact_info['phone'] = matches[0].strip()
                break
        
        # Look for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]
        
        return contact_info
    
    def _extract_menu_content(self, soup: BeautifulSoup) -> List[str]:
        """Extract menu-related content."""
        menu_items = []
        
        menu_selectors = ['.menu', '#menu', '.dishes', '.food-items', '.menu-item']
        
        for selector in menu_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if len(text) > 10:
                    menu_items.append(text)
        
        return menu_items[:20]
    
    def _extract_hours(self, soup: BeautifulSoup) -> str:
        """Extract opening hours information."""
        hours_keywords = ['hours', 'opening', 'schedule', 'horaires', 'ouvert']
        
        for keyword in hours_keywords:
            for element in soup.find_all(string=re.compile(keyword, re.I)):
                parent = element.parent
                if parent:
                    text = parent.get_text(strip=True)
                    if len(text) > 20 and len(text) < 200:
                        return text
        
        return ""
    
    def enhance_with_comprehensive_ai_analysis(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use sophisticated LLM prompts from templates.py for comprehensive analysis.
        """
        enhanced_data = {}
        content = scraped_data.get('content', '')
        
        if len(content) < 100:
            return {'ai_analysis_error': 'Insufficient content for AI analysis'}
        
        try:
            # Step 1: Restaurant Summary with Chef, Ambiance, Philosophy
            summary_analysis = self._get_restaurant_summary(content, scraped_data.get('url', ''))
            if summary_analysis:
                enhanced_data['restaurant_summary'] = summary_analysis
            
            # Step 2: Structured Menu Parsing with Prices
            menu_analysis = self._parse_structured_menu(scraped_data.get('menu_items', []))
            if menu_analysis:
                enhanced_data['structured_menu'] = menu_analysis
            
            # Step 3: Language Detection and Translation if needed
            detected_lang = detect_language(content[:1000])
            enhanced_data['detected_language'] = detected_lang
            
            if detected_lang != 'en' and len(content) > 200:
                translated_content = self._translate_content(content, detected_lang)
                if translated_content:
                    enhanced_data['translated_content'] = translated_content
                    # Re-analyze in English
                    english_summary = self._get_restaurant_summary(translated_content, scraped_data.get('url', ''))
                    if english_summary:
                        enhanced_data['english_analysis'] = english_summary
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Comprehensive AI analysis failed: {e}")
            return {'ai_analysis_error': f'Analysis failed: {str(e)}'}
    
    def _get_restaurant_summary(self, content: str, url: str) -> Optional[Dict]:
        """Use templates.py summary_prompt for chef, ambiance, and philosophy analysis."""
        try:
            # Use the sophisticated summary prompt from templates
            user_prompt = get_summary_prompt(url, content[:3000])
            
            response = self._call_llm(
                system_prompt=summary_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )
            
            if response:
                return json.loads(response)
            
        except Exception as e:
            logger.error(f"Restaurant summary analysis failed: {e}")
        
        return None
    
    def _parse_structured_menu(self, menu_items: List[str]) -> Optional[List[Dict]]:
        """Use templates.py structured_menu_prompt for menu and pricing parsing."""
        if not menu_items:
            return None
        
        try:
            menu_text = ' '.join(menu_items)
            user_prompt = get_structured_menu_user_prompt(menu_text)
            
            response = self._call_llm(
                system_prompt=structured_menu_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )
            
            if response:
                return json.loads(response)
            
        except Exception as e:
            logger.error(f"Menu parsing failed: {e}")
        
        return None
    
    def _translate_content(self, content: str, source_lang: str) -> Optional[str]:
        """Translate content to English if needed."""
        try:
            translation_prompt = get_translation_prompt(source_lang, "en", content[:2000])
            
            response = self._call_llm(
                system_prompt="You are a professional translator.",
                user_prompt=translation_prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return None
    
    def _call_llm(self, system_prompt: str, user_prompt: str, response_format=None) -> Optional[str]:
        """Call LLM with fallback to different methods."""
        try:
            # Try token manager first
            response = call_openai_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                force_model="gpt-4o-mini",
                response_format=response_format
            )
            
            if response:
                return response
            
        except Exception as e:
            logger.debug(f"Token manager call failed: {e}")
        
        # Fallback to direct OpenAI client
        try:
            if openai_client and openai_client.api_key:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=response_format
                )
                return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Direct OpenAI call failed: {e}")
        
        return None
    
    def scrape_images_from_page(self, url: str, restaurant_name: str, max_images: int = 15) -> List[Dict]:
        """Scrape and categorize images from restaurant website."""
        try:
            # Get page with Selenium for dynamic content
            html_content = self.get_with_selenium(url)
            if not html_content:
                return []
            
            soup = BeautifulSoup(html_content, 'html.parser')
            img_elements = soup.find_all('img')
            
            image_urls = set()
            for img in img_elements:
                if len(image_urls) >= max_images:
                    break
                
                src = img.get('src') or img.get('data-src')
                if not src:
                    continue
                
                img_url = urljoin(url, src)
                
                if self._is_relevant_image_url(img_url):
                    image_urls.add(img_url)
            
            # Download and categorize images
            results = []
            clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in restaurant_name.lower())[:50]
            restaurant_dir = self.image_output_dir / clean_name
            restaurant_dir.mkdir(exist_ok=True)
            
            for i, img_url in enumerate(list(image_urls)[:max_images]):
                try:
                    filename = f"{clean_name}_{i+1:03d}.jpg"
                    image_path = self._download_image(img_url, restaurant_dir / filename)
                    
                    if image_path:
                        # AI categorization
                        ai_result = self._categorize_image_with_ai(image_path)
                        
                        results.append({
                            'source_url': img_url,
                            'local_path': str(image_path),
                            'filename': filename,
                            'ai_category': ai_result.get('category', 'uncategorized'),
                            'ai_labels': ai_result.get('labels', []),
                            'ai_description': ai_result.get('description', ''),
                            'status': 'completed'
                        })
                    
                except Exception as e:
                    logger.error(f"Error processing image {img_url}: {e}")
                    results.append({
                        'source_url': img_url,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Image scraping failed for {url}: {e}")
            return []
    
    def _is_relevant_image_url(self, img_url: str) -> bool:
        """Filter out irrelevant images."""
        img_url_lower = img_url.lower()
        
        skip_patterns = [
            'logo', 'icon', 'favicon', 'avatar', 'profile',
            'banner', 'ad', 'advertisement', 'sponsor',
            'social', 'facebook', 'instagram', 'twitter',
            'arrow', 'button', 'nav', 'menu-icon',
            'pixel', 'tracking', 'analytics'
        ]
        
        if any(pattern in img_url_lower for pattern in skip_patterns):
            return False
        
        parsed_url = urlparse(img_url)
        path = parsed_url.path.lower()
        
        if not any(path.endswith(fmt) for fmt in SUPPORTED_FORMATS):
            if any(ext in path for ext in ['.css', '.js', '.pdf', '.txt', '.xml']):
                return False
        
        return True
    
    def _download_image(self, img_url: str, save_path: Path) -> Optional[Path]:
        """Download an image from URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(img_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            if len(response.content) > MAX_FILE_SIZE:
                logger.warning(f"Image too large: {len(response.content)} bytes for {img_url}")
                return None
            
            # Verify and process image
            try:
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                
                if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                    return None
                
                if width > MAX_IMAGE_SIZE or height > MAX_IMAGE_SIZE:
                    img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(save_path, 'JPEG', quality=IMAGE_QUALITY)
                return save_path
                
            except Exception as e:
                logger.error(f"Error processing image from {img_url}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading image from {img_url}: {e}")
            return None
    
    def _categorize_image_with_ai(self, image_path: Path) -> Dict:
        """Use OpenAI Vision API to categorize images."""
        try:
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            categorization_prompt = """
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
            """
            
            if openai_client and openai_client.api_key:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": categorization_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}",
                                        "detail": "low"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                return result
            
        except Exception as e:
            logger.error(f"Error categorizing image {image_path}: {e}")
        
        return {
            'category': 'uncategorized',
            'category_confidence': 0.0,
            'labels': [],
            'description': 'AI categorization failed',
            'description_confidence': 0.0
        }
    
    def scrape_restaurant_comprehensive(self, url: str, restaurant_name: str, 
                                      scrape_images: bool = True, max_images: int = 15) -> Dict[str, Any]:
        """
        Main comprehensive scraping method combining all functionality.
        """
        logger.info(f"Starting comprehensive scraping for: {restaurant_name}")
        
        result = {
            'restaurant_name': restaurant_name,
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'scraping_success': False
        }
        
        try:
            # Check robots.txt compliance
            if not self.check_robots_txt(url):
                raise EthicalScrapingError(f"Robots.txt disallows scraping for {url}")
            
            html_content = None
            method_used = "unknown"
            
            # First attempt: Regular HTTP request
            response = self.get_with_requests(url)
            if response and response.text:
                html_content = response.text
                method_used = "requests"
                logger.info(f"Successfully scraped {url} using requests")
            
            # Second attempt: Selenium for JavaScript-heavy sites
            elif html_content is None:
                html_content = self.get_with_selenium(url)
                if html_content:
                    method_used = "selenium"
                    logger.info(f"Successfully scraped {url} using Selenium")
            
            if not html_content:
                logger.warning(f"Failed to get content from {url}")
                result['error'] = 'Failed to retrieve content'
                return result
            
            # Extract structured data
            structured_data = self.extract_structured_data(html_content, url)
            
            # Clean and extract content
            content_data = self.clean_and_extract_content(html_content, url)
            
            # Comprehensive AI analysis using templates
            ai_analysis = self.enhance_with_comprehensive_ai_analysis(content_data)
            
            # Combine results
            result.update({
                'scraping_success': True,
                'method_used': method_used,
                'content_length': len(html_content),
                'quality_score': content_data.get('quality_score', 0),
                'word_count': content_data.get('word_count', 0),
                'structured_data': structured_data,
                'content': content_data.get('content', ''),
                'headings': content_data.get('headings', []),
                'contact_info': content_data.get('contact_info', {}),
                'menu_items': content_data.get('menu_items', []),
                'opening_hours': content_data.get('opening_hours', ''),
                'comprehensive_ai_analysis': ai_analysis
            })
            
            # Image scraping if enabled
            if scrape_images:
                logger.info(f"Scraping images for {restaurant_name}")
                image_results = self.scrape_images_from_page(url, restaurant_name, max_images)
                result['image_scraping'] = {
                    'total_images': len(image_results),
                    'successful_images': len([img for img in image_results if img.get('status') == 'completed']),
                    'images': image_results
                }
            
            # Save individual result
            self._save_restaurant_data(result, restaurant_name)
            
            logger.info(f"Completed comprehensive scraping for {restaurant_name}")
            return result
            
        except EthicalScrapingError as e:
            logger.warning(f"Ethical scraping violation: {e}")
            result['error'] = str(e)
            return result
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            result['error'] = str(e)
            return result
    
    def _save_restaurant_data(self, result: Dict[str, Any], restaurant_name: str):
        """Save restaurant data to file."""
        try:
            safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in restaurant_name)[:50]
            result_file = self.text_output_dir / f"{safe_name}_comprehensive.json"
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved comprehensive data to {result_file}")
            
        except Exception as e:
            logger.error(f"Error saving restaurant data: {e}")


def run_comprehensive_batch_scraping(csv_file: str, max_restaurants: int = 10) -> Dict[str, Any]:
    """
    Run comprehensive scraping on a batch of restaurants.
    """
    print(f"🚀 Starting comprehensive batch scraping for {max_restaurants} restaurants")
    
    # Load restaurant data
    df = pd.read_csv(csv_file)
    df_with_websites = df[df['WebsiteUrl'].notna()].head(max_restaurants)
    
    print(f"🍽️  Found {len(df_with_websites)} restaurants with websites")
    
    # Initialize comprehensive scraper
    scraper = ComprehensiveRestaurantScraper()
    
    batch_results = {
        'batch_info': {
            'total_restaurants': len(df_with_websites),
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
    
    for idx, row in df_with_websites.iterrows():
        restaurant_name = row['Name']
        restaurant_url = row['WebsiteUrl']
        stars = row.get('Award', '0 Stars')
        cuisine = row.get('Cuisine', 'Unknown')
        
        print(f"\n🍽️  [{idx+1}/{len(df_with_websites)}] {restaurant_name}")
        print(f"   🌟 {stars} | 🍴 {cuisine}")
        print(f"   🌐 {restaurant_url}")
        
        try:
            result = scraper.scrape_restaurant_comprehensive(
                url=restaurant_url,
                restaurant_name=restaurant_name,
                scrape_images=True,
                max_images=15
            )
            
            batch_results['restaurants'].append(result)
            
            if result.get('scraping_success'):
                batch_results['summary']['successful'] += 1
                batch_results['summary']['total_content_words'] += result.get('word_count', 0)
                
                image_data = result.get('image_scraping', {})
                if image_data:
                    batch_results['summary']['total_images'] += image_data.get('total_images', 0)
                
                print(f"   ✅ SUCCESS! Quality: {result.get('quality_score', 0):.2f}")
                
                # Show AI analysis preview
                ai_analysis = result.get('comprehensive_ai_analysis', {})
                if ai_analysis.get('restaurant_summary'):
                    summary = ai_analysis['restaurant_summary']
                    print(f"   🤖 AI Analysis: {summary.get('cuisine_type', 'N/A')} cuisine")
                    if summary.get('atmosphere'):
                        print(f"       Atmosphere: {summary.get('atmosphere', '')[:100]}...")
                
            else:
                batch_results['summary']['failed'] += 1
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
            
            # Delay between restaurants
            time.sleep(3)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            batch_results['restaurants'].append({
                'restaurant_name': restaurant_name,
                'url': restaurant_url,
                'scraping_success': False,
                'error': str(e)
            })
            batch_results['summary']['failed'] += 1
    
    # Final summary
    batch_results['batch_info']['completed_at'] = datetime.now().isoformat()
    
    # Save batch results
    output_dir = Path("comprehensive_scraping_results")
    output_dir.mkdir(exist_ok=True)
    
    final_file = output_dir / f"comprehensive_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(batch_results, f, indent=2, ensure_ascii=False)
    
    # Print final summary
    total = batch_results['summary']['successful'] + batch_results['summary']['failed']
    success_rate = (batch_results['summary']['successful'] / total * 100) if total > 0 else 0
    
    print(f"\n🎉 Comprehensive Batch Scraping Complete!")
    print(f"   Total processed: {total}")
    print(f"   Successful: {batch_results['summary']['successful']}")
    print(f"   Failed: {batch_results['summary']['failed']}")
    print(f"   Success rate: {success_rate:.1f}%")
    print(f"   Total images: {batch_results['summary']['total_images']}")
    print(f"   Total content words: {batch_results['summary']['total_content_words']:,}")
    print(f"   Results saved to: {final_file}")
    
    return batch_results


if __name__ == "__main__":
    # Run comprehensive scraping
    csv_file = Path(__file__).parent.parent / "ingestion" / "michelin_my_maps.csv"
    results = run_comprehensive_batch_scraping(str(csv_file), max_restaurants=5)