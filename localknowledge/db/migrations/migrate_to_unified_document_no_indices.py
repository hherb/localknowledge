#!/usr/bin/env python3
"""
Migration script to move data from separate tables to the unified document table.

This script will:
1. Create the new document tables if they don't exist (WITHOUT INDICES)
2. Migrate data from the preprints table to the document table
3. Migrate data from the pubmed_articles table to the document table
4. Update embeddings references to point to the new document structure

IMPORTANT: This script should be run with caution on a production database.
Always backup your database before running migrations.

This is a modified version that skips index creation for faster migration.
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
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.pubmed import PubMedDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('document_migration.log')
    ]
)
logger = logging.getLogger(__name__)


class DocumentMigration(DatabaseManager):
    """Migration to move data from separate tables to the unified document table."""

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
        self.medrxiv_db = MedRxivDatabaseManager()
        self.pubmed_db = PubMedDatabaseManager()
        logger.info(f"Migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")

    def setup_tables(self):
        """Create the document tables if they don't exist (WITHOUT INDICES)."""
        logger.info("Setting up document tables (without indices)")
        if not self.dry_run:
            # Only create tables, skip indices
            self.document_db.create_tables()
            logger.info("Tables created without indices for faster migration")
        else:
            logger.info("Dry run: Would create document tables (without indices)")

    def create_indices_after_migration(self):
        """Create indices after migration is complete."""
        logger.info("Creating indices after migration")
        if not self.dry_run:
            self.document_db.create_indices()
        else:
            logger.info("Dry run: Would create indices after migration")

    def count_preprints(self) -> int:
        """Count the number of preprints to migrate."""
        query = "SELECT COUNT(*) as count FROM preprints"
        result = self.medrxiv_db.execute(query)
        return result[0]['count'] if result else 0

    def count_pubmed_articles(self) -> int:
        """Count the number of PubMed articles to migrate."""
        query = "SELECT COUNT(*) as count FROM pubmed_articles"
        result = self.pubmed_db.execute(query)
        return result[0]['count'] if result else 0

    def get_preprints_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of preprints to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of preprint records
        """
        query = f"""
        SELECT * FROM preprints
        ORDER BY doi
        LIMIT {self.batch_size} OFFSET {offset}
        """
        return self.medrxiv_db.execute(query) or []

    def get_pubmed_articles_batch(self, offset: int) -> List[Dict[str, Any]]:
        """Get a batch of PubMed articles to migrate.
        
        Args:
            offset: Offset for pagination
            
        Returns:
            List of PubMed article records
        """
        query = f"""
        SELECT * FROM pubmed_articles
        ORDER BY pmid
        LIMIT {self.batch_size} OFFSET {offset}
        """
        return self.pubmed_db.execute(query) or []

    def migrate_preprints(self):
        """Migrate preprints to the document table."""
        logger.info("Migrating preprints to document table")
        
        # Count total preprints
        total_preprints = self.count_preprints()
        logger.info(f"Found {total_preprints} preprints to migrate")
        
        if total_preprints == 0:
            logger.info("No preprints to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        
        with tqdm.tqdm(total=total_preprints, desc="Migrating preprints") as pbar:
            for offset in range(0, total_preprints, self.batch_size):
                preprints = self.get_preprints_batch(offset)
                
                for preprint in preprints:
                    try:
                        # Convert preprint to document format
                        document_data = {
                            'source_name': 'medrxiv',
                            'external_id': preprint['doi'],
                            'doi': preprint['doi'],
                            'title': preprint['title'],
                            'abstract': preprint['abstract'],
                            'category_name': preprint['category'],
                            'authors': self._parse_authors(preprint['authors']),
                            'publication_date': self._parse_date(preprint['date_posted']),
                            'pdf_url': preprint['pdf_url'],
                            'pdf_filename': preprint['local_pdf_path'],
                            'full_text': preprint['full_text']
                        }
                        
                        if not self.dry_run:
                            self.document_db.add_document(document_data)
                        
                        migrated_count += 1
                    except Exception as e:
                        logger.error(f"Error migrating preprint {preprint.get('doi')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
        
        logger.info(f"Migrated {migrated_count} preprints with {error_count} errors")

    def migrate_pubmed_articles(self):
        """Migrate PubMed articles to the document table."""
        logger.info("Migrating PubMed articles to document table")
        
        # Count total articles
        total_articles = self.count_pubmed_articles()
        logger.info(f"Found {total_articles} PubMed articles to migrate")
        
        if total_articles == 0:
            logger.info("No PubMed articles to migrate")
            return
        
        # Process in batches
        migrated_count = 0
        error_count = 0
        
        with tqdm.tqdm(total=total_articles, desc="Migrating PubMed articles") as pbar:
            for offset in range(0, total_articles, self.batch_size):
                articles = self.get_pubmed_articles_batch(offset)
                
                for article in articles:
                    try:
                        # Convert article to document format
                        document_data = {
                            'source_name': 'pubmed',
                            'external_id': article['pmid'],
                            'doi': article['doi'],
                            'title': article['title'],
                            'abstract': article['abstract'],
                            'mesh_terms': self._parse_mesh_terms(article['mesh_terms']),
                            'keywords': self._parse_keywords(article['keywords']),
                            'authors': self._parse_authors(article['authors']),
                            'publication': article['journal'],
                            'publication_date': self._parse_year_to_date(article['publication_year']),
                            'pdf_filename': article['pdf_path']
                        }
                        
                        if not self.dry_run:
                            self.document_db.add_document(document_data)
                        
                        migrated_count += 1
                    except Exception as e:
                        logger.error(f"Error migrating PubMed article {article.get('pmid')}: {e}")
                        error_count += 1
                    
                    pbar.update(1)
        
        logger.info(f"Migrated {migrated_count} PubMed articles with {error_count} errors")

    def update_embeddings_references(self):
        """Update embeddings to reference the new document structure."""
        logger.info("Updating embeddings references")
        
        if self.dry_run:
            logger.info("Dry run: Would update embeddings references")
            return
        
        # This is a complex operation that depends on how embeddings are stored
        # For now, we'll just log that this would be done
        # In a real implementation, you would:
        # 1. Get all embeddings
        # 2. For each embedding, find the corresponding document in the new table
        # 3. Update the embedding to reference the new document
        
        logger.info("Embeddings references would be updated here")
        logger.info("This is a placeholder for the actual implementation")

    def _parse_authors(self, authors_str: Optional[str]) -> Optional[List[str]]:
        """Parse authors string into a list of authors.
        
        Args:
            authors_str: Authors string
            
        Returns:
            List of authors or None
        """
        if not authors_str:
            return None
        
        # Different formats might be used in different tables
        # This is a simple implementation that handles comma-separated authors
        return [author.strip() for author in authors_str.split(',')]

    def _parse_mesh_terms(self, mesh_terms_str: Optional[str]) -> Optional[List[str]]:
        """Parse MeSH terms string into a list of terms.
        
        Args:
            mesh_terms_str: MeSH terms string
            
        Returns:
            List of MeSH terms or None
        """
        if not mesh_terms_str:
            return None
        
        return [term.strip() for term in mesh_terms_str.split(';')]

    def _parse_keywords(self, keywords_str: Optional[str]) -> Optional[List[str]]:
        """Parse keywords string into a list of keywords.
        
        Args:
            keywords_str: Keywords string
            
        Returns:
            List of keywords or None
        """
        if not keywords_str:
            return None
        
        return [keyword.strip() for keyword in keywords_str.split(';')]

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse date string into a date.
        
        Args:
            date_str: Date string
            
        Returns:
            Date string in ISO format or None
        """
        if not date_str:
            return None
        
        try:
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # If no format matches, try to extract year
            if date_str.isdigit() and len(date_str) == 4:
                return f"{date_str}-01-01"
            
            return None
        except Exception:
            return None

    def _parse_year_to_date(self, year_str: Optional[str]) -> Optional[str]:
        """Convert year to date.
        
        Args:
            year_str: Year string
            
        Returns:
            Date string in ISO format or None
        """
        if not year_str:
            return None
        
        try:
            # Extract year if it's embedded in a string
            year = ''.join(c for c in year_str if c.isdigit())
            if year and len(year) == 4:
                return f"{year}-01-01"
            return None
        except Exception:
            return None


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(description='Migrate to unified document table (without indices)')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    parser.add_argument('--create-indices', action='store_true', help='Create indices after migration (default: no)')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    migration = DocumentMigration(dry_run=dry_run, batch_size=batch_size)

    try:
        # Setup tables (without indices)
        migration.setup_tables()

        # Migrate data
        migration.migrate_preprints()
        migration.migrate_pubmed_articles()

        # Update embeddings references
        migration.update_embeddings_references()

        # Create indices if requested
        if args.create_indices:
            logger.info("Creating indices after migration (as requested)")
            migration.create_indices_after_migration()
        else:
            logger.info("Skipping index creation as requested")
            logger.info("You should create indices manually after migration is complete")

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
