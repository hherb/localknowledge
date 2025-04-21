"""
Base chunker class for text chunking strategies.

This module provides a base class for implementing different text chunking strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class Chunk:
    """
    Represents a chunk of text with metadata.
    """

    def __init__(self,
                 text: str,
                 metadata: Optional[Dict[str, Any]] = None,
                 chunk_id: Optional[str] = None):
        """
        Initialize a chunk.

        Args:
            text: The text content of the chunk
            metadata: Optional metadata about the chunk (e.g., heading level, page number)
            chunk_id: Optional identifier for the chunk
        """
        self.text = text
        self.metadata = metadata or {}
        self.chunk_id = chunk_id

    def __str__(self) -> str:
        """String representation of the chunk."""
        return f"Chunk(id={self.chunk_id}, text={self.text[:50]}...)"

    def __repr__(self) -> str:
        """Detailed representation of the chunk."""
        return f"Chunk(id={self.chunk_id}, metadata={self.metadata}, text={self.text[:50]}...)"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the chunk to a dictionary."""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'metadata': self.metadata
        }

class BaseChunker(ABC):
    """
    Base class for text chunking strategies.
    """

    def __init__(self, **kwargs):
        """
        Initialize the chunker with optional parameters.

        Args:
            **kwargs: Additional parameters for the chunker
        """
        self.params = kwargs

    @abstractmethod
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks according to the strategy.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text (e.g., file name, source)
                     This will be enhanced with chunk-specific information
            **kwargs: Additional parameters for chunking

        Returns:
            List of Chunk objects
        """
        pass

    def chunk_with_ids(self, text: str, metadata: Optional[Dict[str, Any]] = None, prefix: str = "", **kwargs) -> List[Chunk]:
        """
        Split text into chunks and assign IDs.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text
            prefix: Prefix for chunk IDs
            **kwargs: Additional parameters for chunking

        Returns:
            List of Chunk objects with IDs
        """
        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Add prefix to metadata if provided
        if prefix and 'id_prefix' not in metadata:
            metadata['id_prefix'] = prefix

        chunks = self.chunk(text, metadata=metadata, **kwargs)

        # Assign IDs to chunks
        for i, chunk in enumerate(chunks):
            if not chunk.chunk_id:
                chunk_prefix = metadata.get('id_prefix', prefix)
                chunk.chunk_id = f"{chunk_prefix}{i:04d}" if chunk_prefix else f"{i:04d}"

        return chunks
