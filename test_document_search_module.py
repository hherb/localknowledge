#!/usr/bin/env python3
"""
Test script for the new DocumentSearchManager module.
This script tests the keyword search functionality using the all_keywords column.
"""

import sys
import time
import argparse
from typing import List, Optional
from localknowledge.db.document_search import DocumentSearchManager

def test_keyword_search(include_terms: List[str],
                       exclude_terms: Optional[List[str]] = None,
                       source_name: Optional[str] = None,
                       limit: int = 20,
                       timeout: Optional[int] = 30,
                       async_mode: bool = False):
    """
    Test the keyword search functionality.

    Args:
        include_terms: List of terms to include in the search
        exclude_terms: List of terms to exclude from the search (optional)
        source_name: Filter by source name (optional)
        limit: Maximum number of results
        timeout: Query timeout in seconds (None for no timeout)
        async_mode: Whether to run the query in asynchronous mode
    """
    print("\n" + "="*80)
    print(f"Testing keyword search with:")
    print(f"  Include terms: {include_terms}")
    print(f"  Exclude terms: {exclude_terms}")
    print(f"  Source: {source_name}")
    print(f"  Limit: {limit}")
    print(f"  Timeout: {timeout if timeout is not None else 'None (unlimited)'}")
    print(f"  Async mode: {async_mode}")
    print("="*80)

    # Create a document search manager
    search_manager = DocumentSearchManager()

    # Measure execution time
    start_time = time.time()

    # Perform the search and collect results
    results = []
    result_count = 0
    first_results = []

    # Get the generator
    result_generator = search_manager.keywords(
        included=include_terms,
        excluded=exclude_terms,
        source_name=source_name,
        limit=limit,
        timeout=timeout,
        async_mode=async_mode
    )

    # Process results as they come in
    try:
        for doc in result_generator:
            results.append(doc)
            result_count += 1

            # Keep track of the first 5 results for display
            if len(first_results) < 5:
                first_results.append(doc)

            # In async mode, print progress updates
            if async_mode and result_count % 10 == 0:
                current_time = time.time()
                elapsed = current_time - start_time
                print(f"Received {result_count} results so far ({elapsed:.2f} seconds elapsed)...")

    except Exception as e:
        print(f"\nError during search: {e}")

    # Calculate execution time
    execution_time = time.time() - start_time

    # Print results
    print(f"\nSearch completed in {execution_time:.2f} seconds")
    print(f"Found {result_count} results")

    # Print the first few results
    if first_results:
        print("\nFirst few results:")
        for i, doc in enumerate(first_results):
            print(f"{i+1}. {doc['title']} ({doc['source_name']})")
            if 'all_keywords' in doc:
                print(f"   Keywords: {', '.join(doc['all_keywords'][:5])}...")
            print()

    # Close the database connection
    search_manager.close()

    return results

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test document search functionality')

    parser.add_argument('include_terms', help='Comma-separated list of terms to include')
    parser.add_argument('--exclude', '-e', help='Comma-separated list of terms to exclude')
    parser.add_argument('--source', '-s', help='Source filter (e.g., pubmed, medrxiv)')
    parser.add_argument('--limit', '-l', type=int, default=20, help='Maximum number of results (default: 20)')
    parser.add_argument('--timeout', '-t', type=int, default=30,
                        help='Query timeout in seconds (default: 30, 0 for no timeout)')
    parser.add_argument('--async', '-a', dest='async_mode', action='store_true',
                        help='Run in asynchronous mode')

    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Parse include terms
    include_terms = [term.strip() for term in args.include_terms.split(",")]

    # Parse exclude terms if provided
    exclude_terms = None
    if args.exclude:
        exclude_terms = [term.strip() for term in args.exclude.split(",")]

    # Get timeout (None for no timeout)
    timeout = args.timeout if args.timeout > 0 else None

    # Run the test
    test_keyword_search(
        include_terms=include_terms,
        exclude_terms=exclude_terms,
        source_name=args.source,
        limit=args.limit,
        timeout=timeout,
        async_mode=args.async_mode
    )
