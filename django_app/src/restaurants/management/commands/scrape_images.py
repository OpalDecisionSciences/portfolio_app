"""
Django management command to scrape restaurant images.

Usage:
    python manage.py scrape_images --test-url https://example.com
    python manage.py scrape_images --csv-file path/to/restaurants.csv --max-restaurants 5
    python manage.py scrape_images --restaurant-id <uuid>
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from restaurants.models import Restaurant, ImageScrapingJob
from restaurants.tasks import scrape_restaurant_images_task
import pandas as pd
import uuid
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape images for restaurants with AI categorization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-url',
            type=str,
            help='Test image scraping on a single URL'
        )
        
        parser.add_argument(
            '--restaurant-id',
            type=str,
            help='Scrape images for a specific restaurant ID'
        )
        
        parser.add_argument(
            '--csv-file',
            type=str,
            help='Path to CSV file with restaurant data'
        )
        
        parser.add_argument(
            '--max-restaurants',
            type=int,
            default=5,
            help='Maximum number of restaurants to process from CSV (default: 5)'
        )
        
        parser.add_argument(
            '--max-images',
            type=int,
            default=10,
            help='Maximum images per restaurant (default: 10)'
        )
        
        parser.add_argument(
            '--no-ai',
            action='store_true',
            help='Disable AI categorization for faster testing'
        )
        
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run as async Celery task instead of synchronously'
        )

    def handle(self, *args, **options):
        try:
            if options['test_url']:
                self.handle_test_url(options)
            elif options['restaurant_id']:
                self.handle_restaurant_id(options)
            elif options['csv_file']:
                self.handle_csv_file(options)
            else:
                raise CommandError('You must specify either --test-url, --restaurant-id, or --csv-file')
                
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise CommandError(f"Image scraping failed: {e}")

    def handle_test_url(self, options):
        """Test image scraping on a single URL."""
        test_url = options['test_url']
        
        self.stdout.write(f"Testing image scraping on: {test_url}")
        
        # Import here to avoid import issues
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "data_pipeline" / "src"))
        
        from scrapers.image_scraper import RestaurantImageScraper
        
        scraper = RestaurantImageScraper()
        
        results = scraper.scrape_restaurant_images(
            restaurant_url=test_url,
            restaurant_name="Test Restaurant",
            max_images=options['max_images'],
            enable_ai_categorization=not options['no_ai']
        )
        
        self.stdout.write(f"\n=== Image Scraping Results ===")
        self.stdout.write(f"Total images processed: {len(results)}")
        
        for i, result in enumerate(results, 1):
            status = result.get('status', 'unknown')
            category = result.get('ai_category', 'N/A')
            labels = result.get('ai_labels', [])
            
            self.stdout.write(f"{i}. Status: {status}")
            if status == 'completed':
                self.stdout.write(f"   Category: {category}")
                self.stdout.write(f"   Labels: {', '.join(labels[:3])}")
            elif status == 'failed':
                self.stdout.write(f"   Error: {result.get('error', 'Unknown error')}")
            self.stdout.write("")
        
        # Summary
        successful = len([r for r in results if r.get('status') == 'completed'])
        failed = len([r for r in results if r.get('status') == 'failed'])
        
        self.stdout.write(self.style.SUCCESS(f"Summary: {successful} successful, {failed} failed"))

    def handle_restaurant_id(self, options):
        """Scrape images for a specific restaurant."""
        restaurant_id = options['restaurant_id']
        
        try:
            restaurant = Restaurant.objects.get(id=restaurant_id)
        except Restaurant.DoesNotExist:
            raise CommandError(f"Restaurant with ID {restaurant_id} does not exist")
        
        self.stdout.write(f"Scraping images for: {restaurant.name}")
        
        # Create image scraping job
        job = ImageScrapingJob.objects.create(
            job_name=f"Manual scrape: {restaurant.name}",
            restaurant=restaurant,
            max_images_per_url=options['max_images'],
            enable_ai_categorization=not options['no_ai']
        )
        
        if options['async']:
            # Run as Celery task
            task = scrape_restaurant_images_task.delay(
                job_id=str(job.id),
                restaurant_id=restaurant_id,
                max_images_per_url=options['max_images']
            )
            
            self.stdout.write(f"Started async task: {task.id}")
            self.stdout.write(f"Job ID: {job.id}")
            self.stdout.write("Check job status in Django admin or database")
        else:
            # Run synchronously
            try:
                result = scrape_restaurant_images_task(
                    job_id=str(job.id),
                    restaurant_id=restaurant_id,
                    max_images_per_url=options['max_images']
                )
                
                self.stdout.write(self.style.SUCCESS("Image scraping completed!"))
                self.stdout.write(f"Results: {result}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Image scraping failed: {e}"))

    def handle_csv_file(self, options):
        """Scrape images for restaurants from a CSV file."""
        csv_file = options['csv_file']
        max_restaurants = options['max_restaurants']
        
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            raise CommandError(f"Failed to read CSV file: {e}")
        
        # Limit to max_restaurants
        if max_restaurants:
            df = df.head(max_restaurants)
        
        self.stdout.write(f"Processing {len(df)} restaurants from {csv_file}")
        
        # Extract URLs from CSV
        url_column = None
        for col in ['url', 'website', 'link', 'URL', 'Website']:
            if col in df.columns:
                url_column = col
                break
        
        if not url_column:
            raise CommandError("CSV file must contain a column named 'url', 'website', or 'link'")
        
        urls_list = df[url_column].dropna().tolist()
        
        if not urls_list:
            raise CommandError("No valid URLs found in CSV file")
        
        self.stdout.write(f"Found {len(urls_list)} URLs to process")
        
        # Create image scraping job
        job = ImageScrapingJob.objects.create(
            job_name=f"CSV batch scrape: {len(urls_list)} restaurants",
            source_urls=urls_list,
            max_images_per_url=options['max_images'],
            enable_ai_categorization=not options['no_ai']
        )
        
        if options['async']:
            # Run as Celery task
            task = scrape_restaurant_images_task.delay(
                job_id=str(job.id),
                urls_list=urls_list,
                max_images_per_url=options['max_images']
            )
            
            self.stdout.write(f"Started async task: {task.id}")
            self.stdout.write(f"Job ID: {job.id}")
            self.stdout.write("Monitor progress in Django admin or check job status in database")
        else:
            # Run synchronously
            try:
                result = scrape_restaurant_images_task(
                    job_id=str(job.id),
                    urls_list=urls_list,
                    max_images_per_url=options['max_images']
                )
                
                self.stdout.write(self.style.SUCCESS("Batch image scraping completed!"))
                self.stdout.write(f"Results: {result}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Batch image scraping failed: {e}"))