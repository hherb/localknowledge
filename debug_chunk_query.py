#!/usr/bin/env python3
"""
Debug script to test the query for retrieving documents without chunks.
"""

import sys
import time
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    # Strategy ID to check
    strategy_id = 2  # This is the ID for adaptive_text_chunker_1500
    
    # Limit to a small number of documents
    limit = 5
    
    print(f"Testing query for documents without chunks for strategy {strategy_id}")
    print(f"Limiting to {limit} documents")
    
    start_time = time.time()
    
    try:
        with get_cursor() as cursor:
            # Use a simpler query first
            print("Executing query...")
            query = """
            SELECT d.id, d.title
            FROM document d
            WHERE d.abstract IS NOT NULL
            AND length(d.abstract) > 0
            LIMIT %s
            """
            
            # Execute the query
            cursor.execute(query, (limit,))
            
            # Fetch all documents
            documents = cursor.fetchall()
            
            # Print results
            print(f"Retrieved {len(documents)} documents in {time.time() - start_time:.2f} seconds")
            for doc in documents:
                print(f"Document ID: {doc['id']}, Title: {doc['title'][:50]}...")
            
            # Now try the actual query
            print("\nNow testing the full query...")
            start_time = time.time()
            
            query = """
            SELECT d.id, d.title
            FROM document d
            WHERE d.abstract IS NOT NULL
            AND length(d.abstract) > 0
            AND NOT EXISTS (
                SELECT 1
                FROM chunks c
                WHERE c.document_id = d.id
                AND c.chunking_strategy_id = %s
            )
            LIMIT %s
            """
            
            # Execute the query
            cursor.execute(query, (strategy_id, limit))
            
            # Fetch all documents
            documents = cursor.fetchall()
            
            # Print results
            print(f"Retrieved {len(documents)} documents in {time.time() - start_time:.2f} seconds")
            for doc in documents:
                print(f"Document ID: {doc['id']}, Title: {doc['title'][:50]}...")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
