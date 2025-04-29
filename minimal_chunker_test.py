#!/usr/bin/env python3
"""
Minimal test script for the AdaptiveTextChunker.
"""

import logging
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set the logger level for the chunker module
chunker_logger = logging.getLogger('localknowledge.textprocessing.chunking.AdaptiveTextChunker')
chunker_logger.setLevel(logging.DEBUG)

# Test data - a simple abstract
test_abstract = """
Background: This is a test abstract for the AdaptiveTextChunker.
Methods: We test the chunker with a simple abstract to see how it works.
Results: The chunker should split this abstract into appropriate chunks.
Conclusion: The chunker works as expected.
"""

def test_chunker():
    """
    Test the AdaptiveTextChunker with a simple abstract.
    """
    # Initialize chunker with a very small chunk size to force splitting
    chunker = AdaptiveTextChunker(
        max_chunk_size=100,  # Very small for testing
        overlap=20,
        min_chunk_size=50
    )

    title = "Test Abstract"

    print(f"\n===== Testing Simple Abstract =====")
    print(f"Abstract length: {len(test_abstract)} characters")

    # Create metadata with title
    metadata = {
        'title': title,
        'source': 'test',
        'document_id': 1
    }

    # Chunk the abstract
    chunks = chunker.chunk(test_abstract, metadata=metadata)

    print(f"Created {len(chunks)} chunks")

    # Display each chunk
    for j, chunk in enumerate(chunks):
        print(f"\nChunk {j+1}:")
        print(f"Length: {len(chunk.text)} characters")
        print(f"Metadata: {chunk.metadata}")
        print(f"Text: {chunk.text}")

if __name__ == "__main__":
    test_chunker()
