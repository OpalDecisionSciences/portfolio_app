"""
Celery tasks for the restaurants app.
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import sys
import os
from pathlib import Path

# Add the shared modules to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'shared' / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'data_pipeline' / 'src'))

from token_management.token_manager import init_token_manager
from scrapers.restaurant_scraper import RestaurantScraper
from processors.data_processor import DataProcessor
from .models import Restaurant, ScrapingJob, Chef, MenuSection, MenuItem
import logging
import json


logger = logging.getLogger(__name__)


@shared_task
def scrape_restaurants_task(job_id, urls_list, batch_size=10):
    """
    Celery task to scrape restaurant data from URLs.
    
    Args:
        job_id: UUID of the scraping job
        urls_list: List of URLs to scrape
        batch_size: Number of URLs to process in each batch
    """
    try:
        # Get the scraping job
        job = ScrapingJob.objects.get(id=job_id)
        job.status = 'running'
        job.started_at = timezone.now()
        job.total_urls = len(urls_list)
        job.save()
        
        # Initialize token manager
        token_dir = Path(settings.PORTFOLIO_TOKEN_MANAGEMENT_DIR)
        init_token_manager(token_dir)
        
        # Initialize scraper
        scraper = RestaurantScraper()
        processor = DataProcessor()
        
        successful_urls = []
        failed_urls = []
        
        for i in range(0, len(urls_list), batch_size):
            batch = urls_list[i:i + batch_size]
            
            for url in batch:
                try:
                    # Scrape restaurant data
                    scraped_data = scraper.scrape_restaurant(url)
                    
                    if scraped_data:
                        # Process and save to database
                        restaurant = processor.process_restaurant_data(scraped_data)
                        
                        if restaurant:
                            successful_urls.append(url)
                            logger.info(f"Successfully processed: {url}")
                        else:
                            failed_urls.append(url)
                            logger.error(f"Failed to process data for: {url}")
                    else:
                        failed_urls.append(url)
                        logger.error(f"Failed to scrape: {url}")
                        
                except Exception as e:
                    failed_urls.append(url)
                    logger.error(f"Error processing {url}: {str(e)}")
                
                # Update job progress
                job.processed_urls += 1
                job.successful_urls = len(successful_urls)
                job.failed_urls = len(failed_urls)
                job.save()
        
        # Update final job status
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.results = {
            'successful_urls': successful_urls,
            'failed_urls': failed_urls,
            'total_processed': len(successful_urls) + len(failed_urls)
        }
        job.save()
        
        logger.info(f"Scraping job {job_id} completed. Success: {len(successful_urls)}, Failed: {len(failed_urls)}")
        
        return {
            'job_id': str(job_id),
            'successful': len(successful_urls),
            'failed': len(failed_urls),
            'total': len(urls_list)
        }
        
    except Exception as e:
        # Update job status to failed
        job = ScrapingJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_log = str(e)
        job.completed_at = timezone.now()
        job.save()
        
        logger.error(f"Scraping job {job_id} failed: {str(e)}")
        raise


@shared_task
def update_restaurant_embeddings(restaurant_id):
    """
    Update embeddings for a restaurant.
    
    Args:
        restaurant_id: UUID of the restaurant
    """
    try:
        from rag_service.src.embeddings.embedding_generator import EmbeddingGenerator
        
        restaurant = Restaurant.objects.get(id=restaurant_id)
        embedding_generator = EmbeddingGenerator()
        
        # Generate embeddings for restaurant content
        content = f"""
        {restaurant.name}
        {restaurant.description}
        {restaurant.city}, {restaurant.country}
        Cuisine: {restaurant.cuisine_type}
        Michelin Stars: {restaurant.michelin_stars}
        Price Range: {restaurant.price_range}
        Atmosphere: {restaurant.atmosphere}
        """
        
        # Add menu content
        menu_content = []
        for section in restaurant.menu_sections.all():
            menu_content.append(f"{section.name}: {section.description}")
            for item in section.items.all():
                menu_content.append(f"{item.name} - {item.description}")
        
        if menu_content:
            content += "\nMenu:\n" + "\n".join(menu_content)
        
        # Generate and store embeddings
        embedding_generator.generate_and_store_embeddings(
            restaurant_id=str(restaurant.id),
            content=content,
            metadata={
                'restaurant_name': restaurant.name,
                'city': restaurant.city,
                'country': restaurant.country,
                'cuisine_type': restaurant.cuisine_type,
                'michelin_stars': restaurant.michelin_stars,
                'price_range': restaurant.price_range,
            }
        )
        
        logger.info(f"Updated embeddings for restaurant: {restaurant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update embeddings for restaurant {restaurant_id}: {str(e)}")
        raise


@shared_task
def process_scraped_data(scraped_data):
    """
    Process scraped restaurant data and save to database.
    
    Args:
        scraped_data: Dictionary containing scraped restaurant information
    """
    try:
        processor = DataProcessor()
        restaurant = processor.process_restaurant_data(scraped_data)
        
        if restaurant:
            # Update embeddings asynchronously
            update_restaurant_embeddings.delay(restaurant.id)
            
            logger.info(f"Successfully processed restaurant: {restaurant.name}")
            return {
                'success': True,
                'restaurant_id': str(restaurant.id),
                'restaurant_name': restaurant.name
            }
        else:
            logger.error(f"Failed to process scraped data")
            return {
                'success': False,
                'error': 'Failed to process scraped data'
            }
            
    except Exception as e:
        logger.error(f"Error processing scraped data: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_scraping_jobs(days_old=30):
    """
    Clean up old scraping jobs.
    
    Args:
        days_old: Number of days old jobs should be before deletion
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        old_jobs = ScrapingJob.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        )
        
        count = old_jobs.count()
        old_jobs.delete()
        
        logger.info(f"Cleaned up {count} old scraping jobs")
        
        return {
            'cleaned_up': count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old scraping jobs: {str(e)}")
        raise


@shared_task
def batch_update_embeddings():
    """
    Batch update embeddings for all restaurants.
    """
    try:
        restaurants = Restaurant.objects.filter(is_active=True)
        
        for restaurant in restaurants:
            update_restaurant_embeddings.delay(restaurant.id)
        
        logger.info(f"Queued embedding updates for {restaurants.count()} restaurants")
        
        return {
            'queued': restaurants.count()
        }
        
    except Exception as e:
        logger.error(f"Error in batch embedding update: {str(e)}")
        raise