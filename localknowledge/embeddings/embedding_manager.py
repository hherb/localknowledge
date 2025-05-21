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

from localknowledge.db.embeddings import EmbeddingsDatabaseManager
from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder
from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker, BaseChunker

# Configure logging
logger = logging.getLogger(__name__)

class EmbeddingManager:
    """Manager for creating and searching vector embeddings."""

    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest",
                 chunker: Optional[BaseChunker] = None):
        """
        Initialize the embedding manager.

        Args:
            model_name: Name of the Ollama model to use for embeddings
            chunker: Custom chunker to use (default: TextChunker)
        """
        # Initialize database first to avoid circular dependency issues
        self.db = EmbeddingsDatabaseManager()

        # Initialize other attributes
        self.embedder = None
        self.model_name = None
        self.set_embedding_model(model_name)

        # Set up chunker
        self.chunker = chunker or TextChunker()


    def get_models_with_embeddings(self) -> List[Dict[str, Any]]:
        """Get a list of models that have embeddings in the database.

        Returns:
            List of dictionaries with model information (id and model_name)
        """
        # Make sure db is initialized
        if not hasattr(self, 'db') or self.db is None:
            self.db = EmbeddingsDatabaseManager()

        try:
            return self.db.get_models_with_embeddings()
        except Exception as e:
            logger.warning(f"Error getting models with embeddings: {e}")
            # Return a default model if we can't get the list from the database
            return [{'id': 1, 'model_name': 'snowflake-arctic-embed2:latest'}]

    def set_embedding_model(self, model_name: str):
        """
        Set the embedding model to use for searches.

        Args:
            model_name: Name of the embedding model
        """
        if model_name == self.model_name:
            return

        self.model_name = model_name

        # Make sure db is initialized
        if not hasattr(self, 'db') or self.db is None:
            self.db = EmbeddingsDatabaseManager()

        try:
            embedder_name = self.db.get_embedder_for_model(model_name)
            match embedder_name:
                case 'ollama': self.embedder=OllamaEmbedder(model_name=model_name)
                case 'pubmedbert': self.embedder=PubMedBERTEmbedder(model_name=model_name)
                case _:
                    # Default to Ollama embedder if no specific embedder is found
                    self.embedder=OllamaEmbedder(model_name=model_name)
                    embedder_name = 'ollama'
            logger.info(f"Set embedding model to: {model_name} (type: {embedder_name})")
        except Exception as e:
            logger.warning(f"Error setting embedding model: {e}. Using default Ollama embedder.")
            self.embedder = OllamaEmbedder(model_name=model_name)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        return self.embedder.embed(text)


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

            # Create embedding for the query
        query_embedding = self.create_embedding(query)

        if not query_embedding:
            logger.error("Failed to create query embedding")
            return [{
                'error': 'Embedding creation failed',
                'document_id': 'error',
                'text': 'Failed to create an embedding for your query. Please try again or use a different query.',
                'similarity': 0.0
            }]

        # Search for similar documents
        logger.info(f"Searching for similar documents with threshold={threshold}")

        # The EmbeddingsDatabaseManager.search_similar method expects 'embedding' and 'embed_source' parameters
        # not 'query_embedding' and 'source_id'
        try:
            results = self.db.search_similar(
                embedding=query_embedding,
                embed_source='abstract',  # Default to abstract as the embedding source
                model_name=self.model_name,
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
                results = filtered_results
        except Exception as e:
            logger.error(f"Error in search: {e}")
            return [{
                'error': 'Search failed',
                'document_id': 'error',
                'text': f'Failed to search for similar documents: {str(e)}',
                'similarity': 0.0
            }]

        print(f"Search returned {len(results)} results")
        if results:
            print(f"Top result similarity: {results[0].get('similarity', 0)}")

        return results


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
