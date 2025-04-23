#!/usr/bin/env python3
"""
Migration script to update summaries table to reference the unified document table.

This script will:
1. Update the summaries table schema to reference the document table
2. Migrate summaries to reference the document table

IMPORTANT: This script should be run after the main document migration is complete.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import tqdm
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('summaries_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class SummariesMigration(DatabaseManager):
    """Migration to update summaries table to reference the unified document table."""

    def __init__(self, dry_run=True, batch_size=1000):
        """Initialize the migration.
        
        Args:
            dry_run: If True, only print what would be done without making changes
            batch_size: Number of records to process in each batch
        """
        super().__init__()
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.document_db = DocumentDatabaseManager()
        
        logger.info(f"Summaries migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")

    def get_document_id_map(self) -> Dict[Tuple[str, str], int]:
        """Get a mapping of (source_name, external_id) to document_id.
        
        Returns:
            Dictionary mapping (source_name, external_id) to document_id
        """
        logger.info("Building document ID mapping")
        
        query = """
        SELECT d.id, s.name AS source_name, d.external_id
        FROM document d
        JOIN sources s ON d.source_id = s.id
        """
        
        results = self.execute(query)
        
        if not results:
            logger.error("No documents found in the document table")
            return {}
        
        # Build mapping of (source_name, external_id) to document_id
        id_map = {(row['source_name'], row['external_id']): row['id'] for row in results}
        
        logger.info(f"Built mapping for {len(id_map)} documents")
        
        return id_map

    def count_summaries(self) -> int:
        """Count the number of summaries to migrate.
        
        Returns:
            Number of summaries
        """
        query = "SELECT COUNT(*) as count FROM summaries"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_summaries_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of summaries to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of summary records
        """
        query = f"""
        SELECT id, publication_id, summary, evaluation, reason, interests, created_at
        FROM summaries
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        
        return self.execute(query) or []

    def update_summaries_schema(self):
        """Update the summaries table schema to reference the document table."""
        logger.info("Updating summaries table schema")
        
        if self.dry_run:
            logger.info("Dry run: Would update summaries table schema")
            return
        
        # Create a new column for the document ID reference
        try:
            self.execute("ALTER TABLE summaries ADD COLUMN document_id INTEGER", commit=True)
            logger.info("Added document_id column to summaries table")
        except Exception as e:
            if "column \"document_id\" of relation \"summaries\" already exists" in str(e):
                logger.info("document_id column already exists in summaries table")
            else:
                logger.error(f"Error adding document_id column to summaries table: {e}")
                raise

    def migrate_summaries(self, id_map: Dict[Tuple[str, str], int]):
        """Migrate summaries to reference the document table.
        
        Args:
            id_map: Mapping of (source_name, external_id) to document_id
        """
        logger.info("Migrating summaries to reference document table")
        
        # Count total summaries
        total_summaries = self.count_summaries()
        logger.info(f"Found {total_summaries} summaries to migrate")
        
        if total_summaries == 0:
            logger.info("No summaries to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        not_found_count = 0
        
        with tqdm.tqdm(total=total_summaries, desc="Migrating summaries") as pbar:
            offset = 0
            while True:
                summaries = self.get_summaries_batch(offset)
                
                if not summaries:
                    break
                
                # Prepare batch updates
                updates = []
                
                for summary in summaries:
                    try:
                        publication_id = summary['publication_id']
                        
                        # Look up document ID in the mapping (assuming medrxiv as source)
                        doc_id = id_map.get(('medrxiv', publication_id))
                        
                        if doc_id:
                            updates.append((doc_id, summary['id']))
                            migrated_count += 1
                        else:
                            not_found_count += 1
                            logger.warning(f"No document found for publication_id={publication_id}")
                    except Exception as e:
                        logger.error(f"Error processing summary {summary.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
                
                # Update the database
                if updates and not self.dry_run:
                    update_query = """
                    UPDATE summaries
                    SET document_id = %s
                    WHERE id = %s
                    """
                    
                    try:
                        self.execute_many(update_query, updates)
                        logger.info(f"Updated {len(updates)} summaries")
                    except Exception as e:
                        logger.error(f"Error updating summaries batch: {e}")
                
                offset += self.batch_size
                
                # Break if we've processed all summaries
                if len(summaries) < self.batch_size:
                    break
        
        logger.info(f"Migrated {migrated_count} summaries with {error_count} errors")
        logger.info(f"Could not find document IDs for {not_found_count} summaries")

    def create_indices(self):
        """Create indices on the new document_id column."""
        logger.info("Creating indices on document_id column")
        
        if self.dry_run:
            logger.info("Dry run: Would create indices on document_id column")
            return
        
        try:
            self.execute("CREATE INDEX IF NOT EXISTS idx_summaries_document_id ON summaries(document_id)", commit=True)
            logger.info("Created index on summaries.document_id")
        except Exception as e:
            logger.error(f"Error creating index on summaries.document_id: {e}")

    def update_foreign_key(self):
        """Update the foreign key constraint to reference the document table."""
        logger.info("Updating foreign key constraint")
        
        if self.dry_run:
            logger.info("Dry run: Would update foreign key constraint")
            return
        
        try:
            # First, drop the existing foreign key constraint
            self.execute("""
            ALTER TABLE summaries
            DROP CONSTRAINT IF EXISTS summaries_publication_id_fkey
            """, commit=True)
            logger.info("Dropped existing foreign key constraint")
            
            # Add new foreign key constraint
            self.execute("""
            ALTER TABLE summaries
            ADD CONSTRAINT summaries_document_id_fkey
            FOREIGN KEY (document_id)
            REFERENCES document(id)
            ON DELETE CASCADE
            """, commit=True)
            logger.info("Added new foreign key constraint")
        except Exception as e:
            logger.error(f"Error updating foreign key constraint: {e}")
            raise


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Migrate summaries to reference the unified document table')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = SummariesMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Update table schema
        migration.update_summaries_schema()

        # Get document ID mapping
        id_map = migration.get_document_id_map()
        
        if not id_map:
            logger.error("No document ID mapping found. Make sure the document migration has completed.")
            return 1

        # Migrate summaries
        migration.migrate_summaries(id_map)
        
        # Create indices
        migration.create_indices()
        
        # Update foreign key constraint
        migration.update_foreign_key()

        logger.info("Summaries migration completed successfully")
    except Exception as e:
        logger.error(f"Summaries migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        migration.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
