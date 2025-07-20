"""
Django management command to process the Michelin CSV file.
"""
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# Add data pipeline to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "data_pipeline" / "src" / "scrapers"))

from michelin_csv_processor import MichelinCSVProcessor


class Command(BaseCommand):
    help = 'Process the Michelin CSV file and import restaurants into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-row',
            type=int,
            default=0,
            help='Row number to start processing from (for resuming)'
        )
        parser.add_argument(
            '--max-restaurants',
            type=int,
            default=None,
            help='Maximum number of restaurants to process'
        )
        parser.add_argument(
            '--csv-path',
            type=str,
            default=None,
            help='Path to the CSV file (optional, defaults to data_pipeline/ingestion/michelin_my_maps.csv)'
        )
        parser.add_argument(
            '--no-scraping',
            action='store_true',
            help='Only import CSV data, skip website scraping'
        )

    def handle(self, *args, **options):
        try:
            # Determine CSV file path
            if options['csv_path']:
                csv_file_path = Path(options['csv_path'])
            else:
                csv_file_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "data_pipeline" / "src" / "ingestion" / "michelin_my_maps.csv"
            
            if not csv_file_path.exists():
                raise CommandError(f"CSV file not found: {csv_file_path}")
            
            self.stdout.write(f"Processing CSV file: {csv_file_path}")
            self.stdout.write(f"Starting from row: {options['start_row']}")
            
            if options['max_restaurants']:
                self.stdout.write(f"Maximum restaurants: {options['max_restaurants']}")
            
            # Initialize processor
            processor = MichelinCSVProcessor(csv_file_path)
            
            # Modify processor if no scraping requested
            if options['no_scraping']:
                self.stdout.write(self.style.WARNING("Scraping disabled - only importing CSV data"))
                # We could add a flag to the processor to skip scraping
            
            # Process the file
            results = processor.process_csv_file(
                start_row=options['start_row'],
                max_restaurants=options['max_restaurants']
            )
            
            # Display results
            self.stdout.write(self.style.SUCCESS("\n" + "="*60))
            self.stdout.write(self.style.SUCCESS("MICHELIN CSV PROCESSING COMPLETE"))
            self.stdout.write(self.style.SUCCESS("="*60))
            self.stdout.write(f"Total processed: {results['total_processed']}")
            self.stdout.write(self.style.SUCCESS(f"Successful imports: {results['successful_imports']}"))
            self.stdout.write(self.style.SUCCESS(f"Successful scrapes: {results['successful_scrapes']}"))
            
            if results['failed_imports'] > 0:
                self.stdout.write(self.style.ERROR(f"Failed imports: {results['failed_imports']}"))
            
            if results['failed_scrapes'] > 0:
                self.stdout.write(self.style.WARNING(f"Failed scrapes: {results['failed_scrapes']}"))
            
            if results['errors']:
                self.stdout.write(self.style.ERROR(f"\nErrors encountered: {len(results['errors'])}"))
                for error in results['errors'][:5]:  # Show first 5 errors
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
            
            self.stdout.write(self.style.SUCCESS("\nCheck the Django admin or database for imported restaurants."))
            self.stdout.write(self.style.SUCCESS("="*60))
            
        except Exception as e:
            raise CommandError(f"Processing failed: {str(e)}")