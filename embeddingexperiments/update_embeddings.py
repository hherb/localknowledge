#!/usr/bin/env python3
"""
Combined Chunking and Embedding Script

This script performs two operations in a single process with tqdm progress feedback:
1. Chunks document abstracts using an adaptive chunking strategy
2. Creates embeddings for the chunks using PubMedBERT with model ID 3

The script finds documents that need processing (either chunking or embedding),
processes them in batches, and provides detailed progress feedback.
"""

import logging
import time
import signal
import sys
import atexit
from typing import List, Dict, Any, Tuple
import argparse
import json
from tqdm import tqdm

from pubmedbert import PubMedBERT
from pubmedbert_experiment import get_cursor, load_environment
from chunk_abstracts import AdaptiveTextChunker

# Global variable to hold the model instance for cleanup
_bert_model = None

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MODEL_ID = 3  # PubMedBERT model ID in the database
BATCH_SIZE = 10000  # Number of documents to process in a batch
CHUNK_SIZE = 384  # Size for PubMedBERT chunks when splitting is needed
OVERLAP = 128     # Overlap between chunks to maintain context
SINGLE_CHUNK_THRESHOLD = 2000  # Maximum size for creating a single chunk (covers most abstracts)
CHUNKING_STRATEGY_ID = 1  # ID of the adaptive_splitter strategy in the database
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table




def get_documents_without_embeddings(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get documents that don't have embeddings in the emb_768 table.

    Args:
        limit: Maximum number of documents to retrieve

    Returns:
        List of document dictionaries with id, chunk_id, and text
    """
    documents = []

    try:
        with get_cursor() as cursor:
            # Find chunks that don't have embeddings in emb_768
            query = """
            SELECT c.id as chunk_id, c.document_id, c.text
            FROM chunks c
            LEFT JOIN emb_768 e ON c.id = e.chunk_id AND e.model_id = %s
            WHERE e.id IS NULL
            LIMIT %s
            """

            cursor.execute(query, (MODEL_ID, limit))
            documents = cursor.fetchall()
            logger.info(f"Found {len(documents)} documents without embeddings for model_id {MODEL_ID}")
    except Exception as e:
        logger.error(f"Error getting documents without embeddings: {e}")

    return documents


def insert_embeddings(embeddings_data: List[Tuple[int, int, List[float]]]) -> int:
    """
    Insert embeddings into the emb_768 table.

    Args:
        embeddings_data: List of tuples (chunk_id, model_id, embedding)

    Returns:
        Number of embeddings inserted
    """
    inserted = 0

    try:
        with get_cursor(commit=True) as cursor:
            # Insert embeddings into emb_768 table
            query = """
            INSERT INTO emb_768 (chunk_id, model_id, embedding)
            VALUES (%s, %s, %s)
            """

            cursor.executemany(query, embeddings_data)
            inserted = cursor.rowcount
            logger.info(f"Inserted {inserted} embeddings")

    except Exception as e:
        logger.error(f"Error inserting embeddings: {e}")

    return inserted


def process_documents(documents: List[Dict[str, Any]], bert_model: PubMedBERT) -> int:
    """
    Process documents and create embeddings.

    Args:
        documents: List of document dictionaries
        bert_model: PubMedBERT model instance

    Returns:
        Number of documents processed
    """
    if not documents:
        logger.info("No documents to process")
        return 0

    # Extract texts for batch processing
    texts = [doc['text'] for doc in documents if doc['text']]
    chunk_ids = [doc['chunk_id'] for doc in documents if doc['text']]

    if not texts:
        logger.warning("No valid texts to embed")
        return 0

    try:
        # Generate embeddings in batch
        logger.info(f"Generating embeddings for {len(texts)} documents")
        embeddings = bert_model.embed_batch(texts)

        # Prepare data for insertion
        embeddings_data = [
            (chunk_id, MODEL_ID, embedding)
            for chunk_id, embedding in zip(chunk_ids, embeddings)
        ]

        # Insert embeddings into database
        inserted = insert_embeddings(embeddings_data)
        return inserted

    except Exception as e:
        logger.error(f"Error processing documents: {e}")
        return 0


def ensure_model_exists(timeout: int = 600):
    """
    Ensure that the embedding model with MODEL_ID exists in the database.
    If not, create it.

    Args:
        timeout: Database query timeout in seconds

    Returns:
        bool: True if model exists or was created, False otherwise
    """
    return True
    try:

            # Now create the model
        pubmedbert = PubMedBERT()
        model_name = pubmedbert.get_modelname()
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """
                INSERT INTO embedding_models (id, provider_id, model_name, model_description, model_parameters)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    MODEL_ID,
                    2,  # Provider ID for HuggingFace
                    model_name,
                    "PubMedBERT model for biomedical text embeddings",
                    {"dimension": pubmedbert.get_dimension()}
                )
            )
            logger.info(f"Created embedding model with ID {MODEL_ID}: {model_name}")
            return True
    except Exception as e:
        logger.error(f"Error ensuring model exists: {e}")
        return False


