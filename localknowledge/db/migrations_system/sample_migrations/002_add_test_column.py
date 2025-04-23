"""
Migration 002: add_test_column

This migration script adds a test column to the version table.
"""

import logging
from typing import Callable, Optional
from localknowledge.db.migrations_system.manager import MigrationsManager

# Configure logging
logger = logging.getLogger(__name__)


def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.
    
    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 002")
    
    # Check if column already exists
    result = db_manager.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'version' AND column_name = 'test_column';
    """)
    
    if not result:
        # Column doesn't exist, add it
        db_manager.execute("""
        ALTER TABLE version
        ADD COLUMN test_column TEXT;
        """, commit=True)
        logger.info("Added test_column to version table")
    else:
        logger.info("test_column already exists in version table")
    
    logger.info("Migration 002 completed")
