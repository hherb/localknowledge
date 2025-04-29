#!/usr/bin/env python3
"""
Debug script to test the chunking process.
"""

import sys
import time
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    # Get a single document to test chunking
    document_id = 62024974  # From the previous debug script
    
    print(f"Testing chunking for document {document_id}")
    
    try:
        with get_cursor() as cursor:
            # Get the document
            query = """
            SELECT d.id, d.title, d.abstract
            FROM document d
            WHERE d.id = %s
            """
            
            # Execute the query
            cursor.execute(query, (document_id,))
            
            # Fetch the document
            document = cursor.fetchone()
            
            if not document:
                print(f"Document {document_id} not found")
                return 1
            
            # Print document info
            print(f"Document ID: {document['id']}")
            print(f"Title: {document['title']}")
            print(f"Abstract length: {len(document['abstract'])} characters")
            
            # Initialize chunker
            chunker = AdaptiveTextChunker(
                max_chunk_size=1500,
                overlap=100,
                min_chunk_size=100
            )
            
            # Create metadata
            metadata = {
                'title': document['title'],
                'source': 'abstract',
                'document_id': document['id']
            }
            
            # Time the chunking process
            start_time = time.time()
            
            # Chunk the abstract
            chunks = chunker.chunk(document['abstract'], metadata=metadata)
            
            # Print results
            print(f"Chunking completed in {time.time() - start_time:.4f} seconds")
            print(f"Created {len(chunks)} chunks")
            
            # Print chunk details
            for i, chunk in enumerate(chunks):
                print(f"\nChunk {i+1}:")
                print(f"Text length: {len(chunk.text)} characters")
                print(f"First 100 chars: {chunk.text[:100]}...")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