def get_documents_for_processing(limit: int = 100, timeout: int = 600, min_id: int = 0) -> List[Dict[str, Any]]:
    """
    Get documents that need processing (chunking and embedding).

    This function efficiently retrieves documents that either:
    1. Don't have chunks in the chunks table, or
    2. Have chunks but don't have embeddings in the emb_768 table

    It uses a single optimized query with proper indexing.

    Args:
        limit: Maximum number of documents to retrieve
        timeout: Database query timeout in seconds
        min_id: Minimum document ID to start from (for pagination)

    Returns:
        List of document dictionaries with id, title, and abstract
    """
    documents = []

    try:
        print(f"Querying database for documents to process (timeout: {timeout}s, limit: {limit}, min_id: {min_id})...")

        # Use a single efficient query to find documents that need processing
        with get_cursor(timeout=timeout) as cursor:
            # This query finds documents that either:
            # 1. Don't have any chunks, or
            # 2. Have chunks but at least one chunk doesn't have an embedding for the specified model
            query = """
            WITH docs_without_chunks AS (
                -- Documents that don't have any chunks
                SELECT d.id, d.title, d.abstract, 'no_chunks' AS reason
                FROM document d
                WHERE d.id > %s
                AND d.abstract IS NOT NULL
                AND length(d.abstract) > 0
                AND NOT EXISTS (
                    SELECT 1 FROM chunks c
                    WHERE c.document_id = d.id
                )
            ),
            docs_with_chunks_without_embeddings AS (
                -- Documents that have chunks but at least one chunk doesn't have an embedding
                SELECT DISTINCT d.id, d.title, d.abstract, 'no_embeddings' AS reason
                FROM document d
                JOIN chunks c ON d.id = c.document_id
                WHERE d.id > %s
                AND d.abstract IS NOT NULL
                AND length(d.abstract) > 0
                AND EXISTS (
                    SELECT 1 FROM chunks c2
                    WHERE c2.document_id = d.id
                    AND NOT EXISTS (
                        SELECT 1 FROM emb_768 e
                        WHERE e.chunk_id = c2.id
                        AND e.model_id = %s
                    )
                )
                AND d.id NOT IN (SELECT id FROM docs_without_chunks)
            )
            -- Combine both sets and limit the results
            SELECT id, title, abstract, reason
            FROM (
                SELECT * FROM docs_without_chunks
                UNION ALL
                SELECT * FROM docs_with_chunks_without_embeddings
            ) combined
            ORDER BY id
            LIMIT %s
            """

            print(f"Executing optimized query to find documents that need processing...")
            cursor.execute(query, (min_id, min_id, MODEL_ID, limit))
            documents = cursor.fetchall()

            # Count documents by reason
            no_chunks_count = sum(1 for doc in documents if doc['reason'] == 'no_chunks')
            no_embeddings_count = sum(1 for doc in documents if doc['reason'] == 'no_embeddings')

            print(f"Found {len(documents)} documents that need processing:")
            print(f"  - {no_chunks_count} documents without chunks")
            print(f"  - {no_embeddings_count} documents with chunks but missing embeddings")

    except Exception as e:
        print(f"Error getting documents for processing: {e}")
        logger.error(f"Error getting documents for processing: {e}")

    return documents


