#!/usr/bin/env python3
"""
Script to initialize the document tables.

This script creates the document tables and indices.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Initialize the document tables."""
    logger.info("Initializing document tables")
    
    # Create document database manager
    document_db = DocumentDatabaseManager()
    
    try:
        # Create tables
        logger.info("Creating document tables")
        document_db.create_tables()
        
        # Create indices
        logger.info("Creating document indices")
        document_db.create_indices()
        
        logger.info("Document tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing document tables: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        document_db.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
