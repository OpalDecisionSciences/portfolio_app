# Standard library imports
import os
import csv
import json
import logging
import traceback
from pathlib import Path
import concurrent.futures

# External dependencies
import pandas as pd
from openai import OpenAI
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from dotenv import load_dotenv

# Handle both relative and absolute imports
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
# Handle both relative and absolute imports for templates
try:
    from .templates import (
        link_system_prompt,
        summary_prompt,
        structured_menu_prompt,
        cleaning_prompt,
        select_english_version_prompt,
        get_links_user_prompt,
        get_translation_prompt,
        get_summary_prompt, 
        get_structured_menu_user_prompt,
        get_multi_restaurant_summary_prompt
    )
except ImportError:
    from templates import (
        link_system_prompt,
        summary_prompt,
        structured_menu_prompt,
        cleaning_prompt,
        select_english_version_prompt,
        get_links_user_prompt,
        get_translation_prompt,
        get_summary_prompt, 
        get_structured_menu_user_prompt,
        get_multi_restaurant_summary_prompt
    )


# Set paths
base_path = Path(__file__).resolve().parent
# CSV file is located in the ingestion folder
data_path = Path("ingestion/michelin_my_maps.csv")
SUMMARY_DIR = Path("restaurant_docs")
SUMMARY_DIR.mkdir(exist_ok=True)

# For testing, use a smaller dataset
# In CLI : "head -n 5 datasets/michelin_my_maps.csv > datasets/test_run.csv"
#data_path = base_path / 'datasets' / 'test_run.csv'

# Load data
INPUT_CSV = None
if data_path.exists():
    INPUT_CSV = pd.read_csv(data_path)
    print(f"Loaded CSV with {len(INPUT_CSV)} rows from {data_path}")
else:
    print(f"Warning: CSV file not found at {data_path}")

OUTPUT_CSV = "scraped_output.csv"

# Load environment variables
load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
openai = OpenAI()

# Token management
MODEL_MINI = "gpt-4o-mini"
MODEL_FULL = "gpt-4o"
current_model = MODEL_FULL
token_usage = 0
TOKEN_LIMIT = 250_000
SWITCH_THRESHOLD = 240_000

# Batch processing configuration
BATCH_SIZE = 10 # Num websites per batch
PAUSE_BETWEEN_BATCHES = 5 # Seconds

# Logging
logging.basicConfig(filename="scrape_errors.log", level=logging.ERROR)

# Translation cache placeholder
translation_cache = {}

# Constants for noise filtering
IRRELEVANT_SECTIONS = [
    "faq", "career", "gallery", "event", "wedding", "spa", "hotel", "press", "media", "newsletter"
]

MULTIRESTAURANT_KEYWORDS = [
    "our restaurants", "locations", "dining options", "branches"
]

MENU_KEYWORDS = [
    "menu", "brunch", "lunch", "dinner", "tasting", "wine", "cocktail", "drink",
    "dessert", "beverage", "food", "appetizer", "entree", "main course", "snacks",
    "courses", "prix fixe", "soups", "salads", "set menu"
]

# Function definitions #

def log_and_print(level, message):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)
    else:
        logging.debug(message)

# Detect language of text
def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"

# Detect if website has multiple restaurant sections
def has_multiple_restaurants(text):
    return any(kw in text.lower() for kw in MULTIRESTAURANT_KEYWORDS)

# Filter irrelevant links based on type
def is_relevant_link(link_type):
    return not any(bad in link_type.lower() for bad in IRRELEVANT_SECTIONS)

# Translate multilingual text to English
def translate_text(text, source_lang, target_lang="en", force_model=MODEL_FULL, retries=2):
    if source_lang == target_lang:
        return text  # No need to translate

    for attempt in range(retries):
        translated = call_openai_chat(
            system_prompt="You are a professional translator fluent in all languages.",
            user_prompt=get_translation_prompt(source_lang, target_lang, text),
            force_model=force_model
        )
        if translated:
            return translated
        else:
            log_and_print("warning", f"[WARN] Translation attempt {attempt + 1} failed or token limit reached.")

    log_and_print("error", "[ERROR] All translation attempts failed, returning original text.")
    return text

