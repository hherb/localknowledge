#!/usr/bin/env python3
"""
Script to chunk all records that do not have chunks for the AdaptiveTextChunker strategy.

This script:
1. Identifies documents without chunks for the specified chunking strategy
2. Processes them in batches of 100 documents
3. Shows progress using tqdm
4. Inserts the chunks into the database

This is a modified version with quieter logging - only showing tqdm progress bars,
warnings and errors.
"""

import logging
import argparse
import time
from typing import List, Dict, Any, Iterator, Optional
import json
from tqdm import tqdm

from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk as DBChunk
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging - silence all loggers by default
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and higher levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Silence INFO logs from dependencies
logging.getLogger("localknowledge.db.base").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.chunker").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.connection_pool").setLevel(logging.WARNING)
logging.getLogger("localknowledge.textprocessing.chunking").setLevel(logging.WARNING)

# Constants
CHUNKING_STRATEGY_NAME = "adaptive_text_chunker_1500"
CHUNKING_STRATEGY_DESCRIPTION = "AdaptiveTextChunker with max_chunk_size=1500, overlap=100"
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table
BATCH_SIZE = 100  # Number of documents to process in each batch

def get_or_create_chunking_strategy() -> int:
    """
    Get or create the chunking strategy for AdaptiveTextChunker.

    Returns:
        The ID of the chunking strategy
    """
    # Parameters for the chunking strategy
    parameters = {
        "max_chunk_size": 1500,
        "overlap": 100,
        "min_chunk_size": 100,
        "includes_title": True,
        "boundary_aware": True,
        "description": CHUNKING_STRATEGY_DESCRIPTION  # Include description in parameters
    }

    # Create database manager
    db_manager = ChunkingDatabaseManager()

    # Get or create the chunking strategy
    strategy_id = db_manager.get_or_create_chunking_strategy(
        strategy_name=CHUNKING_STRATEGY_NAME,
        parameters=parameters
    )

    print(f"Using chunking strategy '{CHUNKING_STRATEGY_NAME}' with ID {strategy_id}")

    return strategy_id

