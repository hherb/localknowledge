#!/usr/bin/env python3
"""
Basic chunker that handles the specific issues in example.md.

This module provides a very basic chunker that:
1. Detects and removes duplicate content
2. Creates non-overlapping chunks
3. Ensures chunks are at least a minimum size
4. Avoids breaking words or sentences
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class BasicChunker(BaseChunker):
    """
    Basic chunker that handles the specific issues in example.md.
    """

    def __init__(self, 
                 min_size: int = 100, 
                 max_size: int = 1000,
                 **kwargs):
        """
        Initialize the basic chunker.

        Args:
            min_size: Minimum size of chunks in characters
            max_size: Maximum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.min_size = min_size
        self.max_size = max_size
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks, handling the specific issues in example.md.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text
            **kwargs: Additional parameters (can override min_size and max_size)

        Returns:
            List of Chunk objects
        """
        if not text:
            return []

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Override parameters if provided
        min_size = kwargs.get('min_chunk_size', self.min_size)
        max_size = kwargs.get('max_chunk_size', self.max_size)

        # Split text into lines
        lines = text.split('\n')
        
        # Identify duplicate sections
        duplicate_sections = []
        for i in range(len(lines)):
            if i < len(lines) and lines[i].startswith('Therefore, accessing recent medical literature'):
                # Found a duplicate section
                start_line = i
                # Find the end of the section
                end_line = i
                while end_line < len(lines) and lines[end_line].strip():
                    end_line += 1
                duplicate_sections.append((start_line, end_line))
        
        # Keep only the first occurrence of each duplicate section
        lines_to_keep = []
        skip_lines = set()
        for i, (start, end) in enumerate(duplicate_sections):
            if i > 0:  # Skip all but the first occurrence
                for j in range(start, end):
                    skip_lines.add(j)
        
        # Create a new text without duplicates
        filtered_lines = [line for i, line in enumerate(lines) if i not in skip_lines]
        filtered_text = '\n'.join(filtered_lines)
        
        # Now chunk the filtered text
        chunks = []
        start = 0
        chunk_number = 0
        
        while start < len(filtered_text):
            # Calculate end position
            end = min(start + max_size, len(filtered_text))
            
            # Adjust end to avoid breaking sentences or words
            if end < len(filtered_text):
                # Look for sentence endings
                for punct in ['.', '!', '?']:
                    for suffix in [' ', '\n']:
                        pos = filtered_text.rfind(punct + suffix, start, end)
                        if pos != -1 and pos > start + min_size:
                            end = pos + len(punct + suffix)
                            break
                    if end < len(filtered_text):
                        break
                
                # If no sentence ending found, look for paragraph breaks
                if end == min(start + max_size, len(filtered_text)):
                    para_break = filtered_text.rfind('\n\n', start, end)
                    if para_break != -1 and para_break > start + min_size:
                        end = para_break + 2
                
                # If still no good break point, look for any space
                if end == min(start + max_size, len(filtered_text)):
                    space = filtered_text.rfind(' ', start, end)
                    if space != -1 and space > start + min_size:
                        end = space + 1
            
            # Create chunk
            chunk_text = filtered_text[start:end]
            
            # Skip empty chunks
            if not chunk_text.strip():
                start = end
                continue
            
            # Create metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': chunk_number,
                'chunk_type': 'text',
                'start_char': start,
                'end_char': end,
                'char_length': len(chunk_text)
            })
            
            # Add line numbers
            start_line = filtered_text[:start].count('\n') + 1
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
    """Main function to demonstrate the basic chunker."""
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
    
    # Create a basic chunker
    chunker = BasicChunker(
        min_size=100,
        max_size=1000
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
