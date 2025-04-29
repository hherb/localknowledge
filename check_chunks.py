#!/usr/bin/env python3
"""
Script to check chunks for a specific document and strategy.
"""

import sys
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    # Document ID to check
    document_id = 62024974
    
    # Strategy ID to check
    strategy_id = 2
    
    print(f"Checking chunks for document {document_id} and strategy {strategy_id}")
    
    try:
        with get_cursor() as cursor:
            # Get all chunks for the document and strategy
            query = """
            SELECT *
            FROM chunks
            WHERE document_id = %s
            AND chunking_strategy_id = %s
            """
            
            # Execute the query
            cursor.execute(query, (document_id, strategy_id))
            
            # Fetch all chunks
            chunks = cursor.fetchall()
            
            # Print results
            print(f"Found {len(chunks)} chunks:")
            for chunk in chunks:
                print(f"Chunk ID: {chunk['id']}, Document ID: {chunk['document_id']}, Strategy ID: {chunk['chunking_strategy_id']}")
                print(f"  Text length: {len(chunk['text']) if 'text' in chunk else 'N/A'}")
                print(f"  Chunk type ID: {chunk['chunktype_id']}")
                print(f"  Chunk number: {chunk['chunk_no']}")
                print()
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
