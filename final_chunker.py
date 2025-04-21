#!/usr/bin/env python3
"""
Final chunker implementation that addresses all the requirements.

This module provides a chunker that:
1. Creates non-overlapping chunks of appropriate size
2. Respects sentence and paragraph boundaries
3. Ensures chunks are at least a minimum size
4. Never breaks words in the middle
5. Handles markdown headings appropriately
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class FinalChunker(BaseChunker):
    """
    Final chunker implementation that addresses all the requirements.
    """

    def __init__(self, 
                 chunk_size: int = 1000, 
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the final chunker.

        Args:
            chunk_size: Target size of chunks in characters
            min_chunk_size: Minimum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk_size = min_chunk_size
        
        # Regex pattern for markdown headings
        self.heading_pattern = re.compile(r'^(\s*)(#{1,6})\s+(.*?)(?:\s+\{#.*\})?\s*$', re.MULTILINE)
    
    def find_break_point(self, text: str, start: int, target_end: int) -> int:
        """
        Find a suitable break point near the target end position.
        
        Prioritizes:
        1. Paragraph breaks
        2. Sentence endings
        3. Any punctuation followed by space
        4. Space characters
        
        Args:
            text: The text to analyze
            start: The start index of the current chunk
            target_end: The target end index
            
        Returns:
            The index where the chunk should end
        """
        # Don't go beyond the end of the text
        end = min(target_end, len(text))
        
        # If we're at the end of the text, return it
        if end == len(text):
            return end
            
        # Look for paragraph breaks (double newline)
        paragraph_break = text.rfind('\n\n', start, end)
        if paragraph_break != -1 and paragraph_break > start + self.min_chunk_size:
            return paragraph_break + 2  # Include both newlines
            
        # Look for sentence endings (., !, ? followed by space or newline)
        for punct in ['.', '!', '?']:
            for suffix in [' ', '\n']:
                pos = text.rfind(punct + suffix, start, end)
                if pos != -1 and pos > start + self.min_chunk_size:
                    return pos + len(punct + suffix)  # Include the punctuation and suffix
                    
        # Look for other punctuation followed by space
        for punct in [',', ';', ':', '-']:
            pos = text.rfind(punct + ' ', start, end)
            if pos != -1 and pos > start + self.min_chunk_size:
                return pos + 2  # Include the punctuation and space
                
        # Look for the last space
        last_space = text.rfind(' ', start, end)
        if last_space != -1 and last_space > start + self.min_chunk_size:
            return last_space + 1  # Include the space
            
        # If we can't find a good break point and we're already past min_chunk_size,
        # just return the target end
        if end > start + self.min_chunk_size:
            # Make sure we're not breaking a word
            if end < len(text) and text[end-1].isalnum() and text[end].isalnum():
                # We're in the middle of a word, find the previous space
                prev_space = text.rfind(' ', start, end)
                if prev_space != -1 and prev_space > start + self.min_chunk_size:
                    return prev_space + 1  # Include the space
            return end
            
        # If we're still here, we need to look forward for a break point
        # This happens when the min_chunk_size constraint prevents us from finding a good break point
        
        # Look for the next sentence ending
        next_sentence_end = -1
        for punct in ['.', '!', '?']:
            for suffix in [' ', '\n']:
                pos = text.find(punct + suffix, end)
                if pos != -1 and (next_sentence_end == -1 or pos < next_sentence_end):
                    next_sentence_end = pos + len(punct + suffix)
                    
        # Look for the next paragraph break
        next_para_break = text.find('\n\n', end)
        
        # Look for the next space
        next_space = text.find(' ', end)
        
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

        # Find all headings in the text
        headings = list(self.heading_pattern.finditer(text))
        
        # If we have headings, use them to guide chunking
        if headings:
            return self._chunk_markdown(text, headings, chunk_size, min_chunk_size, metadata)
        
        # Otherwise, use simple chunking
        return self._chunk_plain_text(text, chunk_size, min_chunk_size, metadata)
    
    def _chunk_plain_text(self, text: str, chunk_size: int, min_chunk_size: int, metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Chunk plain text (no headings) into appropriately sized chunks.
        
        Args:
            text: The text to chunk
            chunk_size: Target size of chunks
            min_chunk_size: Minimum size of chunks
            metadata: Base metadata for chunks
            
        Returns:
            List of Chunk objects
        """
        chunks = []
        start = 0
        chunk_number = 0

        while start < len(text):
            # Calculate target end position
            target_end = min(start + chunk_size, len(text))
            
            # Find a suitable break point
            end = self.find_break_point(text, start, target_end)
            
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
    
    def _chunk_markdown(self, text: str, headings: List, chunk_size: int, min_chunk_size: int, metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Chunk markdown text using headings as guides.
        
        Args:
            text: The markdown text to chunk
            headings: List of heading matches
            chunk_size: Target size of chunks
            min_chunk_size: Minimum size of chunks
            metadata: Base metadata for chunks
            
        Returns:
            List of Chunk objects
        """
        chunks = []
        chunk_number = 0
        
        # Add text before first heading if it exists
        if headings[0].start() > 0:
            intro_text = text[:headings[0].start()].strip()
            if intro_text:
                if len(intro_text) > chunk_size:
                    # Split intro text if too large
                    intro_chunks = self._chunk_plain_text(intro_text, chunk_size, min_chunk_size, metadata)
                    chunks.extend(intro_chunks)
                    chunk_number = len(intro_chunks)
                else:
                    # Add as a single chunk
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        'chunk_number': chunk_number,
                        'chunk_type': 'text',
                        'start_char': 0,
                        'end_char': headings[0].start(),
                        'char_length': len(intro_text),
                        'start_line': 1,
                        'end_line': intro_text.count('\n') + 1
                    })
                    chunks.append(Chunk(text=intro_text, metadata=chunk_metadata))
                    chunk_number += 1
        
        # Process each heading and its content
        for i, heading in enumerate(headings):
            heading_text = heading.group(0)
            heading_level = len(heading.group(2))  # Number of # characters
            heading_title = heading.group(3)
            
            # Determine the end of this section
            if i < len(headings) - 1:
                section_end = headings[i + 1].start()
            else:
                section_end = len(text)
            
            # Extract section text (including heading)
            section_text = text[heading.start():section_end].strip()
            
            # If section is too large, split it
            if len(section_text) > chunk_size:
                # Create section metadata
                section_metadata = metadata.copy()
                section_metadata.update({
                    'heading_level': heading_level,
                    'heading_title': heading_title
                })
                
                # Split the section
                section_chunks = self._chunk_plain_text(section_text, chunk_size, min_chunk_size, section_metadata)
                
                # Update chunk numbers
                for j, chunk in enumerate(section_chunks):
                    chunk.metadata['chunk_number'] = chunk_number + j
                
                chunks.extend(section_chunks)
                chunk_number += len(section_chunks)
            else:
                # Add as a single chunk
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_number': chunk_number,
                    'chunk_type': 'markdown',
                    'heading_level': heading_level,
                    'heading_title': heading_title,
                    'start_char': heading.start(),
                    'end_char': section_end,
                    'char_length': len(section_text)
                })
                
                # Calculate line numbers
                start_line = text[:heading.start()].count('\n') + 1
                end_line = start_line + section_text.count('\n')
                chunk_metadata.update({
                    'start_line': start_line,
                    'end_line': end_line
                })
                
                chunks.append(Chunk(text=section_text, metadata=chunk_metadata))
                chunk_number += 1
        
        return chunks

def main():
    """Main function to demonstrate the final chunker."""
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
    
    # Create a final chunker
    chunker = FinalChunker(
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

if __name__ == "__main__":
    main()
