#!/usr/bin/env python3
"""
Simplified markdown chunker based on the experimental implementation.

This module provides a simplified version of the markdown chunker that:
1. Chunks markdown text based on headings
2. Ensures chunks are within size constraints
3. Preserves the structure of the document
4. Avoids breaking words or sentences
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class SimplifiedMarkdownChunker(BaseChunker):
    """
    Simplified markdown chunker based on the experimental implementation.
    """

    def __init__(self, 
                 min_size: int = 100, 
                 max_size: int = 1000,
                 **kwargs):
        """
        Initialize the simplified markdown chunker.

        Args:
            min_size: Minimum size of chunks in characters
            max_size: Maximum size of chunks in characters
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.min_size = min_size
        self.max_size = max_size
        
        # Regex patterns
        self.heading_pattern = re.compile(r'^(\s*)(#{1,6})\s+(.*?)(?:\s+\{#.*\})?\s*$', re.MULTILINE)
        self.sentence_pattern = re.compile(r'(?<=[.!?])\s+')
    
    def _get_heading_level(self, match) -> int:
        """Get the level of a heading from a regex match."""
        return len(match.group(2))
    
    def _split_text_by_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs (separated by blank lines)."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p for p in paragraphs if p.strip()]
    
    def _split_paragraph_by_sentences(self, paragraph: str) -> List[str]:
        """Split a paragraph into sentences."""
        sentences = self.sentence_pattern.split(paragraph)
        
        # Reconstruct sentences with proper endings
        result = []
        start_idx = 0
        for sentence in sentences:
            # Find where this sentence appears in the original paragraph
            sentence_start = paragraph.find(sentence, start_idx)
            if sentence_start == -1:
                result.append(sentence)  # Fallback
                continue
                
            # Find the end of this sentence (including punctuation)
            sentence_end = sentence_start + len(sentence)
            while sentence_end < len(paragraph) and paragraph[sentence_end] in ".!?":
                sentence_end += 1
            
            # Extract the complete sentence with punctuation
            complete_sentence = paragraph[sentence_start:sentence_end]
            if sentence_end < len(paragraph) and paragraph[sentence_end].isspace():
                complete_sentence += " "  # Add space if it exists
                
            result.append(complete_sentence)
            start_idx = sentence_end
            
        return result
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split markdown text into chunks based on headings and size constraints.

        Args:
            text: The markdown text to chunk
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

        # Get raw text chunks
        raw_chunks = self._chunk_markdown(text, min_size, max_size)
        
        # Convert to Chunk objects with metadata
        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            # Create a copy of the base metadata and enhance it
            chunk_metadata = metadata.copy()
            
            # Extract heading if present
            heading_match = self.heading_pattern.search(chunk_text)
            heading_level = 0
            heading_title = None
            
            if heading_match:
                heading_level = self._get_heading_level(heading_match)
                heading_title = heading_match.group(3)
            
            chunk_metadata.update({
                'chunk_number': i,
                'heading_level': heading_level,
                'heading_title': heading_title,
                'chunk_type': 'markdown',
                'char_length': len(chunk_text)
            })
            
            # Add line numbers if possible
            if i > 0 and 'end_line' in chunks[i-1].metadata:
                start_line = chunks[i-1].metadata['end_line'] + 1
                end_line = start_line + chunk_text.count('\n')
                chunk_metadata.update({
                    'start_line': start_line,
                    'end_line': end_line
                })
            elif i == 0:
                chunk_metadata.update({
                    'start_line': 1,
                    'end_line': chunk_text.count('\n') + 1
                })
            
            chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))
        
        return chunks
    
    def _chunk_markdown(self, text: str, min_size: int, max_size: int) -> List[str]:
        """
        Chunk the markdown text according to headings and size constraints.
        
        Args:
            text: The markdown text to chunk
            min_size: Minimum size of chunks
            max_size: Maximum size of chunks
            
        Returns:
            List of text chunks
        """
        # Find all headings in the text
        headings = list(self.heading_pattern.finditer(text))
        
        # If no headings, treat as plain text
        if not headings:
            return self._chunk_plain_text(text, min_size, max_size)
        
        # Create chunks based on headings
        chunks = []
        current_chunk = ""
        
        # Add text before first heading if it exists
        if headings[0].start() > 0:
            intro_text = text[:headings[0].start()].strip()
            if intro_text:
                if len(intro_text) > max_size:
                    # Split intro text if too large
                    intro_chunks = self._chunk_plain_text(intro_text, min_size, max_size)
                    chunks.extend(intro_chunks)
                else:
                    chunks.append(intro_text)
        
        # Process each heading and its content
        for i, heading in enumerate(headings):
            heading_text = heading.group(0)
            heading_level = self._get_heading_level(heading)
            
            # Determine the end of this section
            if i < len(headings) - 1:
                section_end = headings[i + 1].start()
            else:
                section_end = len(text)
            
            # Extract section text (including heading)
            section_text = text[heading.start():section_end].strip()
            
            # If section is too large, split it
            if len(section_text) > max_size:
                # Always include the heading in our chunk
                section_chunks = self._chunk_section(section_text, heading_text, min_size, max_size)
                chunks.extend(section_chunks)
            else:
                # Add as a single chunk
                chunks.append(section_text)
        
        # Combine small chunks where possible
        return self._combine_small_chunks(chunks, min_size, max_size)
    
    def _chunk_plain_text(self, text: str, min_size: int, max_size: int) -> List[str]:
        """
        Chunk plain text (no headings) into appropriately sized chunks.
        
        Args:
            text: The text to chunk
            min_size: Minimum size of chunks
            max_size: Maximum size of chunks
            
        Returns:
            List of text chunks
        """
        # If text is small enough, return as a single chunk
        if len(text) <= max_size:
            return [text]
        
        # Split text into paragraphs
        paragraphs = self._split_text_by_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If paragraph alone exceeds max_size, split it by sentences
            if len(paragraph) > max_size:
                # Finish current chunk if not empty
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # Split paragraph into sentences
                sentences = self._split_paragraph_by_sentences(paragraph)
                
                # Process sentences
                for sentence in sentences:
                    if len(sentence) > max_size:
                        # Even a single sentence is too large, have to split arbitrarily
                        # First add current chunk if not empty
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = ""
                        
                        # Split the sentence into chunks of max_size
                        for i in range(0, len(sentence), max_size):
                            chunks.append(sentence[i:i+max_size])
                    elif len(current_chunk) + len(sentence) <= max_size:
                        # Add to current chunk
                        separator = "\n\n" if current_chunk and not current_chunk.endswith("\n") else ""
                        current_chunk += separator + sentence
                    else:
                        # Finish current chunk and start a new one
                        chunks.append(current_chunk)
                        current_chunk = sentence
            else:
                # Check if paragraph fits in current chunk
                separator = "\n\n" if current_chunk and not current_chunk.endswith("\n") else ""
                if len(current_chunk) + len(separator) + len(paragraph) <= max_size:
                    # Add to current chunk
                    current_chunk += separator + paragraph
                else:
                    # Finish current chunk and start a new one
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = paragraph
        
        # Add the final chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _chunk_section(self, section_text: str, heading_text: str, min_size: int, max_size: int) -> List[str]:
        """
        Chunk a section that's too large, ensuring the heading is preserved.
        
        Args:
            section_text: The section text (including heading)
            heading_text: The heading text
            min_size: Minimum size of chunks
            max_size: Maximum size of chunks
            
        Returns:
            List of text chunks
        """
        # Remove heading from content
        content = section_text[len(heading_text):].strip()
        
        # Split content into paragraphs
        paragraphs = self._split_text_by_paragraphs(content)
        
        chunks = []
        current_chunk = heading_text
        
        for paragraph in paragraphs:
            # If paragraph alone exceeds max_size, split it by sentences
            if len(paragraph) > max_size:
                # Finish current chunk if it has content beyond the heading
                if current_chunk != heading_text:
                    chunks.append(current_chunk)
                    current_chunk = heading_text
                
                # Split paragraph into sentences
                sentences = self._split_paragraph_by_sentences(paragraph)
                
                # Process sentences
                for sentence in sentences:
                    separator = "\n\n" if current_chunk == heading_text else "\n"
                    
                    if len(current_chunk) + len(separator) + len(sentence) <= max_size:
                        # Add to current chunk
                        current_chunk += separator + sentence
                    else:
                        # Finish current chunk and start a new one with the heading
                        chunks.append(current_chunk)
                        current_chunk = heading_text + "\n\n" + sentence
            else:
                # Check if paragraph fits in current chunk
                separator = "\n\n" if current_chunk == heading_text else "\n"
                if len(current_chunk) + len(separator) + len(paragraph) <= max_size:
                    # Add to current chunk
                    current_chunk += separator + paragraph
                else:
                    # Finish current chunk and start a new one with the heading
                    chunks.append(current_chunk)
                    current_chunk = heading_text + "\n\n" + paragraph
        
        # Add the final chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _combine_small_chunks(self, chunks: List[str], min_size: int, max_size: int) -> List[str]:
        """
        Combine small chunks where possible.
        
        Args:
            chunks: List of text chunks
            min_size: Minimum size of chunks
            max_size: Maximum size of chunks
            
        Returns:
            List of text chunks with small chunks combined where possible
        """
        if not chunks:
            return []
        
        result = [chunks[0]]
        
        for i in range(1, len(chunks)):
            current = chunks[i]
            
            # If current chunk is too small, try to merge with previous
            if len(current) < min_size and result:
                combined = result[-1] + "\n\n" + current
                
                if len(combined) <= max_size:
                    result[-1] = combined
                else:
                    # Couldn't merge, add as is
                    result.append(current)
            else:
                result.append(current)
        
        return result

def main():
    """Main function to demonstrate the simplified markdown chunker."""
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
    
    # Create a simplified markdown chunker
    chunker = SimplifiedMarkdownChunker(
        min_size=100,
        max_size=1000
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
