#!/usr/bin/env python3
"""
Script to clean up duplicate chunks.
"""

import sys
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    print("Cleaning up duplicate chunks")
    
    try:
        with get_cursor() as cursor:
            # Find duplicate chunks
            find_duplicates_query = """
            SELECT document_id, chunking_strategy_id, chunk_no, COUNT(*), array_agg(id) as chunk_ids
            FROM chunks
            GROUP BY document_id, chunking_strategy_id, chunk_no
            HAVING COUNT(*) > 1
            """
            
            # Execute the query
            cursor.execute(find_duplicates_query)
            
            # Fetch all duplicate chunks
            duplicates = cursor.fetchall()
            
            if not duplicates:
                print("No duplicate chunks found")
                return 0
            
            print(f"Found {len(duplicates)} sets of duplicate chunks:")
            
            # Process each set of duplicates
            for duplicate in duplicates:
                document_id = duplicate['document_id']
                strategy_id = duplicate['chunking_strategy_id']
                chunk_no = duplicate['chunk_no']
                count = duplicate['count']
                chunk_ids = duplicate['chunk_ids']
                
                print(f"Document ID: {document_id}, Strategy ID: {strategy_id}, Chunk No: {chunk_no}, Count: {count}")
                print(f"  Chunk IDs: {chunk_ids}")
                
                # Keep the first chunk and delete the rest
                keep_id = chunk_ids[0]
                delete_ids = chunk_ids[1:]
                
                print(f"  Keeping chunk ID: {keep_id}")
                print(f"  Deleting chunk IDs: {delete_ids}")
                
                # Delete the duplicate chunks
                placeholders = ', '.join(['%s'] * len(delete_ids))
                delete_query = f"""
                DELETE FROM chunks
                WHERE id IN ({placeholders})
                """
                
                # Execute the query
                cursor.execute(delete_query, delete_ids)
                
                print(f"  Deleted {cursor.rowcount} duplicate chunks")
            
            # Verify no more duplicates
            cursor.execute(find_duplicates_query)
            remaining_duplicates = cursor.fetchall()
            
            if remaining_duplicates:
                print(f"Warning: {len(remaining_duplicates)} sets of duplicate chunks still remain")
                return 1
            else:
                print("Successfully cleaned up all duplicate chunks")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
