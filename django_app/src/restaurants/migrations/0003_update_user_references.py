# Generated migration to update user references to UUID

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_additional_models"),
        ("restaurants", "0002_restaurant_timezone_info"),
    ]

    operations = [
        # First, remove any existing foreign key constraints
        migrations.RunSQL(
            "ALTER TABLE restaurants_restaurantreview DROP CONSTRAINT IF EXISTS restaurants_restaurantreview_user_id_fkey;",
            reverse_sql="-- No reverse SQL needed"
        ),
        
        # Drop and recreate the user_id column as UUID
        migrations.RunSQL(
            "ALTER TABLE restaurants_restaurantreview DROP COLUMN IF EXISTS user_id;",
            reverse_sql="-- No reverse SQL needed"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE restaurants_restaurantreview ADD COLUMN user_id UUID;",
            reverse_sql="ALTER TABLE restaurants_restaurantreview DROP COLUMN user_id;"
        ),
        
        # Add the foreign key constraint
        migrations.RunSQL(
            "ALTER TABLE restaurants_restaurantreview ADD CONSTRAINT restaurants_restaurantreview_user_id_fkey FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;",
            reverse_sql="ALTER TABLE restaurants_restaurantreview DROP CONSTRAINT restaurants_restaurantreview_user_id_fkey;"
        ),
        
        # Do the same for any other user references in restaurants app
        migrations.RunSQL(
            "ALTER TABLE restaurants_chef DROP CONSTRAINT IF EXISTS restaurants_chef_user_id_fkey;",
            reverse_sql="-- No reverse SQL needed"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE restaurants_chef DROP COLUMN IF EXISTS user_id;",
            reverse_sql="-- No reverse SQL needed"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE restaurants_chef ADD COLUMN user_id UUID;",
            reverse_sql="ALTER TABLE restaurants_chef DROP COLUMN user_id;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE restaurants_chef ADD CONSTRAINT restaurants_chef_user_id_fkey FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE SET NULL;",
            reverse_sql="ALTER TABLE restaurants_chef DROP CONSTRAINT restaurants_chef_user_id_fkey;"
        ),
    ]