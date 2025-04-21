#!/usr/bin/env python3
"""
Example usage of the chunking module with metadata.

This script demonstrates how to use the chunking module with metadata
to provide contextual information about the text being chunked.
"""

import os
import sys
import logging
from pprint import pprint

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example text
EXAMPLE_TEXT = """
This is a sample text that will be chunked into smaller pieces.
It contains multiple sentences that should be kept together when possible.
The chunker will try to break at sentence boundaries.

This is a new paragraph that might be in a different chunk depending on the chunk size.
Chunking is useful for processing large documents that don't fit into memory or exceed token limits.
"""

# Example markdown text
EXAMPLE_MARKDOWN = """
# Introduction

This is an introduction to the document. It provides context for the rest of the content.

## Section 1

This is the first section of the document. It contains important information.

### Subsection 1.1

This is a subsection with more detailed information.

## Section 2

This is the second section of the document. It builds on the first section.
"""

def demonstrate_text_chunking_with_metadata():
    """Demonstrate text chunking with metadata."""
    # Create a text chunker
    chunker = TextChunker(chunk_size=100, overlap=20)

    # Create metadata
    metadata = {
        'file_name': 'example.txt',
        'author': 'John Doe',
        'date': '2023-06-15',
        'source': 'Example Source'
    }

    # Chunk the text with metadata
    chunks = chunker.chunk(EXAMPLE_TEXT, metadata=metadata)

    # Print the chunks with metadata
    print(f"Found {len(chunks)} chunks in the text:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Text: {chunk.text[:50]}...")
        print(f"  Metadata:")
        for key, value in chunk.metadata.items():
            print(f"    {key}: {value}")

    return chunks

def demonstrate_markdown_chunking_with_metadata():
    """Demonstrate markdown chunking with metadata."""
    # Create a markdown chunker
    chunker = MarkdownChunker(max_level=2, min_chunk_size=50, max_chunk_size=500)

    # Create metadata
    metadata = {
        'file_name': 'example.md',
        'author': 'Jane Smith',
        'date': '2023-06-15',
        'source': 'Example Source',
        'document_type': 'markdown'
    }

    # Chunk the markdown text with metadata
    chunks = chunker.chunk(EXAMPLE_MARKDOWN, metadata=metadata)

    # Print the chunks with metadata
    print(f"\nFound {len(chunks)} chunks in the markdown text:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Heading: {chunk.metadata.get('heading_title')}")
        print(f"  Level: {chunk.metadata.get('heading_level')}")
        print(f"  Text: {chunk.text[:50]}...")
        print(f"  Metadata:")
        for key, value in sorted(chunk.metadata.items()):
            if key not in ['heading_title', 'heading_level']:
                print(f"    {key}: {value}")

    return chunks

def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Chunking with metadata example')
    parser.add_argument('--type', choices=['text', 'markdown', 'both'], default='both',
                      help='Type of chunking to demonstrate (default: both)')

    args = parser.parse_args()

    if args.type in ['text', 'both']:
        demonstrate_text_chunking_with_metadata()

    if args.type in ['markdown', 'both']:
        demonstrate_markdown_chunking_with_metadata()

if __name__ == '__main__':
    main()
