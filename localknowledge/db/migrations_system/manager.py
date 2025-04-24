"""
Migrations manager for the LocalKnowledge database.

This module provides a manager class for handling database migrations.
It tracks the current database version and applies migrations in sequence.
"""

import os
import re
import logging
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
import tqdm
from tqdm.gui import tqdm as tqdm_gui

from localknowledge.db.base import DatabaseManager
from .config import get_migrations_dir

# Configure logging
logger = logging.getLogger(__name__)


class MigrationsManager(DatabaseManager):
    """Manager for database migrations."""

    def __init__(self, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """
        Initialize the migrations manager.

        Args:
            progress_callback: Optional callback function for progress updates.
                               Function signature: (current, total, message) -> None
        """
        super().__init__()
        self.progress_callback = progress_callback
        self.migrations_dir = get_migrations_dir()
        self._ensure_version_table()

    def execute_without_timeout(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query without a timeout.

        This method is specifically for migrations that might take a long time to complete.

        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit the transaction

        Returns:
            Query results or None
        """
        import psycopg2
        import psycopg2.extras
        import time

        if not self.connection:
            self.connect()

        # Check if connection is closed and reconnect if needed
        if self.connection.closed:
            logger.warning("Database connection was closed. Reconnecting...")
            self.connect()

        # Disable statement timeout for this connection
        with self.connection.cursor() as timeout_cursor:
            timeout_cursor.execute("SET statement_timeout = 0;")  # 0 means no timeout

        cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        try:
            # Log the query and parameters for debugging
            logger.debug(f"Executing SQL without timeout: {query}")
            logger.debug(f"With parameters: {params}")

            start_time = time.time()
            cursor.execute(query, params or ())
            execution_time = time.time() - start_time
            logger.debug(f"Query executed in {execution_time:.2f} seconds")

            if commit:
                self.connection.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Query affected {cursor.rowcount} rows")
                if cursor.description and query.strip().upper().startswith(('INSERT', 'UPDATE')) and 'RETURNING' in query.upper():
                    # This is an INSERT or UPDATE query with RETURNING clause
                    result = [dict(row) for row in cursor.fetchall()]
                    logger.debug(f"Query returned: {result}")
                    return result
                else:
                    return None
            elif cursor.description:  # This is a SELECT query
                result = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Query returned {len(result)} rows")
                return result
            else:
                return None

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"SQL Error: {e}")
            raise e
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()

    def _ensure_version_table(self) -> None:
        """Create the version table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS version (
            version INTEGER UNIQUE NOT NULL,
            migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            migration_success BOOLEAN NOT NULL
        );
        """
        self.execute(query, commit=True)
        logger.info("Ensured version table exists")

    def get_current_version(self) -> int:
        """
        Get the current database version.

        Returns:
            int: Current database version, or 0 if no migrations have been applied
        """
        query = """
        SELECT MAX(version) as current_version
        FROM version
        WHERE migration_success = TRUE;
        """
        result = self.execute(query)

        if result and result[0]['current_version'] is not None:
            return result[0]['current_version']

        return 0

    def get_available_migrations(self) -> List[Tuple[int, Path]]:
        """
        Get a list of available migration scripts.

        Returns:
            List[Tuple[int, Path]]: List of (version, path) tuples for available migrations
        """
        migrations = []

        # Migration files should be named like: 001_create_tables.py, 002_add_column.py, etc.
        migration_pattern = re.compile(r'^(\d+)_.*\.py$')

        for file_path in self.migrations_dir.glob('*.py'):
            match = migration_pattern.match(file_path.name)
            if match:
                version = int(match.group(1))
                migrations.append((version, file_path))

        # Sort by version number
        migrations.sort(key=lambda x: x[0])

        return migrations

    def get_pending_migrations(self) -> List[Tuple[int, Path]]:
        """
        Get a list of pending migrations.

        Returns:
            List[Tuple[int, Path]]: List of (version, path) tuples for pending migrations
        """
        current_version = self.get_current_version()
        available_migrations = self.get_available_migrations()

        # Filter migrations with version > current_version
        pending_migrations = [
            (version, path) for version, path in available_migrations
            if version > current_version
        ]

        return pending_migrations

    def run_migration(self, version: int, path: Path) -> bool:
        """
        Run a single migration.

        Args:
            version: Migration version number
            path: Path to the migration script

        Returns:
            bool: True if migration was successful, False otherwise
        """
        logger.info(f"Running migration {version}: {path.name}")

        try:
            # Load the migration module
            spec = importlib.util.spec_from_file_location(f"migration_{version}", path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load migration {version}: {path}")
                return False

            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # Run the migration
            if hasattr(migration_module, 'migrate'):
                # Create a progress callback that updates our progress
                def progress_callback(current, total, message=""):
                    if self.progress_callback:
                        self.progress_callback(current, total, f"Migration {version}: {message}")

                # Run the migration with our progress callback
                migration_module.migrate(self, progress_callback)
            else:
                logger.warning(f"Migration {version} does not have a migrate function")

            # Record successful migration
            self._record_migration(version, True)
            logger.info(f"Migration {version} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Record failed migration
            self._record_migration(version, False)
            return False

    def _record_migration(self, version: int, success: bool) -> None:
        """
        Record a migration in the version table.

        Args:
            version: Migration version number
            success: Whether the migration was successful
        """
        # Check if this version already exists
        query = """
        SELECT version FROM version WHERE version = %s;
        """
        result = self.execute(query, (version,))

        if result:
            # Update existing record
            query = """
            UPDATE version
            SET migrated = %s, migration_success = %s
            WHERE version = %s;
            """
            self.execute(query, (datetime.now(), success, version), commit=True)
        else:
            # Insert new record
            query = """
            INSERT INTO version (version, migrated, migration_success)
            VALUES (%s, %s, %s);
            """
            self.execute(query, (version, datetime.now(), success), commit=True)

    def run_pending_migrations(self, use_gui_tqdm: bool = False) -> bool:
        """
        Run all pending migrations.

        Args:
            use_gui_tqdm: Whether to use the GUI version of tqdm for progress display

        Returns:
            bool: True if all migrations were successful, False otherwise
        """
        pending_migrations = self.get_pending_migrations()

        if not pending_migrations:
            logger.info("No pending migrations")
            return True

        logger.info(f"Found {len(pending_migrations)} pending migrations")

        # Choose the appropriate tqdm class
        tqdm_class = tqdm_gui if use_gui_tqdm else tqdm.tqdm

        # Run migrations in order
        success = True
        with tqdm_class(total=len(pending_migrations), desc="Running migrations") as pbar:
            for version, path in pending_migrations:
                pbar.set_description(f"Migration {version}: {path.name}")

                # Run the migration
                if not self.run_migration(version, path):
                    success = False
                    break

                pbar.update(1)

        if success:
            logger.info("All migrations completed successfully")
        else:
            logger.error("Migration process failed")

        return success

    def create_migration_template(self, name: str) -> Path:
        """
        Create a new migration file with a template.

        Args:
            name: Name for the migration (will be used in filename)

        Returns:
            Path: Path to the created migration file
        """
        # Get the next version number
        available_migrations = self.get_available_migrations()
        if available_migrations:
            next_version = max(version for version, _ in available_migrations) + 1
        else:
            next_version = 1

        # Format the version number with leading zeros
        version_str = f"{next_version:03d}"

        # Create a filename with the version and name
        filename = f"{version_str}_{name}.py"
        file_path = self.migrations_dir / filename

        # Create the migration file with a template
        template = f'''"""
Migration {version_str}: {name}

This migration script {name.replace('_', ' ')}.
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
    logger.info("Starting migration {version_str}")

    # TODO: Implement migration logic here

    # Example: Create a new table
    # db_manager.execute("""
    # CREATE TABLE IF NOT EXISTS my_table (
    #     id SERIAL PRIMARY KEY,
    #     name TEXT NOT NULL,
    #     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    # );
    # """, commit=True)

    logger.info("Migration {version_str} completed")
'''

        with open(file_path, 'w') as f:
            f.write(template)

        logger.info(f"Created migration file: {file_path}")
        return file_path
