#!/usr/bin/env python3
"""
Script for embedding medrxiv abstracts directly using MedrxivAbstractEmbedder.

This script bypasses the MedRxivClient and uses the MedrxivAbstractEmbedder directly.
"""

import os
import sys
import logging
import argparse

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Embed medrxiv abstracts')
    parser.add_argument('--limit', type=int, help='Maximum number of abstracts to embed')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of abstracts to process in each batch')
    parser.add_argument('--model', type=str, default="snowflake-arctic-embed2:latest",
                        help='Name of the Ollama model to use for embeddings')
    parser.add_argument('--count', action='store_true',
                        help='Only count abstracts without embeddings, do not embed')

    args = parser.parse_args()

    try:
        logger.info("Starting abstract embedding process")

        # Initialize the embedder directly
        logger.info(f"Initializing MedrxivAbstractEmbedder with model: {args.model}")
        embedder = MedrxivAbstractEmbedder(model_name=args.model)
        logger.info("Embedder initialized successfully")

        if args.count:
            # Count abstracts without embeddings
            logger.info("Counting abstracts without embeddings...")
            count = embedder.count_abstracts_without_embeddings()
            logger.info(f"Found {count} abstracts without embeddings")
            print(f"Found {count} abstracts without embeddings")
        else:
            # Embed abstracts
            logger.info(f"Embedding abstracts (limit={args.limit}, batch_size={args.batch_size})...")
            embedded = embedder.embed_abstracts(
                limit=args.limit,
                batch_size=args.batch_size
            )
            logger.info(f"Successfully embedded {embedded} abstracts")
            print(f"Successfully embedded {embedded} abstracts")

        # Close connections
        embedder.close()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
