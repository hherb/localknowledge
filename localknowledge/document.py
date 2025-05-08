#!/usr/bin/env python3
"""
Unified document access module.

This module provides a unified interface for accessing documents from
different sources (PubMed, medRxiv, etc.) using the new document structure.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import datetime

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.embeddings import EmbeddingsDatabaseManager

logger = logging.getLogger(__name__)


class Document:
    """Unified document class representing a document from any source."""

    def __init__(self, data: Dict[str, Any], similarity: float = None):
        """
        Initialize a document.
        
        Args:
            data: Document data
            similarity: Similarity score (for semantic search results)
        """
        self.id = data.get('id')
        self.source = data.get('source_name')
        self.external_id = data.get('external_id')
        self.title = data.get('title')
        self.abstract = data.get('abstract')
        self.authors = data.get('authors')
        self.publication_date = data.get('publication_date')
        self.journal = data.get('journal')
        self.doi = data.get('doi')
        self.url = data.get('url')
        self.pdf_url = data.get('pdf_url')
        self.local_file_path = data.get('local_file_path')
        self.keywords = data.get('keywords')
        self.mesh_terms = data.get('mesh_terms')
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.similarity = similarity

    def __str__(self) -> str:
        """Return a string representation of the document."""
        return f"{self.title} ({self.source}: {self.external_id})"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the document to a dictionary.
        
        Returns:
            Dictionary representation of the document
        """
        return {
            'id': self.id,
            'source': self.source,
            'external_id': self.external_id,
            'title': self.title,
            'abstract': self.abstract,
            'authors': self.authors,
            'publication_date': self.publication_date,
            'journal': self.journal,
            'doi': self.doi,
            'url': self.url,
            'pdf_url': self.pdf_url,
            'local_file_path': self.local_file_path,
            'keywords': self.keywords,
            'mesh_terms': self.mesh_terms,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'similarity': self.similarity
        }


class DocumentClient:
    """Client for accessing documents from different sources."""

    def __init__(self):
        """Initialize the client."""
        self.document_db = DocumentDatabaseManager()
        self.embedding_db = EmbeddingsDatabaseManager()

    def get_document(self, source: str, external_id: str) -> Optional[Document]:
        """
        Get a document by source and external ID.
        
        Args:
            source: Source name (e.g., 'pubmed', 'medrxiv')
            external_id: External ID (e.g., PMID, DOI)
            
        Returns:
            Document or None if not found
        """
        data = self.document_db.get_document_by_external_id(source, external_id)
        if not data:
            return None
        
        return Document(data)

    def search(self, query: str, max_results: int = 100, sources: List[str] = None) -> List[Document]:
        """
        Search for documents.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            sources: List of sources to search (e.g., ['pubmed', 'medrxiv'])
            
        Returns:
            List of matching documents
        """
        results = self.document_db.search_documents(query, limit=max_results, sources=sources)
        return [Document(data) for data in results]

    def semantic_search(self, query: str, max_results: int = 20, 
                        sources: List[str] = None, model_name: str = None,
                        min_similarity: float = 0.7) -> List[Document]:
        """
        Perform semantic search.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            sources: List of sources to search (e.g., ['pubmed', 'medrxiv'])
            model_name: Name of the embedding model to use
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of matching documents with similarity scores
        """
        # Get embeddings for the query
        if not model_name:
            # Use the default model
            model_name = self.embedding_db.get_default_model()
        
        # Perform semantic search
        results = self.document_db.semantic_search(
            query, 
            model_name=model_name, 
            limit=max_results, 
            sources=sources,
            min_similarity=min_similarity
        )
        
        # Convert to Document objects with similarity scores
        documents = []
        for data in results:
            similarity = data.pop('similarity', 0)
            documents.append(Document(data, similarity=similarity))
        
        return documents

    def get_recent_documents(self, max_results: int = 100, 
                            sources: List[str] = None,
                            days: int = 30) -> List[Document]:
        """
        Get recent documents.
        
        Args:
            max_results: Maximum number of results to return
            sources: List of sources to include (e.g., ['pubmed', 'medrxiv'])
            days: Number of days to look back
            
        Returns:
            List of recent documents
        """
        # Calculate the date range
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)
        
        # Get recent documents
        results = self.document_db.get_documents_by_date_range(
            start_date=start_date,
            end_date=end_date,
            limit=max_results,
            sources=sources
        )
        
        return [Document(data) for data in results]

    def update_document_file_path(self, source: str, external_id: str, 
                                 file_path: str) -> bool:
        """
        Update the file path for a document.
        
        Args:
            source: Source name (e.g., 'pubmed', 'medrxiv')
            external_id: External ID (e.g., PMID, DOI)
            file_path: Path to the file
            
        Returns:
            True if successful, False otherwise
        """
        return self.document_db.update_document_file_path(source, external_id, file_path)

    def close(self):
        """Close the database connections."""
        self.document_db.close()
        self.embedding_db.close()
