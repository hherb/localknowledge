#!/usr/bin/env python3
"""
Simple text chunker that properly handles sentence boundaries and minimum chunk size.

This module provides a simple text chunker that:
1. Ensures chunks are at least a minimum size (unless the entire text is smaller)
2. Never breaks words in the middle
3. Prefers to break at sentence or paragraph boundaries
4. Avoids creating many tiny chunks
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class SimpleTextChunker(BaseChunker):
    """
    Simple text chunker that properly handles sentence boundaries and minimum chunk size.
    """

    def __init__(self, 
                 chunk_size: int = 1000, 
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the simple text chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            min_chunk_size: Minimum size of a chunk in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk_size = min_chunk_size

    def find_break_point(self, text: str, start_idx: int, target_idx: int) -> int:
        """
        Find a suitable break point near the target index.
        
        Prioritizes:
        1. Paragraph breaks
        2. Sentence endings
        3. Any punctuation followed by space
        4. Space characters
        
        Args:
            text: The text to analyze
            start_idx: The start index of the current chunk
            target_idx: The target index where we'd like to break
            
        Returns:
            The index where the chunk should end
        """
        # Don't go beyond the end of the text
        end_idx = min(target_idx, len(text))
        
        # If we're at the end of the text, return it
        if end_idx == len(text):
            return end_idx
            
        # Look for paragraph breaks (double newline)
        paragraph_break = text.rfind('\n\n', start_idx, end_idx)
        if paragraph_break != -1 and paragraph_break > start_idx + self.min_chunk_size:
            return paragraph_break + 2  # Include both newlines
            
        # Look for sentence endings (., !, ? followed by space or newline)
        for punct in ['.', '!', '?']:
            for suffix in [' ', '\n']:
                pos = text.rfind(punct + suffix, start_idx, end_idx)
                if pos != -1 and pos > start_idx + self.min_chunk_size:
                    return pos + len(punct + suffix)  # Include the punctuation and suffix
                    
        # Look for other punctuation followed by space
        for punct in [',', ';', ':', '-']:
            pos = text.rfind(punct + ' ', start_idx, end_idx)
            if pos != -1 and pos > start_idx + self.min_chunk_size:
                return pos + 2  # Include the punctuation and space
                
        # Look for the last space
        last_space = text.rfind(' ', start_idx, end_idx)
        if last_space != -1 and last_space > start_idx + self.min_chunk_size:
            return last_space + 1  # Include the space
            
        # If we can't find a good break point and we're already past min_chunk_size,
        # just return the target index
        if end_idx > start_idx + self.min_chunk_size:
            # Make sure we're not breaking a word
            if end_idx < len(text) and text[end_idx-1].isalnum() and text[end_idx].isalnum():
                # We're in the middle of a word, find the previous space
                prev_space = text.rfind(' ', start_idx, end_idx)
                if prev_space != -1 and prev_space > start_idx + self.min_chunk_size:
                    return prev_space + 1  # Include the space
            return end_idx
            
        # If we're still here, we need to look forward for a break point
        # This happens when the min_chunk_size constraint prevents us from finding a good break point
        
        # Look for the next sentence ending
        next_sentence_end = -1
        for punct in ['.', '!', '?']:
            for suffix in [' ', '\n']:
                pos = text.find(punct + suffix, end_idx)
                if pos != -1 and (next_sentence_end == -1 or pos < next_sentence_end):
                    next_sentence_end = pos + len(punct + suffix)
                    
        # Look for the next paragraph break
        next_para_break = text.find('\n\n', end_idx)
        
        # Look for the next space
        next_space = text.find(' ', end_idx)
        
        # Choose the earliest valid break point
        candidates = [pos for pos in [next_sentence_end, next_para_break, next_space] if pos != -1]
        
        if candidates:
            return min(candidates)
        
        # If we can't find any break point, return the end of the text
        return len(text)

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks, respecting sentence boundaries and minimum chunk size.

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

        # Ensure min_chunk_size is not larger than chunk_size
        min_chunk_size = min(min_chunk_size, chunk_size)
        
        # If the entire text is smaller than min_chunk_size, return it as a single chunk
        if len(text) <= min_chunk_size:
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': 0,
                'start_char': 0,
                'end_char': len(text),
                'chunk_type': 'text',
                'char_length': len(text)
            })
            
            # Add line numbers if available
            if '\n' in text:
                chunk_metadata.update({
                    'start_line': 1,
                    'end_line': text.count('\n') + 1
                })
                
            return [Chunk(text=text, metadata=chunk_metadata)]

        # Create chunks
        chunks = []
        start = 0
        chunk_number = 0

        while start < len(text):
            # Calculate target end position
            target_end = min(start + chunk_size, len(text))
            
            # Find a suitable break point
            end = self.find_break_point(text, start, target_end)
            
            # Create chunk with metadata
            chunk_text = text[start:end]
            
            # Skip empty chunks
            if not chunk_text.strip():
                start = end
                continue
                
            # Create a copy of the base metadata and enhance it with chunk-specific info
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'start_char': start,
                'end_char': end,
                'chunk_type': 'text',
                'char_length': len(chunk_text)
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
            chunk_number += 1
            
            # Move to next chunk
            start = end
            
            # If we've reached the end of the text, we're done
            if start >= len(text):
                break

        return chunks

def main():
    """Main function to demonstrate the simple text chunker."""
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
    
    # Create a simple text chunker
    chunker = SimpleTextChunker(
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
