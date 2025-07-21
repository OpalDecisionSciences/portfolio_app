#!/usr/bin/env python
"""
Vector Database Population from Scraped Restaurant Documents

This script populates the vector database with embeddings from the scraped 
restaurant document files, with progress tracking.
"""

import os
import sys
import django
import requests
import json
import logging
from pathlib import Path
from typing import Dict, List

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
        logging.FileHandler(project_root / 'logs' / 'vector_docs_population.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
(project_root / 'logs').mkdir(exist_ok=True)

RAG_SERVICE_URL = os.getenv('RAG_SERVICE_URL', 'http://localhost:8001')

class DocsVectorPopulator:
    """Populates vector database from scraped restaurant documents."""
    
    def __init__(self, docs_dir: str):
        """Initialize the docs vector populator."""
        self.docs_dir = Path(docs_dir)
        self.rag_url = RAG_SERVICE_URL
        self.state_manager = VectorStateManager()
        
        # Find all document files
        self.doc_files = list(self.docs_dir.glob("*_document.txt"))
        logger.info(f"Found {len(self.doc_files)} document files")
        
        # Statistics
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0
    
    def extract_restaurant_name_from_filename(self, file_path: Path) -> str:
        """Extract restaurant name from document filename."""
        # Remove _document.txt suffix and clean up
        name = file_path.stem.replace('_document', '')
        
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        
        # Title case
        name = name.title()
        
        # Handle special cases
        name = name.replace(' At The ', ' at the ')
        name = name.replace(' By ', ' by ')
        name = name.replace(' De ', ' de ')
        name = name.replace(' Du ', ' du ')
        name = name.replace(' La ', ' la ')
        name = name.replace(' Le ', ' le ')
        name = name.replace(' L ', ' l\'')
        
        return name.strip()
    
    def create_restaurant_content_from_doc(self, file_path: Path) -> str:
        """Create rich content text from document file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                return ""
            
            # Extract restaurant name from filename
            restaurant_name = self.extract_restaurant_name_from_filename(file_path)
            
            # Prepend restaurant name context
            enhanced_content = f"Restaurant: {restaurant_name}\n\n{content}"
            
            # Truncate if too long (embeddings have limits)
            if len(enhanced_content) > 8000:
                enhanced_content = enhanced_content[:8000] + "..."
            
            return enhanced_content
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return ""
    
    def create_metadata_from_doc(self, file_path: Path) -> Dict:
        """Create metadata dictionary from document file."""
        restaurant_name = self.extract_restaurant_name_from_filename(file_path)
        
        # Try to find matching restaurant in database
        restaurant_id = None
        city = None
        country = None
        michelin_stars = 0
        cuisine_type = None
        
        try:
            # Try exact name match
            restaurant = Restaurant.objects.filter(
                name__iexact=restaurant_name,
                is_active=True
            ).first()
            
            if not restaurant:
                # Try partial name match
                restaurant = Restaurant.objects.filter(
                    name__icontains=restaurant_name.split()[0],
                    is_active=True
                ).first()
            
            if restaurant:
                restaurant_id = str(restaurant.id)
                city = restaurant.city
                country = restaurant.country
                michelin_stars = restaurant.michelin_stars
                cuisine_type = restaurant.cuisine_type
                
        except Exception as e:
            logger.warning(f"Could not find restaurant in database: {e}")
        
        return {
            'source': 'scraped_document',
            'document_file': str(file_path.name),
            'restaurant_name': restaurant_name,
            'restaurant_id': restaurant_id,
            'city': city,
            'country': country,
            'michelin_stars': michelin_stars,
            'cuisine_type': cuisine_type,
            'file_size': file_path.stat().st_size,
            'processed_at': Path(file_path).stat().st_mtime
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
                timeout=60  # Longer timeout for large documents
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Failed to create embedding: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            return False
    
    def populate_from_docs(self, max_files: int = None):
        """Populate vector database from document files."""
        
        # Get previously processed files
        progress = self.state_manager.get_progress_summary()
        processed_files = set(progress['scraped_docs'].get('processed_files', []))
        failed_files = set(progress['scraped_docs'].get('failed_files', []))
        
        # Filter to unprocessed files
        unprocessed_files = [
            f for f in self.doc_files 
            if str(f.name) not in processed_files and str(f.name) not in failed_files
        ]
        
        logger.info(f"Found {len(unprocessed_files)} unprocessed document files")
        
        if max_files:
            unprocessed_files = unprocessed_files[:max_files]
            logger.info(f"Limiting to {max_files} files for this session")
        
        # Process files
        for i, file_path in enumerate(unprocessed_files, 1):
            logger.info(f"Processing {i}/{len(unprocessed_files)}: {file_path.name}")
            
            # Create content and metadata
            content = self.create_restaurant_content_from_doc(file_path)
            
            if not content:
                logger.warning(f"No content extracted from {file_path.name}, skipping")
                self.state_manager.add_scraped_doc_progress(str(file_path.name), success=False)
                self.skipped_count += 1
                continue
            
            metadata = self.create_metadata_from_doc(file_path)
            
            # Create embedding
            if self.create_embedding(content, metadata):
                self.state_manager.add_scraped_doc_progress(str(file_path.name), success=True)
                self.success_count += 1
                logger.info(f"✓ Created embedding for {metadata['restaurant_name']}")
            else:
                self.state_manager.add_scraped_doc_progress(str(file_path.name), success=False)
                self.error_count += 1
                logger.error(f"✗ Failed embedding for {metadata['restaurant_name']}")
            
            self.processed_count += 1
            
            # Progress reporting
            if self.processed_count % 10 == 0:
                progress = (self.processed_count / len(unprocessed_files)) * 100
                logger.info(f"Progress: {self.processed_count}/{len(unprocessed_files)} ({progress:.1f}%) - Success: {self.success_count}, Errors: {self.error_count}")
        
        # Final summary
        logger.info(f"\n📊 Document Processing Summary:")
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
    """Main function to run document vector population."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate vector database from scraped restaurant documents')
    parser.add_argument('--docs-dir', default='data_pipeline/src/scrapers/restaurant_docs',
                       help='Directory containing restaurant document files')
    parser.add_argument('--max-files', type=int, help='Maximum files to process in this session')
    parser.add_argument('--test-connection', action='store_true',
                       help='Test RAG service connection only')
    parser.add_argument('--status', action='store_true',
                       help='Show current progress status')
    parser.add_argument('--reset-docs', action='store_true',
                       help='Reset document processing progress')
    
    args = parser.parse_args()
    
    # Handle status command
    if args.status:
        manager = VectorStateManager()
        summary = manager.get_progress_summary()
        
        docs_progress = summary['scraped_docs']
        print(f"\n📄 Document Processing Status:")
        print(f"   Processed Files: {len(docs_progress.get('processed_files', []))}")
        print(f"   Failed Files: {len(docs_progress.get('failed_files', []))}")
        print(f"   Last Processed: {docs_progress.get('last_processed_file', 'None')}")
        print(f"   Last Date: {docs_progress.get('last_processed_date', 'None')}")
        return
    
    # Handle reset command
    if args.reset_docs:
        manager = VectorStateManager()
        manager.reset_progress('docs')
        print("✅ Reset document processing progress")
        return
    
    # Resolve docs directory path
    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_absolute():
        docs_dir = Path(__file__).parent.parent / docs_dir
    
    if not docs_dir.exists():
        logger.error(f"Documents directory not found: {docs_dir}")
        sys.exit(1)
    
    # Initialize populator
    populator = DocsVectorPopulator(str(docs_dir))
    
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
        results = populator.populate_from_docs(max_files=args.max_files)
        
        print(f"\n🎯 Document Processing Completed:")
        print(f"   Processed: {results['processed']}")
        print(f"   Successful: {results['success']}")
        print(f"   Errors: {results['errors']}")
        print(f"   Skipped: {results['skipped']}")
        
    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()