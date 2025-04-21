#!/usr/bin/env python3
"""
Improved text chunker that respects minimum chunk size.

This script demonstrates an improved text chunker that respects a minimum chunk size
and properly handles small chunks by combining them when necessary.
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk

class ImprovedTextChunker(BaseChunker):
    """
    Improved text chunker that respects minimum chunk size.
    """

    def __init__(self,
                 chunk_size: int = 1000,
                 min_chunk_size: int = 100,
                 overlap: int = 200,
                 **kwargs):
        """
        Initialize the improved text chunker.

        Args:
            chunk_size: Maximum size of each chunk in characters
            min_chunk_size: Minimum size of a chunk in characters
            overlap: Number of characters to overlap between chunks
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks based on character count, respecting minimum chunk size.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text
            **kwargs: Additional parameters (can override chunk_size, min_chunk_size, and overlap)

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
        overlap = kwargs.get('overlap', self.overlap)

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

        # Simple chunking by character count
        chunks = []
        start = 0
        chunk_number = 0

        # Calculate how many chunks we'll need (approximately)
        # This helps us avoid creating too many small chunks
        effective_chunk_size = chunk_size - overlap
        if effective_chunk_size <= 0:
            effective_chunk_size = chunk_size // 2  # Ensure we make progress

        total_chunks_needed = max(1, len(text) // effective_chunk_size)

        # Adjust chunk size if we'd end up with too many small chunks at the end
        remaining_size = len(text) % effective_chunk_size
        if 0 < remaining_size < min_chunk_size:
            # Distribute the remainder among all chunks
            effective_chunk_size += remaining_size // total_chunks_needed

        while start < len(text):
            # Check if we're near the end of the text
            remaining_text = len(text) - start

            # If the remaining text is smaller than min_chunk_size and we already have chunks,
            # append it to the previous chunk
            if remaining_text < min_chunk_size and chunks:
                prev_chunk = chunks[-1]
                prev_chunk.text += text[start:]
                prev_chunk.metadata['end_char'] = len(text)
                prev_chunk.metadata['char_length'] = len(prev_chunk.text)

                # Update line numbers if available
                if 'end_line' in prev_chunk.metadata:
                    prev_chunk.metadata['end_line'] += text[start:].count('\n')

                break

            # Calculate end position
            end = min(start + chunk_size, len(text))

            # First, ensure we don't break in the middle of a word
            # If we're not at the end of the text, adjust end to a word boundary
            if end < len(text):
                # Check if we're in the middle of a word
                if end < len(text) and text[end-1].isalnum() and text[end].isalnum():
                    # Find the nearest word boundary (space, punctuation, or newline)
                    word_boundaries = []

                    # Look for spaces
                    space_pos = text.rfind(' ', start, end)
                    if space_pos > start:
                        word_boundaries.append(space_pos + 1)  # Include the space

                    # Look for punctuation followed by space or newline
                    for punct in ['.', '!', '?', ',', ';', ':', '-']:
                        for suffix in [' ', '\n']:
                            pos = text.rfind(punct + suffix, start, end)
                            if pos > start:
                                word_boundaries.append(pos + len(punct + suffix))  # Include the punctuation and suffix

                    # Look for newlines
                    newline_pos = text.rfind('\n', start, end)
                    if newline_pos > start:
                        word_boundaries.append(newline_pos + 1)  # Include the newline

                    # Find the last valid word boundary
                    if word_boundaries:
                        end = max(word_boundaries)

            # Now try to end at a sentence boundary for better semantic coherence
            # Look for sentence boundaries (., !, ?) followed by space or newline
            sentence_boundaries = []

            # Check for sentence-ending punctuation followed by space or newline
            for punct in ['.', '!', '?']:
                for suffix in [' ', '\n']:
                    pos = text.rfind(punct + suffix, start, end)
                    if pos > start:
                        sentence_boundaries.append(pos + len(punct + suffix))  # Include the punctuation and suffix

            # Also consider common punctuation that might end a paragraph
            for punct in [':', ';']:
                pos = text.rfind(punct + '\n', start, end)
                if pos > start:
                    sentence_boundaries.append(pos + len(punct + '\n'))  # Include the punctuation and newline

            # Consider paragraph breaks as potential boundaries
            para_break = text.rfind('\n\n', start, end)
            if para_break > start:
                sentence_boundaries.append(para_break + 2)  # Include both newlines

            # Find the last valid sentence boundary
            if sentence_boundaries:
                sentence_end = max(sentence_boundaries)
                # Only use the sentence boundary if it gives us enough text
                if sentence_end > start + min_chunk_size:
                    end = sentence_end

            # Final check: if we're still breaking a word, find the last space
            if end < len(text) and text[end-1].isalnum() and text[end].isalnum():
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space + 1  # Include the space

            # Create chunk with metadata
            chunk_text = text[start:end]

            # Skip creating a chunk if it's too small (unless it's the only chunk or the last chunk)
            if len(chunk_text) < min_chunk_size and start > 0 and end < len(text):
                # Move forward with a larger step to try to get a chunk of adequate size
                start += max(min_chunk_size // 2, 1)
                continue

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
            chunk_number += 1

            # Calculate next start position with overlap
            if end >= len(text):
                # We've reached the end
                break

            # Ensure we make meaningful progress
            new_start = end - overlap

            # If the overlap is too large (would cause us to stay in place or go backwards),
            # move forward by a significant amount
            if new_start <= start:
                # Move forward by at least 25% of the chunk size
                new_start = start + max(chunk_size // 4, 1)

            # If the remaining text after new_start would be smaller than min_chunk_size,
            # adjust to ensure we don't create a tiny final chunk
            if len(text) - new_start < min_chunk_size:
                # Set start to create the final chunk that includes all remaining text
                new_start = len(text) - min(chunk_size, len(text) - start)

            start = new_start

        # If we have no chunks (unlikely but possible), create at least one
        if not chunks and text:
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

            chunks.append(Chunk(text=text, metadata=chunk_metadata))

        # Post-process: check for incomplete sentences at chunk boundaries
        # and adjust if necessary
        processed_chunks = []

        for i, chunk in enumerate(chunks):
            # Skip the last chunk as it doesn't have a next chunk to check against
            if i == len(chunks) - 1:
                processed_chunks.append(chunk)
                continue

            chunk_text = chunk.text
            next_chunk_text = chunks[i+1].text

            # Check if the chunk ends with an incomplete sentence or word
            # Look for sentence-ending punctuation at the end
            chunk_text_trimmed = chunk_text.rstrip()
            ends_with_sentence = any(chunk_text_trimmed.endswith(end) for end in ['.', '!', '?', ':', ';'])
            ends_with_paragraph = '\n\n' in chunk_text[-4:] if len(chunk_text) >= 4 else False

            # Check if we're breaking a word
            breaking_word = False
            if chunk_text and next_chunk_text:
                last_char = chunk_text[-1]
                first_char = next_chunk_text[0]
                if last_char.isalnum() and first_char.isalnum():
                    breaking_word = True

            if breaking_word or (not ends_with_sentence and not ends_with_paragraph):
                # We need to fix the boundary
                if breaking_word:
                    # Find the next word boundary in the next chunk
                    next_space = next_chunk_text.find(' ')
                    next_newline = next_chunk_text.find('\n')

                    # Use the nearest boundary
                    if next_space == -1 and next_newline == -1:
                        # No boundary found, use the whole next chunk
                        boundary = len(next_chunk_text)
                    elif next_space == -1:
                        boundary = next_newline
                    elif next_newline == -1:
                        boundary = next_space
                    else:
                        boundary = min(next_space, next_newline)

                    # Move this partial word to the current chunk
                    partial_text = next_chunk_text[:boundary+1]  # Include the boundary

                    # Update the current chunk
                    chunk.text += partial_text
                    chunk.metadata['end_char'] += len(partial_text)
                    chunk.metadata['char_length'] = len(chunk.text)

                    # Update the next chunk
                    chunks[i+1].text = next_chunk_text[boundary+1:]
                    chunks[i+1].metadata['start_char'] += len(partial_text)
                    chunks[i+1].metadata['char_length'] = len(chunks[i+1].text)

                    # Update line numbers if available
                    if 'end_line' in chunk.metadata:
                        lines_added = partial_text.count('\n')
                        if lines_added > 0:
                            chunk.metadata['end_line'] += lines_added
                            if 'start_line' in chunks[i+1].metadata:
                                chunks[i+1].metadata['start_line'] += lines_added
                else:
                    # Find the next sentence boundary in the next chunk
                    sentence_end = -1
                    for j, char in enumerate(next_chunk_text):
                        if j > 0 and char in ['.', '!', '?'] and j+1 < len(next_chunk_text) and next_chunk_text[j+1] in [' ', '\n']:
                            # Found a sentence boundary
                            sentence_end = j
                            break

                    # If no sentence boundary found, look for paragraph breaks
                    if sentence_end == -1:
                        para_break = next_chunk_text.find('\n\n')
                        if para_break != -1:
                            sentence_end = para_break + 1  # Include both newlines

                    # If we found a boundary, adjust the chunks
                    if sentence_end != -1:
                        # Move this partial sentence to the current chunk
                        partial_sentence = next_chunk_text[:sentence_end+2]  # Include the punctuation and space/newline

                        # Update the current chunk
                        chunk.text += partial_sentence
                        chunk.metadata['end_char'] += len(partial_sentence)
                        chunk.metadata['char_length'] = len(chunk.text)

                        # Update the next chunk
                        chunks[i+1].text = next_chunk_text[sentence_end+2:]
                        chunks[i+1].metadata['start_char'] += len(partial_sentence)
                        chunks[i+1].metadata['char_length'] = len(chunks[i+1].text)

                        # Update line numbers if available
                        if 'end_line' in chunk.metadata:
                            lines_added = partial_sentence.count('\n')
                            if lines_added > 0:
                                chunk.metadata['end_line'] += lines_added
                                if 'start_line' in chunks[i+1].metadata:
                                    chunks[i+1].metadata['start_line'] += lines_added

            processed_chunks.append(chunk)

        # Add the last chunk if it wasn't already added
        if chunks and chunks[-1] not in processed_chunks:
            processed_chunks.append(chunks[-1])

        # Renumber the chunks
        for i, chunk in enumerate(processed_chunks):
            chunk.metadata['chunk_number'] = i

        return processed_chunks

def main():
    """Main function to demonstrate the improved text chunker."""
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

    # Create an improved text chunker
    chunker = ImprovedTextChunker(
        chunk_size=1000,
        min_chunk_size=100,
        overlap=200
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
