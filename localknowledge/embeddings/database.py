"""
Database functionality for embeddings in the LocalKnowledge library.

This module provides a database manager for working with embeddings stored in the database.
It serves as a bridge between the EmbeddingManager and the actual database operations.
"""

import logging
from typing import List, Dict, Any, Optional, Union, Tuple

from localknowledge.db.embeddings import EmbeddingsDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingDatabaseManager:
    """
    Database manager for embeddings operations.

    This class is a wrapper around the EmbeddingsDatabaseManager to provide a consistent
    interface for the EmbeddingManager class.
    """

    def __init__(self):
        """Initialize the embedding database manager."""
        self.db = EmbeddingsDatabaseManager()

    def get_models_with_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get a list of models that have embeddings in the database.

        Returns:
            List of dictionaries with model information (id and model_name)
        """
        return self.db.get_models_with_embeddings()

    def get_embedder_for_model(self, model_name: str) -> str:
        """
        Get the embedder type for a model.

        Args:
            model_name: Name of the model

        Returns:
            Embedder type (e.g., 'ollama', 'pubmedbert')
        """
        return self.db.get_embedder_for_model(model_name)

    def store_embedding(
        self,
        source_id: str,
        document_id: str,
        chunk_no: int,
        page_no: Optional[int],
        text: str,
        embedding: List[float],
        model_name: str,
        keywords: Optional[List[str]] = None
    ) -> int:
        """
        Store an embedding in the database.

        Args:
            source_id: Source identifier (e.g., 'pubmed', 'medrxiv')
            document_id: Document identifier (e.g., PMID, DOI)
            chunk_no: Chunk number within the document
            page_no: Page number (optional)
            text: Text that was embedded
            embedding: Vector embedding
            model_name: Name of the embedding model
            keywords: List of keywords (optional)

        Returns:
            ID of the new embedding
        """
        return self.db.store_embedding(
            source_id=source_id,
            document_id=document_id,
            chunk_no=chunk_no,
            page_no=page_no,
            text=text,
            embedding=embedding,
            model_name=model_name,
            keywords=keywords
        )

    def search_similar(
        self,
        query_embedding: List[float],
        model_name: str,
        limit: int = 10,
        threshold: float = 0.5,
        source_id: Optional[Union[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using a query embedding.

        Args:
            query_embedding: Query embedding vector
            model_name: Name of the embedding model
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (can be a string name or integer ID)

        Returns:
            List of similar documents with similarity scores
        """
        # The underlying EmbeddingsDatabaseManager.search_similar method expects
        # 'embedding' and 'embed_source' parameters, not 'query_embedding' and 'source_id'

        # Default to 'abstract' as the embedding source type
        embed_source = 'abstract'

        try:
            # Call the underlying search_similar method with the correct parameter names
            results = self.db.search_similar(
                embedding=query_embedding,
                embed_source=embed_source,
                model_name=model_name,
                limit=limit,
                threshold=threshold
            )

            # Filter results by source_id if provided
            if source_id and results:
                filtered_results = []
                for result in results:
                    # Check if the result has a source_id that matches the requested source_id
                    if (result.get('source_id') == source_id or
                        result.get('source_name') == source_id):
                        filtered_results.append(result)
                return filtered_results

            return results
        except Exception as e:
            logger.error(f"Error in search_similar: {e}")
            return []

    def delete_document_embeddings(self, source_id: str, document_id: str) -> int:
        """
        Delete all embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        return self.db.delete_document_embeddings(source_id, document_id)

    def close(self):
        """Close the database connection."""
        self.db.close()
