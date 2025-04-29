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

from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and higher levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence httpx (used by ollama) INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)


class AbstractEmbeddingUpdater:
    """Class for updating abstract embeddings for chunks without embeddings."""
    def __init__(self, embedder=OllamaEmbedder, model_name: str = "snowflake-arctic-embed2:latest"):
        self.embeddings_db = get_embeddings_db()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkingDatabaseManager()
        self.embedder = embedder(model_name)
        self.model_name = model_name
        self.vectorsize = self.embedder.get_vectorsize()
        # Make sure we have a table for this vector size
        self.embeddings_db.ensure_table_for_vectorsize(self.vectorsize)
        # Get the model ID
        self.model_id = self.embeddings_db.get_model_id(model_name)
        if self.model_id == -1:
            logger.warning(f"Model {model_name} not found in embedding_models table. Embeddings will not be stored.")

    def count_chunks_without_embeddings(self) -> int:
        """Count chunks without embeddings.

        Returns:
            Number of chunks without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_id = self.model_id
        tablename = self.embeddings_db.get_tablename_for_vectorsize(vector_size)

        # Check if the table exists
        check_table_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
        """
        table_exists = self.embeddings_db.execute(check_table_query, (tablename,))

        if not table_exists or not table_exists[0]['exists']:
            # If the table doesn't exist, all chunks need embeddings
            logger.info(f"Table '{tablename}' doesn't exist, counting all abstract chunks")
            query = """
            SELECT COUNT(*) as count
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE ct.chunktype = 'abstract'
            """
            params = []
        else:
            # Count chunks that don't have embeddings in this specific table
            query = f"""
            SELECT COUNT(*) as count
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            LEFT JOIN {tablename} e ON c.id = e.chunk_id AND e.model_id = %s
            WHERE ct.chunktype = 'abstract'
            AND e.id IS NULL
            """
            params = [model_id]

        result = self.embeddings_db.execute(query, params)
        count = result[0]['count'] if result else 0
        return count

    def get_chunks_without_embeddings(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Get chunks without embeddings.

        Args:
            limit: Maximum number of chunks to retrieve
            offset: Number of chunks to skip

        Returns:
            List of chunks without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_id = self.model_id
        tablename = self.embeddings_db.get_tablename_for_vectorsize(vector_size)

        # Check if the table exists
        check_table_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
        """
        table_exists = self.embeddings_db.execute(check_table_query, (tablename,))

        if not table_exists or not table_exists[0]['exists']:
            # If the table doesn't exist, all chunks need embeddings
            logger.info(f"Table '{tablename}' doesn't exist, getting all abstract chunks")
            query = """
            SELECT c.*, d.title as document_title, d.abstract
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            JOIN document d ON c.document_id = d.id
            WHERE ct.chunktype = 'abstract'
            ORDER BY c.id
            """
            params = []
        else:
            # Get chunks that don't have embeddings in this specific table
            query = f"""
            SELECT c.*, d.title as document_title, d.abstract
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            JOIN document d ON c.document_id = d.id
            LEFT JOIN {tablename} e ON c.id = e.chunk_id AND e.model_id = %s
            WHERE ct.chunktype = 'abstract'
            AND e.id IS NULL
            ORDER BY c.id
            """
            params = [model_id]

        # Add OFFSET and LIMIT clauses
        if offset > 0:
            query += f" OFFSET {offset}"

        if limit:
            query += f" LIMIT {limit}"

        chunks = self.embeddings_db.execute(query, params)
        logger.debug(f"Found {len(chunks)} abstract chunks without embeddings (offset: {offset}, limit: {limit})")
        return chunks or []

    def update_abstract_embeddings(self, limit: Optional[int] = None, batch_size: int = 20, workers: int = 4, dry_run: bool = False) -> int:
        """Update abstract embeddings for chunks without embeddings.

        Args:
            limit: Maximum number of chunks to process
            batch_size: Number of chunks to process in each batch
            workers: Number of worker threads to use for parallel processing
            dry_run: If True, don't actually modify the database

        Returns:
            Number of chunks successfully processed
        """
        total_processed = 0
        total_to_process = self.count_chunks_without_embeddings()

        if limit:
            total_to_process = min(total_to_process, limit)

        with tqdm.tqdm(total=total_to_process, desc="Updating abstract embeddings") as pbar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                offset = 0
                while True:
                    chunks = self.get_chunks_without_embeddings(limit=batch_size, offset=offset)
                    if not chunks:
                        break

                    futures = [executor.submit(self.process_chunk, chunk, dry_run) for chunk in chunks]

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            success, _ = future.result()
                            if success:
                                total_processed += 1
                        except Exception as e:
                            logger.error(f"Error processing chunk: {e}")

                        pbar.update(1)

                    offset += batch_size
                    if limit and total_processed >= limit:
                        break

        return total_processed

    def process_chunk(self, chunk: Dict[str, Any], dry_run: bool = False) -> Tuple[bool, str]:
        """Process a single chunk to create and store its embedding.

        Args:
            chunk: Chunk data including id, text, document_id, etc.
            dry_run: If True, don't actually modify the database

        Returns:
            Tuple of (success, message)
        """
        chunk_id = chunk['id']
        document_id = chunk['document_id']
        text = chunk.get('text', '')
        document_title = chunk.get('document_title', '')

        # If text is empty, try to use the abstract from the document
        if not text or text.strip() == '':
            text = chunk.get('abstract', '')

        # Skip if text is still empty
        if not text or text.strip() == '':
            return False, f"Skipping chunk {chunk_id} (document {document_id}) with empty text"

        # Skip if model_id is not valid
        if self.model_id == -1:
            return False, f"Skipping chunk {chunk_id} (document {document_id}) - model not found in database"

        try:
            # Create embedding - this will raise an exception if it fails
            embedding = self.create_embedding(text)

            if dry_run:
                # In dry run mode, just log what would happen
                logger.info(f"DRY RUN: Would add embedding for chunk {chunk_id} (document {document_id})")
                return True, f"DRY RUN: Would add embedding for chunk {chunk_id} (document {document_id})"

            # Store embedding in the appropriate table based on vector size
            try:
                # Add the embedding to the database
                embedding_id = self.embeddings_db.add_embedding(
                    chunk_id=chunk_id,
                    model_id=self.model_id,
                    embedding=embedding
                )

                if embedding_id > 0:
                    return True, f"Added embedding for chunk {chunk_id} (document {document_id})"
                else:
                    return False, f"Failed to add embedding for chunk {chunk_id} (document {document_id})"
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_id} (document {document_id}): {e}")
                return False, f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id} (document {document_id}): {e}")
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
        logging.getLogger("localknowledge.db.embeddings").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.base").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.INFO)
    else:
        # Silence INFO logs from various modules
        logging.getLogger("localknowledge.db.embeddings").setLevel(logging.WARNING)
        logging.getLogger("localknowledge.db.base").setLevel(logging.WARNING)
        logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.WARNING)

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

    # Count chunks without embeddings
    count = updater.count_chunks_without_embeddings()
    print(f"Found {count} chunks without embeddings")

    if count == 0:
        print("No chunks to process")
        sys.exit(0)

    if args.dry_run:
        print("Performing dry run - no database modifications will be made")
        # Get a sample of chunks to process
        sample_size = min(5, count)
        chunks = updater.get_chunks_without_embeddings(limit=sample_size)

        print(f"\nSample of {len(chunks)} chunks that would be processed:")
        for chunk in chunks:
            chunk_id = chunk['id']
            document_id = chunk['document_id']
            document_title = chunk.get('document_title', 'No title')
            text = chunk.get('text', '')
            if not text:
                text = chunk.get('abstract', '')
            text_length = len(text) if text else 0

            print(f"\nChunk ID: {chunk_id}")
            print(f"Document ID: {document_id}")
            print(f"Document Title: {document_title}")
            print(f"Text length: {text_length} characters")

            # Create embedding for demonstration
            if text_length > 0:
                try:
                    embedding = updater.create_embedding(text)
                    print(f"Successfully created embedding with {len(embedding)} dimensions")

                    # Show a sample of the embedding vector
                    if len(embedding) > 0:
                        sample = embedding[:3] + ['.....'] + embedding[-3:]
                        print(f"Embedding sample: {sample}")
                except Exception as e:
                    print(f"Error creating embedding: {e}")

        print("\nDry run completed. No changes were made to the database.")
    else:
        # Process chunks
        processed = updater.update_abstract_embeddings(
            limit=args.limit,
            batch_size=args.batch_size,
            workers=args.workers,
            dry_run=args.dry_run
        )

        print(f"Successfully processed {processed} chunks")


if __name__ == "__main__":
    main()
