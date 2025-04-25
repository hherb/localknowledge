#!/usr/bin/env python3
"""
Test script for the HyDE search functionality in DocumentSearchManager.
"""

import sys
import time
import argparse
from typing import List, Optional
from localknowledge.db.document_search import DocumentSearchManager

def test_hyde_search(question: str,
                    similarity_threshold: float = 0.5,
                    max_results: int = 20,
                    source_name: Optional[str] = None,
                    timeout: Optional[int] = 60,  # Longer default timeout for HyDE
                    async_mode: bool = False,
                    hydeprompt: Optional[str] = None,
                    model_name: Optional[str] = None):
    """
    Test the HyDE search functionality.
    
    Args:
        question: The question or query to search for
        similarity_threshold: Minimum similarity score (0-1) for results
        max_results: Maximum number of results to return
        source_name: Filter by source name (optional)
        timeout: Query timeout in seconds (None for no timeout)
        async_mode: Whether to run the query in asynchronous mode
        hydeprompt: Optional pre-generated hypothetical document
        model_name: Model to use for generating the hypothetical document
    """
    print("\n" + "="*80)
    print(f"Testing HyDE search with:")
    print(f"  Question: {question}")
    print(f"  Similarity threshold: {similarity_threshold}")
    print(f"  Max results: {max_results}")
    print(f"  Source: {source_name}")
    print(f"  Timeout: {timeout if timeout is not None else 'None (unlimited)'}")
    print(f"  Async mode: {async_mode}")
    print(f"  Custom HyDE prompt: {'Yes' if hydeprompt else 'No'}")
    print(f"  Model: {model_name or 'Default (gemma3:4b)'}")
    print("="*80)
    
    # Create a document search manager
    search_manager = DocumentSearchManager()
    
    # Measure execution time
    start_time = time.time()
    
    # Perform the search and collect results
    results = []
    result_count = 0
    first_results = []
    hyde_document = None
    
    # Get the generator
    result_generator = search_manager.hyde(
        question=question,
        similarity_threshold=similarity_threshold,
        max_results=max_results,
        source_name=source_name,
        timeout=timeout,
        async_mode=async_mode,
        hydeprompt=hydeprompt,
        model_name=model_name
    )
    
    # Process results as they come in
    try:
        for doc in result_generator:
            results.append(doc)
            result_count += 1
            
            # Keep track of the first 5 results for display
            if len(first_results) < 5:
                first_results.append(doc)
                
            # Save the HyDE document from the first result
            if hyde_document is None and 'hyde_document' in doc:
                hyde_document = doc['hyde_document']
                
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
    
    # Print the HyDE document
    if hyde_document:
        print("\nHyDE Document:")
        print("-" * 80)
        print(hyde_document)
        print("-" * 80)
    
    # Print the first few results
    if first_results:
        print("\nFirst few results:")
        for i, doc in enumerate(first_results):
            print(f"{i+1}. {doc['title']} (Similarity: {doc['similarity']:.4f})")
            if 'abstract' in doc:
                print(f"   Abstract: {doc['abstract'][:150]}...")
            print()
    
    # Close the database connection
    search_manager.close()
    
    return results

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test HyDE search functionality')
    
    parser.add_argument('question', help='The question or query to search for')
    parser.add_argument('--threshold', '-t', type=float, default=0.5, 
                        help='Similarity threshold (default: 0.5)')
    parser.add_argument('--limit', '-l', type=int, default=20, 
                        help='Maximum number of results (default: 20)')
    parser.add_argument('--source', '-s', help='Source filter (e.g., pubmed, medrxiv)')
    parser.add_argument('--timeout', type=int, default=60, 
                        help='Query timeout in seconds (default: 60, 0 for no timeout)')
    parser.add_argument('--async', '-a', dest='async_mode', action='store_true',
                        help='Run in asynchronous mode')
    parser.add_argument('--model', '-m', help='Model to use for generating the hypothetical document')
    parser.add_argument('--hydeprompt', '-p', help='Pre-generated hypothetical document')
    parser.add_argument('--hydefile', '-f', help='File containing pre-generated hypothetical document')
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Get timeout (None for no timeout)
    timeout = args.timeout if args.timeout > 0 else None
    
    # Get hydeprompt from file if specified
    hydeprompt = args.hydeprompt
    if args.hydefile:
        try:
            with open(args.hydefile, 'r') as f:
                hydeprompt = f.read()
            print(f"Loaded HyDE prompt from file: {args.hydefile}")
        except Exception as e:
            print(f"Error loading HyDE prompt from file: {e}")
            sys.exit(1)
    
    # Run the test
    test_hyde_search(
        question=args.question,
        similarity_threshold=args.threshold,
        max_results=args.limit,
        source_name=args.source,
        timeout=timeout,
        async_mode=args.async_mode,
        hydeprompt=hydeprompt,
        model_name=args.model
    )
