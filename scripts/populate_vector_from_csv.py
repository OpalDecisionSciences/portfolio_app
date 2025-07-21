#!/usr/bin/env python
"""
Vector Database Population from CSV with Progress Tracking

This script populates the vector database systematically from the Michelin CSV,
with resume capability and progress monitoring.
"""

import os
import sys
import django
import requests
import json
import logging
import pandas as pd
import time
from pathlib import Path
from typing import Dict, List, Optional

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "django_app" / "src"))
sys.path.insert(0, str(project_root / "shared"))

django.setup()

from restaurants.models import Restaurant
from vector_management.vector_state_manager import VectorStateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / 'vector_population.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
(project_root / 'logs').mkdir(exist_ok=True)

RAG_SERVICE_URL = os.getenv('RAG_SERVICE_URL', 'http://localhost:8001')

class CSVVectorPopulator:
    """Populates vector database from CSV data with progress tracking."""
    
    def __init__(self, csv_file_path: str):
        """Initialize the CSV vector populator."""
        self.csv_file_path = Path(csv_file_path)
        self.rag_url = RAG_SERVICE_URL
        self.state_manager = VectorStateManager()
        
        # Load CSV data
        self.df = pd.read_csv(self.csv_file_path)
        logger.info(f"Loaded CSV with {len(self.df)} rows")
        
        # Statistics
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0
    
    def create_restaurant_content_from_csv(self, row: pd.Series) -> str:
        """Create rich content text from CSV row for embedding."""
        content_parts = []
        
        # Basic restaurant info
        name = str(row.get('Name', '')).strip()
        location = str(row.get('Location', '')).strip()
        
        if name and name != 'nan':
            content_parts.append(f"{name} is a restaurant")
            
            if location and location != 'nan':
                content_parts.append(f"located in {location}")
        
        # Award information (Michelin stars)
        award = str(row.get('Award', '')).strip()
        if award and award != 'nan' and 'Star' in award:
            content_parts.append(f"It has earned {award}")
        
        # Cuisine type
        cuisine = str(row.get('Cuisine', '')).strip()
        if cuisine and cuisine != 'nan':
            content_parts.append(f"The cuisine type is {cuisine}")
        
        # Price range
        price = str(row.get('Price', '')).strip()
        if price and price != 'nan':
            content_parts.append(f"Price range: {price}")
        
        # Description
        description = str(row.get('Description', '')).strip()
        if description and description != 'nan' and len(description) > 10:
            # Truncate very long descriptions
            if len(description) > 1000:
                description = description[:1000] + "..."
            content_parts.append(f"Description: {description}")
        
        # Address
        address = str(row.get('Address', '')).strip()
        if address and address != 'nan':
            content_parts.append(f"Address: {address}")
        
        # Facilities and services
        facilities = str(row.get('FacilitiesAndServices', '')).strip()
        if facilities and facilities != 'nan':
            content_parts.append(f"Facilities: {facilities}")
        
        return " ".join(content_parts)
    
    def create_metadata_from_csv(self, row: pd.Series, row_index: int) -> Dict:
        """Create metadata dictionary from CSV row."""
        
        # Parse Michelin stars from Award field
        award = str(row.get('Award', '')).strip()
        michelin_stars = 0
        if 'Star' in award:
            try:
                if '3 Star' in award:
                    michelin_stars = 3
                elif '2 Star' in award:
                    michelin_stars = 2
                elif '1 Star' in award:
                    michelin_stars = 1
            except:
                pass
        
        # Parse coordinates
        try:
            latitude = float(row.get('Latitude', 0))
            longitude = float(row.get('Longitude', 0))
        except (ValueError, TypeError):
            latitude = None
            longitude = None
        
        return {
            'csv_row_index': row_index,
            'restaurant_name': str(row.get('Name', '')).strip(),
            'location': str(row.get('Location', '')).strip(),
            'address': str(row.get('Address', '')).strip(),
            'cuisine_type': str(row.get('Cuisine', '')).strip(),
            'price_range': str(row.get('Price', '')).strip(),
            'michelin_stars': michelin_stars,
            'award': award,
            'green_star': bool(row.get('GreenStar', 0)),
            'latitude': latitude,
            'longitude': longitude,
            'phone': str(row.get('PhoneNumber', '')).strip(),
            'website': str(row.get('WebsiteUrl', '')).strip(),
            'michelin_url': str(row.get('Url', '')).strip(),
            'facilities': str(row.get('FacilitiesAndServices', '')).strip(),
            'source': 'michelin_csv',
            'processed_at': pd.Timestamp.now().isoformat()
        }
    
    def create_embedding(self, content: str, metadata: Dict) -> bool:
        """Create an embedding via the RAG service."""
        try:
            response = requests.post(
                f"{self.rag_url}/embeddings/generate",
                data={
                    'content': content,
                    'metadata': json.dumps(metadata)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Failed to create embedding: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            return False
    
    def check_existing_restaurant(self, name: str, location: str) -> Optional[Restaurant]:
        """Check if restaurant already exists in database."""
        try:
            # Try exact name match first
            restaurants = Restaurant.objects.filter(
                name__iexact=name.strip(),
                is_active=True
            )
            
            if restaurants.exists():
                return restaurants.first()
            
            # Try partial location match
            if location:
                city_parts = location.split(',')
                if len(city_parts) >= 1:
                    city = city_parts[0].strip()
                    restaurants = Restaurant.objects.filter(
                        name__iexact=name.strip(),
                        city__icontains=city,
                        is_active=True
                    )
                    if restaurants.exists():
                        return restaurants.first()
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking existing restaurant: {e}")
            return None
    
    def populate_from_csv(self, start_row: int = None, max_rows: int = None, skip_existing: bool = True):
        """Populate vector database from CSV with progress tracking."""
        
        # Initialize session
        session_id = self.state_manager.start_csv_processing_session(
            str(self.csv_file_path)
        )
        
        # Determine start position
        if start_row is None:
            start_row = self.state_manager.get_csv_resume_position()
        
        logger.info(f"Starting CSV population from row {start_row}")
        
        # Determine end position
        total_rows = len(self.df)
        end_row = total_rows
        if max_rows:
            end_row = min(start_row + max_rows, total_rows)
        
        logger.info(f"Processing rows {start_row} to {end_row-1} (total: {end_row - start_row})")
        
        # Process rows
        try:
            for idx in range(start_row, end_row):
                row = self.df.iloc[idx]
                
                # Get restaurant info
                name = str(row.get('Name', '')).strip()
                location = str(row.get('Location', '')).strip()
                
                if not name or name == 'nan':
                    logger.warning(f"Row {idx}: No name, skipping")
                    self.state_manager.update_csv_progress(idx, success=False, error_message="No restaurant name")
                    self.skipped_count += 1
                    continue
                
                # Check if restaurant exists in Django database
                if skip_existing:
                    existing = self.check_existing_restaurant(name, location)
                    if existing:
                        logger.info(f"Row {idx}: {name} already exists in database, skipping")
                        self.state_manager.update_csv_progress(idx, success=True)
                        self.skipped_count += 1
                        continue
                
                # Create content and metadata
                content = self.create_restaurant_content_from_csv(row)
                metadata = self.create_metadata_from_csv(row, idx)
                
                # Create embedding
                if self.create_embedding(content, metadata):
                    self.state_manager.update_csv_progress(idx, success=True)
                    self.success_count += 1
                    logger.info(f"✓ Row {idx}: Created embedding for {name}")
                else:
                    self.state_manager.update_csv_progress(idx, success=False, error_message="Failed to create embedding")
                    self.error_count += 1
                    logger.error(f"✗ Row {idx}: Failed embedding for {name}")
                
                self.processed_count += 1
                
                # Progress reporting
                if self.processed_count % 50 == 0:
                    progress = (self.processed_count / (end_row - start_row)) * 100
                    logger.info(f"Progress: {self.processed_count}/{end_row - start_row} ({progress:.1f}%) - Success: {self.success_count}, Errors: {self.error_count}, Skipped: {self.skipped_count}")
                
                # Small delay to avoid overwhelming the system
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
            self.state_manager.pause_csv_processing()
            
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            self.state_manager.pause_csv_processing()
            raise
        
        # Complete session if we processed all rows
        if end_row >= total_rows:
            self.state_manager.complete_csv_processing()
            logger.info("CSV processing completed!")
        else:
            self.state_manager.pause_csv_processing()
            logger.info(f"Partial processing completed. Resume from row {end_row}")
        
        # Final summary
        logger.info(f"\n📊 Processing Summary:")
        logger.info(f"   Processed: {self.processed_count}")
        logger.info(f"   Successful: {self.success_count}")
        logger.info(f"   Errors: {self.error_count}")
        logger.info(f"   Skipped: {self.skipped_count}")
        
        return {
            'processed': self.processed_count,
            'success': self.success_count,
            'errors': self.error_count,
            'skipped': self.skipped_count
        }
    
    def test_rag_connection(self) -> bool:
        """Test connection to RAG service."""
        try:
            response = requests.get(f"{self.rag_url}/health", timeout=10)
            if response.status_code == 200:
                health = response.json()
                logger.info(f"✅ RAG service healthy: {health}")
                return True
            else:
                logger.error(f"❌ RAG service unhealthy: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ RAG service connection failed: {e}")
            return False


def main():
    """Main function to run CSV vector population."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate vector database from Michelin CSV')
    parser.add_argument('--csv-file', default='data_pipeline/src/ingestion/michelin_my_maps.csv',
                       help='Path to Michelin CSV file')
    parser.add_argument('--start-row', type=int, help='Row to start from (default: resume from last)')
    parser.add_argument('--max-rows', type=int, help='Maximum rows to process in this session')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                       help='Skip restaurants that already exist in Django database')
    parser.add_argument('--test-connection', action='store_true',
                       help='Test RAG service connection only')
    parser.add_argument('--status', action='store_true',
                       help='Show current progress status')
    parser.add_argument('--reset', action='store_true',
                       help='Reset all progress tracking')
    
    args = parser.parse_args()
    
    # Handle status command
    if args.status:
        manager = VectorStateManager()
        summary = manager.get_progress_summary()
        
        print("\n📊 Vector Database Population Status:")
        csv_progress = summary['csv_processing']
        print(f"   Status: {csv_progress['status']}")
        print(f"   Total CSV Rows: {csv_progress['total_rows']:,}")
        print(f"   Processed: {csv_progress['processed']:,}")
        print(f"   Failed: {csv_progress['failed']:,}")
        print(f"   Remaining: {csv_progress['remaining']:,}")
        print(f"   Progress: {csv_progress['progress_percentage']}%")
        print(f"   Resume from row: {csv_progress['resume_from_row']:,}")
        
        vector_stats = summary['vector_database']
        print(f"\n🔢 Vector Database Stats:")
        print(f"   Total Embeddings: {vector_stats['total_embeddings_created']:,}")
        print(f"   Failed Embeddings: {vector_stats['failed_embeddings']:,}")
        print(f"   Current Session: {vector_stats['current_session']}")
        print(f"   Last Updated: {vector_stats['last_updated']}")
        return
    
    # Handle reset command
    if args.reset:
        manager = VectorStateManager()
        manager.reset_progress('all')
        print("✅ Reset all progress tracking")
        return
    
    # Resolve CSV file path
    csv_file = Path(args.csv_file)
    if not csv_file.is_absolute():
        csv_file = Path(__file__).parent.parent / csv_file
    
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        sys.exit(1)
    
    # Initialize populator
    populator = CSVVectorPopulator(str(csv_file))
    
    # Test connection if requested
    if args.test_connection:
        if populator.test_rag_connection():
            print("✅ RAG service connection successful")
        else:
            print("❌ RAG service connection failed")
        return
    
    # Test connection before starting
    if not populator.test_rag_connection():
        logger.error("Cannot connect to RAG service. Please ensure it's running.")
        sys.exit(1)
    
    try:
        # Run population
        results = populator.populate_from_csv(
            start_row=args.start_row,
            max_rows=args.max_rows,
            skip_existing=args.skip_existing
        )
        
        print(f"\n🎯 Completed Successfully:")
        print(f"   Processed: {results['processed']}")
        print(f"   Successful: {results['success']}")
        print(f"   Errors: {results['errors']}")
        print(f"   Skipped: {results['skipped']}")
        
    except Exception as e:
        logger.error(f"Population failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()