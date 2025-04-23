"""
Database initialization module for the LocalKnowledge library.

This module is deprecated and will be removed in a future version.
Use create_baseline_db.py for initial database setup and migrations for schema updates.

This module now serves as a compatibility layer that redirects to the new approach.
"""

import logging
import os
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import basic infrastructure module
try:
    from localknowledge.db.basic_infrastructure import (
        check_database_infrastructure,
        DatabaseInfrastructureError
    )
    INFRASTRUCTURE_CHECK_AVAILABLE = True
except ImportError:
    logger.warning("Basic infrastructure module not available. Skipping infrastructure checks.")
    INFRASTRUCTURE_CHECK_AVAILABLE = False

# Import migrations system
try:
    from localknowledge.db.migrations_system import MigrationsManager
    from localknowledge.db.migrations_system.check_migrations import check_migrations
    from localknowledge.db.migrations_system.config import get_migrations_dir
    MIGRATIONS_AVAILABLE = True
except ImportError:
    logger.warning("Migrations system not available. Skipping migrations check.")
    MIGRATIONS_AVAILABLE = False

def create_all_tables() -> None:
    """Create all tables across all database modules.

    This function is deprecated and now redirects to create_baseline_db.py.
    """
    logger.warning(
        "The create_all_tables() function is deprecated. "
        "Use create_baseline_db.py for initial database setup and migrations for schema updates."
    )

    # Check if create_baseline_db.py exists
    try:
        from localknowledge.db.create_baseline_db import BaselineDBCreator

        logger.info("Redirecting to create_baseline_db.py...")
        creator = BaselineDBCreator(force=False)
        creator.create_baseline_database()
        creator.close()
        logger.info("Database initialization complete")
    except ImportError:
        logger.error(
            "create_baseline_db.py not found. "
            "Please run 'python -m localknowledge.db.create_baseline_db' manually."
        )
        raise

def check_database_infrastructure() -> bool:
    """
    Check if the database infrastructure is valid.

    Returns:
        bool: True if infrastructure is valid, False otherwise
    """
    if not INFRASTRUCTURE_CHECK_AVAILABLE:
        logger.warning("Basic infrastructure module not available. Skipping infrastructure checks.")
        return True

    try:
        is_valid, error_message = check_database_infrastructure()
        if not is_valid:
            logger.error(f"Database infrastructure check failed: {error_message}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking database infrastructure: {e}")
        return False


def check_and_run_migrations(auto_migrate: bool = False) -> Tuple[bool, int, int]:
    """
    Check for pending migrations and optionally run them.

    Args:
        auto_migrate: Whether to automatically run pending migrations

    Returns:
        Tuple[bool, int, int]: (has_pending, current_version, pending_count)
    """
    if not MIGRATIONS_AVAILABLE:
        logger.warning("Migrations system not available. Skipping migrations check.")
        return False, 0, 0

    # Copy sample migrations to migrations directory if it's empty
    migrations_dir = get_migrations_dir()
    if not list(migrations_dir.glob('*.py')):
        logger.info("No migrations found. Copying sample migrations...")
        sample_dir = Path(__file__).parent / 'migrations_system' / 'sample_migrations'
        if sample_dir.exists():
            for sample_file in sample_dir.glob('*.py'):
                dest_file = migrations_dir / sample_file.name
                shutil.copy(sample_file, dest_file)
                logger.info(f"Copied sample migration: {dest_file}")

    # Check for pending migrations
    return check_migrations(auto_migrate=auto_migrate)


def main():
    """Main function to execute when run as a script."""
    logger.warning(
        "This script is deprecated. "
        "Use create_baseline_db.py for initial database setup and migrations for schema updates."
    )

    # Check if the database infrastructure is valid
    if not check_database_infrastructure():
        logger.error("Database infrastructure check failed. Please fix the issues and try again.")
        return 1

    # Check for pending migrations
    has_pending, current_version, pending_count = check_and_run_migrations(auto_migrate=False)

    if has_pending:
        logger.warning(f"There are {pending_count} pending migrations. Database is at version {current_version}.")
        logger.warning("Run 'python -m localknowledge.db.migrations_system.run_migrations' to apply them.")
        choice = input("Do you want to run migrations now? [y/N] ")
        if choice.lower() == 'y':
            # Run migrations
            has_pending, current_version, pending_count = check_and_run_migrations(auto_migrate=True)
            if has_pending:
                logger.error("Failed to run all migrations.")
                return 1

    # Ask if the user wants to create the baseline database
    choice = input("Do you want to create/update the baseline database? [y/N] ")
    if choice.lower() == 'y':
        # Create the baseline database
        try:
            create_all_tables()
        except Exception as e:
            logger.error(f"Error creating baseline database: {e}")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())