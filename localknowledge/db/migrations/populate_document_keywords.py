#!/usr/bin/env python3
"""
Migration script to populate document_keywords table from the unified document table.

This script will:
1. Extract keywords from the document table
2. Populate the keywords table with unique keywords
3. Populate the document_keywords table with document-keyword associations

IMPORTANT: This script should be run after the main document migration is complete.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
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
        logging.FileHandler('document_keywords_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class DocumentKeywordsMigration(DatabaseManager):
    """Migration to populate document_keywords table from the unified document table."""

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
        
        logger.info(f"Document keywords migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")

    def count_documents(self) -> int:
        """Count the number of documents to process.
        
        Returns:
            Number of documents
        """
        query = "SELECT COUNT(*) as count FROM document"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_documents_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of documents to process.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of document records
        """
        query = f"""
        SELECT id, keywords, augmented_keywords, mesh_terms
        FROM document
        ORDER BY id
        LIMIT {self.batch_size} OFFSET {offset}
        """
        
        return self.execute(query) or []

    def extract_keywords(self) -> Set[str]:
        """Extract all unique keywords from documents.
        
        Returns:
            Set of unique keywords
        """
        logger.info("Extracting unique keywords from documents")
        
        # Count total documents
        total_documents = self.count_documents()
        logger.info(f"Found {total_documents} documents to process")
        
        if total_documents == 0:
            logger.info("No documents to process")
            return set()
        
        # Process in batches
        all_keywords = set()
        
        with tqdm.tqdm(total=total_documents, desc="Extracting keywords") as pbar:
            offset = 0
            while True:
                documents = self.get_documents_batch(offset)
                
                if not documents:
                    break
                
                for document in documents:
                    # Extract keywords from various fields
                    keywords = document.get('keywords', []) or []
                    augmented_keywords = document.get('augmented_keywords', []) or []
                    mesh_terms = document.get('mesh_terms', []) or []
                    
                    # Add all keywords to the set
                    all_keywords.update(keywords)
                    all_keywords.update(augmented_keywords)
                    all_keywords.update(mesh_terms)
                    
                    pbar.update(1)
                
                offset += self.batch_size
                
                # Break if we've processed all documents
                if len(documents) < self.batch_size:
                    break
        
        logger.info(f"Extracted {len(all_keywords)} unique keywords")
        
        return all_keywords

    def populate_keywords_table(self, keywords: Set[str]):
        """Populate the keywords table with unique keywords.
        
        Args:
            keywords: Set of unique keywords
        """
        logger.info(f"Populating keywords table with {len(keywords)} unique keywords")
        
        if self.dry_run:
            logger.info("Dry run: Would populate keywords table")
            return
        
        # Get existing keywords
        existing_keywords = set()
        query = "SELECT keyword FROM keywords"
        results = self.execute(query)
        
        if results:
            existing_keywords = {row['keyword'] for row in results}
        
        logger.info(f"Found {len(existing_keywords)} existing keywords")
        
        # Filter out existing keywords
        new_keywords = keywords - existing_keywords
        
        logger.info(f"Adding {len(new_keywords)} new keywords")
        
        if not new_keywords:
            logger.info("No new keywords to add")
            return
        
        # Insert new keywords in batches
        batch_size = 1000
        keyword_list = list(new_keywords)
        
        for i in range(0, len(keyword_list), batch_size):
            batch = keyword_list[i:i+batch_size]
            
            # Prepare batch inserts
            inserts = [(keyword,) for keyword in batch]
            
            # Insert into keywords table
            insert_query = """
            INSERT INTO keywords (keyword)
            VALUES (%s)
            ON CONFLICT (keyword) DO NOTHING
            """
            
            try:
                self.execute_many(insert_query, inserts)
                logger.info(f"Inserted {len(batch)} keywords")
            except Exception as e:
                logger.error(f"Error inserting keywords batch: {e}")

    def populate_document_keywords(self):
        """Populate the document_keywords table with document-keyword associations."""
        logger.info("Populating document_keywords table")
        
        # Count total documents
        total_documents = self.count_documents()
        logger.info(f"Found {total_documents} documents to process")
        
        if total_documents == 0:
            logger.info("No documents to process")
            return
        
        # Process in batches
        associations_count = 0
        error_count = 0
        
        with tqdm.tqdm(total=total_documents, desc="Populating document_keywords") as pbar:
            offset = 0
            while True:
                documents = self.get_documents_batch(offset)
                
                if not documents:
                    break
                
                # Prepare batch inserts
                inserts = []
                
                for document in documents:
                    try:
                        doc_id = document['id']
                        
                        # Extract keywords from various fields
                        keywords = document.get('keywords', []) or []
                        augmented_keywords = document.get('augmented_keywords', []) or []
                        mesh_terms = document.get('mesh_terms', []) or []
                        
                        # Combine all keywords
                        all_keywords = set(keywords + augmented_keywords + mesh_terms)
                        
                        # Add document-keyword associations
                        for keyword in all_keywords:
                            if keyword:  # Skip empty keywords
                                inserts.append((doc_id, keyword))
                        
                        associations_count += len(all_keywords)
                    except Exception as e:
                        logger.error(f"Error processing document {document.get('id')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
                
                # Insert into document_keywords table
                if inserts and not self.dry_run:
                    insert_query = """
                    INSERT INTO document_keywords (document_id, keyword)
                    VALUES (%s, %s)
                    ON CONFLICT (document_id, keyword) DO NOTHING
                    """
                    
                    try:
                        self.execute_many(insert_query, inserts)
                        logger.info(f"Inserted {len(inserts)} document-keyword associations")
                    except Exception as e:
                        logger.error(f"Error inserting document-keyword associations batch: {e}")
                
                offset += self.batch_size
                
                # Break if we've processed all documents
                if len(documents) < self.batch_size:
                    break
        
        logger.info(f"Populated document_keywords table with {associations_count} associations")
        logger.info(f"Encountered {error_count} errors")


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Populate document_keywords table from the unified document table')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = DocumentKeywordsMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Extract unique keywords
        keywords = migration.extract_keywords()
        
        # Populate keywords table
        migration.populate_keywords_table(keywords)
        
        # Populate document_keywords table
        migration.populate_document_keywords()

        logger.info("Document keywords migration completed successfully")
    except Exception as e:
        logger.error(f"Document keywords migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        migration.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
