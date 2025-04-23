#!/usr/bin/env python3
"""
Cleanup script to find and delete zero vectors from the embeddings database.

This script identifies and removes embeddings that are all zeros, which might have been
created by error in previous versions of the code.
"""

import argparse
import logging
import sys
from typing import Optional

from localknowledge.db.embeddings import get_embeddings_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_zero_vectors(embed_source: Optional[str] = None) -> int:
    """
    Find embeddings that are all zeros.

    Args:
        embed_source: Name of the embedding source (optional)

    Returns:
        Number of zero vectors found
    """
    embeddings_db = get_embeddings_db()
    zero_vectors = embeddings_db.find_zero_vectors(embed_source)
    
    if not zero_vectors:
        print("No zero vectors found.")
        return 0
    
    print(f"Found {len(zero_vectors)} embeddings with zero vectors:")
    
    # Group by embedding source
    sources = {}
    for record in zero_vectors:
        source = record['embed_source']
        if source not in sources:
            sources[source] = []
        sources[source].append(record)
    
    # Print summary by source
    for source, records in sources.items():
        print(f"  - {source}: {len(records)} zero vectors")
    
    # Print some examples
    print("\nExample zero vectors:")
    for i, record in enumerate(zero_vectors[:5]):
        print(f"  {i+1}. ID: {record['id']}, Document: {record['document_id']}, "
              f"Source: {record['embed_source']}, Model: {record['model_name']}")
    
    if len(zero_vectors) > 5:
        print(f"  ... and {len(zero_vectors) - 5} more")
    
    return len(zero_vectors)


def delete_zero_vectors(embed_source: Optional[str] = None, dry_run: bool = True) -> int:
    """
    Delete embeddings that are all zeros.

    Args:
        embed_source: Name of the embedding source (optional)
        dry_run: If True, only show what would be deleted without actually deleting

    Returns:
        Number of zero vectors deleted
    """
    embeddings_db = get_embeddings_db()
    
    # First find the zero vectors
    zero_vectors = embeddings_db.find_zero_vectors(embed_source)
    
    if not zero_vectors:
        print("No zero vectors found.")
        return 0
    
    print(f"Found {len(zero_vectors)} embeddings with zero vectors.")
    
    # Group by embedding source
    sources = {}
    for record in zero_vectors:
        source = record['embed_source']
        if source not in sources:
            sources[source] = []
        sources[source].append(record)
    
    # Print summary by source
    for source, records in sources.items():
        print(f"  - {source}: {len(records)} zero vectors")
    
    if dry_run:
        print("\nDRY RUN: No embeddings were deleted. Run with --delete to actually delete them.")
        return 0
    
    # Delete the zero vectors
    deleted = embeddings_db.delete_zero_vectors(embed_source)
    print(f"\nDeleted {deleted} embeddings with zero vectors.")
    
    return deleted


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description='Find and delete zero vectors from the embeddings database')
    parser.add_argument('--source', type=str, default=None,
                        help='Embedding source to check (e.g., "abstract"). If not specified, check all sources.')
    parser.add_argument('--delete', action='store_true',
                        help='Delete zero vectors. If not specified, only show what would be deleted.')
    parser.add_argument('--stats', action='store_true',
                        help='Show embedding statistics.')

    args = parser.parse_args()

    try:
        embeddings_db = get_embeddings_db()
        
        if args.stats:
            # Show embedding statistics
            stats = embeddings_db.get_embedding_stats()
            print("\nEmbedding Statistics:")
            print(f"  Total embeddings: {stats['total_embeddings']}")
            print(f"  Documents with embeddings: {stats['documents_with_embeddings']}")
            print(f"  Zero vectors: {stats.get('zero_vectors', 'unknown')}")
            
            print("\nEmbeddings by source:")
            for source in stats['embeddings_by_source']:
                print(f"  - {source['name']}: {source['count']}")
            
            print("\nEmbeddings by model:")
            for model in stats['embeddings_by_model']:
                print(f"  - {model['model_name']}: {model['count']}")
        
        if args.delete:
            # Delete zero vectors
            delete_zero_vectors(args.source, dry_run=False)
        else:
            # Just find and report zero vectors
            find_zero_vectors(args.source)

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
