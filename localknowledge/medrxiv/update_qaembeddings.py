#!/usr/bin/env python3
"""
Module for updating QA embeddings for medrxiv abstracts.

This module provides functionality to identify medrxiv abstracts that don't have
QA embeddings yet, generate question-answer pairs, and store them with embeddings.
"""

import os
import sys
import logging
import argparse
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.qafinder import QAEmbeddingDatabaseManager
from localknowledge.ai.qafinder import QAEmbeddingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set logging levels for specific modules to reduce verbosity
logging.getLogger('localknowledge.db.qafinder').setLevel(logging.WARNING)
logging.getLogger('localknowledge.ai.qafinder').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)


class MedrxivQAEmbedder:
    """Class for generating and embedding QA pairs from medrxiv abstracts."""

    def __init__(self,
                 model_name: str = "gemma3:4b",
                 embedding_model: str = "snowflake-arctic-embed2:latest"):
        """
        Initialize the MedrxivQAEmbedder.

        Args:
            model_name: Name of the Ollama model to use for QA generation
            embedding_model: Name of the Ollama model to use for embeddings
        """
        self.medrxiv_db = MedRxivDatabaseManager()
        self.qa_db = QAEmbeddingDatabaseManager()
        self.qa_manager = QAEmbeddingManager(
            model_name=model_name,
            embedding_model=embedding_model
        )
        logger.debug(f"Initialized MedrxivQAEmbedder with models: {model_name} (QA), {embedding_model} (embedding)")

    def close(self):
        """Close database connections."""
        self.medrxiv_db.close()
        self.qa_db.close()
        self.qa_manager.close()
        logger.debug("Closed all database connections")

    def get_abstracts_without_qa_embeddings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get medrxiv abstracts that don't have QA embeddings yet.

        Args:
            limit: Maximum number of abstracts to retrieve

        Returns:
            List of abstracts without QA embeddings
        """
        # Use a more efficient query that directly gets abstracts without QA embeddings
        query = """
        SELECT p.doi, p.title, p.abstract
        FROM preprints p
        LEFT JOIN (
            SELECT DISTINCT document_id
            FROM qaembeddings
            WHERE source_id = 'medrxiv'
        ) q ON p.doi = q.document_id
        WHERE p.abstract IS NOT NULL
        AND p.abstract != ''
        AND q.document_id IS NULL
        """

        if limit:
            query += f" LIMIT {limit}"

        abstracts_without_qa = self.medrxiv_db.execute(query)
        logger.debug(f"Found {len(abstracts_without_qa)} abstracts without QA embeddings")
        return abstracts_without_qa

    def count_abstracts_without_qa_embeddings(self) -> int:
        """
        Count the number of abstracts without QA embeddings.

        Returns:
            Number of abstracts without QA embeddings
        """
        # This is a more efficient version that uses a JOIN to find abstracts without QA embeddings
        query = """
        SELECT COUNT(DISTINCT p.doi) as count
        FROM preprints p
        LEFT JOIN (
            SELECT DISTINCT document_id
            FROM qaembeddings
            WHERE source_id = 'medrxiv'
        ) q ON p.doi = q.document_id
        WHERE p.abstract IS NOT NULL
        AND p.abstract != ''
        AND q.document_id IS NULL
        """

        result = self.medrxiv_db.execute(query)
        count = result[0]['count'] if result else 0
        return count

    def update_qa_embeddings(self, limit: Optional[int] = None, batch_size: int = 10) -> int:
        """
        Generate QA pairs and embeddings for medrxiv abstracts that don't have them yet.

        Args:
            limit: Maximum number of abstracts to process
            batch_size: Number of abstracts to process in each batch

        Returns:
            Number of abstracts processed
        """
        # Get abstracts without QA embeddings
        abstracts = self.get_abstracts_without_qa_embeddings(limit)

        if not abstracts:
            logger.debug("No abstracts found that need QA embeddings")
            return 0

        # Process abstracts in batches with progress bar
        total_processed = 0
        total_batches = (len(abstracts) + batch_size - 1) // batch_size

        # Create a progress bar for the overall process
        print(f"Processing {len(abstracts)} abstracts in {total_batches} batches")

        # Process each batch
        for batch_idx in tqdm(range(total_batches), desc="Overall progress", unit="batch", ncols=100):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(abstracts))
            batch = abstracts[start_idx:end_idx]

            # Process each abstract in the batch with progress bar
            for abstract in tqdm(batch, desc=f"Processing abstracts", unit="abstract", ncols=100):
                doi = abstract['doi']
                abstract_text = abstract['abstract']

                if not abstract_text or abstract_text.strip() == '':
                    logger.warning(f"Empty abstract for DOI: {doi}, skipping")
                    continue

                try:
                    # Process the text to generate QA pairs and embeddings
                    start_time = time.time()
                    result = self.qa_manager.process_text(
                        source_id='medrxiv',
                        document_id=doi,
                        text=abstract_text,
                        chunk_no=0  # Single chunk for the abstract
                    )

                    processing_time = time.time() - start_time

                    # Any non-negative result indicates success
                    if result >= 0:
                        logger.debug(f"Successfully processed DOI: {doi} in {processing_time:.2f}s")
                        total_processed += 1
                    else:
                        logger.warning(f"Failed to process DOI: {doi}, result: {result}")

                except Exception as e:
                    logger.error(f"Error processing abstract with DOI {doi}: {e}")

        return total_processed


def main():
    """Command-line interface for updating QA embeddings for medrxiv abstracts."""
    parser = argparse.ArgumentParser(description='Update QA embeddings for medrxiv abstracts')
    parser.add_argument('--limit', type=int, help='Maximum number of abstracts to process')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='Number of abstracts to process in each batch')
    parser.add_argument('--qa-model', type=str, default="gemma3:4b",
                        help='Name of the Ollama model to use for QA generation')
    parser.add_argument('--embedding-model', type=str, default="snowflake-arctic-embed2:latest",
                        help='Name of the Ollama model to use for embeddings')
    parser.add_argument('--count', action='store_true',
                        help='Only count abstracts without QA embeddings, do not process')

    args = parser.parse_args()

    try:
        # Initialize the embedder
        embedder = MedrxivQAEmbedder(
            model_name=args.qa_model,
            embedding_model=args.embedding_model
        )

        if args.count:
            # Count abstracts without QA embeddings
            count = embedder.count_abstracts_without_qa_embeddings()
            print(f"Found {count} abstracts without QA embeddings")
        else:
            # Update QA embeddings
            processed = embedder.update_qa_embeddings(limit=args.limit, batch_size=args.batch_size)
            print(f"Successfully processed {processed} abstracts")

        # Close connections
        embedder.close()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
