#!/usr/bin/env python
"""
Quick vector database population script
"""
import os
import sys
import django
import requests
import json
import urllib.parse
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
sys.path.insert(0, str(Path(__file__).parent.parent / "django_app" / "src"))
django.setup()

from restaurants.models import Restaurant

def create_restaurant_content(restaurant):
    """Create content text for embedding."""
    content_parts = [f"{restaurant.name} is a restaurant in {restaurant.city}, {restaurant.country}."]
    
    if restaurant.michelin_stars > 0:
        content_parts.append(f"It has {restaurant.michelin_stars} Michelin star{'s' if restaurant.michelin_stars > 1 else ''}.")
    
    if restaurant.cuisine_type:
        content_parts.append(f"Cuisine: {restaurant.cuisine_type}.")
    
    if restaurant.description:
        content_parts.append(f"Description: {restaurant.description}")
    
    if restaurant.scraped_content and restaurant.scraped_content.strip():
        content_parts.append(f"Additional details: {restaurant.scraped_content[:500]}...")
    
    return " ".join(content_parts)

def populate_restaurants(limit=10):
    """Populate vector database with first few restaurants."""
    restaurants = Restaurant.objects.filter(is_active=True).order_by('name')[:limit]
    
    print(f"Populating vector database with {limit} restaurants...")
    
    success_count = 0
    for restaurant in restaurants:
        content = create_restaurant_content(restaurant)
        
        # URL encode the content for query parameter
        encoded_content = urllib.parse.quote_plus(content)
        
        try:
            response = requests.post(
                f"http://localhost:8001/embeddings/generate?content={encoded_content}",
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"✓ {restaurant.name}")
                success_count += 1
            else:
                print(f"✗ {restaurant.name}: {response.status_code}")
                
        except Exception as e:
            print(f"✗ {restaurant.name}: {str(e)}")
    
    print(f"\nCompleted: {success_count}/{limit} restaurants added to vector database")
    
    # Test search
    print("\n🔍 Testing search...")
    test_queries = ["Michelin star restaurant", "French cuisine", "Italian restaurant"]
    
    for query in test_queries:
        try:
            response = requests.get(f"http://localhost:8001/embeddings/search?query={query}&k=3")
            if response.status_code == 200:
                results = response.json()
                print(f"  '{query}': {len(results['results'])} results")
            else:
                print(f"  '{query}': Search failed")
        except Exception as e:
            print(f"  '{query}': Error - {e}")

if __name__ == "__main__":
    populate_restaurants(10)