def get_documents_without_chunks(strategy_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get documents that do not have chunks for the specified chunking strategy.

    Args:
        strategy_id: The ID of the chunking strategy
        limit: Optional limit on the number of documents to retrieve

    Returns:
        List of document dictionaries
    """
    print(f"Getting documents without chunks for strategy {strategy_id}")

    try:
        with get_cursor() as cursor:
            # Use a more efficient query with EXISTS and index hints
            print("Retrieving documents without chunks...")
            query = """
            SELECT d.id, d.title, d.abstract
            FROM document d
            WHERE d.abstract IS NOT NULL
            AND length(d.abstract) > 0
            AND NOT EXISTS (
                SELECT 1
                FROM chunks c
                WHERE c.document_id = d.id
                AND c.chunking_strategy_id = %s
            )
            """

            # Add ordering to get a consistent result set
            query += " ORDER BY d.id"

            # Add limit if specified
            if limit:
                query += f" LIMIT {limit}"
                print(f"Limiting to {limit} documents")

            # Execute the query
            cursor.execute(query, (strategy_id,))

            # Fetch all documents
            documents = cursor.fetchall()
            print(f"Retrieved {len(documents)} documents")

            # Return all documents as a list
            return documents

    except Exception as e:
        print(f"Error getting documents without chunks: {e}")
        raise

def process_documents(documents: List[Dict[str, Any]], chunker: AdaptiveTextChunker, strategy_id: int) -> int:
    """
    Process documents and create chunks.

    Args:
        documents: List of document dictionaries
        chunker: Text chunker instance
        strategy_id: The ID of the chunking strategy

    Returns:
        Number of chunks created
    """
    if not documents:
        print("No documents to process")
        return 0

    # Create database manager
    db_manager = ChunkingDatabaseManager()

    # Process each document
    total_chunks = 0

    for doc in documents:
        doc_id = doc['id']
        title = doc['title'] or "Untitled"
        abstract = doc['abstract']

        # Skip documents without abstracts
        if not abstract or len(abstract.strip()) == 0:
            print(f"Warning: Skipping document {doc_id} with empty abstract")
            continue

        # Create metadata with title
        metadata = {
            'title': title,
            'source': 'abstract',
            'document_id': doc_id
        }

        try:
            # Chunk the abstract
            chunks = chunker.chunk(abstract, metadata=metadata)

            # Convert to database chunks
            db_chunks = []
            for i, chunk in enumerate(chunks):
                db_chunk = chunk.to_db_chunk(
                    document_id=doc_id,
                    chunking_strategy_id=strategy_id,
                    chunktype_id=CHUNKTYPE_ID,
                    document_title=title,
                    chunk_no=i
                )
                db_chunks.append(db_chunk)

            # Insert chunks into database
            if db_chunks:
                chunk_ids = db_manager.batch_insert_chunks(db_chunks)
                total_chunks += len(chunk_ids)
            else:
                print(f"Warning: No chunks created for document {doc_id}")

        except Exception as e:
            print(f"Error processing document {doc_id}: {e}")
            # Continue with the next document
            continue

    return total_chunks

def ensure_index_exists():
    """
    Ensure that the necessary indexes exist on the chunks table.
    """
    print("Checking for necessary indexes...")

    try:
        with get_cursor() as cursor:
            # Check if the index exists
            query = """
            SELECT 1
            FROM pg_indexes
            WHERE tablename = 'chunks'
            AND indexname = 'idx_chunks_document_id_chunking_strategy_id'
            """
            cursor.execute(query)
            index_exists = cursor.fetchone() is not None

            if not index_exists:
                print("Creating index on chunks(document_id, chunking_strategy_id)...")
                create_index_query = """
                CREATE INDEX idx_chunks_document_id_chunking_strategy_id
                ON chunks(document_id, chunking_strategy_id)
                """
                cursor.execute(create_index_query)
                cursor.connection.commit()
                print("Index created successfully")
            else:
                print("Index already exists")

    except Exception as e:
        print(f"Error checking/creating index: {e}")
        # Continue without the index

def main():
    """
    Main function.
    """
    global BATCH_SIZE

    parser = argparse.ArgumentParser(description="Chunk documents without chunks for AdaptiveTextChunker")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit the number of documents to process (default: process all)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"Number of documents to process in each batch (default: {BATCH_SIZE})")
    parser.add_argument("--verbose", action="store_true",
                        help="Show more detailed logging (default: False)")
    args = parser.parse_args()

    # Update batch size if specified
    BATCH_SIZE = args.batch_size

    # Enable verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.chunker").setLevel(logging.INFO)
        logging.getLogger("localknowledge.textprocessing.chunking").setLevel(logging.INFO)

    # Load environment variables
    load_environment()

    # Ensure necessary indexes exist
    ensure_index_exists()

    # Get or create chunking strategy
    strategy_id = get_or_create_chunking_strategy()

    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=1500,
        overlap=100,
        min_chunk_size=100
    )

    # Get documents without chunks
    try:
        # Get all documents without chunks
        all_documents = get_documents_without_chunks(strategy_id, args.limit)

        if not all_documents:
            print("No documents found without chunks for the specified strategy")
            return

        # Process documents with progress bar
        total_documents = len(all_documents)
        total_chunks = 0
        start_time = time.time()

        # Create a progress bar for all documents
        with tqdm(total=total_documents, desc="Processing documents", unit="doc") as pbar:
            # Process documents in batches
            for i in range(0, len(all_documents), BATCH_SIZE):
                # Get the current batch
                batch = all_documents[i:i+BATCH_SIZE]

                # Process the batch
                chunks_created = process_documents(batch, chunker, strategy_id)

                # Update counters
                total_chunks += chunks_created

                # Update progress bar
                pbar.update(len(batch))
                pbar.set_postfix({
                    "chunks": total_chunks,
                    "chunks/doc": round(total_chunks / max(1, pbar.n), 2)
                })

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        # Print summary
        print(f"Processed {total_documents} documents in {elapsed_time:.2f} seconds")
        print(f"Created {total_chunks} chunks ({total_chunks / max(1, total_documents):.2f} chunks per document)")

    except Exception as e:
        print(f"Error processing documents: {e}")
        raise

if __name__ == "__main__":
    main()
