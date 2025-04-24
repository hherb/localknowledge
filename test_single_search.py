#!/usr/bin/env python3
"""
Test script for a single keyword search.
"""

import sys
import time
from localknowledge.db.document import DocumentDatabaseManager

def test_single_search(query="covid"):
    """
    Test a single keyword search.
    
    Args:
        query: Search query (default: "covid")
    """
    print(f"\n{'='*80}")
    print(f"Testing keyword search with query: '{query}'")
    print(f"{'='*80}")
    
    # Create a document database manager
    db_manager = DocumentDatabaseManager()
    
    # Measure execution time
    start_time = time.time()
    
    try:
        # Perform the search
        results = db_manager.search_documents(
            search_text=query,
            limit=20
        )
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Print results
        print(f"\nSearch completed in {execution_time:.2f} seconds")
        print(f"Found {len(results)} results")
        
        # Print the first few results
        if results:
            print("\nFirst few results:")
            for i, result in enumerate(results[:5]):
                print(f"\n--- Result {i+1} ---")
                print(f"Title: {result.get('title', 'No title')}")
                print(f"Source: {result.get('source_name', 'Unknown')}")
                print(f"DOI: {result.get('doi', 'No DOI')}")
                if 'authors' in result and result['authors']:
                    if isinstance(result['authors'], list):
                        authors = ', '.join(result['authors'])
                    else:
                        authors = str(result['authors'])
                    print(f"Authors: {authors}")
                
            if len(results) > 5:
                print(f"\n... and {len(results) - 5} more results")
        
    except Exception as e:
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Print error
        print(f"\nSearch failed after {execution_time:.2f} seconds")
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())
    
    finally:
        # Close the database connection
        db_manager.close()

if __name__ == "__main__":
    # Use command line argument if provided, otherwise use default
    query = sys.argv[1] if len(sys.argv) > 1 else "covid"
    test_single_search(query)
