"""
Django management command to process the scraping backlog.
"""
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# Add data pipeline to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers"))

from async_scraper_manager import get_scraper_manager


class Command(BaseCommand):
    help = 'Process the scraping backlog for failed image and text scraping tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-tasks',
            type=int,
            default=50,
            help='Maximum number of tasks to process from backlog'
        )
        parser.add_argument(
            '--task-type',
            type=str,
            choices=['images', 'text', 'comprehensive', 'all'],
            default='all',
            help='Type of tasks to process from backlog'
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Only show backlog statistics without processing'
        )

    def handle(self, *args, **options):
        try:
            scraper_manager = get_scraper_manager()
            
            if options['stats_only']:
                self.show_stats(scraper_manager)
                return
            
            self.stdout.write(f"Processing backlog with max {options['max_tasks']} tasks")
            
            if options['task_type'] != 'all':
                self.stdout.write(f"Filtering for task type: {options['task_type']}")
            
            # Process the backlog
            results = scraper_manager.process_backlog(max_tasks=options['max_tasks'])
            
            # Display results
            self.stdout.write(self.style.SUCCESS("\\n" + "="*60))
            self.stdout.write(self.style.SUCCESS("SCRAPING BACKLOG PROCESSING COMPLETE"))
            self.stdout.write(self.style.SUCCESS("="*60))
            self.stdout.write(f"Tasks processed: {results['processed']}")
            self.stdout.write(self.style.SUCCESS(f"Successful: {results['successful']}"))
            
            if results['failed'] > 0:
                self.stdout.write(self.style.ERROR(f"Failed: {results['failed']}"))
            
            # Show updated backlog stats
            backlog_stats = results.get('backlog_stats', {})
            if backlog_stats:
                self.stdout.write("\\nBacklog Statistics:")
                for status, count in backlog_stats.items():
                    color = self.style.SUCCESS if status == 'completed' else (
                        self.style.ERROR if status == 'failed' else self.style.WARNING
                    )
                    self.stdout.write(f"  {status}: {color(str(count))}")
            
            self.stdout.write(self.style.SUCCESS("="*60))
            
        except Exception as e:
            raise CommandError(f"Backlog processing failed: {str(e)}")
    
    def show_stats(self, scraper_manager):
        """Show backlog statistics only."""
        stats = scraper_manager.get_backlog_stats()
        
        self.stdout.write(self.style.SUCCESS("\\n" + "="*60))
        self.stdout.write(self.style.SUCCESS("SCRAPING BACKLOG STATISTICS"))
        self.stdout.write(self.style.SUCCESS("="*60))
        
        if not stats:
            self.stdout.write("No tasks in backlog")
            return
        
        for status, count in stats.items():
            color = self.style.SUCCESS if status == 'completed' else (
                self.style.ERROR if status == 'failed' else self.style.WARNING
            )
            self.stdout.write(f"{status}: {color(str(count))}")
        
        self.stdout.write(self.style.SUCCESS("="*60))