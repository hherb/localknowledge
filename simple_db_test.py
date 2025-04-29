#!/usr/bin/env python3
"""
Simple test script for the AdaptiveTextChunker and database insertion.
"""

import logging
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.textprocessing.chunking import AdaptiveTextChunker, Chunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    # Load environment variables
    load_environment()
    
    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=384,
        overlap=128,
        min_chunk_size=100
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
        print(f"Text: {chunk.text[:100]}...")
    
    # Convert to database chunks
    db_chunks = []
    for i, chunk in enumerate(chunks):
        db_chunk = chunk.to_db_chunk(
            document_id=1,
            chunking_strategy_id=1,
            chunktype_id=1,
            document_title=title,
            chunk_no=i
        )
        db_chunks.append(db_chunk)
    
    print(f"\nConverted to {len(db_chunks)} database chunks")
    
    # Test database connection
    try:
        with get_cursor() as cursor:
            # Check if the chunks table exists
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'chunks'
            )
            """
            cursor.execute(query)
            table_exists = cursor.fetchone()[0]
            
            if table_exists:
                print("Chunks table exists in the database")
                
                # Count existing chunks
                count_query = "SELECT COUNT(*) FROM chunks"
                cursor.execute(count_query)
                count = cursor.fetchone()[0]
                print(f"There are currently {count} chunks in the database")
                
                # Check chunking strategies
                strategies_query = "SELECT id, strategy_name FROM chunking_strategies"
                cursor.execute(strategies_query)
                strategies = cursor.fetchall()
                print("Available chunking strategies:")
                for strategy in strategies:
                    print(f"  ID: {strategy[0]}, Name: {strategy[1]}")
                
                # Check chunk types
                types_query = "SELECT id, chunktype FROM chunktypes"
                cursor.execute(types_query)
                types = cursor.fetchall()
                print("Available chunk types:")
                for type_ in types:
                    print(f"  ID: {type_[0]}, Type: {type_[1]}")
            else:
                print("Chunks table does not exist in the database")
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    test_chunker()
