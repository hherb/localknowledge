#!/usr/bin/env python3
"""
Ultra simple chunker that just splits text into fixed-size, non-overlapping chunks.

This module provides an extremely simple chunker that:
1. Creates non-overlapping chunks of approximately fixed size
2. Tries to break at paragraph or line boundaries
3. Ensures chunks are at least a minimum size
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class UltraSimpleChunker(BaseChunker):
    """
    Ultra simple chunker that just splits text into fixed-size, non-overlapping chunks.
    """

    def __init__(self, 
                 chunk_size: int = 1000, 
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the ultra simple chunker.

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
        Split text into fixed-size, non-overlapping chunks.

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

        # Split text into lines
        lines = text.split('\n')
        
        # Create chunks
        chunks = []
        current_chunk_lines = []
        current_chunk_size = 0
        chunk_number = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for the newline
            
            # If adding this line would exceed chunk_size and we already have content,
            # finish the current chunk
            if current_chunk_lines and current_chunk_size + line_size > chunk_size and current_chunk_size >= min_chunk_size:
                # Join the lines to form the chunk text
                chunk_text = '\n'.join(current_chunk_lines)
                
                # Create chunk metadata
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_number': chunk_number,
                    'chunk_type': 'text',
                    'char_length': len(chunk_text)
                })
                
                # Calculate line numbers
                if chunks:
                    start_line = chunks[-1].metadata['end_line'] + 1
                else:
                    start_line = 1
                end_line = start_line + len(current_chunk_lines) - 1
                chunk_metadata.update({
                    'start_line': start_line,
                    'end_line': end_line
                })
                
                chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))
                chunk_number += 1
                
                # Start a new chunk
                current_chunk_lines = [line]
                current_chunk_size = line_size
            else:
                # Add to current chunk
                current_chunk_lines.append(line)
                current_chunk_size += line_size
        
        # Add the final chunk if it has content
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            
            # Create chunk metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'chunk_type': 'text',
                'char_length': len(chunk_text)
            })
            
            # Calculate line numbers
            if chunks:
                start_line = chunks[-1].metadata['end_line'] + 1
            else:
                start_line = 1
            end_line = start_line + len(current_chunk_lines) - 1
            chunk_metadata.update({
                'start_line': start_line,
                'end_line': end_line
            })
            
            chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))
        
        return chunks

def main():
    """Main function to demonstrate the ultra simple chunker."""
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
    
    # Create an ultra simple chunker
    chunker = UltraSimpleChunker(
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
        
    # Check for overlapping content
    print("\nChecking for overlapping content...")
    for i in range(len(chunks) - 1):
        chunk1 = chunks[i].text
        chunk2 = chunks[i + 1].text
        
        # Check if chunk2 starts with any significant portion of chunk1
        overlap = False
        for j in range(50, min(len(chunk1), 500), 50):  # Check overlaps of 50, 100, 150, ... characters
            if chunk2.startswith(chunk1[-j:]):
                print(f"WARNING: Chunk {i+2} starts with the last {j} characters of Chunk {i+1}")
                overlap = True
                break
        
        if not overlap:
            print(f"No significant overlap between Chunks {i+1} and {i+2}")

if __name__ == "__main__":
    main()
