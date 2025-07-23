"""
Celery tasks for the restaurants app.
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import sys
import os
from pathlib import Path

# Setup portfolio paths for cross-component imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "src"))
from config import setup_portfolio_paths
setup_portfolio_paths()

from token_management.token_manager import init_token_manager
from scrapers.restaurant_scraper import RestaurantScraper
from processors.data_processor import DataProcessor
from .models import Restaurant, ScrapingJob, Chef, MenuSection, MenuItem, RestaurantImage, ImageScrapingJob
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
        # Import locally to avoid circular import
        import requests
        rag_service_url = getattr(settings, 'RAG_SERVICE_URL', 'http://localhost:8001')
        
        restaurant = Restaurant.objects.get(id=restaurant_id)
        
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
        
        # Call RAG service to generate and store embeddings
        metadata = {
            'restaurant_name': restaurant.name,
            'city': restaurant.city,
            'country': restaurant.country,
            'cuisine_type': restaurant.cuisine_type,
            'michelin_stars': restaurant.michelin_stars,
            'price_range': restaurant.price_range,
        }
        
        response = requests.post(
            f"{rag_service_url}/embeddings/generate",
            json={"content": content, "metadata": metadata}
        )
        response.raise_for_status()
        
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


@shared_task
def scrape_restaurant_images_task(job_id, restaurant_id=None, urls_list=None, max_images_per_url=20):
    """
    Celery task to scrape images for restaurants.
    
    Args:
        job_id: UUID of the image scraping job
        restaurant_id: UUID of specific restaurant (optional)
        urls_list: List of URLs to scrape (optional, overrides restaurant_id)
        max_images_per_url: Maximum images to scrape per URL
    """
    try:
        # Get the image scraping job
        job = ImageScrapingJob.objects.get(id=job_id)
        job.status = 'running'
        job.started_at = timezone.now()
        job.save()
        
        # Import image scraper
        from scrapers.image_scraper import RestaurantImageScraper
        
        # Initialize scraper
        scraper = RestaurantImageScraper()
        
        # Determine what to scrape
        if urls_list:
            # Scrape from provided URLs
            job.source_urls = urls_list
            restaurants_to_process = []
            for url in urls_list:
                # Try to find existing restaurant with this URL
                restaurant = Restaurant.objects.filter(original_url=url).first()
                if restaurant:
                    restaurants_to_process.append((restaurant, url))
                else:
                    # Create a temporary entry for tracking
                    restaurants_to_process.append((None, url))
        elif restaurant_id:
            # Scrape for specific restaurant
            restaurant = Restaurant.objects.get(id=restaurant_id)
            restaurants_to_process = [(restaurant, restaurant.original_url or restaurant.website)]
        else:
            raise ValueError("Either restaurant_id or urls_list must be provided")
        
        job.total_images_found = 0
        job.save()
        
        successful_images = 0
        failed_images = 0
        
        for restaurant, url in restaurants_to_process:
            if not url:
                logger.warning(f"No URL available for restaurant {restaurant.name if restaurant else 'Unknown'}")
                continue
            
            try:
                from urllib.parse import urlparse
                restaurant_name = restaurant.name if restaurant else f"Restaurant_{urlparse(url).netloc}"
                
                logger.info(f"Scraping images for {restaurant_name} from {url}")
                
                # Scrape images for this restaurant
                image_results = scraper.scrape_restaurant_images(
                    restaurant_url=url,
                    restaurant_name=restaurant_name,
                    max_images=max_images_per_url,
                    enable_ai_categorization=job.enable_ai_categorization
                )
                
                job.total_images_found += len(image_results)
                
                # Save images to database
                for img_data in image_results:
                    try:
                        if img_data.get('status') in ['completed', 'downloaded']:
                            # Create RestaurantImage record
                            restaurant_image = RestaurantImage.objects.create(
                                restaurant=restaurant,
                                source_url=img_data.get('source_url', ''),
                                caption=f"Scraped from {restaurant_name}",
                                ai_category=img_data.get('ai_category', 'uncategorized'),
                                ai_labels=img_data.get('ai_labels', []),
                                ai_description=img_data.get('ai_description', ''),
                                category_confidence=img_data.get('category_confidence', 0.0),
                                description_confidence=img_data.get('description_confidence', 0.0),
                                width=img_data.get('width'),
                                height=img_data.get('height'),
                                file_size=img_data.get('file_size'),
                                processing_status='completed' if img_data.get('ai_category') else 'pending',
                                processed_at=timezone.now() if img_data.get('ai_category') else None
                            )
                            
                            # Copy the image file to Django media directory if local_path exists
                            if img_data.get('local_path'):
                                # TODO: Copy file to Django MEDIA_ROOT and update image field
                                pass
                            
                            successful_images += 1
                            job.images_downloaded += 1
                            
                            if img_data.get('ai_category') and img_data.get('ai_category') != 'uncategorized':
                                job.images_categorized += 1
                                
                        else:
                            failed_images += 1
                            job.images_failed += 1
                            
                        job.images_processed += 1
                        job.save()
                        
                    except Exception as e:
                        logger.error(f"Error saving image data: {e}")
                        failed_images += 1
                        job.images_failed += 1
                        job.save()
                
            except Exception as e:
                logger.error(f"Error scraping images for {restaurant_name}: {e}")
                job.error_log += f"Error for {restaurant_name}: {str(e)}\n"
                job.save()
        
        # Update final job status
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.results = {
            'total_processed': job.images_processed,
            'successful': successful_images,
            'failed': failed_images,
            'categorized': job.images_categorized
        }
        job.save()
        
        logger.info(f"Image scraping job {job_id} completed. Downloaded: {successful_images}, Failed: {failed_images}")
        
        return {
            'job_id': str(job_id),
            'successful': successful_images,
            'failed': failed_images,
            'total_processed': job.images_processed,
            'categorized': job.images_categorized
        }
        
    except Exception as e:
        # Update job status to failed
        try:
            job = ImageScrapingJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_log += f"Task failed: {str(e)}\n"
            job.completed_at = timezone.now()
            job.save()
        except:
            pass
        
        logger.error(f"Image scraping job {job_id} failed: {str(e)}")
        raise


@shared_task
def process_image_ai_categorization(image_id):
    """
    Process AI categorization for a single image.
    
    Args:
        image_id: UUID of the RestaurantImage to process
    """
    try:
        from scrapers.image_scraper import RestaurantImageScraper
        
        image = RestaurantImage.objects.get(id=image_id)
        
        if image.processing_status == 'completed':
            logger.info(f"Image {image_id} already processed")
            return {'status': 'already_completed'}
        
        image.processing_status = 'processing'
        image.save()
        
        # Download image if not already local
        if not image.image and image.source_url:
            scraper = RestaurantImageScraper()
            
            # Generate filename
            filename = f"{image.restaurant.slug}_{image.id}.jpg"
            
            # Download the image
            image_path = scraper.download_image(image.source_url, filename)
            
            if not image_path:
                image.processing_status = 'failed'
                image.processing_error = 'Failed to download image'
                image.save()
                return {'status': 'download_failed'}
            
            # TODO: Move downloaded image to Django media directory
            # and update image.image field
        
        # Run AI categorization if we have a local image path
        if image.image or image.source_url:
            scraper = RestaurantImageScraper()
            
            # For now, we'll use the source URL for AI analysis
            # In production, you'd want to use the local file
            if image.source_url:
                # This is a simplified approach - in production you'd want to
                # ensure the image is downloaded locally first
                ai_result = scraper.categorize_image_with_ai(image.source_url)
                
                # Update image with AI results
                image.ai_category = ai_result.get('category', 'uncategorized')
                image.ai_labels = ai_result.get('labels', [])
                image.ai_description = ai_result.get('description', '')
                image.category_confidence = ai_result.get('category_confidence', 0.0)
                image.description_confidence = ai_result.get('description_confidence', 0.0)
                image.processing_status = 'completed'
                image.processed_at = timezone.now()
                image.save()
                
                logger.info(f"AI categorization completed for image {image_id}: {image.ai_category}")
                
                return {
                    'status': 'completed',
                    'category': image.ai_category,
                    'confidence': image.category_confidence
                }
        
        image.processing_status = 'failed'
        image.processing_error = 'No image available for processing'
        image.save()
        
        return {'status': 'no_image'}
        
    except Exception as e:
        # Update image status to failed
        try:
            image = RestaurantImage.objects.get(id=image_id)
            image.processing_status = 'failed'
            image.processing_error = str(e)
            image.save()
        except:
            pass
        
        logger.error(f"AI categorization failed for image {image_id}: {str(e)}")
        raise


@shared_task
def batch_process_pending_images():
    """
    Process AI categorization for all pending images.
    """
    try:
        pending_images = RestaurantImage.objects.filter(
            processing_status='pending'
        ).order_by('created_at')
        
        processed = 0
        failed = 0
        
        for image in pending_images:
            try:
                result = process_image_ai_categorization.delay(image.id)
                processed += 1
                
                # Add small delay to avoid overwhelming the API
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error queuing image {image.id} for processing: {e}")
                failed += 1
        
        logger.info(f"Queued {processed} images for AI categorization, {failed} failed")
        
        return {
            'queued': processed,
            'failed': failed
        }
        
    except Exception as e:
        logger.error(f"Error in batch image processing: {str(e)}")
        raise


@shared_task  
def cleanup_old_image_scraping_jobs(days_old=30):
    """
    Clean up old image scraping jobs.
    
    Args:
        days_old: Number of days old jobs should be before deletion
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        old_jobs = ImageScrapingJob.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        )
        
        count = old_jobs.count()
        old_jobs.delete()
        
        logger.info(f"Cleaned up {count} old image scraping jobs")
        
        return {
            'cleaned_up': count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old image scraping jobs: {str(e)}")
        raise


# New async scraping tasks
@shared_task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_scraping_backlog_task(self, max_tasks=50):
    """
    Celery task to process the scraping backlog.
    
    Args:
        max_tasks: Maximum number of tasks to process
        
    Returns:
        dict: Processing results
    """
    try:
        # Add data pipeline to path for async_scraper_manager
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers"))
        
        from async_scraper_manager import get_scraper_manager
        
        scraper_manager = get_scraper_manager()
        results = scraper_manager.process_backlog(max_tasks=max_tasks)
        
        logger.info(f"Processed {results['processed']} backlog tasks: {results['successful']} successful, {results['failed']} failed")
        
        return {
            'success': True,
            'processed': results['processed'],
            'successful': results['successful'],
            'failed': results['failed'],
            'backlog_stats': results.get('backlog_stats', {}),
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Backlog processing task failed: {e}")
        # Retry the task
        raise self.retry(exc=e)


@shared_task(bind=True)
def add_scraping_task_to_backlog_task(self, url, restaurant_name, task_type='images', priority=1):
    """
    Add a scraping task to the backlog.
    
    Args:
        url: Restaurant website URL
        restaurant_name: Name of the restaurant
        task_type: Type of scraping task ('images', 'text', 'comprehensive')
        priority: Task priority (1-10, higher is more important)
        
    Returns:
        dict: Task creation result
    """
    try:
        # Add data pipeline to path for async_scraper_manager
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers"))
        
        from async_scraper_manager import get_scraper_manager
        
        scraper_manager = get_scraper_manager()
        task_id = scraper_manager.add_task_to_backlog(
            url=url,
            restaurant_name=restaurant_name,
            task_type=task_type,
            priority=priority
        )
        
        logger.info(f"Added {task_type} scraping task for {restaurant_name}: {task_id}")
        
        return {
            'success': True,
            'task_id': task_id,
            'message': f"Added {task_type} scraping task for {restaurant_name}"
        }
        
    except Exception as e:
        logger.error(f"Failed to add scraping task: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def get_backlog_stats_task():
    """
    Get current backlog statistics.
    
    Returns:
        dict: Backlog statistics
    """
    try:
        # Add data pipeline to path for async_scraper_manager
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers"))
        
        from async_scraper_manager import get_scraper_manager
        
        scraper_manager = get_scraper_manager()
        stats = scraper_manager.get_backlog_stats()
        
        return {
            'success': True,
            'stats': stats,
            'retrieved_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get backlog stats: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, retry_kwargs={'max_retries': 2, 'countdown': 300})
def periodic_backlog_processing_task(self):
    """
    Periodic task to process scraping backlog.
    This should be scheduled to run every 30 minutes.
    
    Returns:
        dict: Processing results
    """
    try:
        # Process up to 25 tasks every 30 minutes
        result = process_scraping_backlog_task.delay(max_tasks=25)
        
        return {
            'success': True,
            'message': 'Periodic backlog processing started',
            'task_id': result.id,
            'scheduled_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Periodic backlog processing failed: {e}")
        raise self.retry(exc=e)