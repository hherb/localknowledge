#!/usr/bin/env python3
"""
Simple test script for the AdaptiveTextChunker.

This script tests the chunking functionality without database interaction.
"""

import logging
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test data
test_abstracts = [
    {
        "title": "Short Abstract Test",
        "abstract": "This is a short abstract that should fit in a single chunk."
    },
    {
        "title": "Medium Abstract Test",
        "abstract": """This is a medium-length abstract that might be split into multiple chunks.
        It contains multiple sentences and should demonstrate the sentence boundary detection.
        The chunker should try to split at sentence boundaries when possible.
        This abstract is still relatively short but might be split depending on the chunk size."""
    },
    {
        "title": "Long Abstract Test",
        "abstract": """
        This is a longer abstract that will definitely be split into multiple chunks.
        It contains many sentences and paragraphs to test the chunking functionality.
        
        The adaptive text chunker should handle this text by splitting it into appropriate chunks.
        It should try to maintain sentence boundaries and paragraph structure when possible.
        
        This abstract has multiple paragraphs to test how the chunker handles paragraph breaks.
        The chunker should ideally keep paragraphs together when possible, but may need to split
        very long paragraphs across multiple chunks.
        
        The chunker should also handle the overlap between chunks properly, ensuring that there's
        enough context between chunks for semantic understanding. This is particularly important
        for embeddings and semantic search applications.
        
        Finally, this abstract should test how the chunker handles the last chunk, which might be
        smaller than the others. The chunker should handle this case gracefully, possibly by
        extending the chunk to include more content from the previous chunk.
        """
    }
]

def test_chunker():
    """
    Test the AdaptiveTextChunker with sample abstracts.
    """
    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=384,  # Relatively small for testing
        overlap=128,
        min_chunk_size=100
    )
    
    # Process each test abstract
    for i, test_data in enumerate(test_abstracts):
        title = test_data["title"]
        abstract = test_data["abstract"]
        
        print(f"\n===== Testing Abstract {i+1}: {title} =====")
        print(f"Abstract length: {len(abstract)} characters")
        
        # Create metadata with title
        metadata = {
            'title': title,
            'source': 'test',
            'document_id': i+1
        }
        
        # Chunk the abstract
        chunks = chunker.chunk(abstract, metadata=metadata)
        
        print(f"Created {len(chunks)} chunks")
        
        # Display each chunk
        for j, chunk in enumerate(chunks):
            print(f"\nChunk {j+1}:")
            print(f"Length: {len(chunk.text)} characters")
            print(f"Metadata: {chunk.metadata}")
            print(f"Text: {chunk.text[:100]}...")

if __name__ == "__main__":
    test_chunker()
