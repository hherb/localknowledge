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

from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkerDatabaseManager, Chunk
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and higher levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AbstractEmbeddingUpdater:
    """Class for updating abstract embeddings for documents without embeddings."""
    def __init__(self, embedder = OllamaEmbedder, model_name: str = "snowflake-arctic-embed2:latest"):
        self.embeddings_db = get_embeddings_db()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkerDatabaseManager()
        self.embedder = embedder(model_name)
        self.model_name = model_name
        self.vectorsize = self.embedder.get_vectorsize()
        # Make sure we have a table for this vector size
        self.embeddings_db.ensure_table_for_vectorsize(self.vectorsize)
        # Get the model ID
        self.model_id = self.embeddings_db.get_model_id(model_name)
        if self.model_id == -1:
            logger.warning(f"Model {model_name} not found in embedding_models table. Embeddings will not be stored.")

    def count_documents_without_embeddings(self) -> int:
        """Count documents without embeddings.

        Returns:
            Number of documents without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_name = self.embedder.get_model_name()
        return self.embeddings_db.count_documents_without_embeddings(
            embed_source='abstract',
            model_name=model_name,
            vector_size=vector_size
        )

    def get_documents_without_embeddings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get documents without embeddings.

        Args:
            limit: Maximum number of documents to retrieve

        Returns:
            List of documents without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_name = self.embedder.get_model_name()
        return self.embeddings_db.get_documents_without_embeddings_batch(
            embed_source='abstract',
            limit=limit,
            offset=0,
            model_name=model_name,
            vector_size=vector_size
        )

    def update_abstract_embeddings(self, limit: Optional[int] = None, batch_size: int = 20, workers: int = 4, dry_run: bool = False) -> int:
        """Update abstract embeddings for documents without embeddings.

        Args:
            limit: Maximum number of documents to process
            batch_size: Number of documents to process in each batch
            workers: Number of worker threads to use for parallel processing
            dry_run: If True, don't actually modify the database

        Returns:
            Number of documents successfully processed
        """
        total_processed = 0

        with tqdm.tqdm(total=limit, desc="Updating abstract embeddings") as pbar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                while True:
                    documents = self.get_documents_without_embeddings(limit=batch_size)
                    if not documents:
                        break

                    futures = [executor.submit(self.process_document, doc, dry_run) for doc in documents]

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            success, _ = future.result()
                            if success:
                                total_processed += 1
                        except Exception as e:
                            logger.error(f"Error processing document: {e}")

                        pbar.update(1)

        return total_processed

    def process_document(self, document: Dict[str, Any], dry_run: bool = False) -> Tuple[bool, str]:
        """Process a single document to create and store its embedding.

        Args:
            document: Document data including id, abstract, etc.
            dry_run: If True, don't actually modify the database

        Returns:
            Tuple of (success, message)
        """
        document_id = document['id']
        source_name = document['source_name']
        external_id = document['external_id']
        abstract_text = document['abstract']
        title = document.get('title', '')

        # Skip if abstract is empty
        if not abstract_text or abstract_text.strip() == '':
            return False, f"Skipping document {document_id} ({source_name}/{external_id}) with empty abstract"

        # Skip if model_id is not valid
        if self.model_id == -1:
            return False, f"Skipping document {document_id} ({source_name}/{external_id}) - model not found in database"

        try:
            # Create embedding - this will raise an exception if it fails
            embedding = self.create_embedding(abstract_text)

            if dry_run:
                # In dry run mode, just log what would happen
                logger.info(f"DRY RUN: Would create chunk and embedding for document {document_id} ({source_name}/{external_id})")
                return True, f"DRY RUN: Would add embedding for document {document_id} ({source_name}/{external_id})"

            # First, get or create a chunk for this abstract
            # Get the chunking strategy ID for 'abstract'
            chunking_strategy_id = self.chunker_db.get_or_create_chunking_strategy(
                'abstract_single', {'single_chunk': True}
            )

            # Get the chunk type ID for 'abstract'
            chunktype_id = self.chunker_db.get_or_create_chunktype('abstract')

            # Create a chunk object
            chunk = Chunk(
                chunk_id=0,  # Will be assigned by the database
                document_id=document_id,
                chunking_strategy_id=chunking_strategy_id,
                chunktype_id=chunktype_id,
                document_title=title,
                text=abstract_text,
                chunklength=len(abstract_text),
                chunk_no=0,  # For abstracts, we use a single chunk
                page_start=0,
                page_end=0,
                metadata={'source': source_name, 'external_id': external_id}
            )

            # Get or create the chunk in the database
            chunk_id = self.chunker_db.get_or_create_chunk(chunk)

            if chunk_id <= 0:
                return False, f"Failed to create chunk for document {document_id} ({source_name}/{external_id})"

            # Store embedding in the appropriate table based on vector size
            try:
                # Add the embedding to the database
                embedding_id = self.embeddings_db.add_embedding(
                    chunk_id=chunk_id,
                    model_id=self.model_id,
                    embedding=embedding
                )

                if embedding_id > 0:
                    return True, f"Added embedding for document {document_id} ({source_name}/{external_id}), chunk {chunk_id}"
                else:
                    return False, f"Failed to add embedding for document {document_id} ({source_name}/{external_id}), chunk {chunk_id}"
            except Exception as e:
                logger.error(f"Error processing document {document_id} ({source_name}/{external_id}): {e}")
                return False, f"Error: {str(e)}"

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Use the embedder to create the embedding
            embedding = self.embedder.embed(text)

            if not embedding or len(embedding) == 0:
                logger.error("Embedding creation failed - empty result")
                raise ValueError("Embedding creation failed - empty result")

            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise


def main():
    """Main function to update abstract embeddings."""
    parser = argparse.ArgumentParser(description='Update abstract embeddings for documents without embeddings.')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of documents to process')
    parser.add_argument('--batch-size', type=int, default=20, help='Number of documents to process in each batch')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads to use for parallel processing')
    parser.add_argument('--model', type=str, default="snowflake-arctic-embed2:latest", help='Name of the embedding model to use')
    parser.add_argument('--embedder', type=str, default="ollama", choices=["ollama", "pubmedbert"], help='Type of embedder to use')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without modifying the database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information about each document processed')
    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logger.setLevel(logging.INFO)

    # Choose the embedder based on the argument
    if args.embedder == "ollama":
        embedder_class = OllamaEmbedder
    elif args.embedder == "pubmedbert":
        embedder_class = PubMedBERTEmbedder
    else:
        logger.error(f"Unknown embedder type: {args.embedder}")
        sys.exit(1)

    # Create the updater
    updater = AbstractEmbeddingUpdater(embedder=embedder_class, model_name=args.model)

    # Print model information
    print(f"Using model: {args.model}")
    print(f"Model ID: {updater.model_id}")
    print(f"Vector size: {updater.vectorsize}")
    print(f"Table name: {updater.embeddings_db.get_tablename_for_vectorsize(updater.vectorsize)}")

    # Count documents without embeddings
    count = updater.count_documents_without_embeddings()
    print(f"Found {count} documents without embeddings")

    if count == 0:
        print("No documents to process")
        sys.exit(0)

    if args.dry_run:
        print("Performing dry run - no database modifications will be made")
        # Get a sample of documents to process
        sample_size = min(5, count)
        documents = updater.get_documents_without_embeddings(limit=sample_size)

        print(f"\nSample of {len(documents)} documents that would be processed:")
        for doc in documents:
            doc_id = doc['id']
            source_name = doc['source_name']
            external_id = doc['external_id']
            title = doc.get('title', 'No title')
            abstract_length = len(doc['abstract']) if doc['abstract'] else 0

            print(f"\nDocument ID: {doc_id}")
            print(f"Source: {source_name}")
            print(f"External ID: {external_id}")
            print(f"Title: {title}")
            print(f"Abstract length: {abstract_length} characters")

            # Create embedding for demonstration
            if abstract_length > 0:
                try:
                    embedding = updater.create_embedding(doc['abstract'])
                    print(f"Successfully created embedding with {len(embedding)} dimensions")

                    # Show a sample of the embedding vector
                    if len(embedding) > 0:
                        sample = embedding[:3] + ['.....'] + embedding[-3:]
                        print(f"Embedding sample: {sample}")
                except Exception as e:
                    print(f"Error creating embedding: {e}")

        print("\nDry run completed. No changes were made to the database.")
    else:
        # Process documents
        processed = updater.update_abstract_embeddings(
            limit=args.limit,
            batch_size=args.batch_size,
            workers=args.workers,
            dry_run=args.dry_run
        )

        print(f"Successfully processed {processed} documents")


if __name__ == "__main__":
    main()