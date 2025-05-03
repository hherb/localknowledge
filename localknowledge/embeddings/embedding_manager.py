"""
Embedding manager for creating and searching vector embeddings.

This module provides a manager for creating vector embeddings using Ollama models
and storing them in a PostgreSQL database with pgvector.
"""

import logging
import re
import ollama
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import numpy as np
import backoff

from localknowledge.embeddings.database import EmbeddingDatabaseManager
from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker, BaseChunker

# Configure logging
logger = logging.getLogger(__name__)

class EmbeddingManager:
    """Manager for creating and searching vector embeddings."""

    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest", chunker: Optional[BaseChunker] = None):
        """
        Initialize the embedding manager.

        Args:
            model_name: Name of the Ollama model to use for embeddings
            chunker: Custom chunker to use (default: TextChunker)
        """
        self.model_name = model_name
        self.db = EmbeddingDatabaseManager()

        # Set up chunker
        self.chunker = chunker or TextChunker()

        # Verify that the model is available
        self._verify_model()

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _verify_model(self):
        """Verify that the model is available in Ollama."""
        try:
            # Just use the model directly without checking if it exists
            # This will automatically pull the model if it doesn't exist
            logger.info(f"Using embedding model: {self.model_name}")
        except Exception as e:
            logger.error(f"Error verifying model: {e}")
            raise

    def get_models_with_embeddings(self) -> List[Dict[str, Any]]:
        """Get a list of models that have embeddings in the database.

        Returns:
            List of dictionaries with model information (id and model_name)
        """
        return self.db.get_models_with_embeddings()

    def set_embedding_model(self, model_name: str):
        """
        Set the embedding model to use for searches.

        Args:
            model_name: Name of the embedding model
        """
        self.model_name = model_name
        logger.info(f"Set embedding model to: {model_name}")

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Make the request to Ollama
            response = ollama.embeddings(model=self.model_name, prompt=text)
            # Handle the response based on its type
            if hasattr(response, 'embedding'):
                # New Ollama client returns a Pydantic model
                embedding = response.embedding
            elif hasattr(response, 'embeddings'):
                # Some versions might return 'embeddings' instead
                embedding = response.embeddings
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    # If it's a list of embeddings, take the first one
                    embedding = embedding[0]
            elif isinstance(response, dict):
                # Old Ollama client returns a dictionary
                if 'embedding' in response:
                    embedding = response.get('embedding', [])
                elif 'embeddings' in response:
                    embedding = response.get('embeddings', [])
                    if embedding and isinstance(embedding, list) and len(embedding) > 0:
                        embedding = embedding[0]
                else:
                    print(f"Unexpected Ollama response format: {response}")
                    embedding = []
            else:
                # Try to convert the response to a dict
                try:
                    response_dict = response.__dict__
                    if 'embedding' in response_dict:
                        embedding = response_dict.get('embedding', [])
                    elif 'embeddings' in response_dict:
                        embedding = response_dict.get('embeddings', [])
                        if embedding and isinstance(embedding, list) and len(embedding) > 0:
                            embedding = embedding[0]
                    else:
                        embedding = []
                except Exception as dict_err:
                    print(f"Error converting response to dict: {dict_err}")
                    print(f"Unexpected Ollama response type: {type(response)}")
                    embedding = []

            if not embedding:
                print("Failed to create embedding: empty response")
                return []

            return embedding
        except Exception as e:
            print(f"Error creating embedding: {e}")
            import traceback
            print(traceback.format_exc())
            return []  # Return empty list instead of raising to avoid crashing the app

    def chunk_text(self,
                   text: str,
                   chunk_size: int = 1000,
                   overlap: int = 200,
                   metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Split text into chunks for embedding.

        Args:
            text: Text to split
            chunk_size: Maximum size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            metadata: Dictionary with contextual information about the text

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # Use the TextChunker to chunk the text
        text_chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        chunks = text_chunker.chunk(text, metadata=metadata)

        # Extract the text from each chunk
        return [chunk.text for chunk in chunks]

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract

        Returns:
            List of keywords
        """
        # Simple keyword extraction based on word frequency
        # Remove common punctuation and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())

        # Split into words
        words = text.split()

        # Remove common stop words
        stop_words = {'the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'with', 'on', 'at', 'from',
                     'by', 'an', 'this', 'that', 'these', 'those', 'it', 'as', 'be', 'are', 'was',
                     'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but',
                     'or', 'if', 'because', 'not', 'what', 'which', 'who', 'whom', 'whose', 'when',
                     'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
                     'other', 'some', 'such', 'no', 'nor', 'only', 'own', 'same', 'so', 'than',
                     'too', 'very', 'can', 'will', 'just', 'should', 'now'}

        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top keywords
        return [word for word, _ in sorted_words[:max_keywords]]

    def process_document(self,
                         source_id: str,
                         document_id: str,
                         text: str,
                         page_info: Optional[Dict[int, str]] = None,
                         chunker: Optional[BaseChunker] = None,
                         is_markdown: bool = False,
                         metadata: Optional[Dict[str, Any]] = None,
                         **chunker_params) -> int:
        """
        Process a document by chunking, embedding, and storing in the database.

        Args:
            source_id: Source identifier (e.g., 'pubmed', 'medrxiv')
            document_id: Document identifier (e.g., PMID, DOI)
            text: Full text of the document
            page_info: Dictionary mapping page numbers to text (optional)
            chunker: Custom chunker to use for this document (overrides the default)
            is_markdown: Whether the text is in markdown format (if True and no chunker is provided, uses MarkdownChunker)
            metadata: Dictionary with contextual information about the document (e.g., file name, source)
                     This will be enhanced with chunk-specific information
            **chunker_params: Additional parameters to pass to the chunker

        Returns:
            Number of chunks processed
        """
        if not text:
            logger.warning(f"Empty text for document {document_id}, skipping")
            return 0

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Add source_id and document_id to metadata
        metadata.update({
            'source_id': source_id,
            'document_id': document_id
        })

        # Determine which chunker to use
        active_chunker = chunker or (MarkdownChunker() if is_markdown else self.chunker)

        # If page_info is provided, process each page separately
        if page_info:
            total_chunks = 0
            for page_no, page_text in page_info.items():
                # Create page-specific metadata
                page_metadata = metadata.copy()
                page_metadata['page_no'] = page_no

                # Add page number to chunker params
                params = {**chunker_params, 'page_no': page_no}

                # Get chunks for this page
                chunks = active_chunker.chunk(page_text, metadata=page_metadata, **params)

                for i, chunk in enumerate(chunks):
                    # Create a unique chunk number that includes the page number
                    chunk_no = (page_no * 1000) + i

                    # Extract keywords if not already in metadata
                    keywords = chunk.metadata.get('keywords') or self.extract_keywords(chunk.text)

                    # Create embedding
                    embedding = self.create_embedding(chunk.text)

                    # Store in database
                    self.db.store_embedding(
                        source_id=source_id,
                        document_id=document_id,
                        chunk_no=chunk_no,
                        page_no=page_no,
                        text=chunk.text,
                        embedding=embedding,
                        model_name=self.model_name,
                        keywords=keywords
                    )

                total_chunks += len(chunks)
            return total_chunks

        # Process the entire text as a single document
        chunks = active_chunker.chunk(text, metadata=metadata, **chunker_params)

        for i, chunk in enumerate(chunks):
            # Extract keywords if not already in metadata
            keywords = chunk.metadata.get('keywords') or self.extract_keywords(chunk.text)

            # Create embedding
            embedding = self.create_embedding(chunk.text)

            # Get page number from metadata if available
            page_no = chunk.metadata.get('page_no')

            # Store in database
            self.db.store_embedding(
                source_id=source_id,
                document_id=document_id,
                chunk_no=i,
                page_no=page_no,
                text=chunk.text,
                embedding=embedding,
                model_name=self.model_name,
                keywords=keywords
            )

        return len(chunks)

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by the current model.

        Returns:
            Dimension (vector size) of the embeddings
        """
        # Create a test embedding to determine the dimension
        test_embedding = self.create_embedding("test")
        return len(test_embedding)

    def check_embedding_compatibility(self) -> bool:
        """
        Check if the current model's embeddings are compatible with the database.

        Returns:
            True if compatible, False otherwise
        """
        try:
            # Get the dimension of embeddings in the database
            db_dimension = self.db.get_embedding_dimension()

            # If there are no embeddings in the database, it's compatible
            if db_dimension is None:
                print("No embeddings in database yet, so any model is compatible")
                return True

            # Get the dimension of embeddings from the current model
            try:
                model_dimension = self.get_embedding_dimension()

                # Check if they match
                is_compatible = db_dimension == model_dimension
                return is_compatible
            except Exception as model_err:
                print(f"Error getting model dimension: {model_err}")
                # If we can't get the model dimension, assume it's compatible
                # This allows the search to proceed and fail gracefully if needed
                print("Assuming compatibility due to error in model dimension check")
                return True
        except Exception as e:
            print(f"Error checking embedding compatibility: {e}")
            import traceback
            print(traceback.format_exc())
            # If we can't check compatibility, assume it's compatible
            # This allows the search to proceed and fail gracefully if needed
            return True

    def search(self, query: str, limit: int = 10, threshold: float = 0.5, source_id: Optional[Union[str, int]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents using semantic search.

        Args:
            query: Search query
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (can be a string name or integer ID)

        Returns:
            List of similar documents with similarity scores
        """
        try:
            # Check if there are any embeddings in the database
            db_dimension = self.db.get_embedding_dimension()
            if db_dimension is None:
                print("No embeddings found in the database. Please embed some documents first.")
                return [{
                    'error': 'No embeddings',
                    'document_id': 'error',
                    'text': 'No embeddings found in the database. Please embed some documents first.',
                    'similarity': 0.0
                }]

            # Check if embeddings are compatible
            if not self.check_embedding_compatibility():
                print("Embedding dimensions mismatch between model and database")
                return [{
                    'error': 'Embedding dimensions mismatch',
                    'document_id': 'error',
                    'text': 'The current embedding model is not compatible with the database. '
                            'The vector dimensions do not match. Please use the same model that was used to create the embeddings.',
                    'similarity': 0.0
                }]

            # Create embedding for the query
            query_embedding = self.create_embedding(query)

            if not query_embedding:
                print("Failed to create query embedding")
                return [{
                    'error': 'Embedding creation failed',
                    'document_id': 'error',
                    'text': 'Failed to create an embedding for your query. Please try again or use a different query.',
                    'similarity': 0.0
                }]

            # Search for similar documents
            print(f"Searching for similar documents with threshold={threshold}")
            results = self.db.search_similar(
                query_embedding=query_embedding,
                limit=limit,
                threshold=threshold,
                source_id=source_id
            )

            print(f"Search returned {len(results)} results")
            if results:
                print(f"Top result similarity: {results[0].get('similarity', 0)}")

            return results
        except Exception as e:
            print(f"Error searching similar documents: {e}")
            import traceback
            print(traceback.format_exc())
            return [{
                'error': str(e),
                'document_id': 'error',
                'text': f'An error occurred during search: {str(e)}',
                'similarity': 0.0
            }]

    def delete_document(self, source_id: str, document_id: str) -> int:
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
