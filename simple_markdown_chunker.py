#!/usr/bin/env python3
"""
Simple markdown chunker that uses the simple text chunker.

This module provides a simple markdown chunker that:
1. Splits markdown text based on headings
2. Uses the simple text chunker for sections that are too large
3. Ensures chunks are at least a minimum size
4. Never breaks words in the middle
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk
from simple_text_chunker import SimpleTextChunker

class SimpleMarkdownChunker(BaseChunker):
    """
    Simple markdown chunker that uses the simple text chunker.
    """

    def __init__(self,
                 max_level: int = 3,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 2000,
                 include_heading_in_chunk: bool = True,
                 **kwargs):
        """
        Initialize the simple markdown chunker.

        Args:
            max_level: Maximum heading level to consider (1-6)
            min_chunk_size: Minimum size of a chunk in characters
            max_chunk_size: Maximum size of a chunk in characters
            include_heading_in_chunk: Whether to include the heading in the chunk text
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.max_level = max(1, min(6, max_level))  # Ensure between 1-6
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.include_heading_in_chunk = include_heading_in_chunk

        # Fallback chunker for large sections or when no headings are found
        self.text_chunker = SimpleTextChunker(
            chunk_size=max_chunk_size,
            min_chunk_size=min_chunk_size
        )

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split markdown text into chunks based on headings.

        Args:
            text: The markdown text to chunk
            metadata: Dictionary with contextual information about the text (e.g., file name, source)
                     This will be enhanced with chunk-specific information
            **kwargs: Additional parameters (can override instance parameters)

        Returns:
            List of Chunk objects
        """
        if not text:
            return []

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Override parameters if provided
        max_level = kwargs.get('max_level', self.max_level)
        min_chunk_size = kwargs.get('min_chunk_size', self.min_chunk_size)
        max_chunk_size = kwargs.get('max_chunk_size', self.max_chunk_size)
        include_heading = kwargs.get('include_heading_in_chunk', self.include_heading_in_chunk)

        # Find all headings in the text
        # This regex matches both ATX headings (# Heading) and Setext headings (Heading\n====)
        heading_pattern = r'(?:^|\n)(?:#{1,6} .+?|.+?\n[=-]{2,})(?:\n|$)'
        headings = list(re.finditer(heading_pattern, text))

        # If no headings found, use the simple text chunker
        if not headings:
            return self.text_chunker.chunk(
                text,
                metadata=metadata,
                chunk_size=max_chunk_size,
                min_chunk_size=min_chunk_size
            )

        # Extract heading information
        heading_info = []
        for match in headings:
            heading_text = match.group(0).strip()
            start_pos = match.start()

            # Determine heading level
            if heading_text.startswith('#'):
                # ATX heading
                level = len(heading_text) - len(heading_text.lstrip('#'))
                title = heading_text[level:].strip()
            else:
                # Setext heading
                lines = heading_text.split('\n')
                title = lines[0].strip()
                level = 1 if '=' in lines[1] else 2  # = for h1, - for h2

            # Only include headings up to max_level
            if level <= max_level:
                heading_info.append({
                    'text': heading_text,
                    'title': title,
                    'level': level,
                    'start': start_pos,
                    'end': match.end()
                })

        # Sort headings by position
        heading_info.sort(key=lambda h: h['start'])

        # Create chunks based on headings
        chunks = []

        # Add text before first heading if it exists
        if heading_info and heading_info[0]['start'] > 0:
            intro_text = text[:heading_info[0]['start']].strip()
            if intro_text:
                # Use the text chunker if the intro is too large
                if len(intro_text) > max_chunk_size:
                    intro_metadata = metadata.copy()
                    intro_metadata.update({
                        'heading_level': 0,
                        'heading_title': 'Introduction',
                        'chunk_type': 'markdown_intro'
                    })
                    
                    intro_chunks = self.text_chunker.chunk(
                        intro_text,
                        metadata=intro_metadata,
                        chunk_size=max_chunk_size,
                        min_chunk_size=min_chunk_size
                    )
                    chunks.extend(intro_chunks)
                elif len(intro_text) >= min_chunk_size:
                    # Create a copy of the base metadata and enhance it
                    intro_metadata = metadata.copy()
                    intro_metadata.update({
                        'chunk_number': 0,
                        'heading_level': 0,
                        'heading_title': 'Introduction',
                        'chunk_type': 'markdown',
                        'start_char': 0,
                        'end_char': heading_info[0]['start'],
                        'char_length': len(intro_text)
                    })

                    # Add line numbers if available
                    if '\n' in intro_text:
                        intro_metadata.update({
                            'start_line': 1,
                            'end_line': intro_text.count('\n') + 1
                        })

                    chunks.append(Chunk(text=intro_text, metadata=intro_metadata))

        # Process each heading and its content
        for i, heading in enumerate(heading_info):
            # Determine the end of this section
            if i < len(heading_info) - 1:
                section_end = heading_info[i + 1]['start']
            else:
                section_end = len(text)

            # Extract section text
            if include_heading:
                section_text = text[heading['start']:section_end].strip()
                section_start = heading['start']
            else:
                section_text = text[heading['end']:section_end].strip()
                section_start = heading['end']

            # Skip empty sections
            if not section_text:
                continue

            # If section is too large, sub-chunk it
            if len(section_text) > max_chunk_size:
                # Create sub-chunks with enhanced metadata
                sub_metadata = metadata.copy()
                sub_metadata.update({
                    'heading_level': heading['level'],
                    'heading_title': heading['title'],
                    'parent_chunk_number': i,
                    'chunk_type': 'markdown_sub'
                })

                sub_chunks = self.text_chunker.chunk(
                    section_text,
                    metadata=sub_metadata,
                    chunk_size=max_chunk_size,
                    min_chunk_size=min_chunk_size
                )

                # Add heading information to each sub-chunk
                for j, sub_chunk in enumerate(sub_chunks):
                    # Update the chunk type
                    sub_chunk.metadata['sub_chunk_number'] = j

                    # Adjust character positions to be relative to the whole document
                    if 'start_char' in sub_chunk.metadata:
                        sub_chunk.metadata['start_char'] += section_start
                    if 'end_char' in sub_chunk.metadata:
                        sub_chunk.metadata['end_char'] += section_start

                    # Adjust line numbers if available
                    if 'start_line' in sub_chunk.metadata and '\n' in text[:section_start]:
                        line_offset = text[:section_start].count('\n')
                        sub_chunk.metadata['start_line'] += line_offset
                        if 'end_line' in sub_chunk.metadata:
                            sub_chunk.metadata['end_line'] += line_offset

                    chunks.append(sub_chunk)
            else:
                # Only add as a chunk if it meets minimum size
                if len(section_text) >= min_chunk_size:
                    # Create a copy of the base metadata and enhance it
                    section_metadata = metadata.copy()
                    section_metadata.update({
                        'chunk_number': i,
                        'heading_level': heading['level'],
                        'heading_title': heading['title'],
                        'chunk_type': 'markdown',
                        'start_char': section_start,
                        'end_char': section_end,
                        'char_length': len(section_text)
                    })

                    # Add line numbers if available
                    if '\n' in text[:section_start]:
                        start_line = text[:section_start].count('\n') + 1
                        end_line = start_line + section_text.count('\n')
                        section_metadata.update({
                            'start_line': start_line,
                            'end_line': end_line
                        })

                    chunks.append(Chunk(text=section_text, metadata=section_metadata))

        # If we have no chunks (unlikely but possible), fall back to the text chunker
        if not chunks:
            return self.text_chunker.chunk(
                text,
                metadata=metadata,
                chunk_size=max_chunk_size,
                min_chunk_size=min_chunk_size
            )
        
        # Renumber the chunks
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_number'] = i
        
        return chunks

def main():
    """Main function to demonstrate the simple markdown chunker."""
    # Path to the example.md file
    example_file_path = 'localknowledge/textprocessing/chunking/tests/Example.md'
    
    # Read the example.md file
    with open(example_file_path, 'r', encoding='utf-8') as f:
        markdown_text = f.read()
    
    # Create metadata
    metadata = {
        'file_name': 'Example.md',
        'source': 'Test',
        'document_type': 'markdown'
    }
    
    # Create a simple markdown chunker
    chunker = SimpleMarkdownChunker(
        max_level=3,
        min_chunk_size=100,
        max_chunk_size=1000,
        include_heading_in_chunk=True
    )
    
    # Chunk the markdown text
    chunks = chunker.chunk(markdown_text, metadata=metadata)
    
    # Print the chunks
    print(f"\nFound {len(chunks)} chunks in the markdown text:\n")
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Heading: {chunk.metadata.get('heading_title')}")
        print(f"  Level: {chunk.metadata.get('heading_level')}")
        print(f"  Type: {chunk.metadata.get('chunk_type')}")
        print(f"  Text length: {len(chunk.text)} characters")
        print(f"  Text preview: {chunk.text[:100]}...")
        print()

if __name__ == "__main__":
    main()
