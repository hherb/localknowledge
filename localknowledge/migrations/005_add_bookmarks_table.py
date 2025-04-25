"""
Migration 005: add_bookmarks_table

This migration script adds a bookmarks table to the database.
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
    logger.info("Starting migration 005: Adding bookmarks table")

    # Check if bookmarks table already exists
    result = db_manager.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'bookmarks'
    );
    """)
    
    if result and result[0]['exists']:
        logger.info("Bookmarks table already exists, skipping creation")
    else:
        # Create the bookmarks table
        logger.info("Creating bookmarks table")
        db_manager.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            bookmark_type TEXT NOT NULL CHECK (bookmark_type IN ('personal', 'project', 'both')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (document_id, user_id, project_id)
        );
        """, commit=True)
        
        if progress_callback:
            progress_callback(1, 2, "Created bookmarks table")
        
        # Create indices for faster lookups
        logger.info("Creating indices for bookmarks table")
        db_manager.execute("""
        CREATE INDEX IF NOT EXISTS idx_bookmarks_document_id ON bookmarks(document_id);
        CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);
        CREATE INDEX IF NOT EXISTS idx_bookmarks_project_id ON bookmarks(project_id);
        CREATE INDEX IF NOT EXISTS idx_bookmarks_type ON bookmarks(bookmark_type);
        """, commit=True)
        
        if progress_callback:
            progress_callback(2, 2, "Created indices for bookmarks table")
    
    logger.info("Migration 005 completed")
