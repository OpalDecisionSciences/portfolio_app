#!/usr/bin/env python
"""
Master Vector Database Population Script

This script orchestrates the complete population of the vector database from all sources:
1. Michelin CSV data (18K+ restaurants)
2. Scraped restaurant documents
3. Existing Django database restaurants

With comprehensive progress tracking and resume capabilities.
"""

import os
import sys
import django
import argparse
import logging
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "django_app" / "src"))
sys.path.insert(0, str(project_root / "shared"))

django.setup()

from vector_management.vector_state_manager import VectorStateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / 'master_vector_populate.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
(project_root / 'logs').mkdir(exist_ok=True)

class MasterVectorPopulator:
    """Orchestrates complete vector database population from all sources."""
    
    def __init__(self):
        """Initialize the master populator."""
        self.state_manager = VectorStateManager()
        self.project_root = project_root
    
    def populate_from_csv(self, start_row: int = None, max_rows: int = None):
        """Populate from Michelin CSV data."""
        logger.info("🍽️  Starting CSV-based vector population...")
        
        csv_script = self.project_root / "scripts" / "populate_vector_from_csv.py"
        
        # Build command
        cmd_parts = [sys.executable, str(csv_script)]
        
        if start_row is not None:
            cmd_parts.extend(['--start-row', str(start_row)])
        
        if max_rows is not None:
            cmd_parts.extend(['--max-rows', str(max_rows)])
        
        # Execute CSV population
        import subprocess
        try:
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                logger.info("✅ CSV population completed successfully")
                logger.info(result.stdout)
                return True
            else:
                logger.error(f"❌ CSV population failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ CSV population timed out after 1 hour")
            return False
        except Exception as e:
            logger.error(f"❌ CSV population error: {e}")
            return False
    
    def populate_from_docs(self, max_files: int = None):
        """Populate from scraped restaurant documents."""
        logger.info("📄 Starting document-based vector population...")
        
        docs_script = self.project_root / "scripts" / "populate_vector_from_docs.py"
        
        # Build command
        cmd_parts = [sys.executable, str(docs_script)]
        
        if max_files is not None:
            cmd_parts.extend(['--max-files', str(max_files)])
        
        # Execute document population
        import subprocess
        try:
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0:
                logger.info("✅ Document population completed successfully")
                logger.info(result.stdout)
                return True
            else:
                logger.error(f"❌ Document population failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Document population timed out after 30 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Document population error: {e}")
            return False
    
    def populate_from_database(self, limit: int = None):
        """Populate from existing Django database restaurants."""
        logger.info("🗄️  Starting database-based vector population...")
        
        integrated_script = self.project_root / "scripts" / "integrated_scraping_with_vectors.py"
        
        # Build command
        cmd_parts = [sys.executable, str(integrated_script)]
        
        if limit is not None:
            cmd_parts.extend(['--bulk-process', str(limit)])
        else:
            cmd_parts.extend(['--bulk-process', '0'])  # 0 means no limit
        
        # Execute database population
        import subprocess
        try:
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                logger.info("✅ Database population completed successfully")
                logger.info(result.stdout)
                return True
            else:
                logger.error(f"❌ Database population failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Database population timed out after 1 hour")
            return False
        except Exception as e:
            logger.error(f"❌ Database population error: {e}")
            return False
    
    def run_complete_population(self, csv_batch_size: int = 1000, docs_batch_size: int = 50, db_limit: int = None):
        """Run complete vector database population from all sources."""
        logger.info("🚀 Starting COMPLETE vector database population...")
        
        overall_success = True
        
        # Step 1: Populate from CSV (largest dataset)
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Populating from Michelin CSV (18K+ restaurants)")
        logger.info("="*60)
        
        csv_success = self.populate_from_csv(max_rows=csv_batch_size)
        if not csv_success:
            overall_success = False
            logger.warning("CSV population failed, continuing with other sources...")
        
        # Step 2: Populate from scraped documents
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Populating from scraped restaurant documents")
        logger.info("="*60)
        
        docs_success = self.populate_from_docs(max_files=docs_batch_size)
        if not docs_success:
            overall_success = False
            logger.warning("Document population failed, continuing with database...")
        
        # Step 3: Populate from Django database
        logger.info("\n" + "="*60)
        logger.info("STEP 3: Populating from Django database restaurants")
        logger.info("="*60)
        
        db_success = self.populate_from_database(limit=db_limit)
        if not db_success:
            overall_success = False
            logger.warning("Database population failed")
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("MASTER POPULATION SUMMARY")
        logger.info("="*60)
        
        summary = self.state_manager.get_progress_summary()
        vector_stats = summary['vector_database']
        csv_stats = summary['csv_processing']
        docs_stats = summary['scraped_docs']
        
        logger.info(f"CSV Processing: {csv_stats['status']} ({csv_stats['progress_percentage']}%)")
        logger.info(f"Documents Processed: {len(docs_stats.get('processed_files', []))}")
        logger.info(f"Total Vector Embeddings: {vector_stats['total_embeddings_created']:,}")
        logger.info(f"Failed Embeddings: {vector_stats['failed_embeddings']:,}")
        
        if overall_success:
            logger.info("🎉 MASTER POPULATION COMPLETED SUCCESSFULLY!")
        else:
            logger.warning("⚠️  MASTER POPULATION COMPLETED WITH SOME FAILURES")
        
        return overall_success
    
    def resume_population(self):
        """Resume population from where it left off."""
        logger.info("🔄 Resuming vector population from last checkpoint...")
        
        summary = self.state_manager.get_progress_summary()
        csv_stats = summary['csv_processing']
        
        if csv_stats['status'] == 'in_progress' or csv_stats['status'] == 'paused':
            logger.info(f"Resuming CSV population from row {csv_stats['resume_from_row']:,}")
            return self.populate_from_csv(start_row=csv_stats['resume_from_row'])
        elif csv_stats['status'] == 'completed':
            logger.info("CSV population already completed, checking other sources...")
            
            # Check documents
            docs_stats = summary['scraped_docs']
            total_doc_files = len(list((self.project_root / "data_pipeline" / "src" / "scrapers" / "restaurant_docs").glob("*_document.txt")))
            processed_docs = len(docs_stats.get('processed_files', []))
            
            if processed_docs < total_doc_files:
                logger.info(f"Resuming document population ({processed_docs}/{total_doc_files} completed)")
                return self.populate_from_docs()
            else:
                logger.info("All sources appear to be processed. Running database sync...")
                return self.populate_from_database()
        else:
            logger.info("No previous population found, starting fresh...")
            return self.run_complete_population()


