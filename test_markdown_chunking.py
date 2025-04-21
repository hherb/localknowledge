#!/usr/bin/env python3
"""
Script to demonstrate markdown chunking on example.md file.
"""

import os
import sys
from pprint import pprint

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from localknowledge.textprocessing.chunking.markdown_chunker import MarkdownChunker

def main():
    """Main function to demonstrate markdown chunking."""
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
    
    # Create a markdown chunker
    chunker = MarkdownChunker(
        max_level=3,
        min_chunk_size=50,
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
        print(f"  Start line: {chunk.metadata.get('start_line')}")
        print(f"  End line: {chunk.metadata.get('end_line')}")
        print()

if __name__ == "__main__":
    main()
