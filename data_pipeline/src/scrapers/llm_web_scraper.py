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
load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')

# API Key validation
if api_key and api_key.startswith('sk-proj-') and len(api_key) > 10:
    print("API key looks good.")
else:
    print("There might be a problem with your API key. Please check!")

# Model configuration
MODEL = 'gpt-4o-mini'
openai = OpenAI()

# Logging configuration
logging.basicConfig(filename="scrape_errors.log", level=logging.ERROR)


class NewWebsite:
    shared_driver = None  # Shared browser instance across calls

    def __init__(self, url, driver=None, timeout=20, lang="auto"):
        self.url = url
        self.timeout = timeout
        self.lang = lang  # language param retained but unused now
        self.lang_switched = False  # Initialize lang_switched attribute
        self.driver = driver or NewWebsite._get_shared_driver()
        raw_text, self.title, self.links = self._scrape_content()
        self.text = self._clean_text(raw_text)

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

            # Configure Chrome service for ARM64 compatibility
            # Priority: container chromedriver > local ARM64 chromedriver > webdriver-manager
            chromedriver_paths = [
                "/usr/bin/chromedriver",  # Docker container path (ARM64 compatible)
                "/Users/iamai/.wdm/drivers/chromedriver/mac64/138.0.7204.157/chromedriver-mac-arm64/chromedriver"  # Local ARM64 path
            ]
            
            service = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    try:
                        service = Service(path)
                        cls.shared_driver = webdriver.Chrome(service=service, options=options)
                        print(f"Successfully initialized Chrome with driver: {path}")
                        break
                    except Exception as e:
                        print(f"Failed to use chromedriver at {path}: {e}")
                        continue
            
            if cls.shared_driver is None:
                # Fallback to webdriver-manager
                try:
                    service = Service(ChromeDriverManager().install())
                    cls.shared_driver = webdriver.Chrome(service=service, options=options)
                    print("Successfully initialized Chrome with webdriver-manager")
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
                            logging.warning(f"[WARN] Could not click popup close button: {e}")
        except Exception as e:
            logging.warning(f"[WARN] Failed to dismiss popup/modals: {e}")

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
                    logging.warning(f"[WARN] Failed to try button: {inner_click_error}")
                    continue

            print("[INFO] No English language switch button clicked.")
            return False

        except Exception as e:
            logging.warning(f"[WARN] Language switching failed: {e}")
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
    def close_driver(cls):
        if cls.shared_driver:
            cls.shared_driver.quit()
            cls.shared_driver = None

    @classmethod
    def initialize_driver(cls):
        if cls.shared_driver is None:
            cls._get_shared_driver()
