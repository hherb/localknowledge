"""
Migration 001: initialize_version

This migration script initializes the version table.
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
    logger.info("Starting migration 001")
    
    # The version table is already created by the migrations manager
    # This migration is just a placeholder to establish version 1
    
    logger.info("Migration 001 completed")
