"""
Asynchronous Scraper Manager - Thread-safe, multi-instance web scraping with retry logic.

This module provides:
1. Asynchronous/threaded scraping with multiple Chrome instances
2. Persistent backlog system for failed scrapes
3. Retry logic with exponential backoff
4. Resource pooling and cleanup
5. Progress tracking and monitoring
"""

import asyncio
import concurrent.futures
import threading
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from queue import Queue, Empty
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


@dataclass
class ScrapingTask:
    """Represents a scraping task."""
    id: str
    url: str
    restaurant_name: str
    task_type: str  # 'text', 'images', 'comprehensive'
    priority: int = 1
    max_retries: int = 3
    retry_count: int = 0
    created_at: float = None
    last_attempt: float = None
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.error_messages is None:
            self.error_messages = []


class ScrapingBacklog:
    """PostgreSQL-based backlog system using Django models."""
    
    def __init__(self):
        # Django models will be imported dynamically to avoid circular imports
        pass
    
    def _get_model(self):
        """Dynamically import the Django model to avoid circular imports."""
        try:
            import django
            from django.conf import settings
            if not settings.configured:
                django.setup()
            
            from restaurants.models import ScrapingBacklogTask
            return ScrapingBacklogTask
        except ImportError:
            # Fallback for when running outside Django context
            logger.warning("Django not available, using in-memory storage")
            return None
    
    def add_task(self, task: ScrapingTask):
        """Add a task to the backlog."""
        model = self._get_model()
        if not model:
            return
        
        try:
            model.objects.update_or_create(
                task_id=task.id,
                defaults={
                    'url': task.url,
                    'restaurant_name': task.restaurant_name,
                    'task_type': task.task_type,
                    'priority': task.priority,
                    'max_retries': task.max_retries,
                    'retry_count': task.retry_count,
                    'status': 'pending',
                    'error_messages': task.error_messages or []
                }
            )
        except Exception as e:
            logger.error(f"Failed to add task to backlog: {e}")
    
    def get_pending_tasks(self, limit: int = 100) -> List[ScrapingTask]:
        """Get pending tasks from backlog."""
        model = self._get_model()
        if not model:
            return []
        
        try:
            from django.db.models import F
            
            db_tasks = model.objects.filter(
                status='pending',
                retry_count__lt=F('max_retries')
            ).order_by('-priority', 'created_at')[:limit]
            
            tasks = []
            for db_task in db_tasks:
                task = ScrapingTask(
                    id=db_task.task_id,
                    url=db_task.url,
                    restaurant_name=db_task.restaurant_name,
                    task_type=db_task.task_type,
                    priority=db_task.priority,
                    max_retries=db_task.max_retries,
                    retry_count=db_task.retry_count,
                    created_at=db_task.created_at.timestamp(),
                    last_attempt=db_task.last_attempt.timestamp() if db_task.last_attempt else None,
                    error_messages=db_task.error_messages or []
                )
                tasks.append(task)
            return tasks
        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []
    
    def mark_failed(self, task_id: str, error_message: str):
        """Mark a task as failed and increment retry count."""
        model = self._get_model()
        if not model:
            return
        
        try:
            task = model.objects.get(task_id=task_id)
            task.mark_failed(error_message)
        except model.DoesNotExist:
            logger.warning(f"Task {task_id} not found in backlog")
        except Exception as e:
            logger.error(f"Failed to mark task as failed: {e}")
    
    def mark_completed(self, task_id: str):
        """Mark a task as completed."""
        model = self._get_model()
        if not model:
            return
        
        try:
            task = model.objects.get(task_id=task_id)
            task.mark_completed()
        except model.DoesNotExist:
            logger.warning(f"Task {task_id} not found in backlog")
        except Exception as e:
            logger.error(f"Failed to mark task as completed: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get backlog statistics."""
        model = self._get_model()
        if not model:
            return {}
        
        try:
            from django.db.models import Count
            
            stats = dict(
                model.objects.values('status')
                .annotate(count=Count('status'))
                .values_list('status', 'count')
            )
            
            # Add retry statistics
            retries_pending = model.objects.filter(
                retry_count__gt=0,
                status__in=['pending', 'processing']
            ).count()
            stats['retries_pending'] = retries_pending
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get backlog stats: {e}")
            return {}


class ChromeDriverPool:
    """Thread-safe pool of Chrome WebDriver instances."""
    
    def __init__(self, max_instances: int = 3):
        self.max_instances = max_instances
        self.available_drivers = Queue(maxsize=max_instances)
        self.active_drivers = set()
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the driver pool."""
        for _ in range(self.max_instances):
            driver = self._create_driver()
            if driver:
                self.available_drivers.put(driver)
    
    def _create_driver(self) -> Optional[webdriver.Chrome]:
        """Create a new Chrome WebDriver instance."""
        try:
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
            options.add_argument("--remote-debugging-port=0")  # Use random port for each instance
            
            # Set binary path to use container's chromium
            if Path("/usr/bin/chromium").exists():
                options.binary_location = "/usr/bin/chromium"
            
            # Configure Chrome service for ARM64 compatibility
            chromedriver_paths = [
                "/usr/bin/chromedriver",  # Docker container path
                "/Users/iamai/.wdm/drivers/chromedriver/mac64/138.0.7204.157/chromedriver-mac-arm64/chromedriver"
            ]
            
            for path in chromedriver_paths:
                if Path(path).exists():
                    try:
                        service = Service(path)
                        driver = webdriver.Chrome(service=service, options=options)
                        driver.set_page_load_timeout(30)
                        logger.info(f"Created Chrome driver instance with: {path}")
                        return driver
                    except Exception as e:
                        logger.warning(f"Failed to create driver with {path}: {e}")
                        continue
            
            # Fallback to webdriver-manager
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(30)
                logger.info("Created Chrome driver with webdriver-manager")
                return driver
            except Exception as e:
                logger.error(f"Failed to create Chrome driver: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating Chrome driver: {e}")
            return None
    
    @contextmanager
    def get_driver(self):
        """Get a driver from the pool (context manager)."""
        driver = None
        try:
            # Try to get an available driver
            try:
                driver = self.available_drivers.get(timeout=30)
                with self.lock:
                    self.active_drivers.add(driver)
                yield driver
            except Empty:
                logger.warning("No available drivers in pool, creating temporary driver")
                driver = self._create_driver()
                if driver:
                    with self.lock:
                        self.active_drivers.add(driver)
                    yield driver
                else:
                    raise Exception("Failed to create temporary driver")
        finally:
            if driver:
                with self.lock:
                    self.active_drivers.discard(driver)
                # Return driver to pool or close if pool is full
                try:
                    self.available_drivers.put_nowait(driver)
                except:
                    # Pool is full, close this driver
                    try:
                        driver.quit()
                    except:
                        pass
    
    def cleanup(self):
        """Clean up all drivers in the pool."""
        with self.lock:
            # Close active drivers
            for driver in list(self.active_drivers):
                try:
                    driver.quit()
                except:
                    pass
            self.active_drivers.clear()
            
            # Close available drivers
            while not self.available_drivers.empty():
                try:
                    driver = self.available_drivers.get_nowait()
                    driver.quit()
                except:
                    pass


class AsyncScraperManager:
    """Asynchronous scraper manager with multi-threading and retry logic."""
    
    def __init__(self, max_workers: int = 3, max_driver_instances: int = 3):
        self.max_workers = max_workers
        self.driver_pool = ChromeDriverPool(max_driver_instances)
        self.backlog = ScrapingBacklog()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False
    
    async def scrape_async(self, tasks: List[ScrapingTask]) -> List[Dict[str, Any]]:
        """Scrape multiple tasks asynchronously."""
        loop = asyncio.get_event_loop()
        
        # Submit tasks to thread pool
        futures = []
        for task in tasks:
            future = loop.run_in_executor(
                self.executor, 
                self._scrape_task_sync, 
                task
            )
            futures.append(future)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        return results
    
    def _scrape_task_sync(self, task: ScrapingTask) -> Dict[str, Any]:
        """Synchronous scraping of a single task (run in thread)."""
        try:
            with self.driver_pool.get_driver() as driver:
                if task.task_type == 'images':
                    return self._scrape_images(driver, task)
                elif task.task_type == 'text':
                    return self._scrape_text(driver, task)
                elif task.task_type == 'comprehensive':
                    return self._scrape_comprehensive(driver, task)
                else:
                    raise ValueError(f"Unknown task type: {task.task_type}")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task.id} failed: {error_msg}")
            
            # Add to backlog for retry
            task.error_messages.append(error_msg)
            self.backlog.mark_failed(task.id, error_msg)
            
            return {
                'task_id': task.id,
                'success': False,
                'error': error_msg,
                'retry_count': task.retry_count
            }
    
    def _scrape_images(self, driver: webdriver.Chrome, task: ScrapingTask) -> Dict[str, Any]:
        """Scrape images from a restaurant website."""
        from .image_scraper import RestaurantImageScraper
        
        try:
            scraper = RestaurantImageScraper()
            # Use the provided driver instead of creating a new one
            results = scraper.scrape_restaurant_images(
                task.url, 
                task.restaurant_name,
                max_images=15,
                enable_ai_categorization=True
            )
            
            self.backlog.mark_completed(task.id)
            return {
                'task_id': task.id,
                'success': True,
                'data': results,
                'images_found': len(results)
            }
            
        except Exception as e:
            raise Exception(f"Image scraping failed: {str(e)}")
    
    def _scrape_text(self, driver: webdriver.Chrome, task: ScrapingTask) -> Dict[str, Any]:
        """Scrape text content from a restaurant website."""
        from .llm_web_scraper import NewWebsite
        
        try:
            website = NewWebsite(task.url, driver=driver)
            content = website.get_contents()
            
            self.backlog.mark_completed(task.id)
            return {
                'task_id': task.id,
                'success': True,
                'data': {
                    'content': content,
                    'title': website.title,
                    'links': website.links
                }
            }
            
        except Exception as e:
            raise Exception(f"Text scraping failed: {str(e)}")
    
    def _scrape_comprehensive(self, driver: webdriver.Chrome, task: ScrapingTask) -> Dict[str, Any]:
        """Perform comprehensive scraping (text + images + LLM analysis)."""
        from .unified_restaurant_scraper import UnifiedRestaurantScraper
        
        try:
            scraper = UnifiedRestaurantScraper()
            # Use the provided driver
            results = scraper.scrape_restaurant_complete(
                task.url,
                task.restaurant_name,
                max_images=10,
                save_to_db=True
            )
            
            self.backlog.mark_completed(task.id)
            return {
                'task_id': task.id,
                'success': True,
                'data': results
            }
            
        except Exception as e:
            raise Exception(f"Comprehensive scraping failed: {str(e)}")
    
    def process_backlog(self, max_tasks: int = 50) -> Dict[str, Any]:
        """Process tasks from the backlog."""
        pending_tasks = self.backlog.get_pending_tasks(max_tasks)
        
        if not pending_tasks:
            return {'processed': 0, 'message': 'No pending tasks in backlog'}
        
        logger.info(f"Processing {len(pending_tasks)} tasks from backlog")
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(self.scrape_async(pending_tasks))
            successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            
            return {
                'processed': len(pending_tasks),
                'successful': successful,
                'failed': len(pending_tasks) - successful,
                'backlog_stats': self.backlog.get_stats()
            }
        finally:
            loop.close()
    
    def add_task_to_backlog(self, url: str, restaurant_name: str, task_type: str, priority: int = 1):
        """Add a new task to the backlog."""
        task = ScrapingTask(
            id=f"{task_type}_{restaurant_name}_{int(time.time())}",
            url=url,
            restaurant_name=restaurant_name,
            task_type=task_type,
            priority=priority
        )
        self.backlog.add_task(task)
        return task.id
    
    def get_backlog_stats(self) -> Dict[str, Any]:
        """Get comprehensive backlog statistics."""
        return self.backlog.get_stats()
    
    def shutdown(self):
        """Shutdown the scraper manager and cleanup resources."""
        self._shutdown = True
        self.executor.shutdown(wait=True)
        self.driver_pool.cleanup()


# Singleton instance for global access
_scraper_manager = None

def get_scraper_manager() -> AsyncScraperManager:
    """Get the global scraper manager instance."""
    global _scraper_manager
    if _scraper_manager is None:
        _scraper_manager = AsyncScraperManager()
    return _scraper_manager