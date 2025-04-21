#!/usr/bin/env python3
"""
Final simple chunker that combines line-based chunking with basic markdown awareness.

This module provides a simple chunker that:
1. Creates non-overlapping chunks of approximately fixed size
2. Tries to break at paragraph or line boundaries
3. Ensures chunks are at least a minimum size
4. Has basic awareness of markdown headings
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class FinalSimpleChunker(BaseChunker):
    """
    Final simple chunker that combines line-based chunking with basic markdown awareness.
    """

    def __init__(self, 
                 chunk_size: int = 1000, 
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the final simple chunker.

        Args:
            chunk_size: Size of chunks in characters
            min_chunk_size: Minimum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk_size = min_chunk_size
        
        # Regex pattern for markdown headings
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.*?)(?:\s+\{#.*\})?\s*$')
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks with basic markdown awareness.

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
        current_heading = None
        current_heading_level = 0
        
        for line in lines:
            # Check if this line is a heading
            heading_match = self.heading_pattern.match(line.strip())
            if heading_match:
                # If we have content in the current chunk, finish it
                if current_chunk_lines and current_chunk_size >= min_chunk_size:
                    chunk = self._create_chunk(
                        current_chunk_lines, 
                        chunk_number, 
                        current_heading, 
                        current_heading_level, 
                        chunks, 
                        metadata
                    )
                    chunks.append(chunk)
                    chunk_number += 1
                    current_chunk_lines = []
                    current_chunk_size = 0
                
                # Update current heading
                current_heading = heading_match.group(2)
                current_heading_level = len(heading_match.group(1))
            
            line_size = len(line) + 1  # +1 for the newline
            
            # If adding this line would exceed chunk_size and we already have content,
            # finish the current chunk
            if current_chunk_lines and current_chunk_size + line_size > chunk_size and current_chunk_size >= min_chunk_size:
                chunk = self._create_chunk(
                    current_chunk_lines, 
                    chunk_number, 
                    current_heading, 
                    current_heading_level, 
                    chunks, 
                    metadata
                )
                chunks.append(chunk)
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
            chunk = self._create_chunk(
                current_chunk_lines, 
                chunk_number, 
                current_heading, 
                current_heading_level, 
                chunks, 
                metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(self, 
                      lines: List[str], 
                      chunk_number: int, 
                      heading: Optional[str], 
                      heading_level: int, 
                      existing_chunks: List[Chunk], 
                      metadata: Dict[str, Any]) -> Chunk:
        """
        Create a chunk from the given lines.
        
        Args:
            lines: The lines to include in the chunk
            chunk_number: The number of this chunk
            heading: The current heading (if any)
            heading_level: The level of the current heading
            existing_chunks: The chunks created so far
            metadata: The base metadata
            
        Returns:
            A new Chunk object
        """
        chunk_text = '\n'.join(lines)
        
        # Create chunk metadata
        chunk_metadata = metadata.copy()
        chunk_metadata.update({
            'chunk_number': chunk_number,
            'chunk_type': 'markdown' if heading else 'text',
            'heading_title': heading,
            'heading_level': heading_level,
            'char_length': len(chunk_text)
        })
        
        # Calculate line numbers
        if existing_chunks:
            start_line = existing_chunks[-1].metadata['end_line'] + 1
        else:
            start_line = 1
        end_line = start_line + len(lines) - 1
        chunk_metadata.update({
            'start_line': start_line,
            'end_line': end_line
        })
        
        return Chunk(text=chunk_text, metadata=chunk_metadata)

def main():
    """Main function to demonstrate the final simple chunker."""
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
    
    # Create a final simple chunker
    chunker = FinalSimpleChunker(
        chunk_size=1000,
        min_chunk_size=100
    )
    
    # Chunk the text
    chunks = chunker.chunk(text, metadata=metadata)
    
    # Print the chunks
    print(f"\nFound {len(chunks)} chunks in the text:\n")
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Heading: {chunk.metadata.get('heading_title')}")
        print(f"  Level: {chunk.metadata.get('heading_level')}")
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
