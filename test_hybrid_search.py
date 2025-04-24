#!/usr/bin/env python
"""
Test script for the hybrid search module.
"""

import logging
import argparse
from typing import List, Dict, Any

from localknowledge.db.connection_pool import initialize_pool
from localknowledge.embeddings.multiembeddings import EmbeddingManager
from localknowledge.ai.hybrid_search import perform_hybrid_search

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(results: List[Dict[str, Any]], title: str = "Search Results"):
    """
    Print search results in a readable format.
    
    Args:
        results: List of search results
        title: Title to display above results
    """
    print(f"\n{title} ({len(results)} results):")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        # Get source tag
        source_id = result.get('source_id')
        source_tag = '[pubmed] ' if source_id == 1 else '[medrxiv] ' if source_id == 2 else ''
        
        # Print result
        print(f"{i}. {source_tag}{result.get('title', 'Untitled')}")
        print(f"   Similarity: {result.get('similarity', 0):.4f}")
        print(f"   Document ID: {result.get('id')}")
        
        # Print authors if available
        authors = result.get('authors', [])
        if authors:
            if isinstance(authors, list):
                authors_str = ", ".join(authors)
            else:
                authors_str = str(authors)
            print(f"   Authors: {authors_str}")
        
        print()


def main():
    """Main function to test hybrid search."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test hybrid search')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--max-results', type=int, default=10, help='Maximum number of results')
    parser.add_argument('--threshold', type=float, default=0.3, help='Similarity threshold')
    parser.add_argument('--rerank', action='store_true', help='Use reranking')
    args = parser.parse_args()
    
    # Initialize the connection pool
    initialize_pool(min_connections=1, max_connections=5)
    logger.info("Database connection pool initialized")
    
    # Create the embedding manager
    embedding_manager = EmbeddingManager()
    logger.info(f"Using embedding model: {embedding_manager.model_name}")
    
    # Perform hybrid search
    logger.info(f"Performing hybrid search for query: {args.query}")
    result = perform_hybrid_search(
        embedding_manager=embedding_manager,
        query=args.query,
        max_results=args.max_results,
        threshold=args.threshold,
        use_reranker=args.rerank
    )
    
    # Print HyDE abstract if available
    abstract = result.get('abstract')
    if abstract:
        print("\nHyDE Abstract:")
        print("-" * 80)
        print(abstract)
    
    # Print results
    print_results(result.get('results', []), "Hybrid Search Results")


if __name__ == "__main__":
    main()
