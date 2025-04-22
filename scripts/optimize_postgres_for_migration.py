#!/usr/bin/env python3
"""
Script to optimize PostgreSQL settings for high-performance data migration.

This script:
1. Sets PostgreSQL parameters for optimal bulk loading performance
2. Drops indices from the document table if they exist
3. Optionally disables foreign key constraints

Usage:
    python optimize_postgres_for_migration.py --execute

After migration is complete, run:
    python optimize_postgres_for_migration.py --restore
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PostgresOptimizer(DatabaseManager):
    """Optimize PostgreSQL for high-performance data migration."""

    def __init__(self):
        """Initialize the optimizer."""
        super().__init__()
        self.document_db = DocumentDatabaseManager()

    def execute_alter_system(self, query):
        """Execute ALTER SYSTEM command outside of a transaction."""
        # Close existing connection if any
        if self.connection:
            self.connection.close()
            self.connection = None

        # Create a new connection with autocommit
        import psycopg2
        import os

        # Get connection parameters from environment variables
        dbname = os.environ.get('POSTGRES_DB')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')

        if not dbname:
            raise ValueError("POSTGRES_DB environment variable must be set")

        # Create connection with autocommit
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True  # Important: autocommit mode for ALTER SYSTEM

        try:
            cursor = conn.cursor()
            cursor.execute(query)
            cursor.close()
        finally:
            conn.close()

        # Reconnect with our standard connection
        self.connect()

    def optimize_for_migration(self):
        """Set PostgreSQL parameters for optimal bulk loading performance."""
        logger.info("Optimizing PostgreSQL for migration")

        # Memory-related parameters
        self.execute_alter_system("ALTER SYSTEM SET shared_buffers = '40GB'")
        self.execute_alter_system("ALTER SYSTEM SET work_mem = '1GB'")
        self.execute_alter_system("ALTER SYSTEM SET maintenance_work_mem = '8GB'")
        self.execute_alter_system("ALTER SYSTEM SET effective_cache_size = '80GB'")
        self.execute_alter_system("ALTER SYSTEM SET temp_buffers = '1GB'")

        # Write performance parameters
        self.execute_alter_system("ALTER SYSTEM SET wal_buffers = '64MB'")
        self.execute_alter_system("ALTER SYSTEM SET checkpoint_timeout = '1h'")
        self.execute_alter_system("ALTER SYSTEM SET max_wal_size = '32GB'")
        self.execute_alter_system("ALTER SYSTEM SET checkpoint_completion_target = 0.9")

        # Background writer and autovacuum
        self.execute_alter_system("ALTER SYSTEM SET autovacuum = off")
        self.execute_alter_system("ALTER SYSTEM SET bgwriter_delay = '10s'")
        self.execute_alter_system("ALTER SYSTEM SET bgwriter_lru_maxpages = 1000")

        # Parallel query settings
        self.execute_alter_system("ALTER SYSTEM SET max_parallel_workers_per_gather = 4")
        self.execute_alter_system("ALTER SYSTEM SET max_parallel_workers = 8")
        self.execute_alter_system("ALTER SYSTEM SET max_parallel_maintenance_workers = 4")

        # Transaction and logging settings
        self.execute_alter_system("ALTER SYSTEM SET wal_level = 'minimal'")
        self.execute_alter_system("ALTER SYSTEM SET archive_mode = off")
        self.execute_alter_system("ALTER SYSTEM SET synchronous_commit = off")
        self.execute_alter_system("ALTER SYSTEM SET commit_delay = 1000")
        self.execute_alter_system("ALTER SYSTEM SET commit_siblings = 5")

        # Apply changes
        self.execute_alter_system("SELECT pg_reload_conf()")

        logger.info("PostgreSQL optimized for migration")

    def restore_normal_settings(self):
        """Restore normal PostgreSQL settings after migration."""
        logger.info("Restoring normal PostgreSQL settings")

        # Reset memory-related parameters
        self.execute_alter_system("ALTER SYSTEM RESET shared_buffers")
        self.execute_alter_system("ALTER SYSTEM RESET work_mem")
        self.execute_alter_system("ALTER SYSTEM RESET maintenance_work_mem")
        self.execute_alter_system("ALTER SYSTEM RESET effective_cache_size")
        self.execute_alter_system("ALTER SYSTEM RESET temp_buffers")

        # Reset write performance parameters
        self.execute_alter_system("ALTER SYSTEM RESET wal_buffers")
        self.execute_alter_system("ALTER SYSTEM RESET checkpoint_timeout")
        self.execute_alter_system("ALTER SYSTEM RESET max_wal_size")
        self.execute_alter_system("ALTER SYSTEM RESET checkpoint_completion_target")

        # Reset background writer and autovacuum
        self.execute_alter_system("ALTER SYSTEM RESET autovacuum")
        self.execute_alter_system("ALTER SYSTEM RESET bgwriter_delay")
        self.execute_alter_system("ALTER SYSTEM RESET bgwriter_lru_maxpages")

        # Reset parallel query settings
        self.execute_alter_system("ALTER SYSTEM RESET max_parallel_workers_per_gather")
        self.execute_alter_system("ALTER SYSTEM RESET max_parallel_workers")
        self.execute_alter_system("ALTER SYSTEM RESET max_parallel_maintenance_workers")

        # Reset transaction and logging settings
        self.execute_alter_system("ALTER SYSTEM RESET wal_level")
        self.execute_alter_system("ALTER SYSTEM RESET archive_mode")
        self.execute_alter_system("ALTER SYSTEM RESET synchronous_commit")
        self.execute_alter_system("ALTER SYSTEM RESET commit_delay")
        self.execute_alter_system("ALTER SYSTEM RESET commit_siblings")

        # Apply changes
        self.execute_alter_system("SELECT pg_reload_conf()")

        logger.info("Normal PostgreSQL settings restored")

    def drop_indices(self):
        """Drop indices from the document table."""
        logger.info("Dropping indices from document table")
        self.document_db.drop_indices()
        logger.info("Indices dropped")

    def create_indices(self):
        """Create indices for the document table."""
        logger.info("Creating indices for document table")
        self.document_db.create_indices()
        logger.info("Indices created")

    def disable_foreign_key_constraints(self):
        """Disable foreign key constraints for faster loading."""
        logger.info("Disabling foreign key constraints")
        self.execute("SET session_replication_role = 'replica'", commit=True)
        logger.info("Foreign key constraints disabled")

    def enable_foreign_key_constraints(self):
        """Re-enable foreign key constraints."""
        logger.info("Re-enabling foreign key constraints")
        self.execute("SET session_replication_role = 'origin'", commit=True)
        logger.info("Foreign key constraints enabled")

    def analyze_tables(self):
        """Run ANALYZE to update statistics."""
        logger.info("Running ANALYZE on document table")
        self.execute("ANALYZE document", commit=True)
        logger.info("ANALYZE complete")


def main():
    """Run the optimizer."""
    parser = argparse.ArgumentParser(description='Optimize PostgreSQL for migration')
    parser.add_argument('--execute', action='store_true', help='Optimize PostgreSQL for migration')
    parser.add_argument('--restore', action='store_true', help='Restore normal PostgreSQL settings')
    parser.add_argument('--drop-indices', action='store_true', help='Drop indices from document table')
    parser.add_argument('--create-indices', action='store_true', help='Create indices for document table')
    parser.add_argument('--disable-fk', action='store_true', help='Disable foreign key constraints')
    parser.add_argument('--enable-fk', action='store_true', help='Enable foreign key constraints')
    parser.add_argument('--analyze', action='store_true', help='Run ANALYZE on document table')
    args = parser.parse_args()

    optimizer = PostgresOptimizer()

    try:
        if args.execute:
            optimizer.optimize_for_migration()

        if args.restore:
            optimizer.restore_normal_settings()

        if args.drop_indices:
            optimizer.drop_indices()

        if args.create_indices:
            optimizer.create_indices()

        if args.disable_fk:
            optimizer.disable_foreign_key_constraints()

        if args.enable_fk:
            optimizer.enable_foreign_key_constraints()

        if args.analyze:
            optimizer.analyze_tables()

        if not any([args.execute, args.restore, args.drop_indices, args.create_indices,
                   args.disable_fk, args.enable_fk, args.analyze]):
            logger.info("No action specified. Use --help for usage information.")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        optimizer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
