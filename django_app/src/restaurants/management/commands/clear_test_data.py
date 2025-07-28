from django.core.management.base import BaseCommand
from django.db import transaction
from restaurants.models import Restaurant, MenuSection, MenuItem, RestaurantImage, ScrapingJob

class Command(BaseCommand):
    help = 'Clear all test data from the database for production deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL restaurant data. Run with --confirm to proceed.'
                )
            )
            return

        self.stdout.write('Clearing all test data...')

        with transaction.atomic():
            # Delete in order to respect foreign keys
            deleted_items = MenuItem.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_items[0]} menu items')

            deleted_sections = MenuSection.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_sections[0]} menu sections')

            deleted_images = RestaurantImage.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_images[0]} restaurant images')

            deleted_jobs = ScrapingJob.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_jobs[0]} scraping jobs')

            deleted_restaurants = Restaurant.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_restaurants[0]} restaurants')

        self.stdout.write(
            self.style.SUCCESS('Successfully cleared all test data!')
        )
        self.stdout.write(
            self.style.SUCCESS('Database is now clean and ready for production data.')
        )