def main():
    """Main function for master vector population."""
    parser = argparse.ArgumentParser(description='Master Vector Database Population')
    parser.add_argument('--complete', action='store_true',
                       help='Run complete population from all sources')
    parser.add_argument('--resume', action='store_true',
                       help='Resume population from last checkpoint')
    parser.add_argument('--csv-only', action='store_true',
                       help='Populate only from CSV')
    parser.add_argument('--docs-only', action='store_true',
                       help='Populate only from documents')
    parser.add_argument('--database-only', action='store_true',
                       help='Populate only from Django database')
    parser.add_argument('--csv-batch-size', type=int, default=1000,
                       help='Number of CSV rows to process per batch (default: 1000)')
    parser.add_argument('--docs-batch-size', type=int, default=50,
                       help='Number of documents to process per batch (default: 50)')
    parser.add_argument('--db-limit', type=int,
                       help='Limit number of database restaurants to process')
    parser.add_argument('--status', action='store_true',
                       help='Show current population status')
    parser.add_argument('--reset', action='store_true',
                       help='Reset all progress and start fresh')
    
    args = parser.parse_args()
    
    populator = MasterVectorPopulator()
    
    if args.status:
        summary = populator.state_manager.get_progress_summary()
        
        print("\n📊 MASTER VECTOR POPULATION STATUS")
        print("="*50)
        
        csv_stats = summary['csv_processing']
        print(f"📄 CSV Processing:")
        print(f"   Status: {csv_stats['status']}")
        print(f"   Total Rows: {csv_stats['total_rows']:,}")
        print(f"   Processed: {csv_stats['processed']:,}")
        print(f"   Progress: {csv_stats['progress_percentage']}%")
        print(f"   Resume from: Row {csv_stats['resume_from_row']:,}")
        
        docs_stats = summary['scraped_docs']
        print(f"\n📋 Document Processing:")
        print(f"   Processed Files: {len(docs_stats.get('processed_files', []))}")
        print(f"   Failed Files: {len(docs_stats.get('failed_files', []))}")
        
        vector_stats = summary['vector_database']
        print(f"\n🔢 Vector Database:")
        print(f"   Total Embeddings: {vector_stats['total_embeddings_created']:,}")
        print(f"   Failed Embeddings: {vector_stats['failed_embeddings']:,}")
        print(f"   Current Session: {vector_stats['current_session']}")
        
        return
    
    if args.reset:
        populator.state_manager.reset_progress('all')
        print("✅ Reset all progress tracking")
        return
    
    if args.complete:
        success = populator.run_complete_population(
            csv_batch_size=args.csv_batch_size,
            docs_batch_size=args.docs_batch_size,
            db_limit=args.db_limit
        )
        sys.exit(0 if success else 1)
    
    if args.resume:
        success = populator.resume_population()
        sys.exit(0 if success else 1)
    
    if args.csv_only:
        success = populator.populate_from_csv(max_rows=args.csv_batch_size)
        sys.exit(0 if success else 1)
    
    if args.docs_only:
        success = populator.populate_from_docs(max_files=args.docs_batch_size)
        sys.exit(0 if success else 1)
    
    if args.database_only:
        success = populator.populate_from_database(limit=args.db_limit)
        sys.exit(0 if success else 1)
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()