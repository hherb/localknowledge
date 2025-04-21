"""
Unit tests for the markdown chunker.
"""

import unittest
from typing import Dict, Any, List

from localknowledge.textprocessing.chunking.markdown_chunker import MarkdownChunker
from localknowledge.textprocessing.chunking.base import Chunk


class TestMarkdownChunker(unittest.TestCase):
    """Test cases for the MarkdownChunker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.chunker = MarkdownChunker(
            max_level=3,
            min_chunk_size=10,  # Small for testing
            max_chunk_size=500,
            include_heading_in_chunk=True
        )
        
        # Sample markdown text for testing
        self.basic_markdown = """# Main Heading

This is some introduction text.

## Section 1

Content for section 1.

### Subsection 1.1

Content for subsection 1.1.

## Section 2

Content for section 2.
"""

        # Markdown with Setext headings
        self.setext_markdown = """Main Heading
===========

This is some introduction text.

Section 1
---------

Content for section 1.

## Section 2

Content for section 2.
"""

        # Markdown with large sections
        self.large_section_markdown = """# Main Heading

""" + "This is a very long section with repeated text. " * 50 + """

## Section 2

Content for section 2.
"""

    def test_basic_chunking(self):
        """Test basic chunking with headings."""
        chunks = self.chunker.chunk(self.basic_markdown)
        
        # Should have 4 chunks: intro, section 1, subsection 1.1, section 2
        self.assertEqual(len(chunks), 4)
        
        # Check chunk types and headings
        self.assertEqual(chunks[0].metadata['heading_title'], 'Introduction')
        self.assertEqual(chunks[0].metadata['heading_level'], 0)
        
        self.assertEqual(chunks[1].metadata['heading_title'], 'Section 1')
        self.assertEqual(chunks[1].metadata['heading_level'], 2)
        
        self.assertEqual(chunks[2].metadata['heading_title'], 'Subsection 1.1')
        self.assertEqual(chunks[2].metadata['heading_level'], 3)
        
        self.assertEqual(chunks[3].metadata['heading_title'], 'Section 2')
        self.assertEqual(chunks[3].metadata['heading_level'], 2)

    def test_different_heading_levels(self):
        """Test chunking with different heading levels."""
        # Create a chunker with max_level=2
        chunker = MarkdownChunker(max_level=2, min_chunk_size=10)
        chunks = chunker.chunk(self.basic_markdown)
        
        # Should have 3 chunks: intro, section 1, section 2
        # Subsection 1.1 should be part of section 1
        self.assertEqual(len(chunks), 3)
        
        # Check that section 1 includes subsection content
        self.assertIn('Subsection 1.1', chunks[1].text)

    def test_setext_headings(self):
        """Test chunking with Setext headings."""
        chunks = self.chunker.chunk(self.setext_markdown)
        
        # Should have 3 chunks: intro, section 1, section 2
        self.assertEqual(len(chunks), 3)
        
        # Check heading levels
        self.assertEqual(chunks[0].metadata['heading_title'], 'Introduction')
        self.assertEqual(chunks[0].metadata['heading_level'], 0)
        
        self.assertEqual(chunks[1].metadata['heading_title'], 'Section 1')
        self.assertEqual(chunks[1].metadata['heading_level'], 2)
        
        self.assertEqual(chunks[2].metadata['heading_title'], 'Section 2')
        self.assertEqual(chunks[2].metadata['heading_level'], 2)

    def test_empty_text(self):
        """Test chunking with empty text."""
        chunks = self.chunker.chunk("")
        self.assertEqual(len(chunks), 0)

    def test_no_headings(self):
        """Test chunking with no headings (should fall back to TextChunker)."""
        text = "This is a text without any headings. " * 20
        chunks = self.chunker.chunk(text)
        
        # Should use TextChunker and create at least one chunk
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].metadata['chunk_type'], 'text')

    def test_large_sections(self):
        """Test chunking with large sections (should use TextChunker for sub-chunking)."""
        chunks = self.chunker.chunk(self.large_section_markdown)
        
        # Should have multiple chunks due to sub-chunking
        self.assertGreater(len(chunks), 2)
        
        # Check that some chunks are sub-chunks
        sub_chunks = [c for c in chunks if c.metadata.get('chunk_type') == 'markdown_sub']
        self.assertGreater(len(sub_chunks), 0)
        
        # Check that sub-chunks have parent information
        for chunk in sub_chunks:
            self.assertIn('parent_chunk_number', chunk.metadata)
            self.assertEqual(chunk.metadata['heading_title'], 'Main Heading')

    def test_metadata_handling(self):
        """Test metadata handling."""
        metadata = {
            'file_name': 'test.md',
            'author': 'Test Author',
            'source': 'Test Source'
        }
        
        chunks = self.chunker.chunk(self.basic_markdown, metadata=metadata)
        
        # Check that metadata is preserved in all chunks
        for chunk in chunks:
            self.assertEqual(chunk.metadata['file_name'], 'test.md')
            self.assertEqual(chunk.metadata['author'], 'Test Author')
            self.assertEqual(chunk.metadata['source'], 'Test Source')

    def test_parameter_overrides(self):
        """Test parameter overrides in the chunk method."""
        # Override max_level to 1
        chunks = self.chunker.chunk(
            self.basic_markdown,
            max_level=1,
            min_chunk_size=10
        )
        
        # Should only have 2 chunks: intro and main heading
        self.assertEqual(len(chunks), 2)
        
        # Check that only level 1 headings are included
        headings = [c.metadata.get('heading_title') for c in chunks 
                   if c.metadata.get('heading_level') == 1]
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0], 'Main Heading')

    def test_include_heading_in_chunk(self):
        """Test include_heading_in_chunk parameter."""
        # Create a chunker with include_heading_in_chunk=False
        chunker = MarkdownChunker(
            max_level=3,
            min_chunk_size=10,
            include_heading_in_chunk=False
        )
        
        chunks = chunker.chunk(self.basic_markdown)
        
        # Check that headings are not included in the chunk text
        for chunk in chunks:
            if chunk.metadata.get('heading_level') > 0:
                heading_title = chunk.metadata.get('heading_title')
                self.assertNotIn(f"# {heading_title}", chunk.text)
                self.assertNotIn(f"## {heading_title}", chunk.text)
                self.assertNotIn(f"### {heading_title}", chunk.text)


if __name__ == '__main__':
    unittest.main()
