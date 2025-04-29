#!/usr/bin/env python3
"""
Script to add a unique constraint to the chunks table.
"""

import sys
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()

    print("Adding unique constraint to the chunks table")

    try:
        with get_cursor() as cursor:
            # First, check for duplicate chunks
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
                print(f"Found {len(duplicates)} sets of duplicate chunks:")
                for duplicate in duplicates:
                    print(f"Document ID: {duplicate['document_id']}, Strategy ID: {duplicate['chunking_strategy_id']}, Chunk No: {duplicate['chunk_no']}, Count: {duplicate['count']}")

                print("\nYou need to clean up these duplicates before adding the constraint")
                print("You can use the following SQL to find the specific duplicate chunks:")
                print("""
                SELECT *
                FROM chunks
                WHERE (document_id, chunking_strategy_id, chunk_no) IN (
                    SELECT document_id, chunking_strategy_id, chunk_no
                    FROM chunks
                    GROUP BY document_id, chunking_strategy_id, chunk_no
                    HAVING COUNT(*) > 1
                )
                ORDER BY document_id, chunking_strategy_id, chunk_no;
                """)

                return 1

            # Add the unique constraint
            add_constraint_query = """
            ALTER TABLE chunks
            ADD CONSTRAINT chunks_doc_strategy_chunkno_unique
            UNIQUE (document_id, chunking_strategy_id, chunk_no)
            """

            # Execute the query
            cursor.execute(add_constraint_query)

            # Commit the transaction
            cursor.connection.commit()

            print("Successfully added unique constraint to the chunks table")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
