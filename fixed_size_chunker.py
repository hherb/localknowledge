#!/usr/bin/env python3
"""
Fixed-size chunker that just splits text into non-overlapping chunks of fixed size.

This module provides an extremely simple chunker that:
1. Creates non-overlapping chunks of fixed size
2. Tries to break at paragraph or sentence boundaries when possible
3. Ensures chunks are at least a minimum size
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class FixedSizeChunker(BaseChunker):
    """
    Fixed-size chunker that just splits text into non-overlapping chunks of fixed size.
    """

    def __init__(self, 
                 chunk_size: int = 1000, 
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the fixed-size chunker.

        Args:
            chunk_size: Size of chunks in characters
            min_chunk_size: Minimum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk_size = min_chunk_size
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into non-overlapping chunks of fixed size.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text
            **kwargs: Additional parameters (can override chunk_size and min_chunk_size)

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
        min_chunk_size = kwargs.get('min_chunk_size', self.min_chunk_size)

        # If text is smaller than min_chunk_size, return it as a single chunk
        if len(text) <= min_chunk_size:
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': 0,
                'chunk_type': 'text',
                'start_char': 0,
                'end_char': len(text),
                'char_length': len(text),
                'start_line': 1,
                'end_line': text.count('\n') + 1
            })
            return [Chunk(text=text, metadata=chunk_metadata)]

        # Create chunks
        chunks = []
        start = 0
        chunk_number = 0

        while start < len(text):
            # Calculate end position
            end = min(start + chunk_size, len(text))
            
            # Try to find a better break point if not at the end of the text
            if end < len(text):
                # Look for paragraph breaks
                paragraph_break = text.rfind('\n\n', start, end)
                if paragraph_break != -1 and paragraph_break > start + min_chunk_size:
                    end = paragraph_break + 2  # Include both newlines
                else:
                    # Look for sentence endings
                    sentence_end = -1
                    for punct in ['.', '!', '?']:
                        for suffix in [' ', '\n']:
                            pos = text.rfind(punct + suffix, start, end)
                            if pos != -1 and pos > start + min_chunk_size and pos > sentence_end:
                                sentence_end = pos + len(punct + suffix)
                    
                    if sentence_end != -1:
                        end = sentence_end
                    else:
                        # Look for the last space
                        last_space = text.rfind(' ', start, end)
                        if last_space != -1 and last_space > start + min_chunk_size:
                            end = last_space + 1  # Include the space
            
            # Extract chunk text
            chunk_text = text[start:end]
            
            # Create chunk metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'chunk_type': 'text',
                'start_char': start,
                'end_char': end,
                'char_length': len(chunk_text)
            })
            
            # Calculate line numbers
            start_line = text[:start].count('\n') + 1
            end_line = start_line + chunk_text.count('\n')
            chunk_metadata.update({
                'start_line': start_line,
                'end_line': end_line
            })
            
            chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))
            chunk_number += 1
            
            # Move to next chunk
            start = end

        return chunks

def main():
    """Main function to demonstrate the fixed-size chunker."""
    # Path to the example.md file
    example_file_path = 'localknowledge/textprocessing/chunking/tests/Example.md'
    
    # Read the example.md file
    with open(example_file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Create metadata
    metadata = {
        'file_name': 'Example.md',
        'source': 'Test',
        'document_type': 'markdown'
    }
    
    # Create a fixed-size chunker
    chunker = FixedSizeChunker(
        chunk_size=1000,
        min_chunk_size=100
    )
    
    # Chunk the text
    chunks = chunker.chunk(text, metadata=metadata)
    
    # Print the chunks
    print(f"\nFound {len(chunks)} chunks in the text:\n")
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Type: {chunk.metadata.get('chunk_type')}")
        print(f"  Text length: {len(chunk.text)} characters")
        print(f"  Text preview: {chunk.text[:100]}...")
        print(f"  Start line: {chunk.metadata.get('start_line')}")
        print(f"  End line: {chunk.metadata.get('end_line')}")
        print()

if __name__ == "__main__":
    main()
