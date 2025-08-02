#!/usr/bin/env python3
"""
Comprehensive UI functionality test
Tests all main pages and API endpoints to ensure proper data display
"""
import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_page(url, description):
    """Test a page and return status."""
    try:
        response = requests.get(f"{BASE_URL}{url}", timeout=10)
        status = "✅" if response.status_code == 200 else "❌"
        print(f"{status} {description}: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ {description}: Error - {e}")
        return False

def test_api_endpoint(url, description):
    """Test an API endpoint and return data."""
    try:
        response = requests.get(f"{BASE_URL}{url}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {description}: {response.status_code}")
            return data
        else:
            print(f"❌ {description}: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {description}: Error - {e}")
        return None

def main():
    """Run comprehensive UI tests."""
    print("🧪 COMPREHENSIVE UI FUNCTIONALITY TEST")
    print("=" * 50)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test main pages
    print("📄 Testing Main Pages:")
    test_page("/", "Homepage")
    test_page("/restaurants/", "Restaurant List")
    test_page("/restaurants/hisa-franko-kobarid/", "Restaurant Detail (Hiša Franko)")
    print()
    
    # Test API endpoints
    print("🔌 Testing API Endpoints:")
    
    # Test search API
    search_data = test_api_endpoint("/restaurants/api/search/?q=french&max_results=3", "Search API (French)")
    if search_data and search_data.get('results'):
        print(f"   📊 Search returned {len(search_data['results'])} results")
        for result in search_data['results'][:2]:
            print(f"      - {result['name']} ({result['city']}, {result['country']})")
    
    # Test recommendations API
    rec_data = test_api_endpoint("/restaurants/api/recommendations/?max_results=3", "Recommendations API")
    if rec_data and rec_data.get('recommendations'):
        print(f"   📊 Recommendations returned {len(rec_data['recommendations'])} results")
    
    # Test stats API
    stats_data = test_api_endpoint("/restaurants/api/stats/", "Stats API")
    if stats_data:
        print(f"   📊 Database stats:")
        print(f"      - Total restaurants: {stats_data.get('total_restaurants', 'N/A')}")
        print(f"      - Countries: {stats_data.get('total_countries', 'N/A')}")
        print(f"      - Cuisines: {stats_data.get('total_cuisines', 'N/A')}")
    
    print()
    
    # Test filtering
    print("🔍 Testing Filtering:")
    test_page("/restaurants/?country=France", "Filter by Country (France)")
    test_page("/restaurants/?cuisine=French", "Filter by Cuisine (French)")
    test_page("/restaurants/?stars=3", "Filter by Michelin Stars (3)")
    test_page("/restaurants/?search=paris", "Search by keyword (Paris)")
    print()
    
    # Test specific restaurant features
    print("🍽️  Testing Restaurant Detail Features:")
    test_page("/restaurants/hisa-franko-kobarid/", "Restaurant detail page")
    
    print()
    print("=" * 50)
    print("✅ UI functionality test completed!")

if __name__ == "__main__":
    main()