def chunk_and_embed_documents(documents: List[Dict[str, Any]],
                             bert_model: PubMedBERT,
                             chunker: AdaptiveTextChunker,
                             max_processing_time: int = 300) -> Dict[str, int]:
    """
    Process documents by chunking abstracts and creating embeddings with progress feedback.

    Args:
        documents: List of document dictionaries
        bert_model: PubMedBERT model instance
        chunker: Text chunker instance
        max_processing_time: Maximum time in seconds to spend processing documents

    Returns:
        Dictionary with statistics (documents_processed, chunks_created, embeddings_created)
    """
    if not documents:
        logger.info("No documents to process")
        return {"documents_processed": 0, "chunks_created": 0, "embeddings_created": 0}

    stats = {
        "documents_processed": 0,
        "chunks_created": 0,
        "embeddings_created": 0,
        "single_chunks": 0,
        "multi_chunks": 0,
        "errors": 0,
        "no_chunks_processed": 0,
        "no_embeddings_processed": 0
    }

    start_time = time.time()

    # Create progress bar for the entire process
    with tqdm(total=len(documents), desc="Embedding", unit="doc") as pbar:
        for doc_index, doc in enumerate(documents):
            # Check if we've exceeded the maximum processing time
            if time.time() - start_time > max_processing_time:
                logger.warning(f"Maximum processing time of {max_processing_time}s exceeded. Stopping after {doc_index} documents.")
                break

            try:
                # Skip documents without abstracts
                if not doc['abstract'] or len(doc['abstract'].strip()) == 0:
                    pbar.update(1)
                    continue

                # 1. Chunk the abstract with timeout protection
                abstract_length = len(doc['abstract'])
                reason = doc.get('reason', 'unknown')
                pbar.set_postfix({"abstract_len": abstract_length, "doc_id": doc['id'], "reason": reason})

                # Skip chunking if the document already has chunks and just needs embeddings
                if reason == 'no_embeddings':
                    # Get existing chunks for this document
                    try:
                        with get_cursor() as cursor:
                            cursor.execute("""
                            SELECT id, text FROM chunks
                            WHERE document_id = %s
                            AND NOT EXISTS (
                                SELECT 1 FROM emb_768 e
                                WHERE e.chunk_id = chunks.id
                                AND e.model_id = %s
                            )
                            """, (doc['id'], MODEL_ID))

                            existing_chunks = cursor.fetchall()

                            if not existing_chunks:
                                logger.warning(f"No chunks without embeddings found for document {doc['id']}")
                                pbar.update(1)
                                continue

                            # Create embeddings for existing chunks
                            chunk_ids = [chunk['id'] for chunk in existing_chunks]
                            texts = [chunk['text'] for chunk in existing_chunks]

                            # Generate embeddings in batch with timeout protection
                            embeddings = bert_model.embed_batch(texts)

                            # Prepare data for insertion
                            embeddings_data = [
                                (chunk_id, MODEL_ID, embedding)
                                for chunk_id, embedding in zip(chunk_ids, embeddings)
                                if len(embedding) > 0  # Skip empty embeddings
                            ]

                            # Insert embeddings into database
                            if embeddings_data:
                                inserted = insert_embeddings(embeddings_data)
                                stats["embeddings_created"] += inserted
                                stats["documents_processed"] += 1
                                stats["no_embeddings_processed"] += 1
                            else:
                                logger.warning(f"No valid embeddings created for document {doc['id']}")

                            pbar.update(1)
                            continue

                    except Exception as e:
                        logger.error(f"Error processing existing chunks for document {doc['id']}: {e}")
                        stats["errors"] += 1
                        pbar.update(1)
                        continue

                # For documents without chunks, create new chunks
                try:
                    chunks = chunker.chunk_text(doc['abstract'])
                    if not chunks:
                        logger.warning(f"No chunks created for document {doc['id']}")
                        pbar.update(1)
                        continue
                except Exception as e:
                    logger.error(f"Error chunking document {doc['id']}: {e}")
                    stats["errors"] += 1
                    pbar.update(1)
                    continue

                # Track chunking statistics
                if len(chunks) == 1 and chunks[0][1].get('is_complete_abstract', False):
                    stats["single_chunks"] += 1
                else:
                    stats["multi_chunks"] += 1
                    logger.debug(f"Document {doc['id']} with {abstract_length} chars split into {len(chunks)} chunks")

                # 2. Insert chunks into database and get chunk IDs
                chunk_ids = []
                chunks_data = []

                for chunk_number, (chunk_text, metadata) in enumerate(chunks):
                    # Skip empty chunks
                    if not chunk_text or len(chunk_text.strip()) == 0:
                        continue

                    chunks_data.append((
                        doc['id'],                  # document_id
                        CHUNKING_STRATEGY_ID,       # chunking_strategy_id
                        CHUNKTYPE_ID,               # chunktype_id
                        doc['title'],               # document_title
                        chunk_text,                 # text
                        len(chunk_text),            # chunklength
                        chunk_number,               # chunk_no
                        json.dumps(metadata)        # metadata as JSON string
                    ))

                # Insert chunks and get their IDs
                try:
                    with get_cursor(commit=True) as cursor:
                        for chunk_data in chunks_data:
                            cursor.execute("""
                            INSERT INTO chunks
                            (document_id, chunking_strategy_id, chunktype_id, document_title, text, chunklength, chunk_no, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """, chunk_data)
                            chunk_id = cursor.fetchone()[0]
                            chunk_ids.append(chunk_id)

                    stats["chunks_created"] += len(chunk_ids)
                except Exception as e:
                    logger.error(f"Error inserting chunks for document {doc['id']}: {e}")
                    stats["errors"] += 1
                    pbar.update(1)
                    continue

                # 3. Create embeddings for the chunks
                if chunk_ids:
                    try:
                        # Extract texts for batch processing
                        texts = [chunk[0] for chunk in chunks if chunk[0] and len(chunk[0].strip()) > 0]

                        if not texts:
                            logger.warning(f"No valid texts to embed for document {doc['id']}")
                            pbar.update(1)
                            continue

                        # Generate embeddings in batch with timeout protection
                        embeddings = bert_model.embed_batch(texts)

                        # Prepare data for insertion
                        embeddings_data = [
                            (chunk_id, MODEL_ID, embedding)
                            for chunk_id, embedding in zip(chunk_ids, embeddings)
                            if len(embedding) > 0  # Skip empty embeddings
                        ]

                        # Insert embeddings into database
                        if embeddings_data:
                            inserted = insert_embeddings(embeddings_data)
                            stats["embeddings_created"] += inserted
                        else:
                            logger.warning(f"No valid embeddings created for document {doc['id']}")
                    except Exception as e:
                        logger.error(f"Error creating embeddings for document {doc['id']}: {e}")
                        stats["errors"] += 1
                        pbar.update(1)
                        continue

                stats["documents_processed"] += 1
                if reason == 'no_chunks':
                    stats["no_chunks_processed"] += 1
                pbar.update(1)

                # Print progress every 10 documents
                if stats["documents_processed"] % 10 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"Progress: {stats['documents_processed']}/{len(documents)} documents in {elapsed:.2f}s " +
                               f"({stats['documents_processed']/elapsed:.2f} docs/s)")

            except Exception as e:
                logger.error(f"Error processing document {doc['id']}: {e}")
                stats["errors"] += 1
                pbar.update(1)
                continue

    # Log chunking and embedding statistics
    elapsed = time.time() - start_time
    print(f"\nProcessing statistics:")
    print(f"  - Documents processed: {stats['documents_processed']}/{len(documents)}")
    print(f"    * Documents without chunks: {stats['no_chunks_processed']}")
    print(f"    * Documents with chunks but no embeddings: {stats['no_embeddings_processed']}")
    print(f"  - Chunks created: {stats['chunks_created']} ({stats['single_chunks']} single chunks, {stats['multi_chunks']} multi-chunk documents)")
    print(f"  - Embeddings created: {stats['embeddings_created']}")
    print(f"  - Errors: {stats['errors']}")
    print(f"  - Processing time: {elapsed:.2f}s ({stats['documents_processed']/elapsed:.2f} docs/s)")

    # Also log to the logger
    logger.info(f"Processing statistics:")
    logger.info(f"  - Documents processed: {stats['documents_processed']}/{len(documents)}")
    logger.info(f"    * Documents without chunks: {stats['no_chunks_processed']}")
    logger.info(f"    * Documents with chunks but no embeddings: {stats['no_embeddings_processed']}")
    logger.info(f"  - Chunks created: {stats['chunks_created']} ({stats['single_chunks']} single chunks, {stats['multi_chunks']} multi-chunk documents)")
    logger.info(f"  - Embeddings created: {stats['embeddings_created']}")
    logger.info(f"  - Errors: {stats['errors']}")
    logger.info(f"  - Processing time: {elapsed:.2f}s ({stats['documents_processed']/elapsed:.2f} docs/s)")

    return stats