# Updated get_filtered_links_and_landing after multilingual functionality incorporated
def get_filtered_links_and_landing(url):
    try:
        # Step 1: Check for an English version of the website
        original_website = NewWebsite(url)
        original_content = (original_website.text or "").strip()

        if not original_content or original_content.lower().startswith("error"):
            logging.warning(f"[WARN] Scraped landing page is empty or error for {url}: title='{original_website.title}'")
            return [], None

        english_url = url  # default fallback
        try:
            english_response = call_openai_chat(
                system_prompt=select_english_version_prompt,
                user_prompt=original_content[:4000],
                force_model="gpt-4o"
            )
            if english_response and english_response.strip().lower() != "no english version":
                english_url = english_response.strip()
                logging.info(f"[INFO] English version detected for {url} → {english_url}")
        except Exception as e:
            logging.warning(f"[WARN] Failed to detect English version for {url}: {e}")

        # Step 2: Load the appropriate website (original or English version)
        website = NewWebsite(english_url)
        content = (website.text or "").strip()

        if not content or content.lower().startswith("error"):
            logging.warning(f"[WARN] Scraped landing page is empty or error for {english_url}: title='{website.title}'")
            return [], None

        # Step 2.5: Detect language and translate if needed
        try:
            detected_lang = detect(content)
            if detected_lang != "en":
                logging.info(f"[INFO] Translating from {detected_lang} to English for {english_url}")
                website.text = translate_text(content, detected_lang, target_lang="en")
        except Exception as e:
            logging.warning(f"[WARN] Language detection or translation failed for {english_url}: {e}")

        # Step 3: Extract relevant links using LLM
        response_content = call_openai_chat(
            system_prompt=link_system_prompt,
            user_prompt=get_links_user_prompt(website),
            force_model=current_model
        )

        # Step 4: Robust JSON parsing
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            logging.error(f"[ERROR] JSON decode error for links from {english_url}")
            return [], website

        # Step 5: Filter out irrelevant links by type
        filtered_links = [link for link in result.get("links", []) if is_relevant_link(link.get("type", ""))]
        return filtered_links, website

    except Exception as e:
        logging.error(f"Error getting filtered links for {url}:\n{traceback.format_exc()}")
        return [], None
    
def scrape_link(link_obj):
    try:
        page = NewWebsite(link_obj["url"])
        text = page.text.strip()

        # Detect language and translate if needed
        try:
            detected_lang = detect(text)
            if detected_lang != "en":
                logging.info(f"[INFO] Translating from {detected_lang} to English for {link_obj['url']}")
                text = translate_text(text, detected_lang, target_lang="en")
        except Exception as e:
            logging.warning(f"[WARN] Language detection or translation failed for {link_obj['url']}: {e}")

        return {
            "type": link_obj["type"],
            "url": link_obj["url"],
            "title": page.title,
            "text": text,
        }
    except Exception as e:
        logging.error(f"Error scraping linked page {link_obj['url']}:\n{traceback.format_exc()}")
        return {
            "type": link_obj["type"],
            "url": link_obj["url"],
            "title": "Error",
            "text": f"Error loading page: {e}",
        }

def clean_filename(name):
    return"".join(c if c.isalnum() or c in "-_" else "_" for c in name.lower())[:60].strip("_")

