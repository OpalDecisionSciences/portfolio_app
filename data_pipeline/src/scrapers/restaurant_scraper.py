"""
Restaurant scraper module using the existing portfolio scraping logic.
"""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

# Add the original portfolio modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'portfolio'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'shared' / 'src'))

from llm_web_scraper import NewWebsite
from scrape_utils import (
    get_filtered_links_and_landing, 
    scrape_website_and_save,
    detect_language,
    translate_text,
    clean_filename
)
from templates import (
    link_system_prompt,
    summary_prompt,
    structured_menu_prompt,
    get_links_user_prompt,
    get_summary_prompt,
    get_structured_menu_user_prompt
)
from token_management.token_manager import init_token_manager, call_openai_chat

logger = logging.getLogger(__name__)


class RestaurantScraper:
    """
    Main scraper class for restaurant data extraction.
    """
    
    def __init__(self, token_dir: Optional[Path] = None):
        """
        Initialize the restaurant scraper.
        
        Args:
            token_dir: Directory for token management
        """
        # Initialize token manager
        if token_dir is None:
            token_dir = Path(__file__).parent.parent.parent.parent / "shared" / "token_management"
        
        init_token_manager(token_dir)
        
        # Initialize web scraper
        self.web_scraper = NewWebsite
        
        logger.info("Restaurant scraper initialized")
    
    def scrape_restaurant(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single restaurant from URL.
        
        Args:
            url: Restaurant website URL
            
        Returns:
            Dictionary containing scraped restaurant data
        """
        try:
            logger.info(f"Starting scrape for: {url}")
            
            # Get filtered links and landing page
            filtered_links, landing_page = get_filtered_links_and_landing(url)
            
            if not landing_page:
                logger.warning(f"Could not load landing page for: {url}")
                return None
            
            # Detect language
            lang = detect_language(landing_page.text)
            logger.info(f"Detected language: {lang}")
            
            # Translate if needed
            translated_text = landing_page.text
            if lang != "en" and landing_page.text.strip():
                translated_text = translate_text(
                    landing_page.text, 
                    source_lang=lang, 
                    target_lang="en",
                    force_model="gpt-4o"
                )
            
            # Extract basic restaurant information
            restaurant_data = self.extract_restaurant_info(
                url=url,
                title=landing_page.title,
                content=translated_text,
                original_language=lang
            )
            
            if not restaurant_data:
                logger.warning(f"Could not extract restaurant info from: {url}")
                return None
            
            # Extract menu information
            menu_data = self.extract_menu_info(filtered_links, lang)
            if menu_data:
                restaurant_data['menu_sections'] = menu_data
            
            # Extract chef information
            chef_data = self.extract_chef_info(filtered_links, lang)
            if chef_data:
                restaurant_data['chefs'] = chef_data
            
            # Add metadata
            restaurant_data['scraped_at'] = datetime.now().isoformat()
            restaurant_data['original_url'] = url
            restaurant_data['scraped_content'] = translated_text
            restaurant_data['original_language'] = lang
            
            logger.info(f"Successfully scraped restaurant: {restaurant_data.get('name', 'Unknown')}")
            
            return restaurant_data
            
        except Exception as e:
            logger.error(f"Error scraping restaurant {url}: {str(e)}")
            return None
    
    def extract_restaurant_info(
        self, 
        url: str, 
        title: str, 
        content: str, 
        original_language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """
        Extract basic restaurant information from content.
        
        Args:
            url: Restaurant URL
            title: Page title
            content: Page content
            original_language: Detected language
            
        Returns:
            Dictionary with restaurant information
        """
        try:
            # Create enhanced prompt for restaurant extraction
            extraction_prompt = f"""
            Extract restaurant information from the following content and return it as JSON.
            
            Required fields:
            - name: Restaurant name
            - description: Brief description
            - city: City location
            - country: Country location
            - address: Full address if available
            - cuisine_type: Type of cuisine
            - phone: Phone number if available
            - email: Email if available
            - website: Website URL
            - price_range: Price range ($, $$, $$$, $$$$)
            - atmosphere: Atmosphere description
            - opening_hours: Opening hours if available
            - michelin_stars: Number of Michelin stars (0-3)
            - seating_capacity: Number of seats if mentioned
            - has_private_dining: Boolean for private dining availability
            
            Content:
            {content}
            """
            
            response = call_openai_chat(
                system_prompt="You are a restaurant data extraction expert. Extract information accurately and return valid JSON.",
                user_prompt=extraction_prompt,
                response_format="json",
                force_model="gpt-4o-mini"
            )
            
            if not response:
                logger.warning(f"No response from OpenAI for: {url}")
                return None
            
            # Parse JSON response
            restaurant_data = json.loads(response)
            
            # Ensure required fields have defaults
            defaults = {
                'name': title or 'Unknown Restaurant',
                'description': '',
                'city': '',
                'country': '',
                'address': '',
                'cuisine_type': '',
                'phone': '',
                'email': '',
                'website': url,
                'price_range': '',
                'atmosphere': '',
                'opening_hours': '',
                'michelin_stars': 0,
                'seating_capacity': None,
                'has_private_dining': False
            }
            
            # Apply defaults for missing fields
            for key, default_value in defaults.items():
                if key not in restaurant_data or restaurant_data[key] is None:
                    restaurant_data[key] = default_value
            
            # Validate michelin_stars
            try:
                stars = int(restaurant_data.get('michelin_stars', 0))
                restaurant_data['michelin_stars'] = max(0, min(3, stars))
            except (ValueError, TypeError):
                restaurant_data['michelin_stars'] = 0
            
            return restaurant_data
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response for restaurant extraction: {url}")
            return None
        except Exception as e:
            logger.error(f"Error extracting restaurant info from {url}: {str(e)}")
            return None
    
    def extract_menu_info(self, filtered_links: List[Dict], original_language: str = "en") -> Optional[List[Dict]]:
        """
        Extract menu information from filtered links.
        
        Args:
            filtered_links: List of filtered links from the website
            original_language: Original language of the content
            
        Returns:
            List of menu sections with items
        """
        try:
            # Find menu-related links
            menu_keywords = [
                'menu', 'brunch', 'lunch', 'dinner', 'tasting', 'wine', 'cocktail',
                'drink', 'dessert', 'beverage', 'food', 'carte'
            ]
            
            menu_links = []
            for link in filtered_links:
                link_type = link.get('type', '').lower()
                if any(keyword in link_type for keyword in menu_keywords):
                    menu_links.append(link)
            
            if not menu_links:
                logger.info("No menu links found")
                return None
            
            # Scrape menu content
            menu_content = []
            for link in menu_links:
                try:
                    page = NewWebsite(link['url'])
                    if page.text:
                        # Translate if needed
                        text = page.text
                        if original_language != "en":
                            text = translate_text(
                                page.text, 
                                source_lang=original_language, 
                                target_lang="en",
                                force_model="gpt-4o"
                            )
                        
                        menu_content.append({
                            'type': link.get('type', ''),
                            'url': link['url'],
                            'content': text
                        })
                except Exception as e:
                    logger.warning(f"Error scraping menu link {link['url']}: {str(e)}")
                    continue
            
            if not menu_content:
                return None
            
            # Extract structured menu data
            combined_content = "\n\n".join([
                f"{item['type']}:\n{item['content']}" 
                for item in menu_content
            ])
            
            structured_menu = self.extract_structured_menu(combined_content)
            
            return structured_menu
            
        except Exception as e:
            logger.error(f"Error extracting menu info: {str(e)}")
            return None
    
    def extract_structured_menu(self, menu_content: str) -> Optional[List[Dict]]:
        """
        Extract structured menu data from content.
        
        Args:
            menu_content: Raw menu content
            
        Returns:
            List of menu sections with items
        """
        try:
            response = call_openai_chat(
                system_prompt=structured_menu_prompt,
                user_prompt=get_structured_menu_user_prompt(menu_content),
                response_format="json",
                force_model="gpt-4o-mini"
            )
            
            if not response:
                return None
            
            menu_data = json.loads(response)
            
            # Validate structure
            if not isinstance(menu_data, list):
                logger.warning("Menu data is not a list")
                return None
            
            # Clean and validate menu sections
            validated_sections = []
            for section in menu_data:
                if not isinstance(section, dict):
                    continue
                
                section_data = {
                    'name': section.get('section', ''),
                    'description': section.get('description', ''),
                    'items': []
                }
                
                items = section.get('items', [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item_data = {
                                'name': item.get('name', ''),
                                'description': item.get('description', ''),
                                'price': item.get('price', ''),
                                'is_vegetarian': item.get('is_vegetarian', False),
                                'is_vegan': item.get('is_vegan', False),
                                'is_gluten_free': item.get('is_gluten_free', False),
                                'allergens': item.get('allergens', ''),
                                'is_signature': item.get('is_signature', False)
                            }
                            section_data['items'].append(item_data)
                
                if section_data['name'] and section_data['items']:
                    validated_sections.append(section_data)
            
            return validated_sections if validated_sections else None
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON response for menu extraction")
            return None
        except Exception as e:
            logger.error(f"Error extracting structured menu: {str(e)}")
            return None
    
    def extract_chef_info(self, filtered_links: List[Dict], original_language: str = "en") -> Optional[List[Dict]]:
        """
        Extract chef information from filtered links.
        
        Args:
            filtered_links: List of filtered links from the website
            original_language: Original language of the content
            
        Returns:
            List of chef information
        """
        try:
            # Find chef-related links
            chef_keywords = ['chef', 'team', 'about', 'staff', 'kitchen', 'culinary']
            
            chef_links = []
            for link in filtered_links:
                link_type = link.get('type', '').lower()
                if any(keyword in link_type for keyword in chef_keywords):
                    chef_links.append(link)
            
            if not chef_links:
                return None
            
            # Scrape chef content
            chef_content = []
            for link in chef_links:
                try:
                    page = NewWebsite(link['url'])
                    if page.text:
                        # Translate if needed
                        text = page.text
                        if original_language != "en":
                            text = translate_text(
                                page.text, 
                                source_lang=original_language, 
                                target_lang="en",
                                force_model="gpt-4o"
                            )
                        
                        chef_content.append(text)
                except Exception as e:
                    logger.warning(f"Error scraping chef link {link['url']}: {str(e)}")
                    continue
            
            if not chef_content:
                return None
            
            # Extract structured chef data
            combined_content = "\n\n".join(chef_content)
            chef_data = self.extract_structured_chef_data(combined_content)
            
            return chef_data
            
        except Exception as e:
            logger.error(f"Error extracting chef info: {str(e)}")
            return None
    
    def extract_structured_chef_data(self, content: str) -> Optional[List[Dict]]:
        """
        Extract structured chef data from content.
        
        Args:
            content: Raw chef content
            
        Returns:
            List of chef information
        """
        try:
            extraction_prompt = f"""
            Extract chef information from the following content and return it as JSON array.
            
            For each chef, include:
            - first_name: First name
            - last_name: Last name
            - position: Position (head_chef, executive_chef, sous_chef, pastry_chef, chef_de_partie)
            - biography: Brief biography
            - years_experience: Years of experience (number)
            - awards: Awards and recognitions
            
            Content:
            {content}
            """
            
            response = call_openai_chat(
                system_prompt="You are a chef data extraction expert. Extract information accurately and return valid JSON array.",
                user_prompt=extraction_prompt,
                response_format="json",
                force_model="gpt-4o-mini"
            )
            
            if not response:
                return None
            
            chef_data = json.loads(response)
            
            if not isinstance(chef_data, list):
                return None
            
            # Validate and clean chef data
            validated_chefs = []
            for chef in chef_data:
                if not isinstance(chef, dict):
                    continue
                
                chef_info = {
                    'first_name': chef.get('first_name', ''),
                    'last_name': chef.get('last_name', ''),
                    'position': chef.get('position', 'chef_de_partie'),
                    'biography': chef.get('biography', ''),
                    'years_experience': chef.get('years_experience'),
                    'awards': chef.get('awards', '')
                }
                
                # Validate position
                valid_positions = [
                    'head_chef', 'executive_chef', 'sous_chef', 
                    'pastry_chef', 'chef_de_partie'
                ]
                if chef_info['position'] not in valid_positions:
                    chef_info['position'] = 'chef_de_partie'
                
                # Validate years_experience
                try:
                    if chef_info['years_experience'] is not None:
                        chef_info['years_experience'] = int(chef_info['years_experience'])
                except (ValueError, TypeError):
                    chef_info['years_experience'] = None
                
                # Only add if we have at least first/last name
                if chef_info['first_name'] or chef_info['last_name']:
                    validated_chefs.append(chef_info)
            
            return validated_chefs if validated_chefs else None
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON response for chef extraction")
            return None
        except Exception as e:
            logger.error(f"Error extracting structured chef data: {str(e)}")
            return None
    
    def batch_scrape_restaurants(self, urls: List[str], batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape multiple restaurants in batches.
        
        Args:
            urls: List of restaurant URLs
            batch_size: Number of URLs to process per batch
            
        Returns:
            List of scraped restaurant data
        """
        results = []
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} URLs")
            
            for url in batch:
                try:
                    restaurant_data = self.scrape_restaurant(url)
                    if restaurant_data:
                        results.append(restaurant_data)
                        logger.info(f"Successfully scraped: {restaurant_data.get('name', 'Unknown')}")
                    else:
                        logger.warning(f"Failed to scrape: {url}")
                        
                except Exception as e:
                    logger.error(f"Error in batch scraping for {url}: {str(e)}")
                    continue
        
        logger.info(f"Batch scraping completed: {len(results)} successful out of {len(urls)}")
        return results