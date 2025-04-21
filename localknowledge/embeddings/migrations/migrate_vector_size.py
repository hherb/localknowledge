#!/usr/bin/env python3
"""
Migration script to safely change the vector size in the embeddings table.

This script will:
1. Check if the embeddings table exists
2. Check if there are any non-null embeddings in the table
3. Only if there are no embeddings, alter the table to change the vector size
4. If there are embeddings, provide instructions for a more complex migration

IMPORTANT: This script should be run with caution on a production database.
Always backup your database before running migrations.
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the localknowledge package
parent_dir = str(Path(__file__).resolve().parents[3])
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from localknowledge.db.base import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VectorSizeMigration(DatabaseManager):
    """Migration to change the vector size in the embeddings table."""

    def __init__(self, dry_run=True):
        """Initialize the migration.
        
        Args:
            dry_run: If True, only print what would be done without making changes
        """
        super().__init__()
        self.dry_run = dry_run
        logger.info(f"Migration initialized in {'dry run' if dry_run else 'execution'} mode")

    def check_table_exists(self):
        """Check if the embeddings table exists."""
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'embeddings'
        );
        """
        result = self.execute(query)
        exists = result[0]['exists'] if result else False
        logger.info(f"Embeddings table exists: {exists}")
        return exists

    def check_embeddings_exist(self):
        """Check if there are any non-null embeddings in the table."""
        query = """
        SELECT COUNT(*) as count FROM embeddings 
        WHERE embedding IS NOT NULL;
        """
        result = self.execute(query)
        count = result[0]['count'] if result else 0
        logger.info(f"Number of non-null embeddings: {count}")
        return count > 0

    def get_current_vector_size(self):
        """Get the current vector size of the embedding column."""
        query = """
        SELECT atttypmod - 4 as vector_size
        FROM pg_attribute
        WHERE attrelid = 'embeddings'::regclass
        AND attname = 'embedding';
        """
        result = self.execute(query)
        vector_size = result[0]['vector_size'] if result else None
        logger.info(f"Current vector size: {vector_size}")
        return vector_size

    def migrate_vector_size(self, new_size=1024):
        """Migrate the vector size in the embeddings table.
        
        Args:
            new_size: The new vector size to set
            
        Returns:
            True if migration was successful, False otherwise
        """
        # Check if table exists
        if not self.check_table_exists():
            logger.error("Embeddings table does not exist. Migration aborted.")
            return False

        # Get current vector size
        current_size = self.get_current_vector_size()
        if current_size == new_size:
            logger.info(f"Vector size is already {new_size}. No migration needed.")
            return True

        # Check if there are any embeddings
        if self.check_embeddings_exist():
            logger.error(
                "Non-null embeddings exist in the table. "
                "This migration script cannot safely change the vector size "
                "without potentially losing data. "
                "Please use a more complex migration strategy:"
                "\n1. Create a new table with the desired vector size"
                "\n2. Copy the data from the old table to the new table, transforming embeddings as needed"
                "\n3. Rename the tables to swap them"
            )
            return False

        # If no embeddings exist, we can safely alter the table
        if not self.dry_run:
            try:
                # Create a transaction
                self.execute("BEGIN;")
                
                # Alter the table to change the vector size
                query = f"""
                ALTER TABLE embeddings 
                ALTER COLUMN embedding TYPE vector({new_size});
                """
                self.execute(query)
                
                # Commit the transaction
                self.execute("COMMIT;")
                
                logger.info(f"Successfully changed vector size to {new_size}")
                return True
            except Exception as e:
                # Rollback the transaction in case of error
                self.execute("ROLLBACK;")
                logger.error(f"Error during migration: {e}")
                return False
        else:
            logger.info(f"Dry run: Would change vector size from {current_size} to {new_size}")
            return True


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Migrate the vector size in the embeddings table')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--size', type=int, default=1024, help='New vector size (default: 1024)')
    args = parser.parse_args()

    dry_run = not args.execute
    new_size = args.size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = VectorSizeMigration(dry_run=dry_run)
    success = migration.migrate_vector_size(new_size=new_size)
    
    if success:
        logger.info("Migration completed successfully")
        return 0
    else:
        logger.error("Migration failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
