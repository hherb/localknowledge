"""
Module to check for pending migrations on application startup.

This module provides functions to check for pending migrations and
optionally run them automatically.
"""

import logging
from typing import Optional, Callable, Tuple

from .manager import MigrationsManager

# Configure logging
logger = logging.getLogger(__name__)


def check_migrations(auto_migrate: bool = False, 
                     progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[bool, int, int]:
    """
    Check for pending migrations and optionally run them.
    
    Args:
        auto_migrate: Whether to automatically run pending migrations
        progress_callback: Optional callback function for progress updates
        
    Returns:
        Tuple[bool, int, int]: (has_pending, current_version, pending_count)
    """
    # Create a migrations manager
    migrations_manager = MigrationsManager(progress_callback=progress_callback)
    
    # Get current version
    current_version = migrations_manager.get_current_version()
    logger.info(f"Current database version: {current_version}")
    
    # Get pending migrations
    pending_migrations = migrations_manager.get_pending_migrations()
    pending_count = len(pending_migrations)
    
    if not pending_migrations:
        logger.info("No pending migrations")
        return False, current_version, 0
    
    logger.info(f"Found {pending_count} pending migrations")
    
    if auto_migrate:
        # Run migrations
        success = migrations_manager.run_pending_migrations()
        
        if success:
            new_version = migrations_manager.get_current_version()
            logger.info(f"Migrations completed successfully. New database version: {new_version}")
            return False, new_version, 0
        else:
            logger.error("Migration process failed")
            return True, current_version, pending_count
    
    return True, current_version, pending_count
