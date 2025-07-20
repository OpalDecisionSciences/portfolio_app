#!/usr/bin/env python3
"""
Monitor comprehensive scraping progress and provide detailed status
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add Django paths
sys.path.insert(0, str(Path(__file__).resolve().parent / "django_app" / "src"))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
import django
django.setup()

from restaurants.models import Restaurant
from django.utils import timezone

def check_scraping_process():
    """Check if scraping process is running."""
    try:
        result = subprocess.run(['pgrep', '-f', 'scrape_michelin_comprehensive.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, None
    except Exception as e:
        return False, str(e)

def get_scraping_stats():
    """Get comprehensive scraping statistics."""
    now = timezone.now()
    
    # Recent activity (last hour)
    recent_hour = now - timedelta(hours=1)
    recent_restaurants = Restaurant.objects.filter(scraped_at__gte=recent_hour)
    
    # Very recent activity (last 10 minutes)
    very_recent = now - timedelta(minutes=10)
    very_recent_restaurants = Restaurant.objects.filter(scraped_at__gte=very_recent)
    
    # Data quality stats
    with_images = Restaurant.objects.filter(images__isnull=False).distinct().count()
    with_timezone = Restaurant.objects.filter(timezone_info__isnull=False).count()
    with_cuisine = Restaurant.objects.exclude(cuisine_type="").count()
    with_content = Restaurant.objects.exclude(scraped_content="").count()
    
    # Latest scraping results
    latest_results_dir = Path("michelin_scraping_results")
    latest_result_file = None
    if latest_results_dir.exists():
        result_files = list(latest_results_dir.glob("final_results_*.json"))
        if result_files:
            latest_result_file = max(result_files, key=lambda x: x.stat().st_mtime)
    
    return {
        'total_restaurants': Restaurant.objects.count(),
        'recent_hour_count': recent_restaurants.count(),
        'very_recent_count': very_recent_restaurants.count(),
        'data_quality': {
            'with_images': with_images,
            'with_timezone': with_timezone,
            'with_cuisine': with_cuisine,
            'with_content': with_content
        },
        'recent_restaurants': list(recent_restaurants.order_by('-scraped_at')[:5].values_list('name', 'city', 'country', 'scraped_at')),
        'latest_result_file': str(latest_result_file) if latest_result_file else None
    }

def format_time_ago(dt):
    """Format time difference in human readable format."""
    if not dt:
        return "Unknown"
    
    diff = timezone.now() - dt
    minutes = diff.total_seconds() / 60
    
    if minutes < 1:
        return "Just now"
    elif minutes < 60:
        return f"{int(minutes)}m ago"
    else:
        hours = minutes / 60
        return f"{hours:.1f}h ago"

def main():
    """Main monitoring function."""
    print("🔍 COMPREHENSIVE SCRAPING MONITOR")
    print("=" * 60)
    print(f"📅 Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check process status
    is_running, process_info = check_scraping_process()
    status_icon = "🟢" if is_running else "🔴"
    print(f"{status_icon} Scraping Process: {'RUNNING' if is_running else 'STOPPED'}")
    if is_running:
        print(f"   Process ID: {process_info}")
    print()
    
    # Get statistics
    stats = get_scraping_stats()
    
    print("📊 SCRAPING STATISTICS")
    print(f"   Total restaurants in database: {stats['total_restaurants']:,}")
    print(f"   Scraped in last hour: {stats['recent_hour_count']}")
    print(f"   Scraped in last 10 minutes: {stats['very_recent_count']}")
    print()
    
    print("📈 DATA QUALITY METRICS")
    quality = stats['data_quality']
    print(f"   Restaurants with images: {quality['with_images']:,}")
    print(f"   Restaurants with timezone info: {quality['with_timezone']:,}")
    print(f"   Restaurants with cuisine type: {quality['with_cuisine']:,}")
    print(f"   Restaurants with scraped content: {quality['with_content']:,}")
    print()
    
    print("🕐 RECENT ACTIVITY")
    if stats['recent_restaurants']:
        for name, city, country, scraped_at in stats['recent_restaurants']:
            time_str = format_time_ago(scraped_at)
            print(f"   ✅ {name} ({city}, {country}) - {time_str}")
    else:
        print("   No recent scraping activity")
    print()
    
    # Show latest results file
    if stats['latest_result_file']:
        print(f"📁 Latest results file: {stats['latest_result_file']}")
        try:
            with open(stats['latest_result_file'], 'r') as f:
                data = json.load(f)
                if 'results' in data:
                    results = data['results']
                    print(f"   Success rate: {results.get('success_rate', 'N/A')}%")
                    print(f"   Total processed: {results.get('total_processed', 'N/A')}")
                    print(f"   Successful: {results.get('successful_scrapes', 'N/A')}")
                    print(f"   Failed: {results.get('failed_scrapes', 'N/A')}")
        except Exception as e:
            print(f"   Error reading results file: {e}")
    
    print()
    print("=" * 60)
    
    # Rate calculation
    if stats['recent_hour_count'] > 0:
        rate_per_hour = stats['recent_hour_count']
        rate_per_minute = rate_per_hour / 60
        estimated_completion = (18113 - stats['total_restaurants']) / rate_per_hour if rate_per_hour > 0 else float('inf')
        print(f"⚡ Current scraping rate: ~{rate_per_hour} restaurants/hour ({rate_per_minute:.1f}/min)")
        if estimated_completion < 24:
            print(f"⏱️  Estimated completion: ~{estimated_completion:.1f} hours")
        else:
            print(f"⏱️  Estimated completion: ~{estimated_completion/24:.1f} days")
    
    print("✅ Monitoring check completed!")

if __name__ == "__main__":
    main()