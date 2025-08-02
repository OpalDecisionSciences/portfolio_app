import os
import time
import logging
import traceback
import re

from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException  # Currently unused
from webdriver_manager.chrome import ChromeDriverManager

# Note: Cannot use relative import here due to circular import with scrape_utils
# These functions will be available when scrape_utils imports this module


# Load environment variables
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

# API Key validation - removed logging for security
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Model configuration
MODEL = 'gpt-4o-mini'
openai = OpenAI()

# Initialize S3 logging for production web scraping
log_storage = os.getenv('LOG_STORAGE', 'LOCAL')

if log_storage == 'S3':
    import boto3
    from botocore.exceptions import ClientError
    from datetime import datetime
    
    # Configure S3 logging for web scraping
    s3_client = boto3.client('s3')
    log_bucket = os.getenv('LOG_S3_BUCKET', 'michelin-production-logs')
    log_prefix = os.getenv('LOG_S3_PREFIX', 'logs/')
    
    # Setup logging with S3 handler
    web_scraper_logger = logging.getLogger('web_scraper')
    web_scraper_logger.setLevel(logging.INFO)
    
    # Create custom S3 handler
    class S3LogHandler(logging.Handler):
        def __init__(self, bucket, prefix, service_name):
            super().__init__()
            self.bucket = bucket
            self.prefix = prefix
            self.service_name = service_name
            self.s3_client = boto3.client('s3')
            
        def emit(self, record):
            try:
                log_entry = self.format(record)
                timestamp = datetime.now().strftime('%Y-%m-%d-%H')
                key = f"{self.prefix}{self.service_name}/{timestamp}.log"
                
                # Append to existing log or create new
                try:
                    existing = self.s3_client.get_object(Bucket=self.bucket, Key=key)['Body'].read().decode('utf-8')
                    log_content = existing + '\n' + log_entry
                except ClientError:
                    log_content = log_entry
                    
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=log_content.encode('utf-8')
                )
            except Exception:
                pass  # Fail silently to avoid breaking application
    
    s3_handler = S3LogHandler(log_bucket, log_prefix, 'web_scraper')
    s3_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    web_scraper_logger.addHandler(s3_handler)
    
    # Also log to stdout for Docker logs
    if os.getenv('LOG_TO_STDOUT', 'True').lower() == 'true':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        web_scraper_logger.addHandler(console_handler)
