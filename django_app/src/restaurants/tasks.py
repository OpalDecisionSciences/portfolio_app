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
                
                # Trigger enhanced embedding update with new AI image classification
                try:
                    update_restaurant_embeddings_with_images.delay(image.restaurant.id)
                    logger.info(f"Queued enhanced embedding update for {image.restaurant.name} after AI classification")
                except Exception as e:
                    logger.warning(f"Failed to queue enhanced embedding update: {e}")
                
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


@shared_task
def update_document_embeddings(restaurant_name, document_file_path=None):
    """
    Update document embeddings for a restaurant when new document is created.
    
    Args:
        restaurant_name: Name of the restaurant
        document_file_path: Optional path to specific document file
    """
    try:
        import requests
        rag_service_url = getattr(settings, 'RAG_SERVICE_URL', 'http://localhost:8001')
        
        # If no specific file path, construct it from restaurant name
        if not document_file_path:
            from pathlib import Path
            # Clean restaurant name for filename matching
            clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in restaurant_name.lower())[:50]
            docs_dir = Path(__file__).parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers" / "restaurant_docs"
            document_file_path = docs_dir / f"{clean_name}_document.txt"
        
        # Check if document file exists
        from pathlib import Path
        doc_path = Path(document_file_path)
        if not doc_path.exists():
            logger.warning(f"Document file not found: {document_file_path}")
            return {'success': False, 'error': 'Document file not found'}
        
        # Read document content
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            logger.warning(f"Empty document content: {document_file_path}")
            return {'success': False, 'error': 'Empty document content'}
        
        # Enhance content with restaurant name context
        enhanced_content = f"Restaurant: {restaurant_name}\n\n{content}"
        
        # Try to find matching restaurant in database for metadata
        restaurant = None
        try:
            restaurant = Restaurant.objects.filter(
                name__iexact=restaurant_name.strip(),
                is_active=True
            ).first()
            
            if not restaurant:
                # Try partial name match
                restaurant = Restaurant.objects.filter(
                    name__icontains=restaurant_name.split()[0],
                    is_active=True
                ).first()
        except Exception as e:
            logger.warning(f"Could not find restaurant in database: {e}")
        
        # Create metadata
        metadata = {
            'source': 'scraped_document',
            'document_file': str(doc_path.name),
            'restaurant_name': restaurant_name,
            'restaurant_id': str(restaurant.id) if restaurant else None,
            'city': restaurant.city if restaurant else None,
            'country': restaurant.country if restaurant else None,
            'michelin_stars': restaurant.michelin_stars if restaurant else 0,
            'cuisine_type': restaurant.cuisine_type if restaurant else None,
            'processed_at': timezone.now().isoformat()
        }
        
        # Call RAG service to generate and store embeddings
        response = requests.post(
            f"{rag_service_url}/embeddings/generate",
            data={
                'content': enhanced_content,
                'metadata': json.dumps(metadata)
            },
            timeout=60
        )
        response.raise_for_status()
        
        logger.info(f"Updated document embeddings for restaurant: {restaurant_name}")
        
        return {
            'success': True,
            'restaurant_name': restaurant_name,
            'document_file': str(doc_path.name),
            'content_length': len(enhanced_content)
        }
        
    except Exception as e:
        logger.error(f"Failed to update document embeddings for {restaurant_name}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'restaurant_name': restaurant_name
        }


