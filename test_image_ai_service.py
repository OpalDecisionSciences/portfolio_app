#!/usr/bin/env python3
"""
Test script for the new ImageAI service to verify it works correctly
and fixes the circular dependency issue.
"""

import sys
import os
from pathlib import Path

# Add the shared services to Python path
sys.path.insert(0, str(Path(__file__).parent / 'shared' / 'src'))

def test_service_import():
    """Test that we can import the service without circular dependencies."""
    print("🔄 Testing ImageAI service import...")
    try:
        from services.image_ai_service import get_image_ai_service, ImageAIService
        print("✅ Successfully imported ImageAI service")
        return True
    except ImportError as e:
        print(f"❌ Failed to import ImageAI service: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing service: {e}")
        return False

def test_service_initialization():
    """Test service initialization."""
    print("\n🔄 Testing service initialization...")
    try:
        from services.image_ai_service import get_image_ai_service
        service = get_image_ai_service()
        print("✅ Successfully initialized ImageAI service")
        print(f"   Service type: {type(service)}")
        print(f"   Available categories: {len(service.STANDARD_CATEGORIES)}")
        return True, service
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return False, None

def test_category_validation(service):
    """Test category validation functionality."""
    print("\n🔄 Testing category validation...")
    test_cases = [
        ('food', 'food'),
        ('menu', 'menu_item'),
        ('atmosphere', 'scenery_ambiance'),
        ('invalid_category', 'uncategorized'),
        ('', 'uncategorized'),
        ('FOOD', 'food'),  # Case insensitive
    ]
    
    all_passed = True
    for input_cat, expected in test_cases:
        try:
            result = service.validate_category(input_cat)
            if result == expected:
                print(f"✅ '{input_cat}' -> '{result}' (correct)")
            else:
                print(f"❌ '{input_cat}' -> '{result}' (expected '{expected}')")
                all_passed = False
        except Exception as e:
            print(f"❌ Error validating '{input_cat}': {e}")
            all_passed = False
    
    return all_passed

def test_category_suggestions(service):
    """Test category suggestion functionality."""
    print("\n🔄 Testing category suggestions...")
    test_cases = [
        "A delicious pasta dish with cheese",
        "Interior view of the restaurant dining room",
        "Chef preparing food in the kitchen",
        "Exterior view of the building"
    ]
    
    all_passed = True
    for description in test_cases:
        try:
            suggestions = service.get_category_suggestions(description)
            print(f"✅ '{description[:30]}...' -> {suggestions}")
        except Exception as e:
            print(f"❌ Error getting suggestions for '{description[:30]}...': {e}")
            all_passed = False
    
    return all_passed

def test_django_task_import():
    """Test that Django tasks can import without circular dependency."""
    print("\n🔄 Testing Django task import (circular dependency check)...")
    
    # Set up Django environment
    django_src = Path(__file__).parent / 'django_app' / 'src'
    if django_src.exists():
        sys.path.insert(0, str(django_src))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')
        
        try:
            import django
            django.setup()
            
            # Try to import the updated tasks module
            from restaurants.tasks import process_image_ai_categorization
            print("✅ Successfully imported Django tasks without circular dependency")
            return True
        except Exception as e:
            print(f"❌ Failed to import Django tasks: {e}")
            return False
    else:
        print("⚠️  Django app not found, skipping Django task test")
        return True

def test_data_pipeline_import():
    """Test that data pipeline can import without circular dependency."""
    print("\n🔄 Testing data pipeline import (circular dependency check)...")
    
    # Set up data pipeline path
    pipeline_src = Path(__file__).parent / 'data_pipeline' / 'src'
    if pipeline_src.exists():
        sys.path.insert(0, str(pipeline_src))
        
        try:
            # Try to import the updated image scraper
            from scrapers.image_scraper import RestaurantImageScraper
            scraper = RestaurantImageScraper()
            print("✅ Successfully imported data pipeline scraper without circular dependency")
            print(f"   Scraper type: {type(scraper)}")
            return True
        except Exception as e:
            print(f"❌ Failed to import data pipeline scraper: {e}")
            return False
    else:
        print("⚠️  Data pipeline not found, skipping pipeline test")
        return True

def test_mock_image_categorization(service):
    """Test image categorization with a mock scenario."""
    print("\n🔄 Testing mock image categorization...")
    
    # We can't test real API calls without API keys, but we can test the flow
    try:
        # Test with a non-existent URL to see error handling
        result = service.categorize_image_with_ai("https://fake-url.com/fake-image.jpg")
        
        # Should return default result due to failed download
        expected_keys = ['category', 'labels', 'description', 'category_confidence', 'description_confidence']
        if all(key in result for key in expected_keys):
            print("✅ Mock categorization returned correct structure")
            print(f"   Result: {result}")
            return True
        else:
            print(f"❌ Mock categorization missing keys: {result}")
            return False
    except Exception as e:
        print(f"❌ Error in mock categorization: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 ImageAI Service Integration Test Suite")
    print("=" * 50)
    
    test_results = []
    
    # Test 1: Service import
    test_results.append(test_service_import())
    
    # Test 2: Service initialization
    init_success, service = test_service_initialization()
    test_results.append(init_success)
    
    if service:
        # Test 3: Category validation
        test_results.append(test_category_validation(service))
        
        # Test 4: Category suggestions
        test_results.append(test_category_suggestions(service))
        
        # Test 5: Mock image categorization
        test_results.append(test_mock_image_categorization(service))
    
    # Test 6: Django task import (circular dependency check)
    test_results.append(test_django_task_import())
    
    # Test 7: Data pipeline import (circular dependency check)
    test_results.append(test_data_pipeline_import())
    
    # Results summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    passed = sum(test_results)
    total = len(test_results)
    
    if passed == total:
        print(f"🎉 All {total} tests PASSED!")
        print("✅ ImageAI service is working correctly")
        print("✅ Circular dependencies have been resolved")
        return True
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        print("❌ Some issues need to be addressed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)