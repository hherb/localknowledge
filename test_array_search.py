#!/usr/bin/env python3
"""
Test script for the array operator keyword search functionality.
This script tests the search_documents method with include and exclude terms.
"""

import sys
import time
from localknowledge.db.document import DocumentDatabaseManager

def test_array_search(include_terms, exclude_terms=None, source_name=None, limit=20):
    """
    Test the array operator keyword search with the given parameters.

    Args:
        include_terms: List of terms to include in the search
        exclude_terms: List of terms to exclude from the search (optional)
        source_name: Source filter (optional)
        limit: Maximum number of results
    """
    print(f"\n{'='*80}")
    print(f"Testing array operator search with:")
    print(f"  Include terms: {include_terms}")
    print(f"  Exclude terms: {exclude_terms}")
    print(f"  Source: {source_name}")
    print(f"  Limit: {limit}")
    print(f"{'='*80}")

    # Create a document database manager
    db_manager = DocumentDatabaseManager()

    # Join the include terms with commas for the query
    query = ', '.join(include_terms)

    # Measure execution time
    start_time = time.time()

    try:
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

                # Print keywords if available
                if 'keywords' in result and result['keywords']:
                    print(f"Keywords: {result['keywords']}")

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
    # Test with a single include term only
    test_array_search(["covid"])

    # Test with custom terms if provided as command line arguments
    if len(sys.argv) > 1:
        include_terms = sys.argv[1].split(',')
        exclude_terms = sys.argv[2].split(',') if len(sys.argv) > 2 else None
        test_array_search(include_terms, exclude_terms)

if __name__ == "__main__":
    main()
