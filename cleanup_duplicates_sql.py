#!/usr/bin/env python3
"""
Script to clean up duplicate chunks using SQL.
"""

import sys
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()

    print("Cleaning up duplicate chunks using SQL")

    try:
        with get_cursor() as cursor:
            # Delete all chunks for document 62024974 and strategy 2
            delete_query = """
            DELETE FROM chunks
            WHERE document_id = 62024974 AND chunking_strategy_id = 2
            """

            # Execute the query
            cursor.execute(delete_query)

            # Commit the transaction
            cursor.connection.commit()

            print(f"Deleted {cursor.rowcount} chunks")

            # Verify no more duplicates
            check_query = """
            SELECT document_id, chunking_strategy_id, chunk_no, COUNT(*)
            FROM chunks
            GROUP BY document_id, chunking_strategy_id, chunk_no
            HAVING COUNT(*) > 1
            """

            # Execute the query
            cursor.execute(check_query)

            # Fetch all duplicate chunks
            duplicates = cursor.fetchall()

            if duplicates:
                print(f"Warning: {len(duplicates)} sets of duplicate chunks still remain")
                for duplicate in duplicates:
                    print(f"Document ID: {duplicate['document_id']}, Strategy ID: {duplicate['chunking_strategy_id']}, Chunk No: {duplicate['chunk_no']}, Count: {duplicate['count']}")
                return 1
            else:
                print("Successfully cleaned up all duplicate chunks")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