else:
    # Fallback to local file logging
    logging.basicConfig(filename="scraping.log", level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s')
    web_scraper_logger = logging.getLogger('web_scraper')


class NewWebsite:
    shared_driver = None  # Shared browser instance across calls
    _driver_usage_count = 0  # Track usage for cleanup
    _max_usage_before_restart = 50  # Restart driver after this many uses

    def __init__(self, url, driver=None, timeout=20, lang="auto"):
        self.url = url
        self.timeout = timeout
        self.lang = lang  # language param retained but unused now
        self.lang_switched = False  # Initialize lang_switched attribute
        self.driver = driver or NewWebsite._get_shared_driver()
        raw_text, self.title, self.links = self._scrape_content()
        self.text = self._clean_text(raw_text)
        
        # Increment usage counter and restart driver if needed
        NewWebsite._driver_usage_count += 1
        if NewWebsite._driver_usage_count >= NewWebsite._max_usage_before_restart:
            web_scraper_logger.info("Restarting Chrome driver after maximum usage reached")
            NewWebsite._restart_driver()

    @classmethod
    def _get_shared_driver(cls):
        if cls.shared_driver is None:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            )
            
            # Set binary path to use container's chromium
            if os.path.exists("/usr/bin/chromium"):
                options.binary_location = "/usr/bin/chromium"

            # Configure Chrome service with proper Docker/container support
            # Priority: system chromedriver > webdriver-manager
            chromedriver_paths = [
                "/usr/bin/chromedriver",  # Docker container path
                "/usr/local/bin/chromedriver",  # Common system install path
            ]
            
            service = None
            # Try system-installed chromedrivers first (for containers)
            for path in chromedriver_paths:
                if os.path.exists(path):
                    try:
                        service = Service(path)
                        cls.shared_driver = webdriver.Chrome(service=service, options=options)
                        web_scraper_logger.info(f"Successfully initialized Chrome with system driver: {path}")
                        break
                    except Exception as e:
                        web_scraper_logger.warning(f"Failed to use chromedriver at {path}: {e}")
                        continue
            
            # Fallback to webdriver-manager if no system driver found
            if cls.shared_driver is None:
                try:
                    service = Service(ChromeDriverManager().install())
                    cls.shared_driver = webdriver.Chrome(service=service, options=options)
                    web_scraper_logger.info("Successfully initialized Chrome with webdriver-manager")
                except Exception as e:
                    raise Exception(f"Failed to initialize Chrome driver with all methods: {e}")
        return cls.shared_driver

    @classmethod
    def initialize_driver(cls):
        """Explicitly initialize the shared driver once."""
        if cls.shared_driver is None:
            cls._get_shared_driver()

    def _dismiss_popups(self):
        try:
            overlay_selectors = [
                "//button[contains(text(),'close') or contains(text(),'x')]",
                "//div[contains(@class, 'popup') or contains(@class, 'overlay')]//button",
                "//div[contains(@class, 'popup')]//span[contains(text(), 'close')]"
            ]
            for selector in overlay_selectors:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        print(f"[INFO] Closing popup/modal with element text: '{el.text}'")
                        try:
                            el.click()
                            time.sleep(1)
                        except Exception as e:
                            web_scraper_logger.warning(f"[WARN] Could not click popup close button: {e}")
        except Exception as e:
            web_scraper_logger.warning(f"[WARN] Failed to dismiss popup/modals: {e}")

    def _scrape_content(self):
        try:
            self.driver.set_page_load_timeout(self.timeout)
            self.driver.get(self.url)

            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            bypass_lang_switch_domains = ["hisafranko.com", "restaurantfzn.com"]
            parsed_url = self.url.lower()

            if any(domain in parsed_url for domain in bypass_lang_switch_domains):
                print(f"[INFO] Skipping language switching for {self.url}")
            else:
                # Only attempt language switching once per instance if lang="auto"
                if self.lang == "auto" and not self.lang_switched:
                    buttons = self.driver.find_elements(By.XPATH, "//a | //button | //*[@role='button']")
                    lang_button_present = False
                    for btn in buttons:
                        label = " ".join(filter(None, [
                            (btn.text or "").lower().strip(),
                            (btn.get_attribute("aria-label") or "").lower().strip(),
                            (btn.get_attribute("title") or "").lower().strip()
                        ]))
                        if any(k in label for k in ["english", "en", "eng"]):
                            if btn.is_displayed() and btn.is_enabled():
                                lang_button_present = True
                                break

                    if lang_button_present:
                        print(f"[INFO] Trying to switch language to English for {self.url}")
                        switched = self._try_switch_to_english()
                        if switched:
                            self.lang_switched = True  # <--- mark as switched
                            self.url = self.driver.current_url  # <--- update to new URL
                        else:
                            print("[INFO] Language switch button clicked but no success or no page change, proceeding with current language.")
                    else:
                        print("[INFO] No English language switch button found, proceeding with default language.")

            self._dismiss_popups()
            time.sleep(2)  # Allow page to settle

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            for tag in soup(["script", "style", "img", "input", "noscript", "iframe"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
            body = soup.body
            text = body.get_text(separator="\n", strip=True) if body else "No content found."

            links = []
            for link_tag in soup.find_all("a", href=True):
                href = link_tag["href"].strip()
                if href and not href.startswith(("mailto:", "tel:", "javascript:")):
                    full_url = urljoin(self.url, href)
                    links.append(full_url)

            return text, title, links

        except Exception:
            logging.error(f"Failed to scrape {self.url}\n{traceback.format_exc()}")
            return "", "Error loading page", []

    def _try_switch_to_english(self):
        try:
            possible_lang_keywords = ["english", "en", "eng"]
            skip_if_link_contains = [
                "cookies", "privacy", "modal", "mailto:", "instagram", "facebook",
                "twitter", "linkedin", "external", "whatsapp", "tel:", "maps.google"
            ]

            buttons = self.driver.find_elements(By.XPATH, "//a | //button | //*[@role='button']")
            for btn in buttons:
                try:
                    label = " ".join(filter(None, [
                        (btn.text or "").lower().strip(),
                        (btn.get_attribute("aria-label") or "").lower().strip(),
                        (btn.get_attribute("title") or "").lower().strip()
                    ]))
                    href = btn.get_attribute("href") or ""
                    lang_data = btn.get_attribute("lang") or ""
                    data_lang = btn.get_attribute("data-lang") or ""

                    if any(skip in href.lower() for skip in skip_if_link_contains):
                        continue

                    if any(k in label for k in possible_lang_keywords) or \
                       any(k in href.lower() for k in ["/en", "?lang=en", "lang=en"]) or \
                       "en" in lang_data or "en" in data_lang:
                        if btn.is_displayed() and btn.is_enabled():
                            print(f"[INFO] Clicking language switch button: {label} / {href}")
                            btn.click()
                            WebDriverWait(self.driver, self.timeout).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                            time.sleep(3)
                            print(f"[DEBUG] Final URL after language switch: {self.driver.current_url}")
                            return True
                except Exception as inner_click_error:
                    web_scraper_logger.warning(f"[WARN] Failed to try button: {inner_click_error}")
                    continue

            print("[INFO] No English language switch button clicked.")
            return False

        except Exception as e:
            web_scraper_logger.warning(f"[WARN] Language switching failed: {e}")
            return False


    def _clean_text(self, raw_text):
        lines = raw_text.splitlines()
        cleaned = []
        for line in lines:
            l = line.strip()
            if not l:
                continue
            if re.search(
                r"\b(faq|career(s)?|galler(y|ies)|event(s)?|spa(s)?|wedding(s)?|newsletter(s)?|press|privacy|terms|legal)\b",
                l,
                re.IGNORECASE,
            ):
                continue
            cleaned.append(l)
        return "\n".join(cleaned)

    def has_multiple_restaurants(self):
        indicator_keywords = [
            "our restaurants", "dining experiences", "venues",
            "branches", "locations", "multiple restaurants"
        ]
        return any(k in self.text.lower() for k in indicator_keywords)

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"

    @classmethod
    def _restart_driver(cls):
        """Restart the shared driver to prevent memory leaks."""
        cls.close_driver()
        cls._driver_usage_count = 0
        # Driver will be recreated on next request
    
    @classmethod
    def close_driver(cls):
        """Safely close the shared driver and clean up resources."""
        if cls.shared_driver:
            try:
                # Clear cache and cookies to free memory
                cls.shared_driver.delete_all_cookies()
                cls.shared_driver.execute_script("window.localStorage.clear();")
                cls.shared_driver.execute_script("window.sessionStorage.clear();")
                
                # Close all windows
                for handle in cls.shared_driver.window_handles:
                    cls.shared_driver.switch_to.window(handle)
                    cls.shared_driver.close()
                
                # Quit driver
                cls.shared_driver.quit()
            except Exception as e:
                web_scraper_logger.warning(f"Error during driver cleanup: {e}")
            finally:
                cls.shared_driver = None
                cls._driver_usage_count = 0

    @classmethod
    def initialize_driver(cls):
        """Initialize the driver if not already initialized."""
        if cls.shared_driver is None:
            cls._get_shared_driver()
    
    @classmethod
    def get_driver_stats(cls):
        """Get driver usage statistics for monitoring."""
        return {
            "is_active": cls.shared_driver is not None,
            "usage_count": cls._driver_usage_count,
            "max_usage": cls._max_usage_before_restart,
            "remaining_uses": cls._max_usage_before_restart - cls._driver_usage_count
        }
    
    @classmethod
    def set_batch_size(cls, batch_size):
        """
        Set the driver restart frequency based on batch size.
        For batch processing, restart driver after each batch to prevent memory accumulation.
        """
        # Set restart frequency to batch size or minimum of 10 for small batches
        cls._max_usage_before_restart = max(batch_size, 10)
        web_scraper_logger.info(f"Set driver restart frequency to {cls._max_usage_before_restart} based on batch size {batch_size}")
    
    @classmethod
    def cleanup_for_batch_end(cls):
        """
        Perform cleanup at the end of a batch processing session.
        Forces driver restart to ensure clean state for next batch.
        """
        web_scraper_logger.info("Performing batch end cleanup - restarting driver")
        cls._restart_driver()
