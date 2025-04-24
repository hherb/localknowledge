"""
MedRxiv database functionality for the LocalKnowledge library.

This module provides database operations specific to medRxiv data using the unified
document table structure. It abstracts all SQL statements and provides a clean
interface for other modules to interact with medRxiv data.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class MedRxivDatabaseManager(DatabaseManager):
    """
    Database manager for medRxiv preprints using the unified document table.

    This class provides methods for working with medRxiv preprints stored in the
    unified document table. It does not create any tables or indices, as those
    are handled by the migration system.
    """

    def __init__(self):
        """Initialize the medRxiv database manager."""
        super().__init__()
        self.document_db = DocumentDatabaseManager()
        self.source_id = self._get_medrxiv_source_id()

    def _get_medrxiv_source_id(self) -> int:
        """
        Get the source ID for medRxiv.

        Returns:
            int: Source ID for medRxiv
        """
        source_id = self.document_db.get_source_id('medrxiv')
        if not source_id:
            logger.error("MedRxiv source not found in the database")
            raise ValueError("MedRxiv source not found in the database")
        return source_id

    def store_preprint(self, preprint: Dict[str, Any]) -> Optional[int]:
        """
        Store a preprint in the unified document table.

        Args:
            preprint: Dictionary containing preprint data

        Returns:
            Document ID if successful, None otherwise
        """
        # Convert preprint data to document format
        document_data = {
            'source_name': 'medrxiv',
            'external_id': preprint.get('doi', ''),  # Use DOI as external_id
            'doi': preprint.get('doi', ''),
            'title': preprint.get('title', ''),
            'abstract': preprint.get('abstract', ''),
            'authors': preprint.get('authors', '').split(', ') if preprint.get('authors') else [],
            'publication_date': preprint.get('date_posted', ''),
            'category_name': preprint.get('category', ''),
            'url': f"https://www.medrxiv.org/content/{preprint.get('doi')}" if preprint.get('doi') else '',
            'pdf_url': preprint.get('pdf_url', ''),
            'pdf_filename': preprint.get('local_pdf_path', ''),
            'full_text': preprint.get('full_text', '')
        }

        try:
            # Use the document database manager to store the document
            document_id = self.document_db.add_document(document_data)
            if document_id:
                logger.debug(f"Stored preprint with DOI {preprint.get('doi')} as document ID {document_id}")
            else:
                logger.error(f"Failed to store preprint with DOI {preprint.get('doi')}")
            return document_id
        except Exception as e:
            logger.error(f"Error storing preprint: {e}")
            return None

    def store_preprints(self, preprints: List[Dict[str, Any]]) -> int:
        """
        Store multiple preprints in the unified document table.

        Args:
            preprints: List of dictionaries containing preprint data

        Returns:
            Number of preprints successfully stored
        """
        if not preprints:
            return 0

        # Process preprints one by one using the document database manager
        # This is more reliable than batch processing for complex data structures
        count = 0
        for preprint in preprints:
            try:
                document_id = self.store_preprint(preprint)
                if document_id:
                    count += 1
            except Exception as e:
                logger.error(f"Error storing preprint with DOI {preprint.get('doi', 'unknown')}: {e}")
                continue

        return count

    def get_preprint_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a preprint by its DOI from the unified document table.

        Args:
            doi: Digital Object Identifier

        Returns:
            Preprint data or None if not found
        """
        # Use the document database manager to get the document by DOI
        document = self.document_db.get_document_by_doi(doi)

        # Check if the document is from the medrxiv source
        if document and document.get('source_name') == 'medrxiv':
            return document

        return None

    def search_preprints(self,
                         search_text: str,
                         fields: List[str] = None,
                         max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search for medRxiv preprints in the unified document table.

        Args:
            search_text: Search query string
            fields: List of fields to search in (default: title and abstract)
            max_results: Maximum number of results to return

        Returns:
            List of matching preprints
        """
        # Use the document database's search_documents method with source filter
        results = self.document_db.search_documents(
            search_text=search_text,
            source_name='medrxiv',
            limit=max_results,
            offset=0
        )

        return results

    def get_latest_date(self) -> Optional[str]:
        """
        Get the latest publication date for medRxiv preprints in the database.

        Returns:
            Latest date in YYYY-MM-DD format or None if database is empty
        """
        query = """
        SELECT publication_date
        FROM document
        WHERE source_id = %s
        ORDER BY publication_date DESC
        LIMIT 1
        """

        result = self.execute(query, (self.source_id,))

        if result and result[0]['publication_date']:
            # Get the date part if it contains time
            date_str = str(result[0]['publication_date'])
            return date_str.split()[0] if ' ' in date_str else date_str
        return None

    def get_resume_date(self, days_back: int = 1) -> Optional[str]:
        """
        Get the date from which to resume data collection, accounting for
        potentially partial updates by going back a few days.

        Args:
            days_back: Number of days to go back from the latest date

        Returns:
            Date string in YYYY-MM-DD format or None if no data
        """
        latest_date = self.get_latest_date()
        if not latest_date:
            return None

        try:
            date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
            resume_date = date_obj - timedelta(days=days_back)
            return resume_date.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Error parsing date: {e}")
            return None

    def get_preprints_without_pdfs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get medRxiv preprints without downloaded PDFs from the unified document table.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of preprints without downloaded PDFs
        """
        query = """
        SELECT d.id, d.doi, d.title, d.publication_date, c.name as category, d.pdf_url
        FROM document d
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.source_id = %s
        AND (d.pdf_filename = '' OR d.pdf_filename IS NULL)
        ORDER BY d.publication_date DESC
        """

        params = [self.source_id]

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        return self.execute(query, tuple(params)) or []

    def update_pdf_path(self, doi: str, pdf_path: str, full_text: str = "") -> bool:
        """
        Update the PDF path and full text for a medRxiv preprint in the unified document table.

        Args:
            doi: Digital Object Identifier
            pdf_path: Path to the PDF file (filename only)
            full_text: Full text extracted from the PDF

        Returns:
            True if successful, False otherwise
        """
        query = """
        UPDATE document
        SET pdf_filename = %s, full_text = %s, updated_date = CURRENT_TIMESTAMP
        WHERE source_id = %s AND doi = %s
        """

        try:
            self.execute(query, (pdf_path, full_text, self.source_id, doi), commit=True)
            logger.debug(f"Updated PDF path for document with DOI {doi}")
            return True
        except Exception as e:
            logger.error(f"Error updating PDF path: {e}")
            return False

    def update_full_text(self, doi: str, full_text: str) -> bool:
        """
        Update just the full_text field for a medRxiv preprint in the unified document table.

        Args:
            doi: Digital Object Identifier of the preprint
            full_text: Full text content in markdown format

        Returns:
            bool: True if update was successful, False otherwise
        """
        query = """
        UPDATE document
        SET full_text = %s, updated_date = CURRENT_TIMESTAMP
        WHERE source_id = %s AND doi = %s
        """

        try:
            self.execute(query, (full_text, self.source_id, doi), commit=True)
            logger.debug(f"Updated full text for document with DOI {doi}")
            return True
        except Exception as e:
            logger.error(f"Error updating full text for {doi}: {e}")
            return False

    # Summary-related methods

    def store_summary(self, publication_id: str, summary_data: Dict[str, Any]) -> Optional[int]:
        """
        Store a summary for a medRxiv preprint in the unified document structure.

        Args:
            publication_id: DOI of the preprint
            summary_data: Dictionary containing summary data with keys:
                          summary, evaluation, reason, interests

        Returns:
            ID of the created/updated summary or None if failed
        """
        try:
            # Get the document ID for this DOI
            document = self.get_preprint_by_doi(publication_id)
            if not document:
                logger.error(f"Cannot store summary for non-existent publication: {publication_id}")
                return None

            document_id = document['id']

            # Check if summary already exists for this document
            query = "SELECT id FROM summaries WHERE document_id = %s"
            existing = self.execute(query, (document_id,))

            if existing:
                # Update existing summary
                query = """
                UPDATE summaries
                SET summary = %s, evaluation = %s, reason = %s, interests = %s, created_at = CURRENT_TIMESTAMP
                WHERE document_id = %s
                RETURNING id
                """
                params = (
                    summary_data.get('response', ''),
                    summary_data.get('evaluation', False),
                    summary_data.get('reason', ''),
                    summary_data.get('interests', []),
                    document_id
                )
                result = self.execute(query, params, commit=True)
                logger.debug(f"Updated summary for document ID {document_id}")
                return result[0]['id'] if result else None
            else:
                # Create new summary
                query = """
                INSERT INTO summaries (document_id, summary, evaluation, reason, interests)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """
                params = (
                    document_id,
                    summary_data.get('response', ''),
                    summary_data.get('evaluation', False),
                    summary_data.get('reason', ''),
                    summary_data.get('interests', []),
                )
                result = self.execute(query, params, commit=True)
                logger.debug(f"Created new summary for document ID {document_id}")
                return result[0]['id'] if result else None
        except Exception as e:
            logger.error(f"Error storing summary: {e}")
            return None

    def get_summary_by_id(self, summary_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a summary by its ID.

        Args:
            summary_id: Summary ID

        Returns:
            Summary data or None if not found
        """
        query = "SELECT * FROM summaries WHERE id = %s"
        results = self.execute(query, (summary_id,))

        if results and len(results) > 0:
            return results[0]
        return None

    def get_summary_by_publication(self, publication_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the summary for a specific publication using the unified document structure.

        Args:
            publication_id: DOI of the preprint

        Returns:
            Summary data or None if not found
        """
        # First get the document ID for this DOI
        document = self.get_preprint_by_doi(publication_id)
        if not document:
            logger.debug(f"No document found with DOI {publication_id}")
            return None

        document_id = document['id']

        # Now get the summary for this document
        query = "SELECT * FROM summaries WHERE document_id = %s"
        results = self.execute(query, (document_id,))

        if results and len(results) > 0:
            return results[0]
        return None

    def get_preprints_without_summaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get medRxiv preprints that don't have summaries yet using the unified document structure.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of preprints without summaries
        """
        query = """
        SELECT d.id, d.doi, d.title, d.abstract, d.publication_date, c.name as category
        FROM document d
        LEFT JOIN categories c ON d.category_id = c.id
        LEFT JOIN summaries s ON d.id = s.document_id
        WHERE d.source_id = %s
        AND s.id IS NULL
        ORDER BY d.publication_date DESC
        """

        params = [self.source_id]

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        return self.execute(query, tuple(params)) or []

    def get_summaries_by_interests(self, interests: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get summaries that match any of the given interests using the unified document structure.

        Args:
            interests: List of interest strings
            limit: Maximum number of results to return

        Returns:
            List of summaries matching the interests
        """
        if not interests:
            return []

        query = """
        SELECT s.*, d.title, d.abstract, d.authors, d.publication_date, c.name as category
        FROM summaries s
        JOIN document d ON s.document_id = d.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.source_id = %s
        AND s.interests && %s
        ORDER BY d.publication_date DESC
        """

        params = [self.source_id, interests]

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        return self.execute(query, tuple(params)) or []

    def delete_summary(self, summary_id: int) -> bool:
        """
        Delete a summary.

        Args:
            summary_id: Summary ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM summaries WHERE id = %s", (summary_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting summary: {e}")
            return False

    def get_preprints_without_fulltext(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get medRxiv preprints without fulltext content using the unified document structure.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of preprints without fulltext
        """
        query = """
        SELECT d.id, d.doi, d.title
        FROM document d
        WHERE d.source_id = %s
        AND (d.full_text IS NULL OR d.full_text = '')
        ORDER BY d.publication_date DESC
        """

        params = [self.source_id]

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        return self.execute(query, tuple(params)) or []

    def count_preprints_without_fulltext(self) -> int:
        """
        Count the number of medRxiv preprints without fulltext using the unified document structure.

        Returns:
            Number of preprints without fulltext
        """
        query = """
        SELECT COUNT(*) as count
        FROM document
        WHERE source_id = %s
        AND (full_text IS NULL OR full_text = '')
        """

        results = self.execute(query, (self.source_id,))

        if results and len(results) > 0:
            return results[0]['count']
        return 0

    def get_recent_preprints_without_fulltext(self, days_back: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent medRxiv preprints that don't have full text content using the unified document structure.

        Args:
            days_back: Number of days to look back
            limit: Maximum number of results to return

        Returns:
            List of preprints without full text
        """
        # Calculate the date 'days_back' days ago
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        query = """
        SELECT d.*, c.name as category_name
        FROM document d
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.source_id = %s
        AND (d.full_text IS NULL OR d.full_text = '')
        AND d.publication_date >= %s
        ORDER BY d.publication_date DESC
        LIMIT %s
        """

        try:
            results = self.execute(query, (self.source_id, cutoff_date, limit))
            return results or []
        except Exception as e:
            logger.error(f"Error retrieving recent preprints without full text: {e}")
            return []
