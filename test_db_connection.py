#!/usr/bin/env python
"""
Test database connection for Django settings.
"""
import os
import sys
from pathlib import Path

# Add Django settings
sys.path.insert(0, str(Path(__file__).parent / "django_app" / "src"))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

import django
django.setup()

from django.db import connection

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"✅ Database connection successful! Result: {result}")
        
        # Test creating a simple table
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'django_migrations'")
        count = cursor.fetchone()[0]
        print(f"✅ Django migrations table exists: {count > 0}")
        
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    
    # Print connection details for debugging
    print("\nConnection details:")
    print(f"  Host: {connection.settings_dict['HOST']}")
    print(f"  Port: {connection.settings_dict['PORT']}")
    print(f"  Database: {connection.settings_dict['NAME']}")
    print(f"  User: {connection.settings_dict['USER']}")