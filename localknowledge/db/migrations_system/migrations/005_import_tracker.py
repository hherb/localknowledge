"""
Migration 005: Import Tracker

This migration adds the import_tracker table for tracking PubMed file processing
to avoid reprocessing the same files when restarting interrupted processes.
"""

import logging
from typing import Optional, Callable

from localknowledge.db.migrations_system import MigrationsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.

    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 005: Import Tracker")

    # Create import_tracker table
    logger.info("Creating import_tracker table")
    db_manager.execute("""
    CREATE TABLE IF NOT EXISTS import_tracker (
        filename TEXT NOT NULL PRIMARY KEY,
        imported TIMESTAMP WITH TIME ZONE DEFAULT NULL,
        chunked TIMESTAMP WITH TIME ZONE DEFAULT NULL,
        embedded BOOLEAN DEFAULT FALSE,
        md5checked BOOLEAN DEFAULT FALSE
    );
    """, commit=True)

    # Add indexes for performance
    logger.info("Creating indexes for import_tracker")
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_import_tracker_imported ON import_tracker(imported);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_import_tracker_chunked ON import_tracker(chunked);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_import_tracker_embedded ON import_tracker(embedded);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_import_tracker_md5checked ON import_tracker(md5checked);
    """, commit=True)

    logger.info("Migration 005 completed successfully")
