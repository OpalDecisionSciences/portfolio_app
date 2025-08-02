"""
Django management command to create system placeholder records.
Run this before migrating to new model structure.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from restaurants.base_models import (
    SYSTEM_USER_ID, DELETED_RESTAURANT_ID, DISCONTINUED_ITEM_ID,
    DELETED_USER_ID, DELETED_CART_ID, SystemPlaceholder
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Create system placeholder records for zero-NULL architecture'

    def handle(self, *args, **options):
        self.stdout.write('Creating system placeholder records...')
        
        # Create system user
        system_user, created = User.objects.get_or_create(
            id=SYSTEM_USER_ID,
            defaults={
                'username': 'system_user',
                'email': 'system@internal.local',
                'first_name': 'System',
                'last_name': 'User',
                'is_active': False,
                'is_staff': False,
                'is_superuser': False,
                'date_joined': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'✓ Created system user: {system_user.username}')
        else:
            self.stdout.write(f'✓ System user already exists: {system_user.username}')
        
        # Create deleted user placeholder
        deleted_user, created = User.objects.get_or_create(
            id=DELETED_USER_ID,
            defaults={
                'username': 'deleted_user_placeholder',
                'email': 'deleted@internal.local',
                'first_name': '[DELETED]',
                'last_name': 'User',
                'is_active': False,
                'is_staff': False,
                'is_superuser': False,
                'date_joined': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'✓ Created deleted user placeholder: {deleted_user.username}')
        else:
            self.stdout.write(f'✓ Deleted user placeholder already exists: {deleted_user.username}')
        
        # Create system placeholder records
        placeholders = [
            {
                'id': DELETED_RESTAURANT_ID,
                'entity_type': 'restaurant',
                'name': '[DELETED RESTAURANT]',
                'description': 'Placeholder for deleted restaurant references'
            },
            {
                'id': DISCONTINUED_ITEM_ID,
                'entity_type': 'menu_item',
                'name': '[DISCONTINUED ITEM]',
                'description': 'Placeholder for discontinued menu item references'  
            },
            {
                'id': DELETED_CART_ID,
                'entity_type': 'cart',
                'name': '[DELETED CART]',
                'description': 'Placeholder for deleted shopping cart references'
            },
        ]
        
        for placeholder_data in placeholders:
            placeholder, created = SystemPlaceholder.objects.get_or_create(
                id=placeholder_data['id'],
                defaults=placeholder_data
            )
            if created:
                self.stdout.write(f'✓ Created {placeholder_data["entity_type"]} placeholder: {placeholder_data["name"]}')
            else:
                self.stdout.write(f'✓ {placeholder_data["entity_type"]} placeholder already exists: {placeholder_data["name"]}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created all system placeholder records!')
        )