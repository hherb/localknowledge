"""
Database functionality for PubMed articles using the unified document table structure.

This module provides database operations specific to PubMed data using the unified
document table structure. It abstracts all SQL statements and provides a clean
interface for other modules to interact with PubMed data.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class PubMedDatabaseManager(DatabaseManager):
    """
    Database manager for PubMed articles using the unified document table.

    This class provides methods for working with PubMed articles stored in the
    unified document table. It does not create any tables or indices, as those
    are handled by the migration system.
    """

    def __init__(self):
        """Initialize the PubMed database manager."""
        super().__init__()
        logger.info("Initializing PubMed database manager")
        self.document_db = DocumentDatabaseManager()
        self.source_id = self._get_pubmed_source_id()

    def _get_pubmed_source_id(self) -> int:
        """
        Get the source ID for PubMed.

        Returns:
            int: Source ID for PubMed
        """
        source_id = self.document_db.get_source_id('pubmed')
        if not source_id:
            logger.error("PubMed source not found in the database")
            raise ValueError("PubMed source not found in the database")
        return source_id


    def store_article(self, article: Dict[str, Any]) -> Optional[int]:
        """
        Store a PubMed article in the unified document table.

        Args:
            article: Dictionary containing article data

        Returns:
            Document ID if successful, None otherwise
        """
        # Convert PubMed article data to document format
        document_data = {
            'source_name': 'pubmed',
            'external_id': article.get('pmid', ''),  # Use PMID as external_id
            'doi': article.get('doi', ''),
            'title': article.get('title', ''),
            'abstract': article.get('abstract', ''),
            'authors': article.get('authors', '').split(', ') if article.get('authors') else [],
            'publication_date': article.get('date_created', ''),
            'publication': article.get('journal', ''),
            'mesh_terms': article.get('mesh_terms', '').split('; ') if article.get('mesh_terms') else [],
            'keywords': article.get('keywords', '').split('; ') if article.get('keywords') else [],
            'url': f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}" if article.get('pmid') else '',
            'pdf_filename': article.get('pdf_path', '')
        }

        try:
            # Use the document database manager to store the document
            document_id = self.document_db.add_document(document_data)
            if document_id:
                logger.debug(f"Stored PubMed article with PMID {article.get('pmid')} as document ID {document_id}")
            else:
                logger.error(f"Failed to store PubMed article with PMID {article.get('pmid')}")
            return document_id
        except Exception as e:
            logger.error(f"Error storing PubMed article: {e}")
            return None

    def store_articles_batch(self, articles: List[Dict[str, Any]]) -> int:
        """
        Store multiple PubMed articles in the unified document table.

        Args:
            articles: List of dictionaries containing article data

        Returns:
            Number of articles successfully stored
        """
        if not articles:
            return 0

        # Process articles one by one using the document database manager
        # This is more reliable than batch processing for complex data structures
        count = 0
        for article in articles:
            try:
                document_id = self.store_article(article)
                if document_id:
                    count += 1
            except Exception as e:
                logger.error(f"Error storing article with PMID {article.get('pmid', 'unknown')}: {e}")
                continue

        return count

    def get_article_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an article by its PMID from the unified document table.

        Args:
            pmid: PubMed ID

        Returns:
            Article data or None if not found
        """
        # Use the document database manager to get the document by external_id
        document = self.document_db.get_document_by_external_id('pubmed', pmid)

        if document:
            return document

        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the PubMed articles in the unified document table.

        Returns:
            Dictionary with statistics
        """
        stats = {}

        # Total articles
        query = "SELECT COUNT(*) AS total FROM document WHERE source_id = %s"
        result = self.execute(query, (self.source_id,))
        stats['total_articles'] = result[0]['total'] if result else 0

        # Articles by year
        query = """
            SELECT EXTRACT(YEAR FROM publication_date) as publication_year, COUNT(*) as count
            FROM document
            WHERE source_id = %s
            GROUP BY publication_year
            ORDER BY publication_year DESC
        """
        result = self.execute(query, (self.source_id,))
        stats['articles_by_year'] = result if result else []

        # Latest import date
        query = "SELECT MAX(added_date) AS latest FROM document WHERE source_id = %s"
        result = self.execute(query, (self.source_id,))
        stats['latest_import'] = result[0]['latest'] if result else None

        return stats
