#!/usr/bin/env python3
"""
Test script to verify that vector search works with the migrated embeddings.
"""

import sys
import argparse
import logging
from typing import List, Dict, Any

from localknowledge.db.unified_multiembeddings import get_unified_multiembeddings_db
import ollama

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def search_similar_documents(query_text: str,
                            embed_source: str = 'abstract',
                            model_name: str = 'snowflake-arctic-embed2:latest',
                            limit: int = 10,
                            threshold: float = 0.5) -> List[Dict[str, Any]]:
    """
    Search for documents similar to the query text.

    Args:
        query_text: The text to search for
        embed_source: The source of embeddings to search in ('abstract' or 'qa_pairs')
        model_name: The name of the embedding model
        limit: Maximum number of results to return
        threshold: Similarity threshold (0-1)

    Returns:
        List of similar documents with similarity scores
    """
    logger.info(f"Generating embedding for query: '{query_text[:50]}...' if len(query_text) > 50 else query_text")

    # Generate embedding for the query text using Ollama
    try:
        response = ollama.embeddings(model=model_name, prompt=query_text)
        query_embedding = response['embedding']
    except Exception as e:
        logger.error(f"Error getting embedding with model {model_name}: {e}")
        return []

    if not query_embedding:
        logger.error(f"Failed to generate embedding for query text")
        return []

    logger.info(f"Generated embedding with {len(query_embedding)} dimensions")

    # Get the unified_multiembeddings database manager
    db = get_unified_multiembeddings_db()

    # Search for similar documents
    logger.info(f"Searching for similar documents in {embed_source} embeddings with model {model_name}")
    results = db.search_similar(
        embedding=query_embedding,
        embed_source=embed_source,
        model_name=model_name,
        limit=limit,
        threshold=threshold
    )

    logger.info(f"Found {len(results)} similar documents")

    return results

def main():
    """Run the vector search test."""
    parser = argparse.ArgumentParser(description='Test vector search with migrated embeddings')
    parser.add_argument('--query', type=str, required=True, help='Query text to search for')
    parser.add_argument('--source', type=str, default='abstract', choices=['abstract', 'qa_pairs'],
                        help='Source of embeddings to search in (default: abstract)')
    parser.add_argument('--model', type=str, default='snowflake-arctic-embed2:latest',
                        help='Name of the embedding model (default: snowflake-arctic-embed2:latest)')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of results (default: 10)')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Similarity threshold 0-1 (default: 0.5)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Search for similar documents
    results = search_similar_documents(
        query_text=args.query,
        embed_source=args.source,
        model_name=args.model,
        limit=args.limit,
        threshold=args.threshold
    )

    # Print results
    if results:
        print(f"\nFound {len(results)} similar documents:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. Document ID: {result['document_id']}")
            print(f"   Title: {result.get('title', 'N/A')}")
            print(f"   Similarity: {result['similarity']:.4f}")
            print(f"   Source: {result['embed_source']}")
            print(f"   Model: {result['model_name']}")
            print(f"   Chunk: {result['chunk_no']}, Page: {result['page_no'] or 'N/A'}")

            # Print a snippet of the abstract
            abstract = result.get('abstract', '')
            if abstract:
                snippet = abstract[:200] + "..." if len(abstract) > 200 else abstract
                print(f"   Abstract: {snippet}")

            print()
    else:
        print("No similar documents found.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
