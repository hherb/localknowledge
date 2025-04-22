#!/usr/bin/env python3
"""
Migration script to update embeddings references to work with the unified document structure.

This script will:
1. Find all embeddings in the database (both regular and multiembeddings)
2. For each embedding, find the corresponding document in the new document table
3. Update the embedding to reference the new document ID
4. Update multiembeddings tables to use the new document IDs

IMPORTANT: This script should be run with caution on a production database.
Always backup your database before running migrations.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import tqdm

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.embeddings.database import EmbeddingDatabaseManager
from localknowledge.db.multiembeddings import EmbeddingTableManager

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
    """Migration to update embeddings references to work with the unified document structure."""

    def __init__(self, dry_run=True, batch_size=100):
        """Initialize the migration.

        Args:
            dry_run: If True, only print what would be done without making changes
            batch_size: Number of records to process in each batch
        """
        super().__init__()
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.document_db = DocumentDatabaseManager()
        self.embedding_db = EmbeddingDatabaseManager()
        self.multi_embedding_db = EmbeddingTableManager()
        logger.info(f"Migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")

    def count_embeddings(self) -> int:
        """Count the number of embeddings to update."""
        query = "SELECT COUNT(*) as count FROM embeddings"
        result = self.embedding_db.execute(query)
        return result[0]['count'] if result else 0

    def get_embeddings_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of embeddings to update.

        Args:
            offset: Offset for pagination

        Returns:
            List of embedding records
        """
        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, text, model_name
        FROM embeddings
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        return self.embedding_db.execute(query) or []

    def get_document_id(self, source_name: str, external_id: str) -> Optional[int]:
        """Get the document ID for a source and external ID.

        Args:
            source_name: Source name (e.g., 'pubmed', 'medrxiv')
            external_id: External ID (e.g., DOI, PMID)

        Returns:
            Document ID or None if not found
        """
        # Get source ID
        source_id_query = "SELECT id FROM sources WHERE name = %s"
        source_result = self.execute(source_id_query, (source_name,))
        if not source_result:
            logger.warning(f"Source '{source_name}' not found")
            return None

        source_id = source_result[0]['id']

        # Get document ID
        document_query = "SELECT id FROM document WHERE source_id = %s AND external_id = %s"
        document_result = self.execute(document_query, (source_id, external_id))
        if not document_result:
            logger.warning(f"Document not found for {source_name}/{external_id}")
            return None

        return document_result[0]['id']

    def update_embedding_reference(self, embedding_id: int, document_id: int) -> bool:
        """Update an embedding to reference the new document ID.

        Args:
            embedding_id: Embedding ID
            document_id: New document ID

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.debug(f"Dry run: Would update embedding {embedding_id} to reference document {document_id}")
            return True

        query = """
        UPDATE embeddings
        SET document_id = %s
        WHERE id = %s
        """

        try:
            self.execute(query, (document_id, embedding_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error updating embedding {embedding_id}: {e}")
            return False

    def get_multiembedding_tables(self) -> List[str]:
        """Get a list of all multiembedding tables.

        Returns:
            List of table names
        """
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'emb_%'
        """
        result = self.execute(query)
        return [row['table_name'] for row in result] if result else []

    def count_multiembeddings(self, table_name: str) -> int:
        """Count the number of embeddings in a multiembedding table.

        Args:
            table_name: Name of the multiembedding table

        Returns:
            Number of embeddings in the table
        """
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_multiembeddings_batch(self, table_name: str, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of embeddings from a multiembedding table.

        Args:
            table_name: Name of the multiembedding table
            offset: Offset for pagination

        Returns:
            List of embedding records
        """
        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, text
        FROM {table_name}
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        return self.execute(query) or []

    def update_multiembedding_reference(self, table_name: str, embedding_id: int, document_id: int) -> bool:
        """Update a multiembedding to reference the new document ID.

        Args:
            table_name: Name of the multiembedding table
            embedding_id: Embedding ID
            document_id: New document ID

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.debug(f"Dry run: Would update multiembedding {embedding_id} in {table_name} to reference document {document_id}")
            return True

        query = f"""
        UPDATE {table_name}
        SET document_id = %s
        WHERE id = %s
        """

        try:
            self.execute(query, (document_id, embedding_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error updating multiembedding {embedding_id} in {table_name}: {e}")
            return False

    def update_embeddings(self):
        """Update all embeddings to reference the new document structure."""
        logger.info("Updating regular embeddings references")

        # Count total embeddings
        total_embeddings = self.count_embeddings()
        logger.info(f"Found {total_embeddings} regular embeddings to update")

        if total_embeddings > 0:
            # Process in batches
            updated_count = 0
            skipped_count = 0
            error_count = 0

            with tqdm.tqdm(total=total_embeddings, desc="Updating regular embeddings") as pbar:
                for offset in range(0, total_embeddings, self.batch_size):
                    embeddings = self.get_embeddings_batch(offset)

                    for embedding in embeddings:
                        try:
                            # Get source name and external ID
                            source_name = embedding['source_id']
                            external_id = embedding['document_id']

                            # Get new document ID
                            document_id = self.get_document_id(source_name, external_id)

                            if document_id:
                                # Update embedding reference
                                success = self.update_embedding_reference(embedding['id'], document_id)
                                if success:
                                    updated_count += 1
                                else:
                                    error_count += 1
                            else:
                                skipped_count += 1
                        except Exception as e:
                            logger.error(f"Error processing embedding {embedding.get('id')}: {e}")
                            error_count += 1

                        pbar.update(1)

            logger.info(f"Updated {updated_count} regular embeddings, skipped {skipped_count}, with {error_count} errors")
        else:
            logger.info("No regular embeddings to update")

        # Now update multiembeddings tables
        logger.info("Updating multiembeddings references")

        # Get all multiembedding tables
        tables = self.get_multiembedding_tables()
        logger.info(f"Found {len(tables)} multiembedding tables: {', '.join(tables)}")

        if not tables:
            logger.info("No multiembedding tables found")
            return

        # Process each table
        for table_name in tables:
            logger.info(f"Processing table {table_name}")

            # Count embeddings in this table
            total_multiembeddings = self.count_multiembeddings(table_name)
            logger.info(f"Found {total_multiembeddings} embeddings in {table_name}")

            if total_multiembeddings == 0:
                logger.info(f"No embeddings to update in {table_name}")
                continue

            # Process in batches
            updated_count = 0
            skipped_count = 0
            error_count = 0

            with tqdm.tqdm(total=total_multiembeddings, desc=f"Updating {table_name}") as pbar:
                for offset in range(0, total_multiembeddings, self.batch_size):
                    embeddings = self.get_multiembeddings_batch(table_name, offset)

                    for embedding in embeddings:
                        try:
                            # Get source name and external ID
                            source_name = embedding['source_id']
                            external_id = embedding['document_id']

                            # Get new document ID
                            document_id = self.get_document_id(source_name, external_id)

                            if document_id:
                                # Update embedding reference
                                success = self.update_multiembedding_reference(table_name, embedding['id'], document_id)
                                if success:
                                    updated_count += 1
                                else:
                                    error_count += 1
                            else:
                                skipped_count += 1
                        except Exception as e:
                            logger.error(f"Error processing multiembedding {embedding.get('id')} in {table_name}: {e}")
                            error_count += 1

                        pbar.update(1)

            logger.info(f"Updated {updated_count} embeddings in {table_name}, skipped {skipped_count}, with {error_count} errors")


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Update embeddings references')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = EmbeddingsMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Update embeddings references
        migration.update_embeddings()

        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        migration.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
