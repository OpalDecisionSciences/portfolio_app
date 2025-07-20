# 🍽️ Restaurant Scraping Guide

This guide explains how to process the `michelin_my_maps.csv` file and scrape restaurant data for your portfolio application.

## 📋 Available Scripts

### 1. Quick CSV Import (Recommended for Testing)
**File**: `src/scrapers/quick_csv_import.py`
- **Purpose**: Import basic restaurant data from CSV without web scraping
- **Speed**: Fast (no API calls)
- **Token Usage**: None

### 2. Full CSV Processor (Recommended for Production)
**File**: `src/scrapers/michelin_csv_processor.py`
- **Purpose**: Import CSV data + scrape additional details from restaurant websites
- **Speed**: Slower (makes API calls)
- **Token Usage**: Uses token manager for translations and content processing

### 3. Django Management Command
**File**: `django_app/src/restaurants/management/commands/process_michelin_csv.py`
- **Purpose**: Run the processor from Django's management interface
- **Integration**: Full Django integration with admin interface

## 🚀 Getting Started

### Step 1: Quick Test Import

Start with a quick import to verify everything works:

```bash
# Navigate to the data pipeline directory
cd /Users/iamai/projects/portfolio_app/data_pipeline/src/scrapers

# Run quick import (no web scraping)
python quick_csv_import.py
```

This will:
- ✅ Import all 20 Michelin restaurants from the CSV
- ✅ Create Restaurant records in your database
- ✅ No token usage or web scraping
- ✅ Complete in under 1 minute

### Step 2: Verify Import

Check your Django admin to see the imported restaurants:

```bash
# Navigate to Django directory
cd /Users/iamai/projects/portfolio_app/django_app/src

# Start Django server
python manage.py runserver
```

Visit: `http://localhost:8000/admin/` and check the Restaurants section.

### Step 3: Full Scraping (Optional)

Once basic import works, run the full scraper for additional data:

```bash
# Navigate to data pipeline directory
cd /Users/iamai/projects/portfolio_app/data_pipeline/src/scrapers

# Run full processor with web scraping
python michelin_csv_processor.py
```

Or use the Django management command:

```bash
# Navigate to Django directory
cd /Users/iamai/projects/portfolio_app/django_app/src

# Run via Django management command
python manage.py process_michelin_csv
```

## 🔧 Advanced Usage

### Resume Processing

If scraping stops due to token limits, resume from a specific row:

```bash
# Resume from row 10
python manage.py process_michelin_csv --start-row 10
```

### Limit Processing

Process only a subset of restaurants:

```bash
# Process only first 5 restaurants
python manage.py process_michelin_csv --max-restaurants 5
```

### Skip Web Scraping

Import only CSV data using Django command:

```bash
# Import CSV data without web scraping
python manage.py process_michelin_csv --no-scraping
```

### Custom CSV File

Use a different CSV file:

```bash
python manage.py process_michelin_csv --csv-path /path/to/your/file.csv
```

## 📊 What Gets Imported

### From CSV File
- ✅ Restaurant name and description
- ✅ Location (city, country, address)
- ✅ Coordinates (latitude, longitude)
- ✅ Contact info (phone, website)
- ✅ Michelin stars (1-3 stars)
- ✅ Cuisine type
- ✅ Price range ($, $$, $$$, $$$$)
- ✅ Original Michelin Guide URL

### From Web Scraping (if enabled)
- ✅ Extended descriptions
- ✅ Opening hours
- ✅ Menu sections and items
- ✅ Chef information
- ✅ Additional restaurant details
- ✅ Translated content (non-English sites)

## 🎯 Token Management

The scraper uses intelligent token management:

### Translation Quality
- ✅ All translations use **gpt-4o** for highest quality
- ✅ Forced model selection ensures accuracy

### Budget Protection
- ✅ Starts with gpt-4o (250k tokens)
- ✅ Auto-switches to gpt-4o-mini (2.5M tokens)
- ✅ Stops gracefully when limits reached
- ✅ Daily reset functionality

### Monitor Usage
Check token usage via the RAG service:
```bash
curl http://localhost:8001/token-usage
```

## 📁 File Structure

```
data_pipeline/
├── src/
│   ├── ingestion/
│   │   └── michelin_my_maps.csv          # Source data
│   ├── scrapers/
│   │   ├── quick_csv_import.py           # Fast CSV import
│   │   ├── michelin_csv_processor.py     # Full processor
│   │   ├── restaurant_scraper.py         # Core scraper
│   │   └── scrape_utils.py              # Utilities
│   └── processors/
│       └── data_processor.py             # Database integration
└── SCRAPING_GUIDE.md                     # This file
```

## 🔍 Troubleshooting

### Common Issues

**1. CSV File Not Found**
```bash
# Check if file exists
ls /Users/iamai/projects/portfolio_app/data_pipeline/src/ingestion/michelin_my_maps.csv
```

**2. Django Import Errors**
```bash
# Make sure Django environment is set up
cd /Users/iamai/projects/portfolio_app/django_app/src
python manage.py check
```

**3. Token Limits Reached**
- Use `--start-row` to resume processing
- Check token usage with `/token-usage` endpoint
- Wait for daily reset or use quick import

**4. Database Errors**
```bash
# Run migrations if needed
python manage.py migrate
```

### Logs and Monitoring

**View Processing Logs**:
- Check `shared/token_management/logs/token_manager.log`
- Django logs show import progress
- Scraping jobs tracked in Django admin

**Monitor Progress**:
- Django admin shows ScrapingJob progress
- Token usage endpoint shows current limits
- Console output shows real-time progress

## 🎉 Expected Results

After running the full processor, you should have:

- ✅ **20 Michelin-starred restaurants** in your database
- ✅ **Rich descriptions** with AI translations
- ✅ **Menu data** for restaurants with accessible menus
- ✅ **Chef information** where available
- ✅ **Geocoded locations** for map integration
- ✅ **Categorized images** (if image scraping enabled)
- ✅ **Recommendation data** ready for the recommender system

The restaurants will be immediately available in:
- 🔍 **Search functionality** on your frontend
- 🤖 **Recommender system** for similar restaurants
- 💬 **RAG service** for AI-powered restaurant queries
- 🖼️ **Image galleries** (if additional scraping performed)

## 🚀 Next Steps

1. **Start with quick import** to verify setup
2. **Check admin interface** to confirm data import
3. **Test frontend search** with imported restaurants
4. **Run full scraper** for additional details
5. **Set up image scraping** for visual content
6. **Configure RAG embeddings** for AI search

Happy scraping! 🍽️✨