@shared_task
def update_restaurant_embeddings_with_images(restaurant_id):
    """
    Enhanced version of update_restaurant_embeddings that includes AI image classifications.
    
    Args:
        restaurant_id: UUID of the restaurant
    """
    try:
        import requests
        rag_service_url = getattr(settings, 'RAG_SERVICE_URL', 'http://localhost:8001')
        
        restaurant = Restaurant.objects.get(id=restaurant_id)
        
        # Generate enhanced content including AI image classifications
        content_parts = [
            f"Restaurant Name: {restaurant.name}",
            f"Description: {restaurant.description}" if restaurant.description else "",
            f"Location: {restaurant.city}, {restaurant.country}",
            f"Cuisine Type: {restaurant.cuisine_type}" if restaurant.cuisine_type else "",
            f"Michelin Stars: {restaurant.michelin_stars}" if restaurant.michelin_stars > 0 else "",
            f"Price Range: {restaurant.price_range}" if restaurant.price_range else "",
            f"Atmosphere: {restaurant.atmosphere}" if restaurant.atmosphere else ""
        ]
        
        # Add menu content
        menu_content = []
        for section in restaurant.menu_sections.all():
            menu_content.append(f"{section.name}: {section.description}")
            for item in section.items.all():
                menu_content.append(f"{item.name} - {item.description}")
        
        if menu_content:
            content_parts.append(f"Menu:\n" + "\n".join(menu_content))
        
        # Add AI image classifications and descriptions
        image_descriptions = []
        
        # Get menu item images with AI classifications
        menu_images = restaurant.images.filter(
            ai_category='menu_item',
            processing_status='completed'
        ).exclude(ai_description__isnull=True).exclude(ai_description__exact='')
        
        if menu_images.exists():
            menu_descriptions = [img.ai_description for img in menu_images[:5]]  # Top 5 menu images
            image_descriptions.append(f"Menu Items: {'; '.join(menu_descriptions)}")
        
        # Get ambiance/scenery images with AI classifications
        ambiance_images = restaurant.images.filter(
            ai_category='scenery_ambiance',
            processing_status='completed'
        ).exclude(ai_description__isnull=True).exclude(ai_description__exact='')
        
        if ambiance_images.exists():
            ambiance_descriptions = [img.ai_description for img in ambiance_images[:3]]  # Top 3 ambiance images
            image_descriptions.append(f"Ambiance and Setting: {'; '.join(ambiance_descriptions)}")
        
        # Add AI-generated image insights
        if image_descriptions:
            content_parts.append(f"Visual Elements:\n" + "\n".join(image_descriptions))
        
        # Filter out empty parts
        content = "\n\n".join([part for part in content_parts if part.strip()])
        
        # Enhanced metadata including image information
        metadata = {
            'restaurant_name': restaurant.name,
            'city': restaurant.city,
            'country': restaurant.country,
            'cuisine_type': restaurant.cuisine_type,
            'michelin_stars': restaurant.michelin_stars,
            'price_range': restaurant.price_range,
            'has_menu_images': menu_images.exists(),
            'has_ambiance_images': ambiance_images.exists(),
            'total_ai_classified_images': restaurant.images.filter(
                processing_status='completed'
            ).exclude(ai_category='uncategorized').count(),
            'updated_at': timezone.now().isoformat()
        }
        
        # Call RAG service to generate and store embeddings
        response = requests.post(
            f"{rag_service_url}/embeddings/generate",
            data={
                'content': content,
                'metadata': json.dumps(metadata)
            },
            timeout=60
        )
        response.raise_for_status()
        
        logger.info(f"Updated enhanced embeddings with AI image data for restaurant: {restaurant.name}")
        
        return {
            'success': True,
            'restaurant_id': str(restaurant_id),
            'restaurant_name': restaurant.name,
            'content_length': len(content),
            'ai_classified_images': metadata['total_ai_classified_images']
        }
        
    except Exception as e:
        logger.error(f"Failed to update enhanced embeddings for restaurant {restaurant_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'restaurant_id': str(restaurant_id)
        }


@shared_task
def batch_process_document_embeddings(max_docs=50):
    """
    Batch process document embeddings for restaurants that have document files but no embeddings.
    
    Args:
        max_docs: Maximum number of documents to process in this batch
    """
    try:
        from pathlib import Path
        
        # Get all document files
        docs_dir = Path(__file__).parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers" / "restaurant_docs"
        doc_files = list(docs_dir.glob("*_document.txt"))
        
        processed = 0
        successful = 0
        failed = 0
        
        for doc_file in doc_files[:max_docs]:
            # Extract restaurant name from filename
            restaurant_name = doc_file.stem.replace('_document', '').replace('_', ' ').title()
            
            try:
                result = update_document_embeddings.delay(restaurant_name, str(doc_file))
                processed += 1
                
                # Add small delay to avoid overwhelming the system
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error queuing document {doc_file.name} for embedding: {e}")
                failed += 1
        
        logger.info(f"Queued {processed} documents for embedding processing, {failed} failed")
        
        return {
            'success': True,
            'queued': processed,
            'failed': failed,
            'total_docs_available': len(doc_files)
        }
        
    except Exception as e:
        logger.error(f"Error in batch document processing: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def trigger_document_embedding_on_scrape(restaurant_name, scraping_results=None):
    """
    Trigger document embedding when new scraped data includes document generation.
    This should be called after successful scraping with document.txt generation.
    
    Args:
        restaurant_name: Name of the restaurant
        scraping_results: Optional scraping results dict with document info
    """
    try:
        # Check if document was generated in scraping results
        if scraping_results and scraping_results.get('document_txt'):
            logger.info(f"Document generated for {restaurant_name}, triggering embedding...")
            
            # Queue document embedding task
            update_document_embeddings.delay(restaurant_name)
            
            # Also update restaurant embeddings with any new AI image classifications
            # Try to find the restaurant in database
            try:
                restaurant = Restaurant.objects.filter(
                    name__icontains=restaurant_name.split()[0],
                    is_active=True
                ).first()
                
                if restaurant:
                    update_restaurant_embeddings_with_images.delay(restaurant.id)
                    logger.info(f"Queued enhanced embedding update for {restaurant.name}")
                
            except Exception as e:
                logger.warning(f"Could not find restaurant for enhanced embedding: {e}")
            
            return {
                'success': True,
                'restaurant_name': restaurant_name,
                'document_embedding_queued': True,
                'enhanced_embedding_queued': restaurant is not None
            }
        else:
            logger.info(f"No document generated for {restaurant_name}, skipping document embedding")
            return {
                'success': True,
                'restaurant_name': restaurant_name,
                'document_embedding_queued': False,
                'reason': 'No document generated'
            }
            
    except Exception as e:
        logger.error(f"Error triggering document embedding for {restaurant_name}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'restaurant_name': restaurant_name
        }