#!/usr/bin/env python3
"""
Command-line interface for embedding medrxiv abstracts.
"""

import sys
import argparse
import logging

from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Command-line interface for embedding medrxiv abstracts."""
    parser = argparse.ArgumentParser(description='Embed medrxiv abstracts')
    parser.add_argument('--limit', type=int, help='Maximum number of abstracts to embed')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of abstracts to process in each batch')
    parser.add_argument('--model', type=str, default="snowflake-arctic-embed2:latest",
                        help='Name of the Ollama model to use for embeddings')
    parser.add_argument('--count', action='store_true',
                        help='Only count abstracts without embeddings, do not embed')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)

    try:
        # Initialize the embedder
        embedder = MedrxivAbstractEmbedder(model_name=args.model)
        logger.info("Embedder initialized successfully")

        if args.count:
            # Count abstracts without embeddings
            count = embedder.count_abstracts_without_embeddings()
            print(f"Found {count} abstracts without embeddings")
        else:
            # Embed abstracts
            logger.info(f"Embedding abstracts (limit={args.limit}, batch_size={args.batch_size})...")
            embedded = embedder.embed_abstracts(limit=args.limit, batch_size=args.batch_size)
            print(f"Successfully embedded {embedded} abstracts")

        # Close connections
        embedder.close()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
