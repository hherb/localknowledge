#!/usr/bin/env python3
"""
Migration script to update reading_records table to reference the unified document table.

This script will:
1. Update the reading_records table schema to reference the document table
2. Migrate reading_records to reference the document table

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
        logging.FileHandler('reading_records_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class ReadingRecordsMigration(DatabaseManager):
    """Migration to update reading_records table to reference the unified document table."""

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
        
        logger.info(f"Reading records migration initialized in {'dry run' if dry_run else 'execution'} mode")
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

    def count_reading_records(self) -> int:
        """Count the number of reading records to migrate.
        
        Returns:
            Number of reading records
        """
        query = "SELECT COUNT(*) as count FROM reading_records"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_reading_records_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of reading records to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of reading record records
        """
        query = f"""
        SELECT id, source_type, content_id, user_id, read_timestamp, rating, notes
        FROM reading_records
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        
        return self.execute(query) or []

    def update_reading_records_schema(self):
        """Update the reading_records table schema to reference the document table."""
        logger.info("Updating reading_records table schema")
        
        if self.dry_run:
            logger.info("Dry run: Would update reading_records table schema")
            return
        
        # Create a new column for the document ID reference
        try:
            self.execute("ALTER TABLE reading_records ADD COLUMN document_id INTEGER", commit=True)
            logger.info("Added document_id column to reading_records table")
        except Exception as e:
            if "column \"document_id\" of relation \"reading_records\" already exists" in str(e):
                logger.info("document_id column already exists in reading_records table")
            else:
                logger.error(f"Error adding document_id column to reading_records table: {e}")
                raise

    def migrate_reading_records(self, id_map: Dict[Tuple[str, str], int]):
        """Migrate reading records to reference the document table.
        
        Args:
            id_map: Mapping of (source_name, external_id) to document_id
        """
        logger.info("Migrating reading records to reference document table")
        
        # Count total reading records
        total_records = self.count_reading_records()
        logger.info(f"Found {total_records} reading records to migrate")
        
        if total_records == 0:
            logger.info("No reading records to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        not_found_count = 0
        
        with tqdm.tqdm(total=total_records, desc="Migrating reading records") as pbar:
            offset = 0
            while True:
                records = self.get_reading_records_batch(offset)
                
                if not records:
                    break
                
                # Prepare batch updates
                updates = []
                
                for record in records:
                    try:
                        source_type = record['source_type']
                        content_id = record['content_id']
                        
                        # Map source_type to source_name
                        source_name = None
                        if source_type == 'medrxiv':
                            source_name = 'medrxiv'
                        elif source_type == 'pubmed':
                            source_name = 'pubmed'
                        else:
                            logger.warning(f"Unknown source type: {source_type}")
                            continue
                        
                        # Look up document ID in the mapping
                        doc_id = id_map.get((source_name, content_id))
                        
                        if doc_id:
                            updates.append((doc_id, record['id']))
                            migrated_count += 1
                        else:
                            not_found_count += 1
                            logger.warning(f"No document found for source_type={source_type}, content_id={content_id}")
                    except Exception as e:
                        logger.error(f"Error processing reading record {record.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
                
                # Update the database
                if updates and not self.dry_run:
                    update_query = """
                    UPDATE reading_records
                    SET document_id = %s
                    WHERE id = %s
                    """
                    
                    try:
                        self.execute_many(update_query, updates)
                        logger.info(f"Updated {len(updates)} reading records")
                    except Exception as e:
                        logger.error(f"Error updating reading records batch: {e}")
                
                offset += self.batch_size
                
                # Break if we've processed all reading records
                if len(records) < self.batch_size:
                    break
        
        logger.info(f"Migrated {migrated_count} reading records with {error_count} errors")
        logger.info(f"Could not find document IDs for {not_found_count} reading records")

    def create_indices(self):
        """Create indices on the new document_id column."""
        logger.info("Creating indices on document_id column")
        
        if self.dry_run:
            logger.info("Dry run: Would create indices on document_id column")
            return
        
        try:
            self.execute("CREATE INDEX IF NOT EXISTS idx_reading_records_document_id ON reading_records(document_id)", commit=True)
            logger.info("Created index on reading_records.document_id")
        except Exception as e:
            logger.error(f"Error creating index on reading_records.document_id: {e}")

    def add_foreign_key(self):
        """Add a foreign key constraint to reference the document table."""
        logger.info("Adding foreign key constraint")
        
        if self.dry_run:
            logger.info("Dry run: Would add foreign key constraint")
            return
        
        try:
            # Add new foreign key constraint
            self.execute("""
            ALTER TABLE reading_records
            ADD CONSTRAINT reading_records_document_id_fkey
            FOREIGN KEY (document_id)
            REFERENCES document(id)
            ON DELETE CASCADE
            """, commit=True)
            logger.info("Added foreign key constraint")
        except Exception as e:
            if "constraint \"reading_records_document_id_fkey\" for relation \"reading_records\" already exists" in str(e):
                logger.info("Foreign key constraint already exists")
            else:
                logger.error(f"Error adding foreign key constraint: {e}")
                raise


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Migrate reading records to reference the unified document table')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = ReadingRecordsMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Update table schema
        migration.update_reading_records_schema()

        # Get document ID mapping
        id_map = migration.get_document_id_map()
        
        if not id_map:
            logger.error("No document ID mapping found. Make sure the document migration has completed.")
            return 1

        # Migrate reading records
        migration.migrate_reading_records(id_map)
        
        # Create indices
        migration.create_indices()
        
        # Add foreign key constraint
        migration.add_foreign_key()

        logger.info("Reading records migration completed successfully")
    except Exception as e:
        logger.error(f"Reading records migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        migration.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
