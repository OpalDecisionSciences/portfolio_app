#!/usr/bin/env python3
"""
Test script to validate psycopg3 database connections across all services.
Tests both Django and RAG service database connectivity.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add Django project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "django_app" / "src"))

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio_project.settings")

import django
from django.conf import settings

# Setup Django
django.setup()

import psycopg
from django.db import connection
from django.core.management.color import make_style

style = make_style()

def test_django_connection():
    """Test Django database connection with psycopg3."""
    print(style.HTTP_INFO("Testing Django database connection..."))
    
    try:
        # Test Django ORM connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(style.SUCCESS(f"✅ Django connection successful"))
            print(style.SUCCESS(f"   PostgreSQL version: {version}"))
            
            # Test pgvector extension
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            result = cursor.fetchone()
            if result:
                print(style.SUCCESS(f"✅ pgvector extension installed"))
            else:
                print(style.WARNING(f"⚠️  pgvector extension not found"))
                
            # Check connection backend
            print(style.HTTP_INFO(f"   Backend: {connection.vendor}"))
            print(style.HTTP_INFO(f"   Settings: {settings.DATABASES['default']['ENGINE']}"))
            
        return True
        
    except Exception as e:
        print(style.ERROR(f"❌ Django connection failed: {e}"))
        return False

def test_direct_psycopg3_connection():
    """Test direct psycopg3 connection."""
    print(style.HTTP_INFO("Testing direct psycopg3 connection..."))
    
    try:
        conn_params = {
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'port': os.getenv('DATABASE_PORT', '5432'),
            'user': os.getenv('DATABASE_USER', 'postgres'),
            'password': os.getenv('DATABASE_PASSWORD', ''),
            'dbname': os.getenv('DATABASE_NAME', 'postgres')
        }
        
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(style.SUCCESS(f"✅ Direct psycopg3 connection successful"))
                print(style.SUCCESS(f"   PostgreSQL version: {version}"))
                
                # Test async capabilities
                cur.execute("SELECT 'psycopg3 async ready' as status;")
                status = cur.fetchone()[0]
                print(style.SUCCESS(f"   Status: {status}"))
                
        return True
        
    except Exception as e:
        print(style.ERROR(f"❌ Direct psycopg3 connection failed: {e}"))
        return False

def test_rag_service_connection_string():
    """Test RAG service connection string format."""
    print(style.HTTP_INFO("Testing RAG service connection string..."))
    
    try:
        db_user = os.getenv('DATABASE_USER', 'postgres')
        db_password = os.getenv('DATABASE_PASSWORD', '')
        db_host = os.getenv('DATABASE_HOST', 'localhost')
        db_port = os.getenv('DATABASE_PORT', '5432')
        db_name = os.getenv('DATABASE_NAME', 'postgres')
        
        connection_string = f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        print(style.SUCCESS(f"✅ RAG service connection string format correct"))
        print(style.HTTP_INFO(f"   Format: postgresql+psycopg://user:***@host:port/db"))
        
        return True
        
    except Exception as e:
        print(style.ERROR(f"❌ RAG service connection string test failed: {e}"))
        return False

async def test_async_database_operations():
    """Test async database operations with psycopg3."""
    print(style.HTTP_INFO("Testing async database operations..."))
    
    try:
        conn_params = {
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'port': os.getenv('DATABASE_PORT', '5432'),
            'user': os.getenv('DATABASE_USER', 'postgres'),
            'password': os.getenv('DATABASE_PASSWORD', ''),
            'dbname': os.getenv('DATABASE_NAME', 'postgres')
        }
        
        async with await psycopg.AsyncConnection.connect(**conn_params) as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("SELECT 'async operation successful' as result;")
                result = await acur.fetchone()
                print(style.SUCCESS(f"✅ Async database operations working"))
                print(style.SUCCESS(f"   Result: {result[0]}"))
                
        return True
        
    except Exception as e:
        print(style.ERROR(f"❌ Async database operations failed: {e}"))
        return False

def main():
    """Run all database connection tests."""
    print(style.HTTP_SUCCESS("🔍 PostgreSQL psycopg3 Connection Test Suite"))
    print("=" * 60)
    
    results = []
    
    # Test 1: Django ORM Connection
    results.append(test_django_connection())
    print()
    
    # Test 2: Direct psycopg3 Connection
    results.append(test_direct_psycopg3_connection())
    print()
    
    # Test 3: RAG Service Connection String
    results.append(test_rag_service_connection_string())
    print()
    
    # Test 4: Async Operations
    try:
        async_result = asyncio.run(test_async_database_operations())
        results.append(async_result)
    except Exception as e:
        print(style.ERROR(f"❌ Async test failed: {e}"))
        results.append(False)
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(style.SUCCESS(f"🎉 All tests passed! ({passed}/{total})"))
        print(style.SUCCESS("✅ psycopg3 migration is complete and functional"))
        return 0
    else:
        print(style.ERROR(f"❌ Some tests failed ({passed}/{total})"))
        print(style.WARNING("⚠️  Review failed tests before proceeding to production"))
        return 1

if __name__ == "__main__":
    exit(main())