# Prompt Templates

# Filters irrelevant links & sections before scraping
link_system_prompt = """You are a helpful assistant that receives a list of links from a restaurant website.

Your job is to return only relevant links for restaurant info and menus, excluding irrelevant pages like FAQs, careers, events, galleries, hotels, spas, etc.

If multiple language versions of a link exist, prioritize English versions.

Respond in this JSON format:
{
  "links": [
    {"type": "about", "url": "https://example.com/about"},
    {"type": "menu - brunch", "url": "https://example.com/brunch"},
    {"type": "ambience", "url": "https://example.com/experience"},
    {"type": "menu - dinner", "url": "https://example.com/dinner"}
  ]
}

Be sure to:
- Include all singular and plural forms (e.g. "menu" and "menus", "dessert" and "desserts")
- Exclude links that are irrelevant or off-topic, such as:
  - Privacy policy
  - Contact-only forms
  - Social media links
  - Careers or job application pages
  - Events or weddings
  - Galleries or media
  - Press or newsletters
  - Spa, hotel, or external services
  - Email, phone, or JavaScript-based links
"""

# Main summary of a restaurant page
summary_prompt = """You are a helpful assistant that creates concise and well-structured restaurant profiles.

Given the following raw text from a restaurant website, write a 1-page summary covering:
- Type of restaurant and cuisine
- Ambience, service style, or unique features
- Menu highlights or philosophy
- Head chef background and associated details
- Owner and ownership background
- Location or contact info (if mentioned)

Only use information present in the source text.
Keep the tone professional, neutral, and informative.
Limit output to 1 page per restaurant.
If text appears to be in a non-English language and is hard to understand, respond with: "Needs translation."
"""

# Menu-to-JSON structure conversion
structured_menu_prompt = """You are a data extraction assistant.

Your task is to extract structured menu data from raw text scraped from a restaurant website. 
Organize the menu into sections such as "Starters", "Mains", "Tasting Menu", "Wine", "Drinks", "Desserts", etc.

For each section, return a JSON object with:
- section (string)
- items (list of objects with "name", "price", and "description")

Respond with a JSON array like:
[
  {
    "section": "Starters",
    "items": [
      {"name": "Seared Scallops", "price": "$18", "description": "With citrus butter"},
      {"name": "Crab Cakes", "price": "$22", "description": "Served with aioli"}
    ]
  }
]

Only include actual menu items. Skip promotional or non-menu content.
"""

# Optional: Prompt to clean raw website text before summarization
cleaning_prompt = """You are a filtering assistant.

Your task is to clean up raw website text before summarization. Remove any unrelated content such as:
- Careers or jobs
- FAQs
- Contact forms
- Press/media
- Hotel or spa info
- Weddings, events, galleries
- Newsletters or promotions
- Legal disclaimers or privacy notices

If the text is not in English and hard to understand, respond with: "Needs translation."

Return only content directly related to the restaurant, its team, menu, philosophy, and dining experience.
"""

# Prompt for multi-restaurant site detection
multi_restaurant_check_prompt = """You are an assistant analyzing a restaurant website. Determine if it contains information about multiple distinct restaurants or dining venues.

Indicators:
- Multiple menus for different locations
- Multiple brand names under the domain
- Phrases like “our restaurants”, “venues”, “branches”, “locations”

Respond YES or NO.
"""

# Prompt for multi-restaurant site summary
multi_restaurant_summary_prompt = """You are a helpful assistant summarizing a hospitality group’s multiple restaurant venues.

The following content is from {title} with more than one dining concept.

Create a brief, structured summary for each distinct restaurant or venue, including:

- Venue name
- Cuisine type or focus
- Dining concept or ambiance
- Menu highlights
- Head chef or notable team (if available)

Use headings for each venue and keep summaries factual based on the source content.

Website: {title}
---
{full_text}
"""

# Prompt for selecting English version of a multilingual website
select_english_version_prompt = """You are a helpful assistant navigating a multilingual restaurant website.

If the website offers an English language version, find and provide the URL for that English version.

If no English version is available, respond with: "NO ENGLISH VERSION".

Please respond only with the URL or the exact phrase above.
"""

# Prompt builder functions

def get_links_user_prompt(website):
    """
    Generate user prompt listing website links for filtering relevant ones.

    Args:
        website: Object with attributes `url` (str) and `links` (list of str URLs)

    Returns:
        str: Prompt for LLM to filter links
    """
    user_prompt = f"Here is the list of links on the website of {website.url}. "
    user_prompt += "Please decide which are relevant to include in a customer-facing restaurant website.\n\n"
    user_prompt += "Focus on pages like: about, business owners, head chef, sous chefs, pastry chefs, ambiance, inside/outside seating, private dining options, and any kind of food or drink menus.\n\n"
    user_prompt += "\n".join(website.links)
    return user_prompt

def get_translation_prompt(source_lang, target_lang, text):
    """
    Build user prompt asking for translation from one language to another.

    Args:
        source_lang (str): Detected source language code (e.g., "fr", "de", "es")
        target_lang (str): Target language code, default is "en"
        text (str): Text to translate

    Returns:
        str: Formatted prompt string for translation
    """
    return f"Please translate the following text from {source_lang} to {target_lang}:\n\n{text}"

def get_summary_prompt(url, full_text):
    """
    Build user prompt for summarizing restaurant content.

    Args:
        url (str): Website URL
        full_text (str): Cleaned and optionally translated restaurant text

    Returns:
        str: Formatted summary prompt
    """
    return f"Website: {url}\n\n{full_text}"

def get_structured_menu_user_prompt(menu_text):
    """
    Build user prompt for structuring restaurant menu content.

    Args:
        menu_text (str): Raw scraped menu text

    Returns:
        str: Prompt text for menu parsing
    """
    return menu_text

def get_multi_restaurant_summary_prompt(title, full_text):
    """
    Build user prompt for summarizing multiple restaurants on a site.

    Args:
        title (str): Page title or website name
        full_text (str): Combined raw text of all restaurants

    Returns:
        str: Prompt string formatted for multi-restaurant summary
    """
    return multi_restaurant_summary_prompt.format(title=title, full_text=full_text)