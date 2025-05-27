"""
Migration 003: add_missing_details_column

This migration script adds the missing_details column to the document table.
This column will be used to flag records that need their details updated.
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
    logger.info("Starting migration 003: add_missing_details_column")

    # Step 1: Check if the missing_details column already exists
    logger.info("Checking if missing_details column already exists")
    result = db_manager.execute_without_timeout("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'document' AND column_name = 'missing_details';
    """)

    if not result:
        # Column doesn't exist, add it
        logger.info("Adding missing_details column to document table")
        db_manager.execute_without_timeout("""
        ALTER TABLE public.document
        ADD COLUMN missing_details BOOLEAN DEFAULT FALSE;
        """, commit=True)

        if progress_callback:
            progress_callback(1, 2, "Added missing_details column")
    else:
        logger.info("missing_details column already exists in document table")
        if progress_callback:
            progress_callback(1, 2, "missing_details column already exists")

    # Step 2: Create an index on the missing_details column for faster queries
    logger.info("Checking if index on missing_details column already exists")
    result = db_manager.execute_without_timeout("""
    SELECT indexname
    FROM pg_indexes
    WHERE tablename = 'document' AND indexname = 'idx_document_missing_details';
    """)

    if not result:
        logger.info("Creating index on missing_details column")
        db_manager.execute_without_timeout("""
        CREATE INDEX idx_document_missing_details ON public.document (missing_details)
        WHERE missing_details = TRUE;
        """, commit=True)

        if progress_callback:
            progress_callback(2, 2, "Created index on missing_details column")
    else:
        logger.info("Index on missing_details column already exists")
        if progress_callback:
            progress_callback(2, 2, "Index already exists")

    logger.info("Migration 003 completed successfully")
