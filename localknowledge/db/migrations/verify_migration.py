#!/usr/bin/env python3
"""
Script to verify the migration to the unified document structure.

This script will:
1. Count the number of records in the original tables
2. Count the number of records in the new document table
3. Compare the counts to ensure all records were migrated
4. Perform sample checks on random records to ensure data integrity
"""

import argparse
import logging
import sys
import os
import random
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('migration_verification.log')
    ]
)
logger = logging.getLogger(__name__)


class MigrationVerifier(DatabaseManager):
    """Verifier for the migration to the unified document structure."""

    def __init__(self):
        """Initialize the verifier."""
        super().__init__()
        self.document_db = DocumentDatabaseManager()
        self.medrxiv_db = MedRxivDatabaseManager()
        self.pubmed_db = PubMedDatabaseManager()

    def verify_counts(self) -> bool:
        """
        Verify that the counts match between the original tables and the new document table.
        
        Returns:
            True if counts match, False otherwise
        """
        logger.info("Verifying record counts")
        
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
        
        # Check if counts match
        preprints_match = preprints_count == medrxiv_docs_count
        pubmed_match = pubmed_count == pubmed_docs_count
        
        if preprints_match:
            logger.info("✓ Preprints count matches")
        else:
            logger.warning(f"✗ Preprints count mismatch: {preprints_count} vs {medrxiv_docs_count}")
        
        if pubmed_match:
            logger.info("✓ PubMed articles count matches")
        else:
            logger.warning(f"✗ PubMed articles count mismatch: {pubmed_count} vs {pubmed_docs_count}")
        
        return preprints_match and pubmed_match

    def verify_sample_records(self, sample_size: int = 10) -> bool:
        """
        Verify a sample of records to ensure data integrity.
        
        Args:
            sample_size: Number of records to sample from each source
            
        Returns:
            True if all sampled records match, False otherwise
        """
        logger.info(f"Verifying {sample_size} sample records from each source")
        
        # Verify preprints
        preprints_match = self._verify_sample_preprints(sample_size)
        
        # Verify PubMed articles
        pubmed_match = self._verify_sample_pubmed_articles(sample_size)
        
        return preprints_match and pubmed_match

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

    def _get_random_preprint_dois(self, count: int) -> List[str]:
        """
        Get a list of random preprint DOIs.
        
        Args:
            count: Number of DOIs to retrieve
            
        Returns:
            List of DOIs
        """
        query = f"""
        SELECT doi
        FROM preprints
        ORDER BY RANDOM()
        LIMIT {count}
        """
        result = self.medrxiv_db.execute(query)
        return [row['doi'] for row in result] if result else []

    def _get_random_pubmed_pmids(self, count: int) -> List[str]:
        """
        Get a list of random PubMed PMIDs.
        
        Args:
            count: Number of PMIDs to retrieve
            
        Returns:
            List of PMIDs
        """
        query = f"""
        SELECT pmid
        FROM pubmed_articles
        ORDER BY RANDOM()
        LIMIT {count}
        """
        result = self.pubmed_db.execute(query)
        return [row['pmid'] for row in result] if result else []

    def _verify_sample_preprints(self, count: int) -> bool:
        """
        Verify a sample of preprints to ensure data integrity.
        
        Args:
            count: Number of preprints to sample
            
        Returns:
            True if all sampled preprints match, False otherwise
        """
        # Get random DOIs
        dois = self._get_random_preprint_dois(count)
        if not dois:
            logger.warning("No preprints found to sample")
            return False
        
        logger.info(f"Sampled {len(dois)} preprints")
        
        # Check each DOI
        match_count = 0
        for doi in dois:
            # Get original preprint
            original_query = "SELECT * FROM preprints WHERE doi = %s"
            original_result = self.medrxiv_db.execute(original_query, (doi,))
            if not original_result:
                logger.warning(f"Original preprint not found for DOI: {doi}")
                continue
            original = original_result[0]
            
            # Get migrated document
            migrated = self.document_db.get_document_by_external_id('medrxiv', doi)
            if not migrated:
                logger.warning(f"Migrated document not found for DOI: {doi}")
                continue
            
            # Compare fields
            fields_match = (
                original['title'] == migrated['title'] and
                original['abstract'] == migrated['abstract'] and
                original['doi'] == migrated['external_id']
            )
            
            if fields_match:
                match_count += 1
                logger.debug(f"✓ Preprint {doi} matches")
            else:
                logger.warning(f"✗ Preprint {doi} does not match")
        
        match_percentage = (match_count / len(dois)) * 100 if dois else 0
        logger.info(f"Preprints match: {match_count}/{len(dois)} ({match_percentage:.2f}%)")
        
        return match_count == len(dois)

    def _verify_sample_pubmed_articles(self, count: int) -> bool:
        """
        Verify a sample of PubMed articles to ensure data integrity.
        
        Args:
            count: Number of articles to sample
            
        Returns:
            True if all sampled articles match, False otherwise
        """
        # Get random PMIDs
        pmids = self._get_random_pubmed_pmids(count)
        if not pmids:
            logger.warning("No PubMed articles found to sample")
            return False
        
        logger.info(f"Sampled {len(pmids)} PubMed articles")
        
        # Check each PMID
        match_count = 0
        for pmid in pmids:
            # Get original article
            original_query = "SELECT * FROM pubmed_articles WHERE pmid = %s"
            original_result = self.pubmed_db.execute(original_query, (pmid,))
            if not original_result:
                logger.warning(f"Original article not found for PMID: {pmid}")
                continue
            original = original_result[0]
            
            # Get migrated document
            migrated = self.document_db.get_document_by_external_id('pubmed', pmid)
            if not migrated:
                logger.warning(f"Migrated document not found for PMID: {pmid}")
                continue
            
            # Compare fields
            fields_match = (
                original['title'] == migrated['title'] and
                (original['abstract'] == migrated['abstract'] or 
                 (original['abstract'] is None and migrated['abstract'] is None)) and
                original['pmid'] == migrated['external_id']
            )
            
            if fields_match:
                match_count += 1
                logger.debug(f"✓ PubMed article {pmid} matches")
            else:
                logger.warning(f"✗ PubMed article {pmid} does not match")
        
        match_percentage = (match_count / len(pmids)) * 100 if pmids else 0
        logger.info(f"PubMed articles match: {match_count}/{len(pmids)} ({match_percentage:.2f}%)")
        
        return match_count == len(pmids)


def main():
    """Run the verification."""
    parser = argparse.ArgumentParser(description='Verify migration to unified document table')
    parser.add_argument('--sample-size', type=int, default=10, help='Number of records to sample from each source (default: 10)')
    args = parser.parse_args()

    verifier = MigrationVerifier()

    try:
        # Verify counts
        counts_match = verifier.verify_counts()
        
        # Verify sample records
        samples_match = verifier.verify_sample_records(args.sample_size)
        
        # Overall result
        if counts_match and samples_match:
            logger.info("✓ Migration verification successful")
            return 0
        else:
            logger.warning("✗ Migration verification failed")
            return 1
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        verifier.close()


if __name__ == "__main__":
    sys.exit(main())
