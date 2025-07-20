"""
Django management command to create sample restaurant data for testing.

Usage:
    python manage.py create_sample_data
"""

from django.core.management.base import BaseCommand
from restaurants.models import Restaurant, RestaurantImage
from django.contrib.auth.models import User
import uuid


class Command(BaseCommand):
    help = 'Create sample restaurant data for testing the recommender system'

    def handle(self, *args, **options):
        # Create sample restaurants
        restaurants_data = [
            {
                'name': 'Le Bernardin',
                'city': 'New York',
                'country': 'USA',
                'cuisine_type': 'French Seafood',
                'michelin_stars': 3,
                'rating': 4.8,
                'price_range': '$$$$',
                'description': 'Exquisite French seafood restaurant with three Michelin stars in the heart of Manhattan.',
                'atmosphere': 'Elegant',
                'website': 'https://le-bernardin.com'
            },
            {
                'name': 'Osteria Francescana',
                'city': 'Modena',
                'country': 'Italy',
                'cuisine_type': 'Italian',
                'michelin_stars': 3,
                'rating': 4.9,
                'price_range': '$$$$',
                'description': 'World-renowned Italian restaurant showcasing the best of Modenese cuisine.',
                'atmosphere': 'Intimate',
                'website': 'https://osteriafrancescana.it'
            },
            {
                'name': 'Noma',
                'city': 'Copenhagen',
                'country': 'Denmark',
                'cuisine_type': 'Nordic',
                'michelin_stars': 2,
                'rating': 4.7,
                'price_range': '$$$$',
                'description': 'Innovative Nordic cuisine using local and seasonal ingredients.',
                'atmosphere': 'Modern',
                'website': 'https://noma.dk'
            },
            {
                'name': 'Sukiyabashi Jiro',
                'city': 'Tokyo',
                'country': 'Japan',
                'cuisine_type': 'Sushi',
                'michelin_stars': 3,
                'rating': 4.9,
                'price_range': '$$$$',
                'description': 'Legendary sushi restaurant in Tokyo with master chef Jiro Ono.',
                'atmosphere': 'Traditional',
                'website': 'https://sukiyabashijiro.com'
            },
            {
                'name': 'The French Laundry',
                'city': 'Yountville',
                'country': 'USA',
                'cuisine_type': 'French American',
                'michelin_stars': 3,
                'rating': 4.8,
                'price_range': '$$$$',
                'description': 'Thomas Keller\'s acclaimed restaurant in Napa Valley wine country.',
                'atmosphere': 'Rustic Elegant',
                'website': 'https://frenchlaundry.com'
            },
            {
                'name': 'El Celler de Can Roca',
                'city': 'Girona',
                'country': 'Spain',
                'cuisine_type': 'Modern Catalan',
                'michelin_stars': 3,
                'rating': 4.7,
                'price_range': '$$$$',
                'description': 'Creative Catalan cuisine by the Roca brothers in northeastern Spain.',
                'atmosphere': 'Contemporary',
                'website': 'https://cellercanroca.com'
            },
            {
                'name': 'Chez L\'Ami Jean',
                'city': 'Paris',
                'country': 'France',
                'cuisine_type': 'French Bistro',
                'michelin_stars': 1,
                'rating': 4.5,
                'price_range': '$$$',
                'description': 'Beloved Parisian bistro serving hearty French regional cuisine.',
                'atmosphere': 'Casual',
                'website': 'https://amijean.fr'
            },
            {
                'name': 'Da Vittorio',
                'city': 'Bergamo',
                'country': 'Italy',
                'cuisine_type': 'Italian',
                'michelin_stars': 3,
                'rating': 4.8,
                'price_range': '$$$$',
                'description': 'Family-run Italian restaurant with innovative takes on traditional dishes.',
                'atmosphere': 'Family-style',
                'website': 'https://davittorio.com'
            },
            {
                'name': 'Café Central',
                'city': 'Vienna',
                'country': 'Austria',
                'cuisine_type': 'Austrian',
                'michelin_stars': 0,
                'rating': 4.2,
                'price_range': '$$',
                'description': 'Historic Viennese coffeehouse serving traditional Austrian dishes.',
                'atmosphere': 'Historic',
                'website': 'https://cafecentral.wien'
            },
            {
                'name': 'Blue Hill at Stone Barns',
                'city': 'Pocantico Hills',
                'country': 'USA',
                'cuisine_type': 'Farm-to-Table',
                'michelin_stars': 1,
                'rating': 4.6,
                'price_range': '$$$$',
                'description': 'Farm-to-table restaurant featuring ingredients from their own farm.',
                'atmosphere': 'Rustic',
                'website': 'https://bluehillfarm.com'
            }
        ]

        created_count = 0
        
        for restaurant_data in restaurants_data:
            # Check if restaurant already exists
            if not Restaurant.objects.filter(name=restaurant_data['name']).exists():
                restaurant = Restaurant.objects.create(**restaurant_data)
                
                # Create sample images for each restaurant
                self.create_sample_images(restaurant)
                
                created_count += 1
                self.stdout.write(f"Created restaurant: {restaurant.name}")

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} restaurants with sample data!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('All sample restaurants already exist in the database.')
            )

    def create_sample_images(self, restaurant):
        """Create sample image records for a restaurant."""
        
        # Sample image data - using placeholder URLs
        sample_images = [
            {
                'source_url': f'https://picsum.photos/400/300?random={restaurant.id}1',
                'ai_category': 'scenery_ambiance',
                'ai_labels': ['dining room', 'elegant interior', 'ambient lighting'],
                'ai_description': f'Elegant dining room at {restaurant.name} with sophisticated ambiance',
                'category_confidence': 0.85,
                'is_featured': True,
                'is_ambiance_highlight': True
            },
            {
                'source_url': f'https://picsum.photos/400/300?random={restaurant.id}2',
                'ai_category': 'menu_item',
                'ai_labels': ['signature dish', 'fine dining', 'plated food'],
                'ai_description': f'Signature dish from {restaurant.name} showcasing culinary artistry',
                'category_confidence': 0.92,
                'is_menu_highlight': True
            },
            {
                'source_url': f'https://picsum.photos/400/300?random={restaurant.id}3',
                'ai_category': 'scenery_ambiance',
                'ai_labels': ['exterior view', 'restaurant facade', 'street view'],
                'ai_description': f'Exterior view of {restaurant.name}',
                'category_confidence': 0.78
            }
        ]

        for image_data in sample_images:
            RestaurantImage.objects.create(
                restaurant=restaurant,
                caption=f"{restaurant.name} - {image_data['ai_category'].replace('_', ' ').title()}",
                processing_status='completed',
                **image_data
            )