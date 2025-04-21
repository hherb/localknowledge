#!/usr/bin/env python3
"""
Example script for embedding medrxiv abstracts.

This script demonstrates how to use the MedrxivAbstractEmbedder to embed
medrxiv abstracts that haven't been embedded yet.
"""

import os
import sys
import logging
import argparse

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.medrxiv import MedRxivClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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
        # Initialize the client
        client = MedRxivClient()

        if args.count:
            # Count abstracts without embeddings
            count = client.count_abstracts_without_embeddings()
            print(f"Found {count} abstracts without embeddings")
        else:
            # Embed abstracts
            embedded = client.embed_abstracts(
                limit=args.limit,
                batch_size=args.batch_size,
                model_name=args.model
            )
            print(f"Successfully embedded {embedded} abstracts")

        # Close connections
        client.close()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