# Summarize_and_save to optionally fallback to gpt-4o
def summarize_and_save(title, url, full_text, lang="en", is_multi=False, force_model=None):
    try:
        model_to_use = force_model or MODEL_MINI
        full_text_en = full_text

        if lang != "en":
            log_and_print("info", f"[INFO] Translating summary text from {lang} to English...")
            if full_text in translation_cache:
                full_text_en = translation_cache[full_text]
            else:
                full_text_en = translate_text(full_text, source_lang=lang, force_model=MODEL_FULL)
                translation_cache[full_text] = full_text_en

        cleaned_text = call_openai_chat(
            system_prompt=cleaning_prompt,
            user_prompt=full_text_en,
            force_model=model_to_use
        )
        if cleaned_text:
            full_text_en = cleaned_text.strip()

        user_prompt = (
            get_multi_restaurant_summary_prompt(title, full_text_en)
            if is_multi else
            get_summary_prompt(url, full_text_en)
        )

        response_content = call_openai_chat(
            system_prompt=summary_prompt,
            user_prompt=user_prompt,
            response_format='json',
            force_model=model_to_use
        )

        if not response_content or response_content.strip() == "{}":
            log_and_print("warning", "[WARN] Poor summary or token issue, retrying with gpt-4o...")
            response_content = call_openai_chat(
                system_prompt=summary_prompt,
                user_prompt=user_prompt,
                response_format='json',
                force_model=MODEL_FULL
            )

        try:
            summary = response_content.strip()
        except Exception as e:
            log_and_print("error", f"[ERROR] Could not parse summary content for {url}: {e}")
            return True

        filename_base = clean_filename(title or url or "restaurant")
        summary_path = SUMMARY_DIR / f"{filename_base}.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

        if lang != "en":
            orig_path = SUMMARY_DIR / f"{filename_base}_original_{lang}.txt"
            with open(orig_path, "w", encoding="utf-8") as f:
                f.write(full_text)

        log_and_print("info", f"[INFO] Saved summary: {summary_path.name}")
        return True

    except Exception as e:
        log_and_print("error", f"[ERROR] Summarization failed for {url}: {e}")
        return True
    
def structured_menu_to_csv(structured_menu, title_or_url):
    filename = f"{clean_filename(title_or_url)}_menu.csv"
    rows = []

    for section in structured_menu:
        for item in section.get("items", []):
            rows.append({
                "section": section.get("section", ""),
                "name": item.get("name", ""),
                "price": item.get("price", ""),
                "description": item.get("description", "")
            })
    if rows:
        with open(SUMMARY_DIR / filename, "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["section", "name", "price", "description"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV menu saved to: {filename}")

# Send scraped menu text to OpenAI and parse the response
def extract_structured_menu_from_text(menu_text, title_or_url, lang="en", force_model=None):
    try:
        model_to_use = force_model or MODEL_MINI

        if lang != "en":
            log_and_print("info", f"[INFO] Translating menu content from {lang} to English...")
            menu_text = translate_text(menu_text, source_lang=lang, target_lang="en", force_model=model_to_use)

        response_content = call_openai_chat(
            system_prompt=structured_menu_prompt,
            user_prompt=get_structured_menu_user_prompt(menu_text),
            response_format="json",
            force_model=model_to_use
        )

        if response_content is None:
            log_and_print("info", f"[INFO] Token limit hit during structured menu extraction.")
            return False

        try:
            data = json.loads(response_content)
        except json.JSONDecodeError:
            log_and_print("error", f"[ERROR] Failed to parse structured menu JSON for {title_or_url}")
            return []

        filename = f"{clean_filename(title_or_url or 'restaurant')}_menu.json"
        with open(SUMMARY_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log_and_print("info", f"Structured menu saved to: {filename}")
        return data

    except Exception as e:
        log_and_print("error", f"[ERROR] Structuring menu failed for {title_or_url}: {e}")
        return []
    
def extract_and_save_menu(title, landing_url, filtered_links, lang="en", force_model=None):
    try:
        model_to_use = force_model or MODEL_MINI

        menu_links = [
            link for link in filtered_links
            if any(keyword in link["type"].lower() for keyword in MENU_KEYWORDS)
        ]

        if not menu_links:
            log_and_print("info", f"No menu links found for {landing_url}")
            return True

        log_and_print("info", f"Found {len(menu_links)} menu link(s) for {landing_url}")
        menu_texts = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(scrape_link, link) for link in menu_links]
            for future in concurrent.futures.as_completed(futures):
                page = future.result()
                if page and "text" in page and page["text"].strip():
                    menu_texts.append(f"{page['type']}:\n{page['text']}\n")

        if not menu_texts:
            return True

        combined_text = "\n\n".join(menu_texts)

        filename = f"{clean_filename(title or landing_url or 'restaurant')}_menu.txt"
        with open(SUMMARY_DIR / filename, "w", encoding="utf-8") as f:
            f.write(combined_text)
        log_and_print("info", f"Saved menu content to {filename}")

        structured = extract_structured_menu_from_text(combined_text, title or landing_url, lang=lang, force_model=model_to_use)
        if structured is False:
            return False

        structured_menu_to_csv(structured, title or landing_url)
        return True

    except Exception as e:
        log_and_print("error", f"[ERROR] extract_and_save_menu failed: {e}")
        return True

