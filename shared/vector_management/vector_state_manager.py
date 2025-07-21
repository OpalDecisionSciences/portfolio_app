#!/usr/bin/env python
"""
Vector Database State Management System

Tracks progress of vector database population from CSV data sources,
similar to the web scraping progress tracking system.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStateManager:
    """Manages the state and progress of vector database population."""
    
    def __init__(self, state_dir: Path = None):
        """Initialize the vector state manager."""
        if state_dir is None:
            # Default to shared/vector_management/state/
            base_dir = Path(__file__).parent.parent
            state_dir = base_dir / "vector_management" / "state"
        
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # State files
        self.vector_state_file = self.state_dir / "vector_population_state.json"
        self.csv_progress_file = self.state_dir / "csv_progress.json"
        
        # Load current state
        self.vector_state = self._load_vector_state()
        self.csv_progress = self._load_csv_progress()
    
    def _load_vector_state(self) -> Dict:
        """Load vector database population state."""
        if self.vector_state_file.exists():
            try:
                with open(self.vector_state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load vector state: {e}")
        
        return {
            "total_restaurants_processed": 0,
            "total_embeddings_created": 0,
            "failed_embeddings": 0,
            "last_updated": None,
            "current_session": None,
            "processing_errors": []
        }
    
    def _load_csv_progress(self) -> Dict:
        """Load CSV processing progress state."""
        if self.csv_progress_file.exists():
            try:
                with open(self.csv_progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load CSV progress: {e}")
        
        return {
            "michelin_csv": {
                "last_completed_row": -1,
                "total_rows": 0,
                "processed_count": 0,
                "failed_count": 0,
                "last_processed_date": None,
                "processing_status": "not_started"  # not_started, in_progress, completed, paused
            },
            "scraped_docs": {
                "last_processed_file": None,
                "processed_files": [],
                "failed_files": [],
                "total_files": 0,
                "last_processed_date": None
            }
        }
    
    def _save_vector_state(self):
        """Save vector database state to file."""
        self.vector_state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.vector_state_file, 'w') as f:
                json.dump(self.vector_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vector state: {e}")
    
    def _save_csv_progress(self):
        """Save CSV progress state to file."""
        try:
            with open(self.csv_progress_file, 'w') as f:
                json.dump(self.csv_progress, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save CSV progress: {e}")
    
    def start_csv_processing_session(self, csv_file_path: str, session_id: str = None) -> str:
        """Start a new CSV processing session."""
        if session_id is None:
            session_id = f"csv_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Count total rows in CSV
        try:
            df = pd.read_csv(csv_file_path)
            total_rows = len(df)
        except Exception as e:
            logger.error(f"Failed to read CSV file: {e}")
            total_rows = 0
        
        # Update state
        self.csv_progress["michelin_csv"]["total_rows"] = total_rows
        self.csv_progress["michelin_csv"]["processing_status"] = "in_progress"
        self.vector_state["current_session"] = session_id
        
        self._save_csv_progress()
        self._save_vector_state()
        
        logger.info(f"Started CSV processing session: {session_id}")
        logger.info(f"Total rows to process: {total_rows}")
        logger.info(f"Starting from row: {self.csv_progress['michelin_csv']['last_completed_row'] + 1}")
        
        return session_id
    
    def update_csv_progress(self, row_number: int, success: bool = True, error_message: str = None):
        """Update progress for CSV row processing."""
        csv_state = self.csv_progress["michelin_csv"]
        
        if success:
            csv_state["last_completed_row"] = row_number
            csv_state["processed_count"] += 1
            self.vector_state["total_restaurants_processed"] += 1
            self.vector_state["total_embeddings_created"] += 1
        else:
            csv_state["failed_count"] += 1
            self.vector_state["failed_embeddings"] += 1
            
            if error_message:
                self.vector_state["processing_errors"].append({
                    "row": row_number,
                    "error": error_message,
                    "timestamp": datetime.now().isoformat()
                })
        
        csv_state["last_processed_date"] = datetime.now().isoformat()
        
        # Auto-save every 10 rows
        if row_number % 10 == 0:
            self._save_csv_progress()
            self._save_vector_state()
    
    def complete_csv_processing(self):
        """Mark CSV processing as completed."""
        self.csv_progress["michelin_csv"]["processing_status"] = "completed"
        self.vector_state["current_session"] = None
        
        self._save_csv_progress()
        self._save_vector_state()
        
        logger.info("CSV processing session completed")
    
    def pause_csv_processing(self):
        """Pause CSV processing session."""
        self.csv_progress["michelin_csv"]["processing_status"] = "paused"
        self._save_csv_progress()
        self._save_vector_state()
        
        logger.info("CSV processing session paused")
    
    def get_csv_resume_position(self) -> int:
        """Get the row number to resume CSV processing from."""
        return self.csv_progress["michelin_csv"]["last_completed_row"] + 1
    
    def get_progress_summary(self) -> Dict:
        """Get a summary of current progress."""
        csv_state = self.csv_progress["michelin_csv"]
        
        progress_percentage = 0
        if csv_state["total_rows"] > 0:
            progress_percentage = (csv_state["processed_count"] / csv_state["total_rows"]) * 100
        
        return {
            "csv_processing": {
                "status": csv_state["processing_status"],
                "total_rows": csv_state["total_rows"],
                "processed": csv_state["processed_count"],
                "failed": csv_state["failed_count"],
                "remaining": csv_state["total_rows"] - csv_state["processed_count"],
                "progress_percentage": round(progress_percentage, 2),
                "last_completed_row": csv_state["last_completed_row"],
                "resume_from_row": self.get_csv_resume_position()
            },
            "vector_database": {
                "total_restaurants_processed": self.vector_state["total_restaurants_processed"],
                "total_embeddings_created": self.vector_state["total_embeddings_created"],
                "failed_embeddings": self.vector_state["failed_embeddings"],
                "current_session": self.vector_state["current_session"],
                "last_updated": self.vector_state["last_updated"]
            },
            "scraped_docs": self.csv_progress["scraped_docs"]
        }
    
    def add_scraped_doc_progress(self, file_path: str, success: bool = True):
        """Track progress of scraped document processing."""
        docs_state = self.csv_progress["scraped_docs"]
        
        if success:
            if file_path not in docs_state["processed_files"]:
                docs_state["processed_files"].append(file_path)
            docs_state["last_processed_file"] = file_path
        else:
            if file_path not in docs_state["failed_files"]:
                docs_state["failed_files"].append(file_path)
        
        docs_state["last_processed_date"] = datetime.now().isoformat()
        self._save_csv_progress()
    
    def reset_progress(self, component: str = "all"):
        """Reset progress for specified component."""
        if component in ["all", "csv"]:
            self.csv_progress["michelin_csv"] = {
                "last_completed_row": -1,
                "total_rows": 0,
                "processed_count": 0,
                "failed_count": 0,
                "last_processed_date": None,
                "processing_status": "not_started"
            }
        
        if component in ["all", "docs"]:
            self.csv_progress["scraped_docs"] = {
                "last_processed_file": None,
                "processed_files": [],
                "failed_files": [],
                "total_files": 0,
                "last_processed_date": None
            }
        
        if component in ["all", "vector"]:
            self.vector_state = {
                "total_restaurants_processed": 0,
                "total_embeddings_created": 0,
                "failed_embeddings": 0,
                "last_updated": None,
                "current_session": None,
                "processing_errors": []
            }
        
        self._save_csv_progress()
        self._save_vector_state()
        
        logger.info(f"Reset progress for: {component}")


def main():
    """Test the vector state manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Vector State Manager')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--reset', choices=['all', 'csv', 'docs', 'vector'], help='Reset progress')
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = VectorStateManager()
    
    if args.status:
        summary = manager.get_progress_summary()
        print("\n📊 Vector Database Population Status:")
        print(f"   CSV Processing Status: {summary['csv_processing']['status']}")
        print(f"   Total Rows: {summary['csv_processing']['total_rows']}")
        print(f"   Processed: {summary['csv_processing']['processed']}")
        print(f"   Failed: {summary['csv_processing']['failed']}")
        print(f"   Progress: {summary['csv_processing']['progress_percentage']}%")
        print(f"   Resume from row: {summary['csv_processing']['resume_from_row']}")
        
        print(f"\n🔢 Vector Database Stats:")
        print(f"   Total Embeddings: {summary['vector_database']['total_embeddings_created']}")
        print(f"   Failed Embeddings: {summary['vector_database']['failed_embeddings']}")
        print(f"   Current Session: {summary['vector_database']['current_session']}")
    
    if args.reset:
        manager.reset_progress(args.reset)
        print(f"✅ Reset {args.reset} progress")


if __name__ == "__main__":
    main()