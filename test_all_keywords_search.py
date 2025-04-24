#!/usr/bin/env python3
"""
Test script for the all_keywords column and search functionality.
This script tests the search_documents method with the all_keywords column.
"""

import sys
import time
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from localknowledge.db.document import DocumentDatabaseManager

def test_search(include_terms: List[str], exclude_terms: Optional[List[str]] = None, source_name: Optional[str] = None, limit: int = 20):
    """
    Test the search functionality with the all_keywords column.
    
    Args:
        include_terms: List of terms to include in the search
        exclude_terms: List of terms to exclude from the search (optional)
        source_name: Source filter (optional)
        limit: Maximum number of results
    """
    print("\n" + "="*80)
    print(f"Testing search with:")
    print(f"  Include terms: {include_terms}")
    print(f"  Exclude terms: {exclude_terms}")
    print(f"  Source: {source_name}")
    print(f"  Limit: {limit}")
    print("="*80)
    
    # Create a document database manager
    db_manager = DocumentDatabaseManager()
    
    # Join the include terms with commas for the query
    query = ', '.join(include_terms)
    
    # Measure execution time
    start_time = time.time()
    
    try:
        # Check if the all_keywords column exists
        result = db_manager.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'document' AND column_name = 'all_keywords';
        """)
        
        has_all_keywords = bool(result)
        print(f"all_keywords column exists: {has_all_keywords}")
        
        # Perform the search
        results = db_manager.search_documents(
            search_text=query,
            source_name=source_name,
            limit=limit,
            exclude_terms=exclude_terms
        )
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Print results
        print(f"\nSearch completed in {execution_time:.2f} seconds")
        print(f"Found {len(results)} results")
        
        # Print the first few results
        if results:
            print("\nFirst few results:")
            for i, result in enumerate(results[:3]):
                print(f"\n--- Result {i+1} ---")
                print(f"Title: {result.get('title', 'No title')}")
                print(f"Source: {result.get('source_name', 'Unknown')}")
                print(f"DOI: {result.get('doi', 'No DOI')}")
                
                # Print keywords if available
                if 'all_keywords' in result:
                    print(f"All Keywords: {result['all_keywords']}")
                if 'keywords' in result:
                    print(f"Keywords: {result['keywords']}")
                if 'mesh_terms' in result:
                    print(f"Mesh Terms: {result['mesh_terms']}")
                
            if len(results) > 3:
                print(f"\n... and {len(results) - 3} more results")
        
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
    # Test with a single include term
    test_search(["covid"])
    
    # Test with multiple include terms
    test_search(["covid", "vaccine"])
    
    # Test with include and exclude terms
    test_search(["covid", "vaccine"], ["children", "pediatric"])
    
    # Test with source filter
    test_search(["covid"], None, "pubmed")
    
    # Test with custom terms if provided as command line arguments
    if len(sys.argv) > 1:
        include_terms = []
        exclude_terms = []
        
        # Parse command line arguments
        for arg in sys.argv[1:]:
            if arg.startswith('-'):
                # This is an exclude term
                term = arg[1:].strip()
                if term:
                    exclude_terms.append(term)
            else:
                # This is an include term
                include_terms.append(arg)
        
        if include_terms:
            test_search(include_terms, exclude_terms if exclude_terms else None)
        else:
            print("Please provide at least one include term.")

if __name__ == "__main__":
    main()
