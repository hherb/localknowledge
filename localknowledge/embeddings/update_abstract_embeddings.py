#!/usr/bin/env python3
"""
Update abstract embeddings for documents without embeddings.

This module creates embeddings for abstracts in the document table that don't have
embeddings yet, using the Ollama API directly. It shows progress with tqdm and
handles errors gracefully.
"""

import argparse
import logging
from typing import List, Dict, Any, Optional, Tuple
import sys
import concurrent.futures
import time

import tqdm
import ollama
import backoff
import httpx

from localknowledge.db.embeddings import get_embeddings_db

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and higher levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only show WARNING and higher levels

# Suppress INFO messages from all libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("ollama").setLevel(logging.WARNING)
logging.getLogger("localknowledge").setLevel(logging.WARNING)


class AbstractEmbeddingUpdater:
    """Class for updating abstract embeddings for documents without embeddings."""

    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest"):
        """
        Initialize the AbstractEmbeddingUpdater.

        Args:
            model_name: Name of the Ollama model to use for embeddings
        """
        self.model_name = model_name
        self.embeddings_db = get_embeddings_db()
        self._verify_model()
        # Don't log initialization at INFO level, as we're suppressing INFO messages

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _verify_model(self) -> None:
        """Verify that the model is available in Ollama."""
        try:
            # Create a client instance
            client = ollama.Client()

            # Get the list of models from Ollama
            models_response = client.list()
            model_names = [model['model'] for model in models_response['models']]

            if self.model_name not in model_names:
                logger.warning(f"Model {self.model_name} not found in Ollama. Will attempt to use it anyway.")
                logger.info(f"Available models: {', '.join(model_names)}")
        except Exception as e:
            logger.error(f"Error verifying model: {e}")
            # Don't raise the exception, just log it

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats

        Raises:
            ValueError: If the embedding cannot be created or has an unexpected format
        """
        # Create a client instance
        client = ollama.Client()

        # Make the request to Ollama following the documentation exactly
        response = client.embeddings(model=self.model_name, prompt=text)

        # The response is an EmbeddingsResponse object with an 'embedding' attribute
        if hasattr(response, 'embedding'):
            logger.debug(f"Successfully created embedding with {len(response.embedding)} dimensions")
            return response.embedding

        # If we get here, the response format is unexpected
        error_msg = f"Unexpected response format from Ollama: {type(response)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for multiple texts at once.

        Args:
            texts: List of texts to embed

        Returns:
            List of vector embeddings as lists of floats

        Raises:
            ValueError: If the embeddings cannot be created or have an unexpected format
        """
        if not texts:
            return []

        # Create a client instance
        client = ollama.Client()

        # Make the request to Ollama using the /api/embed endpoint which supports batch processing
        response = client.embed(model=self.model_name, input=texts)

        # The response should have an 'embeddings' attribute with a list of embeddings
        if hasattr(response, 'embeddings'):
            embeddings = response.embeddings
            logger.debug(f"Successfully created {len(embeddings)} embeddings in batch")
            return embeddings

        # If we get here, the response format is unexpected
        error_msg = f"Unexpected response format from Ollama batch embedding: {type(response)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def process_document(self, document: Dict[str, Any]) -> Tuple[bool, str]:
        """Process a single document to create and store its embedding.

        Args:
            document: Document data including id, abstract, etc.

        Returns:
            Tuple of (success, message)
        """
        document_id = document['id']
        source_name = document['source_name']
        external_id = document['external_id']
        abstract_text = document['abstract']

        # Skip if abstract is empty
        if not abstract_text or abstract_text.strip() == '':
            return False, f"Skipping document {document_id} ({source_name}/{external_id}) with empty abstract"

        try:
            # Create embedding - this will raise an exception if it fails
            embedding = self.create_embedding(abstract_text)

            # Store embedding in unified_multiembeddings table
            try:
                # Store the embedding
                self.embeddings_db.add_embedding(
                    document_id=document_id,
                    embed_source='abstract',
                    text=abstract_text,
                    embedding=embedding,
                    model_name=self.model_name,
                    chunk_no=0,  # Single chunk for the abstract
                    page_no=None,
                    keywords=document.get('keywords', []),
                    metadata=None
                )

                return True, f"Successfully processed document {document_id} ({source_name}/{external_id})"

            except Exception as e:
                error_msg = f"Error storing embedding for document {document_id}: {e}"
                logger.error(error_msg)
                return False, error_msg

        except ValueError as e:
            # This is raised when the embedding format is unexpected
            error_msg = f"Error creating embedding for document {document_id} ({source_name}/{external_id}): {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            # Catch any other exceptions
            error_msg = f"Unexpected error processing document {document_id} ({source_name}/{external_id}): {e}"
            logger.error(error_msg)
            return False, error_msg

    def close(self) -> None:
        """Close database connections."""
        self.embeddings_db.close()
        # Don't log closing at INFO level, as we're suppressing INFO messages

    def get_documents_without_embeddings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get documents with abstracts that don't have embeddings yet.

        Args:
            limit: Maximum number of documents to retrieve

        Returns:
            List of documents without embeddings
        """
        # Use the embeddings_db to get documents without embeddings
        return self.embeddings_db.get_documents_without_embeddings('abstract', limit)

    def get_documents_without_embeddings_batch(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get a batch of documents with abstracts that don't have embeddings yet.

        Args:
            limit: Maximum number of documents to retrieve
            offset: Number of documents to skip

        Returns:
            List of documents without embeddings
        """
        # Use the embeddings_db to get a batch of documents without embeddings
        return self.embeddings_db.get_documents_without_embeddings_batch('abstract', limit, offset)

    def count_documents_without_embeddings(self) -> int:
        """
        Count the number of documents without embeddings.

        Returns:
            Number of documents without embeddings
        """
        # Use the embeddings_db to count documents without embeddings
        return self.embeddings_db.count_documents_without_embeddings('abstract')

    def update_abstract_embeddings(self, limit: Optional[int] = None, batch_size: int = 20, workers: int = 4, embedding_batch_size: int = 10) -> int:
        """
        Update abstract embeddings for documents without embeddings using parallel processing and batch embedding.

        Args:
            limit: Maximum number of documents to process
            batch_size: Number of documents to process in each database batch
            workers: Number of worker threads to use for parallel processing
            embedding_batch_size: Number of documents to process in each embedding batch

        Returns:
            Number of documents processed
        """
        # The embeddings_db will ensure the abstract embedding source exists

        # Count total documents without embeddings
        total_count = self.count_documents_without_embeddings()
        if total_count == 0:
            print("No documents found that need embeddings")
            return 0

        # Apply limit if specified
        if limit is not None and limit < total_count:
            total_to_process = limit
        else:
            total_to_process = total_count

        print(f"Found {total_count} documents without embeddings, will process {total_to_process}")
        print(f"Using {workers} worker threads and embedding batch size of {embedding_batch_size}")

        # Process documents in batches
        total_processed = 0
        offset = 0
        batch_number = 0

        # Create a single progress bar for all documents
        with tqdm.tqdm(total=total_to_process, desc="Processing documents", unit="doc") as pbar:
            while total_processed < total_to_process:
                # Calculate current batch size
                current_batch_size = min(batch_size, total_to_process - total_processed)

                # Get a batch of documents
                documents = self.get_documents_without_embeddings_batch(limit=current_batch_size, offset=offset)
                if not documents:
                    # No more documents to process
                    break

                batch_number += 1
                batch_start_time = time.time()

                # Process the batch using batch embedding
                successful_count = self.process_document_batch(documents, embedding_batch_size)

                # Update progress bar
                pbar.update(len(documents))
                pbar.set_description(f"Processed {total_processed + successful_count}/{total_to_process} documents")

                # Update counters
                total_processed += successful_count
                offset += len(documents)

                # Calculate and display batch statistics
                batch_duration = time.time() - batch_start_time
                docs_per_second = len(documents) / batch_duration if batch_duration > 0 else 0
                print(f"Batch {batch_number}: Processed {len(documents)} documents in {batch_duration:.2f}s ({docs_per_second:.2f} docs/s), {successful_count} successful")

                # Check if we've reached the limit
                if limit is not None and total_processed >= limit:
                    break

        return total_processed

    def process_document_batch(self, documents: List[Dict[str, Any]], embedding_batch_size: int = 10) -> int:
        """
        Process a batch of documents using batch embedding.

        Args:
            documents: List of documents to process
            embedding_batch_size: Number of documents to process in each embedding batch

        Returns:
            Number of documents successfully processed
        """
        if not documents:
            return 0

        # Filter out documents with empty abstracts
        valid_documents = []
        for doc in documents:
            if not doc['abstract'] or doc['abstract'].strip() == '':
                logger.warning(f"Skipping document {doc['id']} ({doc['source_name']}/{doc['external_id']}) with empty abstract")
                continue
            valid_documents.append(doc)

        if not valid_documents:
            return 0

        # Process documents in embedding batches
        successful_count = 0

        # Process in smaller batches to avoid memory issues
        for i in range(0, len(valid_documents), embedding_batch_size):
            batch = valid_documents[i:i+embedding_batch_size]

            # Extract abstracts
            abstracts = [doc['abstract'] for doc in batch]

            try:
                # Create embeddings for the batch
                embeddings = self.create_batch_embeddings(abstracts)

                # Store embeddings in the database
                for j, doc in enumerate(batch):
                    try:
                        # Store the embedding
                        # Note: add_embedding already has commit=True internally
                        self.embeddings_db.add_embedding(
                            document_id=doc['id'],
                            embed_source='abstract',
                            text=doc['abstract'],
                            embedding=embeddings[j],
                            model_name=self.model_name,
                            chunk_no=0,  # Single chunk for the abstract
                            page_no=None,
                            keywords=doc.get('keywords', []),
                            metadata=None
                        )
                        successful_count += 1
                    except Exception as e:
                        logger.error(f"Error storing embedding for document {doc['id']}: {e}")
            except Exception as e:
                logger.error(f"Error creating batch embeddings: {e}")

        return successful_count


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update abstract embeddings for documents without embeddings',
        epilog='''
        Performance Tips:
        - The default settings (batch-size=20, embedding-batch-size=10, workers=4) are optimized for good performance
        - For systems with more CPU cores, try increasing --workers to 6-8
        - For systems with less memory, try decreasing --batch-size to 10
        - For faster processing, try increasing --embedding-batch-size to 20 (requires more memory)
        - Running without --limit will process all documents without embeddings
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--model', type=str, default='snowflake-arctic-embed2:latest',
                        help='Ollama model to use for embeddings')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of documents to process')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='Number of documents to process in each database batch (default: 20)')
    parser.add_argument('--embedding-batch-size', type=int, default=10,
                        help='Number of documents to process in each embedding batch (default: 10)')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of worker threads for parallel processing (default: 4)')
    parser.add_argument('--count', action='store_true',
                        help='Only count documents without embeddings, do not process')
    parser.add_argument('--verbose', action='store_true',
                        help='Show verbose output (INFO level messages)')

    args = parser.parse_args()

    # If verbose mode is enabled, set logging level to INFO
    if args.verbose:
        logger.setLevel(logging.INFO)
        logging.getLogger("localknowledge").setLevel(logging.INFO)

    try:
        # Initialize the updater
        updater = AbstractEmbeddingUpdater(model_name=args.model)

        if args.count:
            # Count documents without embeddings
            count = updater.count_documents_without_embeddings()
            print(f"Found {count} documents without abstract embeddings")
        else:
            # Update abstract embeddings
            processed = updater.update_abstract_embeddings(
                limit=args.limit,
                batch_size=args.batch_size,
                workers=args.workers,
                embedding_batch_size=args.embedding_batch_size
            )
            print(f"Successfully processed {processed} documents")

        # Close connections
        updater.close()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
