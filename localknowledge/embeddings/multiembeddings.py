"""Multi-model embedding manager for creating and searching vector embeddings.

This module provides a manager for creating and searching vector embeddings using
different embedding models, with support for model comparison and performance tracking.
"""

import logging
import ollama
from typing import List, Dict, Any, Optional
import backoff

from localknowledge.db.multiembeddings import EmbeddingTableManager

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Manager for creating and searching vector embeddings with multiple model support.

    This class provides an interface for creating embeddings using different models,
    storing them in model-specific database tables, and searching across models.
    It also supports comparing search results from different models.
    """

    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest"):
        """Initialize the embedding manager.

        Args:
            model_name: Name of the Ollama model to use for embeddings
        """
        self.model_name = model_name
        self.db = EmbeddingTableManager()
        self._verify_model()

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _verify_model(self) -> None:
        """Verify that the model is available in Ollama.

        Attempts to verify the model exists in Ollama. If not, logs a warning
        but does not raise an exception to allow for graceful fallback.
        """
        try:
            # Get the list of models from Ollama
            model_names = [model['model'] for model in ollama.list()['models']]

            if self.model_name not in model_names:
                logger.warning(f"Model {self.model_name} not found in Ollama. Will attempt to use it anyway.")
                logger.info(f"Available models: {', '.join(model_names)}")
        except Exception as e:
            logger.error(f"Error verifying model: {e}")
            # Don't raise the exception, just log it

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Make the request to Ollama
            response = ollama.embed(model=self.model_name, input=text).embeddings[0]
            return response
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise

    def process_text(
        self,
        source_id: str,
        document_id: str,
        text: str,
        chunk_no: int = 0,
        page_no: Optional[int] = None,
        keywords: Optional[List[str]] = None
    ) -> int:
        """Process and store text embedding.

        Args:
            source_id: Source identifier (e.g., 'medrxiv', 'pubmed')
            document_id: Document identifier (e.g., DOI, PMID)
            text: Text to embed
            chunk_no: Chunk number within the document
            page_no: Page number (optional)
            keywords: List of keywords (optional)

        Returns:
            ID of the inserted record
        """
        embedding = self.create_embedding(text)

        return self.db.store_embedding(
            self.model_name,
            {
                'source_id': source_id,
                'document_id': document_id,
                'chunk_no': chunk_no,
                'page_no': page_no,
                'text': text,
                'keywords': keywords,
                'embedding': embedding
            }
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
        source_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using the current model.

        Args:
            query: Text query to search for
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold (0-1)
            source_id: Optional source ID to filter results

        Returns:
            List of dictionaries containing search results with similarity scores
        """
        query_embedding = self.create_embedding(query)

        return self.db.search_similar(
            self.model_name,
            query_embedding,
            limit=limit,
            threshold=threshold,
            source_id=source_id
        )

    def compare_models(
        self,
        query: str,
        models: List[str],
        limit: int = 10,
        threshold: float = 0.7,
        source_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Compare search results across different embedding models.

        Args:
            query: Text query to search for
            models: List of model names to compare
            limit: Maximum number of results to return per model
            threshold: Minimum similarity threshold (0-1)
            source_id: Optional source ID to filter results

        Returns:
            Dictionary mapping model names to their results and statistics
        """
        results = {}

        for model in models:
            try:
                temp_manager = EmbeddingManager(model_name=model)
                model_results = temp_manager.search(query, limit, threshold, source_id)
                results[model] = {
                    'results': model_results,
                    'stats': self.db.get_model_stats(model),
                    'result_count': len(model_results)
                }
            except Exception as e:
                logger.error(f"Error comparing model {model}: {e}")
                results[model] = {
                    'error': str(e),
                    'results': [],
                    'stats': self.db.get_model_stats(model),
                    'result_count': 0
                }

        return results

    def get_available_models(self) -> List[str]:
        """Get a list of available embedding models from Ollama.

        Returns:
            List of model names available in Ollama
        """
        try:
            return [model['model'] for model in ollama.list()['models']]
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return []

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self.db, 'close'):
            self.db.close()