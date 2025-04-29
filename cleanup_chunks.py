#!/usr/bin/env python3
"""
Script to clean up chunks for a specific document and strategy.
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
    
    print(f"Cleaning up chunks for document {document_id} and strategy {strategy_id}")
    
    try:
        with get_cursor() as cursor:
            # Get count of chunks for the document and strategy
            count_query = """
            SELECT COUNT(*) as count
            FROM chunks
            WHERE document_id = %s
            AND chunking_strategy_id = %s
            """
            
            # Execute the query
            cursor.execute(count_query, (document_id, strategy_id))
            
            # Get the count
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            print(f"Found {count} chunks to delete")
            
            if count > 0:
                # Delete all chunks for the document and strategy
                delete_query = """
                DELETE FROM chunks
                WHERE document_id = %s
                AND chunking_strategy_id = %s
                """
                
                # Execute the query
                cursor.execute(delete_query, (document_id, strategy_id))
                
                # Print results
                print(f"Deleted {cursor.rowcount} chunks")
            
            # Verify deletion
            cursor.execute(count_query, (document_id, strategy_id))
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            print(f"Verification: {count} chunks remaining")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
