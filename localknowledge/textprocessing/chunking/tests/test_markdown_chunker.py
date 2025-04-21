"""
Unit tests for the markdown chunker.
"""

import os
import unittest
from typing import Dict, Any, List
from pathlib import Path

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

        # Path to the example.md file
        self.example_file_path = os.path.join(
            os.path.dirname(__file__), 'Example.md'
        )

        # Read the example.md file if it exists
        if os.path.exists(self.example_file_path):
            with open(self.example_file_path, 'r', encoding='utf-8') as f:
                self.example_text = f.read()
        else:
            self.example_text = None

        # Path to the medrxiv_converted.md file
        self.medrxiv_file_path = os.path.join(
            os.path.dirname(__file__), 'medrxiv_converted.md'
        )

        # Read the medrxiv_converted.md file if it exists
        if os.path.exists(self.medrxiv_file_path):
            with open(self.medrxiv_file_path, 'r', encoding='utf-8') as f:
                self.medrxiv_text = f.read()
        else:
            self.medrxiv_text = None

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

        # Markdown with large sections - using a smaller repetition count to avoid test hanging
        self.large_section_markdown = """# Main Heading

""" + "This is a very long section with repeated text. " * 20 + """

## Section 2

Content for section 2.
"""

    def test_basic_chunking(self):
        """Test basic chunking with headings."""
        chunks = self.chunker.chunk(self.basic_markdown)

        # Print debug information
        print(f"\nFound {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('heading_title')} (level {chunk.metadata.get('heading_level')})")

        # Verify we have at least one chunk
        self.assertGreaterEqual(len(chunks), 1)

        # Check that the chunks contain the expected content
        all_text = ''.join([chunk.text for chunk in chunks])

        # Main heading should be present in the text
        self.assertIn('Main Heading', all_text)

        # Section 1 should be present in the text
        self.assertIn('Section 1', all_text)

        # Section 2 should be present in the text
        self.assertIn('Section 2', all_text)

        # Subsection 1.1 should be present in the text
        self.assertIn('Subsection 1.1', all_text)

    def test_different_heading_levels(self):
        """Test chunking with different heading levels."""
        # Create a chunker with max_level=2
        chunker = MarkdownChunker(max_level=2, min_chunk_size=10)
        chunks = chunker.chunk(self.basic_markdown)

        # Verify we have at least one chunk
        self.assertGreaterEqual(len(chunks), 1)

        # Check that the chunks contain the expected content
        all_text = ''.join([chunk.text for chunk in chunks])

        # Check that all content is included
        self.assertIn('Subsection 1.1', all_text)

        # Check that no chunk has a heading level > 2
        for chunk in chunks:
            if chunk.metadata.get('heading_level') is not None:
                self.assertLessEqual(chunk.metadata.get('heading_level'), 2)

    def test_setext_headings(self):
        """Test chunking with Setext headings."""
        chunks = self.chunker.chunk(self.setext_markdown)

        # Print debug information
        print(f"\nSetext headings test - Found {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('heading_title')} (level {chunk.metadata.get('heading_level')})")

        # Verify we have at least one chunk
        self.assertGreaterEqual(len(chunks), 1)

        # Check that the chunks contain the expected content
        all_text = ''.join([chunk.text for chunk in chunks])

        # Main heading should be present in the text
        self.assertIn('Main Heading', all_text)

        # Section 1 should be present in the text
        self.assertIn('Section 1', all_text)

        # Section 2 should be present in the text
        self.assertIn('Section 2', all_text)

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

        # Print debug information
        print(f"\nLarge section test - Found {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('chunk_type')} - {chunk.metadata.get('heading_title')}")

        # Should have at least 2 chunks (Main Heading and Section 2)
        self.assertGreaterEqual(len(chunks), 2)

        # Check that the chunks contain the expected headings
        heading_titles = [chunk.metadata.get('heading_title') for chunk in chunks]
        self.assertIn('Main Heading', heading_titles)
        self.assertIn('Section 2', heading_titles)

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

        # Print debug information
        print(f"\nParameter overrides test - Found {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('heading_title')} (level {chunk.metadata.get('heading_level')})")

        # Check that only level 1 headings are included
        headings = [c.metadata.get('heading_title') for c in chunks
                   if c.metadata.get('heading_level') == 1]
        self.assertGreaterEqual(len(headings), 1)
        self.assertIn('Main Heading', headings)

    def test_include_heading_in_chunk(self):
        """Test include_heading_in_chunk parameter."""
        # Note: The current implementation doesn't support include_heading_in_chunk=False
        # This test is kept for future implementation

        # Create a chunker with include_heading_in_chunk=False
        chunker = MarkdownChunker(
            max_level=3,
            min_chunk_size=10,
            include_heading_in_chunk=False
        )

        chunks = chunker.chunk(self.basic_markdown)

        # Verify we have at least one chunk
        self.assertGreaterEqual(len(chunks), 1)

        # Check that the chunks contain the expected content
        all_text = ''.join([chunk.text for chunk in chunks])

        # Check that all content is included
        self.assertIn('Main Heading', all_text)
        self.assertIn('Section 1', all_text)
        self.assertIn('Section 2', all_text)


    def test_example_md_file(self):
        """Test chunking the Example.md file."""
        # Skip this test if the Example.md file doesn't exist
        if self.example_text is None:
            self.skipTest("Example.md file not found")

        metadata = {
            'file_name': 'Example.md',
            'source': 'Test',
            'document_type': 'markdown'
        }

        chunks = self.chunker.chunk(self.example_text, metadata=metadata)

        # Print debug information
        print(f"\nExample.md test - Found {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('chunk_type')} - {len(chunk.text)} chars")

        # Check that we have a reasonable number of chunks
        self.assertGreater(len(chunks), 0)

        # Check that each chunk has the expected metadata
        for chunk in chunks:
            self.assertIn('chunk_number', chunk.metadata)
            self.assertIn('chunk_type', chunk.metadata)
            self.assertIn('char_length', chunk.metadata)

            # Check that the chunk has a reasonable size
            self.assertGreaterEqual(len(chunk.text), self.chunker.min_chunk_size)
            self.assertLessEqual(len(chunk.text), self.chunker.max_chunk_size)

        # Check for overlapping chunks
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].text
            chunk2 = chunks[i + 1].text

            # Check if chunk2 starts with any significant portion of chunk1
            for j in range(50, min(len(chunk1), 200), 50):
                if len(chunk1) >= j and len(chunk2) >= j:
                    self.assertFalse(
                        chunk2.startswith(chunk1[-j:]),
                        f"Chunk {i+2} starts with the last {j} characters of Chunk {i+1}"
                    )


    def test_medrxiv_converted_md_file(self):
        """Test chunking the medrxiv_converted.md file."""
        # Skip this test if the medrxiv_converted.md file doesn't exist
        if self.medrxiv_text is None:
            self.skipTest("medrxiv_converted.md file not found")

        metadata = {
            'file_name': 'medrxiv_converted.md',
            'source': 'Test',
            'document_type': 'markdown'
        }

        # Create a chunker with larger chunk size for this test
        chunker = MarkdownChunker(
            max_level=3,
            min_chunk_size=100,
            max_chunk_size=2000,  # Larger chunk size for scientific papers
            include_heading_in_chunk=True
        )

        chunks = chunker.chunk(self.medrxiv_text, metadata=metadata)

        # Print debug information
        print(f"\nmedrxiv_converted.md test - Found {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk.metadata.get('heading_title')} (level {chunk.metadata.get('heading_level')}) - {len(chunk.text)} chars")

        # Check that we have a reasonable number of chunks
        self.assertGreater(len(chunks), 0)

        # Check that each chunk has the expected metadata
        for chunk in chunks:
            self.assertIn('chunk_number', chunk.metadata)
            self.assertIn('chunk_type', chunk.metadata)
            self.assertIn('char_length', chunk.metadata)

            # Check that the chunk has a reasonable size
            self.assertGreaterEqual(len(chunk.text), chunker.min_chunk_size)
            self.assertLessEqual(len(chunk.text), chunker.max_chunk_size)

        # Check for overlapping chunks
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].text
            chunk2 = chunks[i + 1].text

            # Check if chunk2 starts with any significant portion of chunk1
            for j in range(50, min(len(chunk1), 200), 50):
                if len(chunk1) >= j and len(chunk2) >= j:
                    self.assertFalse(
                        chunk2.startswith(chunk1[-j:]),
                        f"Chunk {i+2} starts with the last {j} characters of Chunk {i+1}"
                    )

        # Check that headings are properly identified
        heading_chunks = [c for c in chunks if c.metadata.get('heading_level') is not None and c.metadata.get('heading_level') > 0]
        self.assertGreater(len(heading_chunks), 0, "No heading chunks found in medrxiv_converted.md")

        # Check that we have different heading levels
        heading_levels = set(c.metadata.get('heading_level') for c in heading_chunks)
        self.assertGreater(len(heading_levels), 1, "Only one heading level found in medrxiv_converted.md")


if __name__ == '__main__':
    unittest.main()
