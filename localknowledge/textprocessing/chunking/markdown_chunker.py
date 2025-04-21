"""
Markdown heading-based chunker.

This module provides a chunker that splits markdown text into chunks
based on headings and subheadings, using a tree-based approach for better
semantic coherence.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk
from localknowledge.textprocessing.chunking.text_chunker import TextChunker

class MarkdownChunker(BaseChunker):
    """
    Markdown heading-based chunker.

    This chunker:
    - Creates chunks based on markdown heading structure
    - Ensures no chunk exceeds max_chunk_size
    - Tries to keep chunks above min_chunk_size unless unavoidable
    - Preserves headings with their content
    - Maintains proper metadata for each chunk
    """

    def __init__(self,
                 max_level: int = 3,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 2000,
                 include_heading_in_chunk: bool = True,
                 **kwargs):
        """
        Initialize the markdown chunker.

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

        # Regex patterns
        self.heading_pattern = re.compile(r'^(\s*)(#{1,6})\s+(.*?)(?:\s+\{#.*\})?\s*$', re.MULTILINE)
        self.sentence_pattern = re.compile(r'(?<=[.!?])\s+')

        # Fallback chunker for when no headings are found
        # Use a small overlap to avoid creating many tiny chunks
        self.text_chunker = TextChunker(chunk_size=max_chunk_size, overlap=min(50, max_chunk_size // 20))

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

    def _build_markdown_tree(self, text: str) -> Dict:
        """
        Build a tree representation of the markdown structure.

        Returns:
            Dictionary representing the markdown hierarchy
        """
        lines = text.split('\n')

        root = {
            'level': 0,
            'heading': None,
            'heading_title': None,
            'content': [],
            'children': [],
            'start_line': 1,
            'end_line': len(lines)
        }

        current_node = root
        parent_stack = []

        for i, line in enumerate(lines):
            line_number = i + 1  # 1-based line numbering
            match = self.heading_pattern.match(line)

            if match:
                # Found a heading
                indent = match.group(1)
                level = self._get_heading_level(match)
                heading_text = match.group(3)

                # If this heading is a child of current node, we go deeper
                if not parent_stack or level > parent_stack[-1]['level']:
                    parent_stack.append(current_node)

                # If this heading is at same level or higher, we go up
                else:
                    while parent_stack and level <= parent_stack[-1]['level']:
                        parent_stack.pop()

                    if not parent_stack:
                        parent_stack.append(root)

                # Update the end_line of the parent node
                if parent_stack[-1] != root:
                    parent_stack[-1]['end_line'] = line_number - 1

                # Create new node for this heading
                new_node = {
                    'level': level,
                    'heading': indent + match.group(2) + ' ' + heading_text,
                    'heading_title': heading_text,
                    'content': [],
                    'children': [],
                    'start_line': line_number,
                    'end_line': len(lines)  # Will be updated when next heading is found
                }

                parent_stack[-1]['children'].append(new_node)
                current_node = new_node
            else:
                # Content line, add to current node
                if current_node:
                    current_node['content'].append(line)

        # Update end_line for all nodes in the stack
        for node in parent_stack:
            if node != root:
                node['end_line'] = len(lines)

        return root

    def _node_to_text(self, node: Dict) -> str:
        """Convert a node to text with its heading and content."""
        result = []

        if node['heading']:
            result.append(node['heading'])

        if node['content']:
            result.extend(node['content'])

        return '\n'.join(result)

    def _node_size(self, node: Dict) -> int:
        """Calculate the size of a node's text."""
        return len(self._node_to_text(node))

    def _is_too_small(self, text: str) -> bool:
        """Determine if a text is too small."""
        return len(text) < self.min_chunk_size

    def _can_fit_in_chunk(self, current_text: str, new_text: str) -> bool:
        """Check if adding new_text to current_text exceeds max size."""
        separator = '\n\n' if current_text and new_text else ''
        return len(current_text) + len(separator) + len(new_text) <= self.max_chunk_size

    def _create_chunks_from_tree(self, node: Dict, original_text: str) -> List[Tuple[str, Dict]]:
        """
        Recursively create chunks from the markdown tree.
        Ensures headings always stay with content.

        Returns:
            List of tuples (chunk_text, chunk_metadata)
        """
        chunks = []
        current_chunk = ""
        current_metadata = {
            'heading_level': node['level'],
            'heading_title': node['heading_title'],
            'start_line': node['start_line'],
            'end_line': node['start_line'],  # Will be updated as we add content
            'chunk_type': 'markdown'
        }

        # Process this node's heading and content first
        node_text = self._node_to_text(node)

        # If this node alone exceeds max_chunk_size, we need special handling
        if len(node_text) > self.max_chunk_size:
            # Always include the heading in our chunk if it exists
            heading = node['heading'] if node['heading'] else ""
            heading_lines = 1 if heading else 0

            # Split content into paragraphs
            paragraphs = node['content']

            # Initialize the first chunk with the heading
            current_chunk = heading
            current_metadata['end_line'] = node['start_line'] + heading_lines - 1

            # Track if we've added at least some content after heading
            content_added = False
            current_line = node['start_line'] + heading_lines

            for paragraph in paragraphs:
                # Skip empty paragraphs
                if not paragraph.strip():
                    current_chunk += '\n' if current_chunk else ''
                    current_line += 1
                    continue

                paragraph_lines = paragraph.count('\n') + 1

                # Check if this paragraph would fit in current chunk
                separator = '\n' if current_chunk else ''
                if len(current_chunk) + len(separator) + len(paragraph) <= self.max_chunk_size:
                    # Add to current chunk
                    current_chunk += separator + paragraph
                    current_metadata['end_line'] = current_line + paragraph_lines - 1
                    content_added = True
                else:
                    # If we've added content already, finalize current chunk
                    if content_added:
                        chunks.append((current_chunk, current_metadata.copy()))
                        # Start new chunk with heading
                        current_chunk = heading + '\n' + paragraph
                        current_metadata = {
                            'heading_level': node['level'],
                            'heading_title': node['heading_title'],
                            'start_line': current_metadata['end_line'] + 1,
                            'end_line': current_metadata['end_line'] + 1 + heading_lines + paragraph_lines - 1,
                            'chunk_type': 'markdown'
                        }
                        content_added = True
                    else:
                        # Need to split this paragraph itself (it's too big even with just the heading)
                        sentences = self._split_paragraph_by_sentences(paragraph)

                        for sentence in sentences:
                            sentence_lines = sentence.count('\n') + 1

                            if len(current_chunk) + len(sentence) <= self.max_chunk_size:
                                separator = '\n' if current_chunk else ''
                                current_chunk += separator + sentence
                                current_metadata['end_line'] += sentence_lines
                                content_added = True
                            else:
                                if content_added:
                                    chunks.append((current_chunk, current_metadata.copy()))
                                    # Start new chunk with heading
                                    current_chunk = heading + '\n' + sentence
                                    current_metadata = {
                                        'heading_level': node['level'],
                                        'heading_title': node['heading_title'],
                                        'start_line': current_metadata['end_line'] + 1,
                                        'end_line': current_metadata['end_line'] + 1 + heading_lines + sentence_lines - 1,
                                        'chunk_type': 'markdown'
                                    }
                                    content_added = True
                                else:
                                    # Even a single sentence won't fit with heading, we have to exceed max_chunk_size
                                    current_chunk += sentence
                                    current_metadata['end_line'] += sentence_lines
                                    chunks.append((current_chunk, current_metadata.copy()))
                                    # Reset for next chunk
                                    current_chunk = heading
                                    current_metadata = {
                                        'heading_level': node['level'],
                                        'heading_title': node['heading_title'],
                                        'start_line': current_metadata['end_line'] + 1,
                                        'end_line': current_metadata['end_line'] + 1 + heading_lines - 1,
                                        'chunk_type': 'markdown'
                                    }
                                    content_added = False

                current_line += paragraph_lines

            # Add the final chunk if it has content
            if content_added:
                chunks.append((current_chunk, current_metadata.copy()))
                current_chunk = ""
                current_metadata = {}
        else:
            current_chunk = node_text
            current_metadata['end_line'] = node['end_line']

        # Process children recursively
        for child in node['children']:
            child_chunks = self._create_chunks_from_tree(child, original_text)

            # If we have an existing chunk, try to combine with first child chunk
            if current_chunk and child_chunks:
                child_text, child_metadata = child_chunks[0]
                combined = current_chunk + '\n\n' + child_text

                if len(combined) <= self.max_chunk_size:
                    current_chunk = combined
                    current_metadata['end_line'] = child_metadata['end_line']
                    child_chunks = child_chunks[1:]
                else:
                    # Can't combine, add current chunk to results
                    if current_chunk:
                        chunks.append((current_chunk, current_metadata.copy()))
                    current_chunk = ""
                    current_metadata = {}

            # Add any remaining child chunks
            if child_chunks:
                if not current_chunk:
                    current_chunk, current_metadata = child_chunks[0]
                    child_chunks = child_chunks[1:]

                chunks.extend(child_chunks)

        # Add final chunk if not empty
        if current_chunk:
            chunks.append((current_chunk, current_metadata.copy()))

        return chunks

    def _expand_small_chunks(self, chunks: List[Tuple[str, Dict]]) -> List[Tuple[str, Dict]]:
        """
        Perform a pass to try to expand chunks that are below min_chunk_size.
        Will try to merge small chunks with previous or next chunk if possible.
        """
        if not chunks:
            return []

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            current_text, current_metadata = chunks[i]

            # If current chunk is too small, try to merge with previous
            if self._is_too_small(current_text) and result:
                prev_text, prev_metadata = result[-1]
                combined = prev_text + '\n\n' + current_text

                if len(combined) <= self.max_chunk_size:
                    # Update the previous chunk
                    result[-1] = (combined, {
                        **prev_metadata,
                        'end_line': current_metadata['end_line']
                    })
                else:
                    # Couldn't merge, add as is
                    result.append((current_text, current_metadata))
            else:
                result.append((current_text, current_metadata))

        return result

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

        # Check if there are any headings in the text
        if not self.heading_pattern.search(text):
            # No headings found, use the text chunker with line-based chunking
            # to avoid creating many tiny chunks
            lines = text.split('\n')
            chunks = []
            current_chunk_lines = []
            current_chunk_size = 0
            chunk_number = 0

            for i, line in enumerate(lines):
                line_size = len(line) + 1  # +1 for the newline

                # If adding this line would exceed max_chunk_size and we already have content,
                # finish the current chunk
                if current_chunk_lines and current_chunk_size + line_size > max_chunk_size and current_chunk_size >= min_chunk_size:
                    # Join the lines to form the chunk text
                    chunk_text = '\n'.join(current_chunk_lines)

                    # Create chunk metadata
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        'chunk_number': chunk_number,
                        'chunk_type': 'text',
                        'char_length': len(chunk_text),
                        'start_line': i - len(current_chunk_lines) + 1,
                        'end_line': i
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
                    'char_length': len(chunk_text),
                    'start_line': len(lines) - len(current_chunk_lines) + 1,
                    'end_line': len(lines)
                })

                chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))

            return chunks

        # Build markdown tree structure
        tree = self._build_markdown_tree(text)

        # Create initial chunks from tree
        raw_chunks = self._create_chunks_from_tree(tree, text)

        # Expand small chunks where possible
        raw_chunks = self._expand_small_chunks(raw_chunks)

        # Convert to Chunk objects with metadata
        chunks = []
        for i, (chunk_text, chunk_metadata) in enumerate(raw_chunks):
            # Create a copy of the base metadata and enhance it with chunk-specific info
            combined_metadata = metadata.copy()
            combined_metadata.update(chunk_metadata)
            combined_metadata['chunk_number'] = i
            combined_metadata['char_length'] = len(chunk_text)

            # Calculate character positions if possible
            lines = text.split('\n')
            if 'start_line' in combined_metadata and 'end_line' in combined_metadata:
                start_line = combined_metadata['start_line']
                end_line = combined_metadata['end_line']

                # Calculate start_char and end_char safely
                try:
                    # Calculate start_char
                    start_char = 0
                    for j in range(min(start_line - 1, len(lines))):
                        start_char += len(lines[j]) + 1  # +1 for the newline

                    # Calculate end_char
                    end_char = start_char
                    for j in range(min(start_line - 1, len(lines)), min(end_line, len(lines))):
                        end_char += len(lines[j]) + 1  # +1 for the newline
                except IndexError:
                    # Fallback if there's an issue with line numbers
                    start_char = 0
                    end_char = len(text)

                combined_metadata['start_char'] = start_char
                combined_metadata['end_char'] = end_char

            chunks.append(Chunk(text=chunk_text, metadata=combined_metadata))

        return chunks
