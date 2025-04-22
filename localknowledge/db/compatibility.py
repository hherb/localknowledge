"""
Compatibility layer for existing database managers to use the new document structure.

This module provides adapter functions that allow existing code to continue working
with the new unified document structure. It serves as a bridge during the transition
period until all code can be updated to use the new structure directly.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class MedRxivCompatibilityAdapter:
    """Adapter for MedRxiv database operations to use the unified document structure."""

    def __init__(self):
        """Initialize the adapter."""
        self.document_db = DocumentDatabaseManager()

    def get_preprint_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Get a preprint by DOI using the unified document structure.

        Args:
            doi: Preprint DOI

        Returns:
            Preprint data in the original format or None if not found
        """
        document = self.document_db.get_document_by_external_id('medrxiv', doi)
        if not document:
            return None

        # Convert to original format
        return {
            'doi': document['external_id'],
            'title': document['title'],
            'abstract': document['abstract'],
            'authors': self._format_authors(document['authors']),
            'date_posted': self._format_date(document['publication_date']),
            'category': document.get('category_name', ''),
            'pdf_url': document.get('pdf_url', ''),
            'local_pdf_path': document.get('pdf_filename', ''),
            'full_text': document.get('full_text', '')
        }

    def get_recent_preprints(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get recent preprints using the unified document structure.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of preprints in the original format
        """
        documents = self.document_db.get_recent_documents(
            limit=limit,
            offset=offset,
            source_name='medrxiv'
        )

        # Convert to original format
        return [
            {
                'doi': doc['external_id'],
                'title': doc['title'],
                'abstract': doc['abstract'],
                'authors': self._format_authors(doc['authors']),
                'date_posted': self._format_date(doc['publication_date']),
                'category': doc.get('category_name', ''),
                'pdf_url': doc.get('pdf_url', ''),
                'local_pdf_path': doc.get('pdf_filename', ''),
                'full_text': doc.get('full_text', '')
            }
            for doc in documents
        ]

    def search_preprints(self, search_text: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search preprints using the unified document structure.

        Args:
            search_text: Text to search for
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching preprints in the original format
        """
        documents = self.document_db.search_documents(
            search_text=search_text,
            source_name='medrxiv',
            limit=limit,
            offset=offset
        )

        # Convert to original format
        return [
            {
                'doi': doc['external_id'],
                'title': doc['title'],
                'abstract': doc['abstract'],
                'authors': self._format_authors(doc['authors']),
                'date_posted': self._format_date(doc['publication_date']),
                'category': doc.get('category_name', ''),
                'pdf_url': doc.get('pdf_url', ''),
                'local_pdf_path': doc.get('pdf_filename', ''),
                'full_text': doc.get('full_text', '')
            }
            for doc in documents
        ]

    def _format_authors(self, authors: Optional[List[str]]) -> str:
        """Format authors list as a string."""
        if not authors:
            return ''
        return ', '.join(authors)

    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date as a string."""
        if not date_str:
            return ''
        return date_str


class PubMedCompatibilityAdapter:
    """Adapter for PubMed database operations to use the unified document structure."""

    def __init__(self):
        """Initialize the adapter."""
        self.document_db = DocumentDatabaseManager()

    def get_article_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        """
        Get a PubMed article by PMID using the unified document structure.

        Args:
            pmid: PubMed ID

        Returns:
            Article data in the original format or None if not found
        """
        document = self.document_db.get_document_by_external_id('pubmed', pmid)
        if not document:
            return None

        # Convert to original format
        return {
            'pmid': document['external_id'],
            'title': document['title'],
            'abstract': document['abstract'],
            'authors': self._format_authors(document['authors']),
            'publication_year': self._extract_year(document['publication_date']),
            'journal': document.get('publication', ''),
            'mesh_terms': self._format_list(document.get('mesh_terms')),
            'keywords': self._format_list(document.get('keywords')),
            'doi': document.get('doi', ''),
            'pdf_path': document.get('pdf_filename', '')
        }

    def get_recent_articles(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get recent PubMed articles using the unified document structure.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of articles in the original format
        """
        documents = self.document_db.get_recent_documents(
            limit=limit,
            offset=offset,
            source_name='pubmed'
        )

        # Convert to original format
        return [
            {
                'pmid': doc['external_id'],
                'title': doc['title'],
                'abstract': doc['abstract'],
                'authors': self._format_authors(doc['authors']),
                'publication_year': self._extract_year(doc['publication_date']),
                'journal': doc.get('publication', ''),
                'mesh_terms': self._format_list(doc.get('mesh_terms')),
                'keywords': self._format_list(doc.get('keywords')),
                'doi': doc.get('doi', ''),
                'pdf_path': doc.get('pdf_filename', '')
            }
            for doc in documents
        ]

    def search_articles(self, search_text: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search PubMed articles using the unified document structure.

        Args:
            search_text: Text to search for
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching articles in the original format
        """
        documents = self.document_db.search_documents(
            search_text=search_text,
            source_name='pubmed',
            limit=limit,
            offset=offset
        )

        # Convert to original format
        return [
            {
                'pmid': doc['external_id'],
                'title': doc['title'],
                'abstract': doc['abstract'],
                'authors': self._format_authors(doc['authors']),
                'publication_year': self._extract_year(doc['publication_date']),
                'journal': doc.get('publication', ''),
                'mesh_terms': self._format_list(doc.get('mesh_terms')),
                'keywords': self._format_list(doc.get('keywords')),
                'doi': doc.get('doi', ''),
                'pdf_path': doc.get('pdf_filename', '')
            }
            for doc in documents
        ]

    def _format_authors(self, authors: Optional[List[str]]) -> str:
        """Format authors list as a string."""
        if not authors:
            return ''
        return ', '.join(authors)

    def _format_list(self, items: Optional[List[str]]) -> str:
        """Format a list as a semicolon-separated string."""
        if not items:
            return ''
        return '; '.join(items)

    def _extract_year(self, date_str: Optional[str]) -> str:
        """Extract year from date string."""
        if not date_str:
            return ''
        try:
            return date_str.split('-')[0]
        except (IndexError, AttributeError):
            return ''