# Threaded scraper for linked pages to support multi-restaurant detection
def scrape_website_and_save(url, writer):
    try:
        filtered_links, landing_page = get_filtered_links_and_landing(url)
        if not landing_page:
            print(f"[WARN] Could not load landing page for {url}. Skipping.")
            return True

        lang = detect_language(landing_page.text)
        print(f"[INFO] Detected language for {url}: {lang}")

        # Translate landing page text if needed (after scraping)
        translated_text = landing_page.text
        if lang != "en" and landing_page.text.strip():
            print(f"[INFO] Translating landing page content from {lang} to English...")
            if landing_page.text in translation_cache:
                translated_text = translation_cache[landing_page.text]
            else:
                translated_text = translate_text(landing_page.text, source_lang=lang, force_model="gpt-4o")
                translation_cache[landing_page.text] = translated_text

        # Detect if this website has multiple restaurant venues
        if has_multiple_restaurants(translated_text):
            print(f"[INFO] Detected multiple restaurants on {url}")

            # For each restaurant-specific link, scrape and summarize with is_multi=True
            restaurant_links = [link for link in filtered_links if "restaurant" in link["type"].lower()]
            for link in restaurant_links:
                subpage = scrape_link(link)
                if not subpage:
                    continue

                lang_sub = detect_language(subpage["text"])

                # Translate subpage text if needed
                subpage_text_translated = subpage["text"]
                if lang_sub != "en" and subpage["text"].strip():
                    if subpage["text"] in translation_cache:
                        subpage_text_translated = translation_cache[subpage["text"]]
                    else:
                        subpage_text_translated = translate_text(subpage["text"], source_lang=lang_sub, force_model="gpt-4o")
                        translation_cache[subpage["text"]] = subpage_text_translated

                # Pass is_multi=True so summarization uses multi-restaurant prompt
                summarize_and_save(
                    subpage["title"], link["url"], subpage_text_translated, lang="en", is_multi=True
                )
                extract_and_save_menu(subpage["title"], link["url"], filtered_links, lang="en")

            return True

        # Single-restaurant website flow
        writer.writerow([
            landing_page.url,
            landing_page.title,
            "landing page",
            landing_page.url,
            landing_page.title,
            translated_text
        ])

        summary_success = summarize_and_save(
            landing_page.title, landing_page.url, translated_text, lang="en", is_multi=False
        )
        if not summary_success:
            return False

        menu_success = extract_and_save_menu(
            landing_page.title, landing_page.url, filtered_links, lang="en"
        )
        if not menu_success:
            return False

        # Scrape linked pages concurrently and save content
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(scrape_link, link) for link in filtered_links]
            for future in concurrent.futures.as_completed(futures):
                page = future.result()
                if not page or "text" not in page:
                    continue

                # Translate linked page text if needed before saving
                page_text_translated = page["text"]
                lang_page = detect_language(page["text"])
                if lang_page != "en" and page["text"].strip():
                    if page["text"] in translation_cache:
                        page_text_translated = translation_cache[page["text"]]
                    else:
                        page_text_translated = translate_text(page["text"], source_lang=lang_page, force_model="gpt-4o")
                        translation_cache[page["text"]] = page_text_translated

                writer.writerow([
                    landing_page.url,
                    landing_page.title,
                    page["type"],
                    page["url"],
                    page["title"],
                    page_text_translated,
                ])

        return True

    except Exception as e:
        logging.error(f"[ERROR] Exception scraping {url}: {e}")
        traceback.print_exc()
        return True  # Continue to next URL even if one fails