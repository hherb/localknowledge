#!/usr/bin/env python3
"""
Test script for the keyword search functionality.
This script tests the search_documents method in isolation without the GUI.
"""

import sys
import time
from localknowledge.db.document import DocumentDatabaseManager

def test_keyword_search(query, source_name=None, limit=20):
    """
    Test the keyword search with the given parameters.
    
    Args:
        query: Search query
        source_name: Source filter (optional)
        limit: Maximum number of results
    """
    print(f"\n{'='*80}")
    print(f"Testing keyword search with query: '{query}', source: {source_name}, limit: {limit}")
    print(f"{'='*80}")
    
    # Create a document database manager
    db_manager = DocumentDatabaseManager()
    
    # Measure execution time
    start_time = time.time()
    
    try:
        # Perform the search
        results = db_manager.search_documents(
            search_text=query,
            source_name=source_name,
            limit=limit
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
                print(f"Authors: {', '.join(result.get('authors', []))}")
                if 'abstract' in result and result['abstract']:
                    abstract = result['abstract']
                    if len(abstract) > 200:
                        abstract = abstract[:200] + "..."
                    print(f"Abstract: {abstract}")
                
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

def main():
    """Run a series of test searches."""
    # Test with a simple query
    test_keyword_search("covid")
    
    # Test with a more specific query
    test_keyword_search("vaccine efficacy")
    
    # Test with a source filter
    test_keyword_search("covid", source_name="pubmed")
    test_keyword_search("covid", source_name="medrxiv")
    
    # Test with a query that might be slow
    test_keyword_search("the")
    
    # Test with a query containing special characters
    test_keyword_search("covid-19")
    
    # Test with a query that should return no results
    test_keyword_search("xyzabc123notfound")
    
    # Test with a custom query if provided as command line argument
    if len(sys.argv) > 1:
        custom_query = sys.argv[1]
        test_keyword_search(custom_query)

if __name__ == "__main__":
    main()
