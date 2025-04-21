"""
Simple text chunker based on character count.

This module provides a simple text chunker that splits text into chunks
based on character count, trying to break at sentence boundaries.
"""

import re
from typing import List, Dict, Any, Optional, Tuple, Union

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class TextChunker(BaseChunker):
    """
    Simple text chunker based on character count.
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 200, **kwargs):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Maximum size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks based on character count.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text (e.g., file name, source)
                     This will be enhanced with chunk-specific information
            **kwargs: Additional parameters (can override chunk_size and overlap)

        Returns:
            List of Chunk objects
        """
        if not text:
            return []

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Override parameters if provided
        chunk_size = kwargs.get('chunk_size', self.chunk_size)
        overlap = kwargs.get('overlap', self.overlap)

        # Simple chunking by character count
        chunks = []
        start = 0
        chunk_number = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Try to end at a sentence boundary
            if end < len(text):
                # Look for sentence boundaries (., !, ?) followed by space or newline
                sentence_end = max(
                    text.rfind('. ', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('.\n', start, end),
                    text.rfind('!\n', start, end),
                    text.rfind('?\n', start, end)
                )

                if sentence_end > start:
                    end = sentence_end + 1  # Include the period

            # Create chunk with metadata
            chunk_text = text[start:end]

            # Create a copy of the base metadata and enhance it with chunk-specific info
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'start_char': start,
                'end_char': end,
                'chunk_type': 'text',
                'char_length': end - start
            })

            # Add line numbers if available in the text
            if '\n' in text[:start]:
                start_line = text[:start].count('\n') + 1
                end_line = start_line + chunk_text.count('\n')
                chunk_metadata.update({
                    'start_line': start_line,
                    'end_line': end_line
                })

            chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))

            # Move to next chunk with overlap
            start = end - overlap
            chunk_number += 1

        return chunks
