#!/usr/bin/env python3
"""
Test script for batch inserting chunks into the database.
"""

import logging
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNKING_STRATEGY_ID = 1  # Use existing strategy
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table

# Test data - multiple abstracts
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

def test_batch_insert():
    """
    Test batch inserting chunks into the database.
    """
    # Load environment variables
    load_environment()
    
    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=384,
        overlap=128,
        min_chunk_size=100
    )
    
    print(f"\n===== Testing Batch Chunk Insertion =====")
    
    # Create database manager
    db_manager = ChunkingDatabaseManager()
    
    # Process each abstract
    total_chunks = 0
    
    for i, test_data in enumerate(test_abstracts):
        title = test_data["title"]
        abstract = test_data["abstract"]
        
        print(f"\nProcessing abstract {i+1}: {title}")
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
        
        # Convert to database chunks
        db_chunks = []
        for j, chunk in enumerate(chunks):
            db_chunk = chunk.to_db_chunk(
                document_id=i+1,
                chunking_strategy_id=CHUNKING_STRATEGY_ID,
                chunktype_id=CHUNKTYPE_ID,
                document_title=title,
                chunk_no=j
            )
            db_chunks.append(db_chunk)
        
        total_chunks += len(db_chunks)
        
        # Insert chunks in batch
        try:
            # Insert the chunks
            chunk_ids = db_manager.batch_insert_chunks(db_chunks)
            
            print(f"Successfully inserted {len(chunk_ids)} chunks with IDs: {chunk_ids}")
            
        except Exception as e:
            print(f"Error batch inserting chunks: {e}")
    
    print(f"\nTotal chunks inserted: {total_chunks}")

if __name__ == "__main__":
    test_batch_insert()
