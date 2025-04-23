#!/usr/bin/env python3
"""
Migration script to update embeddings and qaembeddings tables to reference the unified document table.

This script will:
1. Update the embeddings table to reference the document table
2. Update the qaembeddings table to reference the document table

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
        logging.FileHandler('embeddings_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class EmbeddingsMigration(DatabaseManager):
    """Migration to update embeddings and qaembeddings tables to reference the unified document table."""

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
        
        logger.info(f"Embeddings migration initialized in {'dry run' if dry_run else 'execution'} mode")
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

    def count_embeddings(self) -> int:
        """Count the number of embeddings to migrate.
        
        Returns:
            Number of embeddings
        """
        query = "SELECT COUNT(*) as count FROM embeddings"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def count_qaembeddings(self) -> int:
        """Count the number of QA embeddings to migrate.
        
        Returns:
            Number of QA embeddings
        """
        query = "SELECT COUNT(*) as count FROM qaembeddings"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_embeddings_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of embeddings to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of embedding records
        """
        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, text, keywords, embedding, model_name, created_at
        FROM embeddings
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        
        return self.execute(query) or []

    def get_qaembeddings_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of QA embeddings to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of QA embedding records
        """
        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, embedding, model_name, created_at
        FROM qaembeddings
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        
        return self.execute(query) or []

    def update_embeddings_schema(self):
        """Update the embeddings table schema to reference the document table."""
        logger.info("Updating embeddings table schema")
        
        if self.dry_run:
            logger.info("Dry run: Would update embeddings table schema")
            return
        
        # Create a new column for the document ID reference
        try:
            self.execute("ALTER TABLE embeddings ADD COLUMN document_ref_id INTEGER", commit=True)
            logger.info("Added document_ref_id column to embeddings table")
        except Exception as e:
            if "column \"document_ref_id\" of relation \"embeddings\" already exists" in str(e):
                logger.info("document_ref_id column already exists in embeddings table")
            else:
                logger.error(f"Error adding document_ref_id column to embeddings table: {e}")
                raise

    def update_qaembeddings_schema(self):
        """Update the qaembeddings table schema to reference the document table."""
        logger.info("Updating qaembeddings table schema")
        
        if self.dry_run:
            logger.info("Dry run: Would update qaembeddings table schema")
            return
        
        # Create a new column for the document ID reference
        try:
            self.execute("ALTER TABLE qaembeddings ADD COLUMN document_ref_id INTEGER", commit=True)
            logger.info("Added document_ref_id column to qaembeddings table")
        except Exception as e:
            if "column \"document_ref_id\" of relation \"qaembeddings\" already exists" in str(e):
                logger.info("document_ref_id column already exists in qaembeddings table")
            else:
                logger.error(f"Error adding document_ref_id column to qaembeddings table: {e}")
                raise

    def migrate_embeddings(self, id_map: Dict[Tuple[str, str], int]):
        """Migrate embeddings to reference the document table.
        
        Args:
            id_map: Mapping of (source_name, external_id) to document_id
        """
        logger.info("Migrating embeddings to reference document table")
        
        # Count total embeddings
        total_embeddings = self.count_embeddings()
        logger.info(f"Found {total_embeddings} embeddings to migrate")
        
        if total_embeddings == 0:
            logger.info("No embeddings to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        not_found_count = 0
        
        with tqdm.tqdm(total=total_embeddings, desc="Migrating embeddings") as pbar:
            offset = 0
            while True:
                embeddings = self.get_embeddings_batch(offset)
                
                if not embeddings:
                    break
                
                # Prepare batch updates
                updates = []
                
                for embedding in embeddings:
                    try:
                        source_id = embedding['source_id']
                        document_id = embedding['document_id']
                        
                        # Look up document ID in the mapping
                        doc_id = id_map.get((source_id, document_id))
                        
                        if doc_id:
                            updates.append((doc_id, embedding['id']))
                            migrated_count += 1
                        else:
                            not_found_count += 1
                            logger.warning(f"No document found for source_id={source_id}, document_id={document_id}")
                    except Exception as e:
                        logger.error(f"Error processing embedding {embedding.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
                
                # Update the database
                if updates and not self.dry_run:
                    update_query = """
                    UPDATE embeddings
                    SET document_ref_id = %s
                    WHERE id = %s
                    """
                    
                    try:
                        self.execute_many(update_query, updates)
                        logger.info(f"Updated {len(updates)} embeddings")
                    except Exception as e:
                        logger.error(f"Error updating embeddings batch: {e}")
                
                offset += self.batch_size
                
                # Break if we've processed all embeddings
                if len(embeddings) < self.batch_size:
                    break
        
        logger.info(f"Migrated {migrated_count} embeddings with {error_count} errors")
        logger.info(f"Could not find document IDs for {not_found_count} embeddings")

    def migrate_qaembeddings(self, id_map: Dict[Tuple[str, str], int]):
        """Migrate QA embeddings to reference the document table.
        
        Args:
            id_map: Mapping of (source_name, external_id) to document_id
        """
        logger.info("Migrating QA embeddings to reference document table")
        
        # Count total QA embeddings
        total_qaembeddings = self.count_qaembeddings()
        logger.info(f"Found {total_qaembeddings} QA embeddings to migrate")
        
        if total_qaembeddings == 0:
            logger.info("No QA embeddings to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        not_found_count = 0
        
        with tqdm.tqdm(total=total_qaembeddings, desc="Migrating QA embeddings") as pbar:
            offset = 0
            while True:
                qaembeddings = self.get_qaembeddings_batch(offset)
                
                if not qaembeddings:
                    break
                
                # Prepare batch updates
                updates = []
                
                for qaembedding in qaembeddings:
                    try:
                        source_id = qaembedding['source_id']
                        document_id = qaembedding['document_id']
                        
                        # Look up document ID in the mapping
                        doc_id = id_map.get((source_id, document_id))
                        
                        if doc_id:
                            updates.append((doc_id, qaembedding['id']))
                            migrated_count += 1
                        else:
                            not_found_count += 1
                            logger.warning(f"No document found for source_id={source_id}, document_id={document_id}")
                    except Exception as e:
                        logger.error(f"Error processing QA embedding {qaembedding.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
                
                # Update the database
                if updates and not self.dry_run:
                    update_query = """
                    UPDATE qaembeddings
                    SET document_ref_id = %s
                    WHERE id = %s
                    """
                    
                    try:
                        self.execute_many(update_query, updates)
                        logger.info(f"Updated {len(updates)} QA embeddings")
                    except Exception as e:
                        logger.error(f"Error updating QA embeddings batch: {e}")
                
                offset += self.batch_size
                
                # Break if we've processed all QA embeddings
                if len(qaembeddings) < self.batch_size:
                    break
        
        logger.info(f"Migrated {migrated_count} QA embeddings with {error_count} errors")
        logger.info(f"Could not find document IDs for {not_found_count} QA embeddings")

    def create_indices(self):
        """Create indices on the new document_ref_id columns."""
        logger.info("Creating indices on document_ref_id columns")
        
        if self.dry_run:
            logger.info("Dry run: Would create indices on document_ref_id columns")
            return
        
        try:
            self.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_document_ref_id ON embeddings(document_ref_id)", commit=True)
            logger.info("Created index on embeddings.document_ref_id")
        except Exception as e:
            logger.error(f"Error creating index on embeddings.document_ref_id: {e}")
        
        try:
            self.execute("CREATE INDEX IF NOT EXISTS idx_qaembeddings_document_ref_id ON qaembeddings(document_ref_id)", commit=True)
            logger.info("Created index on qaembeddings.document_ref_id")
        except Exception as e:
            logger.error(f"Error creating index on qaembeddings.document_ref_id: {e}")


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Migrate embeddings to reference the unified document table')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = EmbeddingsMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Update table schemas
        migration.update_embeddings_schema()
        migration.update_qaembeddings_schema()

        # Get document ID mapping
        id_map = migration.get_document_id_map()
        
        if not id_map:
            logger.error("No document ID mapping found. Make sure the document migration has completed.")
            return 1

        # Migrate embeddings
        migration.migrate_embeddings(id_map)
        
        # Migrate QA embeddings
        migration.migrate_qaembeddings(id_map)
        
        # Create indices
        migration.create_indices()

        logger.info("Embeddings migration completed successfully")
    except Exception as e:
        logger.error(f"Embeddings migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        migration.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
