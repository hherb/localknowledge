#!/usr/bin/env python3
"""
Very simple chunker that just breaks text into non-overlapping chunks.

This module provides a very simple chunker that:
1. Creates non-overlapping chunks of approximately the target size
2. Tries to break at sentence or paragraph boundaries
3. Ensures chunks are at least a minimum size
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class VerySimpleChunker(BaseChunker):
    """
    Very simple chunker that just breaks text into non-overlapping chunks.
    """

    def __init__(self, 
                 target_size: int = 1000, 
                 min_size: int = 100,
                 **kwargs):
        """
        Initialize the very simple chunker.

        Args:
            target_size: Target size of chunks in characters
            min_size: Minimum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.target_size = target_size
        self.min_size = min_size
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into non-overlapping chunks.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text
            **kwargs: Additional parameters (can override target_size and min_size)

        Returns:
            List of Chunk objects
        """
        if not text:
            return []

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Override parameters if provided
        target_size = kwargs.get('chunk_size', self.target_size)
        min_size = kwargs.get('min_chunk_size', self.min_size)

        # If text is smaller than min_size, return it as a single chunk
        if len(text) <= min_size:
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

        # Split text into paragraphs
        paragraphs = []
        current_para = ""
        for line in text.split('\n'):
            if line.strip():
                if current_para:
                    current_para += '\n' + line
                else:
                    current_para = line
            else:
                if current_para:
                    paragraphs.append(current_para)
                    current_para = ""
                paragraphs.append("")  # Empty line
        
        if current_para:
            paragraphs.append(current_para)

        # Create chunks from paragraphs
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_number = 0

        for para in paragraphs:
            # If adding this paragraph would exceed target_size and we already have content,
            # finish the current chunk
            if current_chunk and len(current_chunk) + len(para) + 1 > target_size and len(current_chunk) >= min_size:
                # Create chunk metadata
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_number': chunk_number,
                    'chunk_type': 'text',
                    'start_char': current_start,
                    'end_char': current_start + len(current_chunk),
                    'char_length': len(current_chunk),
                    'start_line': text[:current_start].count('\n') + 1,
                    'end_line': text[:current_start].count('\n') + current_chunk.count('\n') + 1
                })
                
                chunks.append(Chunk(text=current_chunk, metadata=chunk_metadata))
                chunk_number += 1
                
                # Start a new chunk
                current_chunk = para
                current_start += len(current_chunk) + 1  # +1 for the newline
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += '\n' + para
                else:
                    current_chunk = para

        # Add the final chunk if it has content
        if current_chunk:
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'chunk_type': 'text',
                'start_char': current_start,
                'end_char': current_start + len(current_chunk),
                'char_length': len(current_chunk),
                'start_line': text[:current_start].count('\n') + 1,
                'end_line': text[:current_start].count('\n') + current_chunk.count('\n') + 1
            })
            
            chunks.append(Chunk(text=current_chunk, metadata=chunk_metadata))

        return chunks

def main():
    """Main function to demonstrate the very simple chunker."""
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
    
    # Create a very simple chunker
    chunker = VerySimpleChunker(
        target_size=1000,
        min_size=100
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
