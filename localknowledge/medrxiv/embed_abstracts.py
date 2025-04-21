#!/usr/bin/env python3
"""
Module for embedding medrxiv abstracts.

This module provides functionality to identify and embed medrxiv abstracts
that haven't been embedded yet.
"""

import os
import sys
import logging
import argparse
import time
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm
import ollama

from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.embeddings import EmbeddingManager
from localknowledge.embeddings.database import EmbeddingDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.ERROR,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CustomEmbeddingManager(EmbeddingManager):
    """Custom EmbeddingManager that handles the current Ollama API response structure."""

    def _verify_model(self):
        """Verify that the model is available in Ollama."""
        logger.debug(f"Verifying model: {self.model_name}")
        try:
            # Get the list of models from Ollama
            model_names = [model['model'] for model in ollama.list()['models']]

            if self.model_name not in model_names:
                logger.warning(f"Model {self.model_name} not found in Ollama. Will attempt to pull it.")
                logger.debug(f"Pulling model: {self.model_name}...")
                ollama.pull(self.model_name)
                logger.info(f"Successfully pulled model {self.model_name}")
            
        except Exception as e:
            logger.error(f"Error verifying model: {e}")
            # Don't raise the exception, just log it
            # This allows the process to continue even if the model verification fails

    def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Use the embeddings method with prompt parameter (not input)
            start_time = time.time()
            response = ollama.embeddings(model=self.model_name, prompt=text)
            end_time = time.time()

            # Get the embedding from the response
            if 'embedding' in response:
                embedding = response['embedding']
                return embedding
            else:
                logger.error(f"Unexpected response format from Ollama: {response}")
                return []
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            # Return an empty list instead of raising an exception
            return []


class MedrxivAbstractEmbedder:
    """Class for embedding medrxiv abstracts."""

    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest"):
        """
        Initialize the MedrxivAbstractEmbedder.

        Args:
            model_name: Name of the Ollama model to use for embeddings
        """
        self.medrxiv_db = MedRxivDatabaseManager()
        self.embedding_db = EmbeddingDatabaseManager()
        self.embedding_manager = CustomEmbeddingManager(model_name=model_name)
        logger.info(f"Initialized MedrxivAbstractEmbedder with model: {model_name}")

    def close(self):
        """Close database connections."""
        self.medrxiv_db.close()
        self.embedding_db.close()
        self.embedding_manager.close()
        logger.info("Closed all database connections")

    def get_abstracts_without_embeddings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get medrxiv abstracts that haven't been embedded yet.

        Args:
            limit: Maximum number of abstracts to retrieve

        Returns:
            List of abstracts without embeddings
        """
        # Get all preprints with abstracts
        query = """
        SELECT doi, title, abstract
        FROM preprints
        WHERE abstract IS NOT NULL AND abstract != ''
        """

        if limit:
            query += f" LIMIT {limit}"

        all_abstracts = self.medrxiv_db.execute(query)
        logger.info(f"Found {len(all_abstracts)} total abstracts in the database")

        # Filter out abstracts that already have embeddings
        abstracts_without_embeddings = []
        for i, abstract in enumerate(all_abstracts):
            doi = abstract['doi']
            # Check if this abstract has any embeddings
            embeddings = self.embedding_db.get_document_embeddings(
                source_id='medrxiv',
                document_id=doi
            )
            if not embeddings:
                abstracts_without_embeddings.append(abstract)

        logger.info(f"Found {len(abstracts_without_embeddings)} abstracts without embeddings")
        return abstracts_without_embeddings

    def embed_abstracts(self, limit: Optional[int] = None, batch_size: int = 100) -> int:
        """
        Embed medrxiv abstracts that haven't been embedded yet.

        Args:
            limit: Maximum number of abstracts to embed
            batch_size: Number of abstracts to process in each batch

        Returns:
            Number of abstracts embedded
        """
        # Get abstracts without embeddings
        abstracts = self.get_abstracts_without_embeddings(limit)

        if not abstracts:
            logger.info("No abstracts found that need embedding")
            return 0

        # Process abstracts in batches with progress bar
        total_embedded = 0
        total_batches = (len(abstracts) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(abstracts))
            batch = abstracts[start_idx:end_idx]


            # Process each abstract in the batch with progress bar
            for abstract in tqdm(batch, desc=f"Batch {batch_idx + 1}"):
                doi = abstract['doi']
                abstract_text = abstract['abstract']

                if not abstract_text or abstract_text.strip() == '':
                    continue

                try:
                    # Log abstract length

                    # Create embedding directly
                    start_time = time.time()
                    embedding = self.embedding_manager.create_embedding(abstract_text)
                    embedding_time = time.time() - start_time

                    # Skip if embedding creation failed
                    if not embedding:
                        logger.warning(f"Failed to create embedding for DOI: {doi}, skipping")
                        continue

                    # Extract keywords
                    keywords_start = time.time()
                    keywords = self.embedding_manager.extract_keywords(abstract_text)
                    keywords_time = time.time() - keywords_start

                    # Store the embedding
                    store_start = time.time()
                    try:
                        # Use the existing embedding_db manager to store the embedding
                        # This ensures we're using the same database connection and schema as the rest of the application
                        self.embedding_db.store_embedding(
                            source_id='medrxiv',
                            document_id=doi,
                            chunk_no=0,  # Single chunk for the abstract
                            page_no=None,
                            text=abstract_text,
                            embedding=embedding,
                            model_name=self.embedding_manager.model_name,
                            keywords=keywords,
                            commit=True  # Explicitly commit the transaction
                        )

                        storage_time = time.time() - store_start
                    except Exception as e:
                        storage_time = time.time() - store_start
                        logger.error(f"Error storing embedding: {e} (after {storage_time:.2f} seconds)")
                        # Continue with the next abstract even if this one fails

                    total_embedded += 1

                except Exception as e:
                    logger.error(f"Error embedding abstract with DOI {doi}: {e}")


        return total_embedded

    def count_abstracts_without_embeddings(self) -> int:
        """
        Count the number of abstracts without embeddings.

        Returns:
            Number of abstracts without embeddings
        """
        # This is a more efficient version that uses a JOIN to find abstracts without embeddings
        query = """
        SELECT COUNT(DISTINCT p.doi) as count
        FROM preprints p
        LEFT JOIN (
            SELECT DISTINCT document_id
            FROM embeddings
            WHERE source_id = 'medrxiv'
        ) e ON p.doi = e.document_id
        WHERE p.abstract IS NOT NULL
        AND p.abstract != ''
        AND e.document_id IS NULL
        """

        result = self.medrxiv_db.execute(query)
        count = result[0]['count'] if result else 0
        return count


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

    args = parser.parse_args()

    try:
        # Initialize the embedder
        embedder = MedrxivAbstractEmbedder(model_name=args.model)

        if args.count:
            # Count abstracts without embeddings
            count = embedder.count_abstracts_without_embeddings()
            print(f"Found {count} abstracts without embeddings")
        else:
            # Embed abstracts
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
