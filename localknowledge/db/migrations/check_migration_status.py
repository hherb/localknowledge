#!/usr/bin/env python3
"""
Script to check the status of the migration to the unified document structure.

This script will:
1. Count the number of records in the original tables
2. Count the number of records in the new document table
3. Compare the counts to show migration progress
"""

import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.pubmed import PubMedDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationStatusChecker(DatabaseManager):
    """Check the status of the migration to the unified document structure."""

    def __init__(self):
        """Initialize the checker."""
        super().__init__()
        self.document_db = DocumentDatabaseManager()
        self.medrxiv_db = MedRxivDatabaseManager()
        self.pubmed_db = PubMedDatabaseManager()

    def check_status(self):
        """Check the status of the migration."""
        # Count preprints
        preprints_count = self._count_preprints()
        logger.info(f"Found {preprints_count} preprints in original table")
        
        # Count PubMed articles
        pubmed_count = self._count_pubmed_articles()
        logger.info(f"Found {pubmed_count} PubMed articles in original table")
        
        # Count documents by source
        medrxiv_docs_count = self._count_documents_by_source('medrxiv')
        logger.info(f"Found {medrxiv_docs_count} medrxiv documents in new table")
        
        pubmed_docs_count = self._count_documents_by_source('pubmed')
        logger.info(f"Found {pubmed_docs_count} pubmed documents in new table")
        
        # Calculate progress
        total_original = preprints_count + pubmed_count
        total_migrated = medrxiv_docs_count + pubmed_docs_count
        
        if total_original > 0:
            progress_percentage = (total_migrated / total_original) * 100
            logger.info(f"Migration progress: {progress_percentage:.2f}% ({total_migrated}/{total_original})")
        else:
            logger.info("No records found in original tables")
        
        # Check embeddings migration
        self._check_embeddings_migration()

    def _count_preprints(self) -> int:
        """Count the number of preprints in the original table."""
        query = "SELECT COUNT(*) as count FROM preprints"
        result = self.medrxiv_db.execute(query)
        return result[0]['count'] if result else 0

    def _count_pubmed_articles(self) -> int:
        """Count the number of PubMed articles in the original table."""
        query = "SELECT COUNT(*) as count FROM pubmed_articles"
        result = self.pubmed_db.execute(query)
        return result[0]['count'] if result else 0

    def _count_documents_by_source(self, source_name: str) -> int:
        """
        Count the number of documents in the new table by source.
        
        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            
        Returns:
            Number of documents for the specified source
        """
        query = """
        SELECT COUNT(*) as count
        FROM document d
        JOIN sources s ON d.source_id = s.id
        WHERE s.name = %s
        """
        result = self.document_db.execute(query, (source_name,))
        return result[0]['count'] if result else 0

    def _check_embeddings_migration(self):
        """Check the status of the embeddings migration."""
        # Check if document_embeddings table exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'document_embeddings'
        ) as exists
        """
        result = self.execute(check_query)
        
        if not result or not result[0]['exists']:
            logger.info("Document embeddings table does not exist yet")
            return
        
        # Count embeddings in the new table
        count_query = "SELECT COUNT(*) as count FROM document_embeddings"
        result = self.execute(count_query)
        embeddings_count = result[0]['count'] if result else 0
        
        logger.info(f"Found {embeddings_count} embeddings in the new document_embeddings table")
        
        # Count embeddings by type
        type_query = """
        SELECT embedding_type, COUNT(*) as count
        FROM document_embeddings
        GROUP BY embedding_type
        ORDER BY count DESC
        """
        result = self.execute(type_query)
        
        if result:
            logger.info("Embeddings by type:")
            for row in result:
                logger.info(f"  {row['embedding_type']}: {row['count']}")
        
        # Count embeddings by model
        model_query = """
        SELECT model_name, COUNT(*) as count
        FROM document_embeddings
        GROUP BY model_name
        ORDER BY count DESC
        """
        result = self.execute(model_query)
        
        if result:
            logger.info("Embeddings by model:")
            for row in result:
                logger.info(f"  {row['model_name']}: {row['count']}")


def main():
    """Run the status check."""
    checker = MigrationStatusChecker()
    try:
        checker.check_status()
    finally:
        checker.close()


if __name__ == "__main__":
    main()
