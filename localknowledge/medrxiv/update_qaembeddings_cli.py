#!/usr/bin/env python3
"""
Command-line interface for updating QA embeddings for medrxiv abstracts.

This script provides a convenient way to run the update_qaembeddings module
from the command line.

Examples:
    # Count abstracts without QA embeddings
    python -m localknowledge.medrxiv.update_qaembeddings_cli --count

    # Process all abstracts without QA embeddings
    python -m localknowledge.medrxiv.update_qaembeddings_cli

    # Process a limited number of abstracts
    python -m localknowledge.medrxiv.update_qaembeddings_cli --limit 100

    # Use a different QA model
    python -m localknowledge.medrxiv.update_qaembeddings_cli --qa-model "llama3:8b"

    # Use a different embedding model
    python -m localknowledge.medrxiv.update_qaembeddings_cli --embedding-model "nomic-embed-text:latest"
"""

import sys
import logging
from localknowledge.medrxiv.update_qaembeddings import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set logging levels for specific modules to reduce verbosity
logging.getLogger('localknowledge.db.qafinder').setLevel(logging.WARNING)
logging.getLogger('localknowledge.ai.qafinder').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

if __name__ == "__main__":
    sys.exit(main())
