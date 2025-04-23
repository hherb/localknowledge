#!/usr/bin/env python3
"""
Migration script with checkpoint support to move data from separate tables to the unified document table.

This script will:
1. Create the new document tables if they don't exist (WITHOUT INDICES)
2. Migrate data from the preprints table to the document table
3. Migrate data from the pubmed_articles table to the document table
4. Update embeddings references to point to the new document structure

Features:
- Checkpoint support to resume from last processed record
- Larger batch sizes for better performance
- No indices during migration for maximum speed

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

# Checkpoint file
CHECKPOINT_FILE = 'migration_checkpoint.json'


class DocumentMigration(DatabaseManager):
    """Migration to move data from separate tables to the unified document table with checkpoint support."""

    def __init__(self, dry_run=True, batch_size=10000, start_id=None, end_id=None):
        """Initialize the migration.

        Args:
            dry_run: If True, only print what would be done without making changes
            batch_size: Number of records to process in each batch
            start_id: Starting ID for migration (for resuming)
            end_id: Ending ID for migration (for segmenting)
        """
        super().__init__()
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.start_id = start_id
        self.end_id = end_id
        self.document_db = DocumentDatabaseManager()
        self.medrxiv_db = MedRxivDatabaseManager()
        self.pubmed_db = PubMedDatabaseManager()

        logger.info(f"Migration initialized in {'dry run' if dry_run else 'execution'} mode")
        logger.info(f"Using batch size of {batch_size}")
        if start_id:
            logger.info(f"Starting from ID {start_id}")
        if end_id:
            logger.info(f"Ending at ID {end_id}")

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

    def save_checkpoint(self, source_name, last_id):
        """Save migration checkpoint.

        Args:
            source_name: Name of the source being migrated
            last_id: Last processed ID
        """
        if self.dry_run:
            logger.info(f"Dry run: Would save checkpoint for {source_name} at ID {last_id}")
            return

        import json

        # Load existing checkpoints if any
        checkpoints = {}
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r') as f:
                    checkpoints = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading checkpoint file: {e}")

        # Update checkpoint
        checkpoints[source_name] = last_id

        # Save checkpoint
        try:
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoints, f)
            logger.info(f"Checkpoint saved for {source_name} at ID {last_id}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")

    def load_checkpoint(self, source_name):
        """Load migration checkpoint.

        Args:
            source_name: Name of the source to load checkpoint for

        Returns:
            Last processed ID or None if no checkpoint exists
        """
        import json

        if not os.path.exists(CHECKPOINT_FILE):
            return None

        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoints = json.load(f)

            if source_name in checkpoints:
                last_id = checkpoints[source_name]
                logger.info(f"Loaded checkpoint for {source_name} at ID {last_id}")
                return last_id
        except Exception as e:
            logger.warning(f"Error loading checkpoint file: {e}")

        return None

    def count_preprints(self) -> int:
        """Count the number of preprints to migrate."""
        query = "SELECT COUNT(*) as count FROM preprints"
        if self.start_id is not None:
            query += f" WHERE id >= {self.start_id}"
        if self.end_id is not None:
            query += f" {'AND' if self.start_id is not None else 'WHERE'} id <= {self.end_id}"

        result = self.medrxiv_db.execute(query)
        return result[0]['count'] if result else 0

    def count_pubmed_articles(self) -> int:
        """Count the number of PubMed articles to migrate."""
        query = "SELECT COUNT(*) as count FROM pubmed_articles"
        if self.start_id is not None:
            query += f" WHERE id >= {self.start_id}"
        if self.end_id is not None:
            query += f" {'AND' if self.start_id is not None else 'WHERE'} id <= {self.end_id}"

        result = self.pubmed_db.execute(query)
        return result[0]['count'] if result else 0

    def get_preprints_batch(self, offset: int, last_doi: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get a batch of preprints to migrate.

        Args:
            offset: Offset for pagination
            last_doi: Last processed DOI for resuming

        Returns:
            List of preprint records
        """
        query = f"""
        SELECT * FROM preprints
        WHERE 1=1
        """

        if last_doi is not None:
            query += f" AND doi > '{last_doi}'"
        elif self.start_id is not None:
            # For preprints, we'll interpret start_id as a string prefix for DOI
            query += f" AND doi >= '{self.start_id}'"

        if self.end_id is not None:
            # For preprints, we'll interpret end_id as a string prefix for DOI
            query += f" AND doi <= '{self.end_id}'"

        query += f"""
        ORDER BY doi
        LIMIT {self.batch_size}
        """

        return self.medrxiv_db.execute(query) or []

    def get_pubmed_articles_batch(self, offset: int, last_pmid: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get a batch of PubMed articles to migrate.

        Args:
            offset: Offset for pagination
            last_pmid: Last processed PMID for resuming

        Returns:
            List of PubMed article records
        """
        query = f"""
        SELECT * FROM pubmed_articles
        WHERE 1=1
        """

        if last_pmid is not None:
            query += f" AND pmid > '{last_pmid}'"
        elif self.start_id is not None:
            # For PubMed articles, we'll interpret start_id as a string prefix for PMID
            query += f" AND pmid >= '{self.start_id}'"

        if self.end_id is not None:
            # For PubMed articles, we'll interpret end_id as a string prefix for PMID
            query += f" AND pmid <= '{self.end_id}'"

        query += f"""
        ORDER BY pmid
        LIMIT {self.batch_size}
        """

        return self.pubmed_db.execute(query) or []

    def migrate_preprints(self):
        """Migrate preprints to the document table."""
        logger.info("Migrating preprints to document table")

        # Load checkpoint if any
        last_doi = self.load_checkpoint('preprints')

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
            offset = 0
            while True:
                preprints = self.get_preprints_batch(offset, last_doi)

                if not preprints:
                    break

                batch_last_doi = None

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
                        batch_last_doi = preprint['doi']
                    except Exception as e:
                        logger.error(f"Error migrating preprint {preprint.get('doi')}: {e}")
                        error_count += 1

                    pbar.update(1)

                # Save checkpoint after each batch
                if batch_last_doi is not None:
                    self.save_checkpoint('preprints', batch_last_doi)
                    last_doi = batch_last_doi

                offset += self.batch_size

                # Break if we've migrated all preprints
                if len(preprints) < self.batch_size:
                    break

        logger.info(f"Migrated {migrated_count} preprints with {error_count} errors")

    def migrate_pubmed_articles(self):
        """Migrate PubMed articles to the document table."""
        logger.info("Migrating PubMed articles to document table")

        # Load checkpoint if any
        last_pmid = self.load_checkpoint('pubmed_articles')

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
            offset = 0
            while True:
                articles = self.get_pubmed_articles_batch(offset, last_pmid)

                if not articles:
                    break

                batch_last_pmid = None

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
                        batch_last_pmid = article['pmid']
                    except Exception as e:
                        logger.error(f"Error migrating PubMed article {article.get('pmid')}: {e}")
                        error_count += 1

                    pbar.update(1)

                # Save checkpoint after each batch
                if batch_last_pmid is not None:
                    self.save_checkpoint('pubmed_articles', batch_last_pmid)
                    last_pmid = batch_last_pmid

                offset += self.batch_size

                # Break if we've migrated all articles
                if len(articles) < self.batch_size:
                    break

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
    parser = argparse.ArgumentParser(description='Migrate to unified document table with checkpoint support')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for processing (default: 10000)')
    parser.add_argument('--create-indices', action='store_true', help='Create indices after migration (default: no)')
    parser.add_argument('--start-id', type=int, help='Starting ID for migration (for resuming)')
    parser.add_argument('--end-id', type=int, help='Ending ID for migration (for segmenting)')
    parser.add_argument('--reset-checkpoint', action='store_true', help='Reset checkpoint and start from beginning')
    args = parser.parse_args()

    dry_run = not args.execute
    batch_size = args.batch_size
    start_id = args.start_id
    end_id = args.end_id

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    # Reset checkpoint if requested
    if args.reset_checkpoint and os.path.exists(CHECKPOINT_FILE):
        logger.info("Resetting checkpoint")
        os.remove(CHECKPOINT_FILE)

    migration = DocumentMigration(dry_run=dry_run, batch_size=batch_size, start_id=start_id, end_id=end_id)

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