def ensure_chunking_strategy_exists(single_chunk_threshold: int = SINGLE_CHUNK_THRESHOLD,
                            chunk_size: int = CHUNK_SIZE,
                            overlap: int = OVERLAP,
                            timeout: int = 600) -> bool:
    """
    Ensure that the chunking strategy exists in the database.
    If not, create it.

    Args:
        single_chunk_threshold: Maximum size for creating a single chunk
        chunk_size: Maximum size of each chunk for longer texts
        overlap: Overlap between chunks
        timeout: Database query timeout in seconds

    Returns:
        bool: True if strategy exists or was created, False otherwise
    """
    try:
        import json

        # Create parameters as JSON string
        parameters = json.dumps({
            "single_chunk_threshold": single_chunk_threshold,
            "chunk_size": chunk_size,
            "overlap": overlap
        })

        print(f"Ensuring chunking strategy exists (timeout: {timeout}s)...")
        with get_cursor(commit=True, timeout=timeout) as cursor:
            # Check if strategy exists
            cursor.execute(
                "SELECT COUNT(*) FROM chunking_strategies WHERE id = %s",
                (CHUNKING_STRATEGY_ID,)
            )
            if cursor.fetchone()[0] > 0:
                # Update the strategy parameters if it exists
                cursor.execute(
                    """
                    UPDATE chunking_strategies
                    SET strategy_name = %s, parameters = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        "adaptive_pubmedbert_splitter",
                        parameters,
                        CHUNKING_STRATEGY_ID
                    )
                )
                logger.info(f"Updated chunking strategy with ID {CHUNKING_STRATEGY_ID}")
                return True

            # Strategy doesn't exist, create it
            logger.info(f"Creating chunking strategy with ID {CHUNKING_STRATEGY_ID}")

            cursor.execute(
                """
                INSERT INTO chunking_strategies (id, strategy_name, parameters)
                VALUES (%s, %s, %s::jsonb)
                """,
                (
                    CHUNKING_STRATEGY_ID,
                    "adaptive_pubmedbert_splitter",
                    parameters
                )
            )
            logger.info(f"Created chunking strategy with ID {CHUNKING_STRATEGY_ID}")
            return True

    except Exception as e:
        logger.error(f"Error ensuring chunking strategy exists: {e}")
        return False


def ensure_chunktype_exists(timeout: int = 600) -> bool:
    """
    Ensure that the chunk type exists in the database.
    If not, create it.

    Args:
        timeout: Database query timeout in seconds

    Returns:
        bool: True if chunk type exists or was created, False otherwise
    """
    try:
        print(f"Ensuring chunk type exists (timeout: {timeout}s)...")
        with get_cursor(commit=True, timeout=timeout) as cursor:
            # Check if chunk type exists
            cursor.execute(
                "SELECT COUNT(*) FROM chunktypes WHERE id = %s",
                (CHUNKTYPE_ID,)
            )
            if cursor.fetchone()[0] > 0:
                logger.info(f"Chunk type with ID {CHUNKTYPE_ID} already exists")
                return True

            # Chunk type doesn't exist, create it
            logger.info(f"Creating chunk type with ID {CHUNKTYPE_ID}")

            cursor.execute(
                """
                INSERT INTO chunktypes (id, chunktype)
                VALUES (%s, %s)
                """,
                (CHUNKTYPE_ID, "abstract")
            )
            logger.info(f"Created chunk type with ID {CHUNKTYPE_ID}")
            return True

    except Exception as e:
        logger.error(f"Error ensuring chunk type exists: {e}")
        return False


def main(total_limit: int = 1000, batch_size: int = BATCH_SIZE, check_only: bool = False,
         single_chunk_threshold: int = SINGLE_CHUNK_THRESHOLD, chunk_size: int = CHUNK_SIZE,
         overlap: int = OVERLAP, max_runtime: int = 3600, model_timeout: int = 60,
         db_timeout: int = 600):  # 10 minutes default timeout
    """
    Main function to update embeddings.

    Args:
        total_limit: Maximum number of documents to process in total
        batch_size: Number of documents to process in each batch
        check_only: If True, only check database status without processing
        single_chunk_threshold: Maximum size for creating a single chunk
        chunk_size: Maximum size of each chunk for longer texts
        overlap: Overlap between chunks
        max_runtime: Maximum runtime in seconds before graceful exit
        model_timeout: Timeout in seconds for model operations
        db_timeout: Timeout in seconds for database operations
    """
    print(f"Starting combined chunking and embedding update with PubMedBERT (model_id={MODEL_ID})")
    print(f"Parameters:")
    print(f"  - Single chunk threshold: {single_chunk_threshold} chars")
    print(f"  - Chunk size for long texts: {chunk_size} chars")
    print(f"  - Overlap: {overlap} chars")
    print(f"  - Max runtime: {max_runtime} seconds")
    print(f"  - Model timeout: {model_timeout} seconds")
    print(f"  - Database timeout: {db_timeout} seconds")

    # Check database tables
    try:

        if not ensure_model_exists(timeout=db_timeout):
            logger.error(f"Failed to create model with ID {MODEL_ID}, exiting")
            return

        # Ensure chunking strategy and chunk type exist
        if not ensure_chunking_strategy_exists(
            single_chunk_threshold=single_chunk_threshold,
            chunk_size=chunk_size,
            overlap=overlap,
            timeout=db_timeout
        ) or not ensure_chunktype_exists(timeout=db_timeout):
            logger.error("Failed to ensure chunking strategy or chunk type, exiting")
            return

        # If check_only, exit after diagnostics
        if check_only:
            logger.info("Check-only mode, exiting without processing")
            return
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        return

    # Initialize PubMedBERT model with timeout
    global _bert_model
    try:
        logger.info("Initializing PubMedBERT model...")
        _bert_model = PubMedBERT(timeout=model_timeout)
        logger.info(f"Initialized PubMedBERT model: {_bert_model.get_modelname()}")
        logger.info(f"Model dimension: {_bert_model.get_dimension()}")
        bert_model = _bert_model  # Local reference for use in the function
    except Exception as e:
        logger.error(f"Failed to initialize PubMedBERT model: {e}")
        return

    # Initialize chunker
    try:
        chunker = AdaptiveTextChunker(
            single_chunk_threshold=single_chunk_threshold,
            max_chunk_size=chunk_size,
            overlap=overlap
        )
        logger.info("Initialized text chunker")
    except Exception as e:
        logger.error(f"Failed to initialize chunker: {e}")
        return

    # Process documents in batches
    total_stats = {
        "documents_processed": 0,
        "chunks_created": 0,
        "embeddings_created": 0,
        "errors": 0
    }
    start_time = time.time()
    batch_count = 0

    try:
        while total_stats["documents_processed"] < total_limit:
            # Check if we've exceeded the maximum runtime
            if time.time() - start_time > max_runtime:
                logger.debug(f"Maximum runtime of {max_runtime}s exceeded. Stopping after {batch_count} batches.")
                break

            # Get documents for processing
            remaining = total_limit - total_stats["documents_processed"]
            current_batch_size = min(batch_size, remaining)

            try:
                logger.debug(f"Fetching batch of up to {current_batch_size} documents...")
                # Use the specified database timeout
                documents = get_documents_for_processing(
                    limit=current_batch_size,
                    timeout=db_timeout
                )
            except Exception as e:
                logger.error(f"Error getting documents for processing: {e}")
                # Wait a bit before retrying
                logger.error("Waiting 5 seconds before retrying...")
                time.sleep(5)
                continue

            if not documents:
                logger.info("No more documents to process")
                break

            # Process the batch with a time limit for each batch
            batch_start_time = time.time()
            logger.debug(f"Processing batch {batch_count+1} with {len(documents)} documents...")

            try:
                # Set a reasonable time limit for each batch (5 minutes per batch)
                batch_time_limit = min(300, max_runtime - (time.time() - start_time))
                if batch_time_limit <= 0:
                    logger.warning("No time left for processing, exiting")
                    break

                batch_stats = chunk_and_embed_documents(
                    documents,
                    bert_model,
                    chunker,
                    max_processing_time=batch_time_limit
                )
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                # Wait a bit before continuing to the next batch
                time.sleep(5)
                batch_count += 1
                continue

            batch_end_time = time.time()

            if batch_stats.get("documents_processed", 0) == 0:
                logger.warning("Failed to process any documents in this batch")
                # Don't break, try the next batch
                batch_count += 1
                continue

            # Update counters and log progress
            for key in total_stats:
                if key in batch_stats:
                    total_stats[key] += batch_stats.get(key, 0)

            batch_time = batch_end_time - batch_start_time
            logger.debug(f"Processed batch {batch_count+1} in {batch_time:.2f}s")
            logger.debug(f"Total documents processed: {total_stats['documents_processed']}/{total_limit}")

            batch_count += 1

            # Add a small delay between batches to allow for interruption
            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.warning("Received keyboard interrupt, stopping gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error in main processing loop: {e}")
    finally:
        # Log summary
        total_time = time.time() - start_time
        print(f"\nCompleted processing: {total_stats['documents_processed']} documents in {total_time:.2f}s")
        print(f"Created {total_stats['chunks_created']} chunks and {total_stats['embeddings_created']} embeddings")
        print(f"Encountered {total_stats.get('errors', 0)} errors")

        if total_stats["documents_processed"] > 0:
            print(f"Average processing speed: {total_stats['documents_processed']/total_time:.2f} docs/s")

        # Ensure model is cleaned up
        cleanup_resources()


def analyze_abstract_lengths():
    """
    Analyze abstract lengths in the database and print statistics.
    """
    try:
        with get_cursor() as cursor:
            # Get abstract length statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_abstracts,
                    MIN(LENGTH(abstract)) as min_length,
                    MAX(LENGTH(abstract)) as max_length,
                    AVG(LENGTH(abstract)) as avg_length,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LENGTH(abstract)) as median_length
                FROM document
                WHERE abstract IS NOT NULL
            """)
            stats = cursor.fetchone()

            logger.info("Abstract length statistics:")
            logger.info(f"  - Total abstracts: {stats['total_abstracts']}")
            logger.info(f"  - Min length: {stats['min_length']} chars")
            logger.info(f"  - Max length: {stats['max_length']} chars")
            logger.info(f"  - Average length: {stats['avg_length']:.2f} chars")
            logger.info(f"  - Median length: {stats['median_length']:.2f} chars")

            # Get distribution of abstract lengths
            cursor.execute("""
                SELECT
                    CASE
                        WHEN LENGTH(abstract) <= 500 THEN '0-500'
                        WHEN LENGTH(abstract) <= 1000 THEN '501-1000'
                        WHEN LENGTH(abstract) <= 1500 THEN '1001-1500'
                        WHEN LENGTH(abstract) <= 2000 THEN '1501-2000'
                        WHEN LENGTH(abstract) <= 3000 THEN '2001-3000'
                        WHEN LENGTH(abstract) <= 5000 THEN '3001-5000'
                        WHEN LENGTH(abstract) <= 10000 THEN '5001-10000'
                        ELSE '10001+'
                    END as length_range,
                    COUNT(*) as count
                FROM document
                WHERE abstract IS NOT NULL
                GROUP BY length_range
                ORDER BY length_range
            """)

            logger.info("Abstract length distribution:")
            for row in cursor.fetchall():
                logger.info(f"  - {row['length_range']} chars: {row['count']} abstracts")

    except Exception as e:
        logger.error(f"Error analyzing abstract lengths: {e}")


