"""
medRxiv database access functionality.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from localknowledge.base import LocalKnowledgeBase
from localknowledge.db.medrxiv import MedRxivDatabaseManager

# Import the abstract embedder
from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder


class MedRxivClient(LocalKnowledgeBase):
    """Client for accessing and managing local medRxiv database."""

    def __init__(self):
        """Initialize the medRxiv client."""
        super().__init__()
        self.db = MedRxivDatabaseManager()

    def search(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search the local medRxiv database.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of articles matching the query
        """
        return self.db.search_preprints(query, ['title', 'abstract', 'full_text'], max_results)

    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific article by medRxiv ID.

        Args:
            article_id: medRxiv ID of the article (typically a DOI)

        Returns:
            Article data or None if not found
        """
        return self.db.get_preprint_by_doi(article_id)

    def download_updates(self, from_date: Optional[datetime] = None) -> int:
        """
        Update the local database with the latest medRxiv articles.

        Args:
            from_date: Download articles published after this date

        Returns:
            Number of new articles added
        """
        # If no date is specified, try to get the latest date from the database
        if from_date is None:
            resume_date = self.db.get_resume_date(days_back=1)
            if resume_date:
                from_date = datetime.strptime(resume_date, '%Y-%m-%d')
            else:
                # Default to papers from the last 90 days
                from_date = datetime.now() - timedelta(days=90)

        # This will be implemented to use the medrxiv_import functionality
        # For now, it's just a placeholder
        return 0

    def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        medRxiv-specific method to fetch a preprint directly from medRxiv by DOI.

        Args:
            doi: Digital Object Identifier for the preprint

        Returns:
            Preprint data from medRxiv or None if not found
        """
        # This would use the medRxiv API or website to fetch the preprint
        # and store it in the local database
        return None

    def download_missing_pdfs(self, limit: Optional[int] = None) -> int:
        """
        Download PDFs for articles that don't have them yet.

        Args:
            limit: Maximum number of PDFs to download

        Returns:
            Number of PDFs downloaded
        """
        # Get articles without PDFs
        preprints = self.db.get_preprints_without_pdfs(limit)

        # This will be implemented to use the medrxiv_import functionality
        # For now, it's just a placeholder
        return 0

    def embed_abstracts(self, limit: Optional[int] = None, batch_size: int = 100, model_name: str = "snowflake-arctic-embed2:latest") -> int:
        """
        Embed medrxiv abstracts that haven't been embedded yet.

        Args:
            limit: Maximum number of abstracts to embed
            batch_size: Number of abstracts to process in each batch
            model_name: Name of the Ollama model to use for embeddings

        Returns:
            Number of abstracts embedded
        """
        embedder = MedrxivAbstractEmbedder(model_name=model_name)
        try:
            return embedder.embed_abstracts(limit=limit, batch_size=batch_size)
        finally:
            embedder.close()

    def count_abstracts_without_embeddings(self) -> int:
        """
        Count the number of abstracts without embeddings.

        Returns:
            Number of abstracts without embeddings
        """
        embedder = MedrxivAbstractEmbedder()
        try:
            return embedder.count_abstracts_without_embeddings()
        finally:
            embedder.close()

    def close(self):
        """Close the database connection."""
        if hasattr(self, 'db'):
            self.db.close()
