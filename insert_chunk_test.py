#!/usr/bin/env python3
"""
Test script for inserting a single chunk into the database.
"""

import logging
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk as DBChunk
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

# Test data - a simple abstract
test_abstract = """
Background: This is a test abstract for the AdaptiveTextChunker.
Methods: We test the chunker with a simple abstract to see how it works.
Results: The chunker should split this abstract into appropriate chunks.
Conclusion: The chunker works as expected.
"""

def test_insert_chunk():
    """
    Test inserting a single chunk into the database.
    """
    # Load environment variables
    load_environment()
    
    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=384,
        overlap=128,
        min_chunk_size=100
    )
    
    title = "Test Abstract"
    
    print(f"\n===== Testing Chunk Insertion =====")
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
    
    # Convert to database chunks
    db_chunks = []
    for i, chunk in enumerate(chunks):
        db_chunk = chunk.to_db_chunk(
            document_id=1,
            chunking_strategy_id=CHUNKING_STRATEGY_ID,
            chunktype_id=CHUNKTYPE_ID,
            document_title=title,
            chunk_no=i
        )
        db_chunks.append(db_chunk)
    
    print(f"Converted to {len(db_chunks)} database chunks")
    
    # Create database manager
    db_manager = ChunkingDatabaseManager()
    
    # Insert a single chunk
    if db_chunks:
        try:
            # Get the first chunk
            chunk = db_chunks[0]
            
            # Insert the chunk
            chunk_id = db_manager.get_or_create_chunk(chunk)
            
            print(f"Successfully inserted chunk with ID: {chunk_id}")
            
            # Retrieve the chunk to verify
            retrieved_chunk = db_manager.get_chunk_by_id(chunk_id)
            
            if retrieved_chunk:
                print(f"Retrieved chunk with ID: {retrieved_chunk.chunk_id}")
                print(f"Chunk text: {retrieved_chunk.text[:100]}...")
            else:
                print("Failed to retrieve the inserted chunk")
                
        except Exception as e:
            print(f"Error inserting chunk: {e}")
    else:
        print("No chunks to insert")

if __name__ == "__main__":
    test_insert_chunk()