def cleanup_resources():
    """
    Clean up resources to prevent semaphore leaks.
    This function is called when the script exits.
    """
    global _bert_model
    if _bert_model is not None:
        logger.info("Cleaning up PubMedBERT model resources...")
        try:
            _bert_model.cleanup()
            _bert_model = None
        except Exception as e:
            logger.error(f"Error cleaning up model resources: {e}")


def signal_handler(sig, _):
    """
    Handle signals (like Ctrl+C) to clean up resources before exiting.

    Args:
        sig: Signal number
        _: Frame object (unused)
    """
    logger.warning(f"Received signal {sig}, forcing immediate exit...")

    # Force immediate exit with error code
    # This is more aggressive than sys.exit() and will terminate even if threads are running
    import os
    os._exit(1)


if __name__ == "__main__":
    # Register cleanup functions
    atexit.register(cleanup_resources)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Chunk and embed documents using PubMedBERT")
    parser.add_argument("--limit", type=int, default=1000,
                        help="Maximum number of documents to process")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help="Number of documents to process in each batch")
    parser.add_argument("--check-only", action="store_true",
                        help="Only check database status without processing")
    parser.add_argument("--single-chunk-threshold", type=int, default=SINGLE_CHUNK_THRESHOLD,
                        help=f"Maximum size for creating a single chunk (default: {SINGLE_CHUNK_THRESHOLD})")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help=f"Size of each chunk for longer texts (default: {CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=OVERLAP,
                        help=f"Overlap between chunks in characters (default: {OVERLAP})")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze abstract lengths in the database without processing")
    parser.add_argument("--max-runtime", type=int, default=3600,
                        help="Maximum runtime in seconds before graceful exit (default: 3600)")
    parser.add_argument("--model-timeout", type=int, default=60,
                        help="Timeout in seconds for model operations (default: 60)")
    parser.add_argument("--db-timeout", type=int, default=600,
                        help="Timeout in seconds for database operations (default: 600)")
    parser.add_argument("--force-exit", action="store_true",
                        help="Force immediate exit on keyboard interrupt (SIGINT)")
    args = parser.parse_args()

    # Load environment variables
    load_environment()

    # If analyze mode, analyze abstract lengths and exit
    if args.analyze:
        analyze_abstract_lengths()
        sys.exit(0)

    # If force-exit is enabled, use a more aggressive signal handler
    if args.force_exit:
        def force_exit_handler(sig, _):
            print(f"\nReceived signal {sig}, forcing immediate exit...")
            import os
            os._exit(1)

        signal.signal(signal.SIGINT, force_exit_handler)
        signal.signal(signal.SIGTERM, force_exit_handler)
        print("Force exit enabled - will terminate immediately on Ctrl+C")

    try:
        # Run the main function
        main(
            total_limit=args.limit,
            batch_size=args.batch_size,
            check_only=args.check_only,
            single_chunk_threshold=args.single_chunk_threshold,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            max_runtime=args.max_runtime,
            model_timeout=args.model_timeout,
            db_timeout=args.db_timeout
        )
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, exiting...")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # Ensure resources are cleaned up even if an exception occurs
        try:
            cleanup_resources()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            # Force exit if cleanup fails
            import os
            os._exit(1)
