#!/usr/bin/env python3
"""
Migration script to update QA embeddings references to work with the unified document structure.

This script will:
1. Find all QA embeddings in the database
2. For each QA embedding, find the corresponding document in the new document table
3. Update the QA embedding to reference the new document ID

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
from localknowledge.db.qafinder import QAEmbeddingDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('qaembeddings_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class QAEmbeddingsMigration(DatabaseManager):
    """Migration to update QA embeddings references to work with the unified document structure."""

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
        self.qa_embedding_db = QAEmbeddingDatabaseManager()
        logger.info(f"Migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")

    def count_qaembeddings(self) -> int:
        """Count the number of QA embeddings to update."""
        query = "SELECT COUNT(*) as count FROM qaembeddings"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_qaembeddings_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of QA embeddings to update.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of QA embedding records
        """
        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, model_name
        FROM qaembeddings
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        return self.execute(query) or []

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

    def update_qaembedding_reference(self, embedding_id: int, document_id: int) -> bool:
        """Update a QA embedding to reference the new document ID.
        
        Args:
            embedding_id: QA Embedding ID
            document_id: New document ID
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.debug(f"Dry run: Would update QA embedding {embedding_id} to reference document {document_id}")
            return True
        
        query = """
        UPDATE qaembeddings
        SET document_id = %s
        WHERE id = %s
        """
        
        try:
            self.execute(query, (document_id, embedding_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error updating QA embedding {embedding_id}: {e}")
            return False

    def update_qaembeddings(self):
        """Update all QA embeddings to reference the new document structure."""
        logger.info("Updating QA embeddings references")
        
        # Count total QA embeddings
        total_qaembeddings = self.count_qaembeddings()
        logger.info(f"Found {total_qaembeddings} QA embeddings to update")
        
        if total_qaembeddings == 0:
            logger.info("No QA embeddings to update")
            return
        
        # Process in batches
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        with tqdm.tqdm(total=total_qaembeddings, desc="Updating QA embeddings") as pbar:
            for offset in range(0, total_qaembeddings, self.batch_size):
                qaembeddings = self.get_qaembeddings_batch(offset)
                
                for qaembedding in qaembeddings:
                    try:
                        # Get source name and external ID
                        source_name = qaembedding['source_id']
                        external_id = qaembedding['document_id']
                        
                        # Get new document ID
                        document_id = self.get_document_id(source_name, external_id)
                        
                        if document_id:
                            # Update QA embedding reference
                            success = self.update_qaembedding_reference(qaembedding['id'], document_id)
                            if success:
                                updated_count += 1
                            else:
                                error_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        logger.error(f"Error processing QA embedding {qaembedding.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
        
        logger.info(f"Updated {updated_count} QA embeddings, skipped {skipped_count}, with {error_count} errors")


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Update QA embeddings references')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = QAEmbeddingsMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Update QA embeddings references
        migration.update_qaembeddings()

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
