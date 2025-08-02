# Generated migration to add missing cart_status field
# Engineering Excellence: Aligning database schema with Django models

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0006_enhanced_search_indexes'),
    ]

    operations = [
        # Add cart_status field to UserCart model
        migrations.AddField(
            model_name='usercart',
            name='cart_status',
            field=models.CharField(
                max_length=50,
                default='active',
                db_index=True,
                help_text='Specific cart state - works alongside is_active from BaseModel',
                choices=[
                    ('active', 'Active'),
                    ('abandoned', 'Abandoned'),
                    ('converted', 'Converted to Order'),
                    ('restaurant_unavailable', 'Restaurant No Longer Available'),
                    ('user_deactivated', 'User Account Deactivated'),
                ]
            ),
        ),

        # Data migration: Set all existing carts to 'active' status
        migrations.RunSQL(
            "UPDATE restaurants_usercart SET cart_status = 'active' WHERE cart_status IS NULL OR cart_status = '';",
            reverse_sql="UPDATE restaurants_usercart SET cart_status = 'active';"
        ),
    ]