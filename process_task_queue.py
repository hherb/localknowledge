#!/usr/bin/env python3
"""
Task Queue Processor for Chunking Operations

This script processes documents from the task queue that need chunking with the
adaptive chunker (task=1). For each document:

1. Retrieves pending tasks from the task queue (task_id=1)
2. Checks if chunks already exist for the document/strategy/type combination
3. If chunks exist, deletes them first to replace with new chunks
4. Processes the document with AdaptiveTextChunker
5. Inserts the new chunks into the database
6. Marks the task as completed (status=2)

This script uses the TaskQueueManager for thread-safe task processing and can
be run in parallel with other instances.
"""

import logging
import argparse
import time
import signal
import sys
from typing import Dict, Any, Optional, List, Tuple
from tqdm import tqdm

from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.task_queue import TaskQueueManager
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk as DBChunk
from localknowledge.db.connection_pool import get_cursor
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging - quieter by default
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Silence INFO logs from dependencies
logging.getLogger("localknowledge.db.base").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.chunker").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.connection_pool").setLevel(logging.WARNING)
logging.getLogger("localknowledge.db.task_queue").setLevel(logging.WARNING)
logging.getLogger("localknowledge.textprocessing.chunking").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Constants
CHUNKING_TASK_ID = 1  # Task ID for chunking operations
NEXT_TASK_ID = 2  # Task ID to transition to after successful chunking (e.g., embedding)
CHUNKING_STRATEGY_NAME = "adaptive_text_chunker_1500"
CHUNKING_STRATEGY_DESCRIPTION = "AdaptiveTextChunker with max_chunk_size=1500, overlap=100"
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    print(f"\nReceived signal {signum}. Requesting graceful shutdown...")
    shutdown_requested = True


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
        "description": CHUNKING_STRATEGY_DESCRIPTION
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


def get_document_details(document_id: int) -> Optional[Dict[str, Any]]:
    """
    Get document details from the database.

    Args:
        document_id: ID of the document

    Returns:
        Dictionary with document details or None if not found
    """
    try:
        with get_cursor() as cursor:
            query = """
            SELECT id, title, abstract
            FROM document
            WHERE id = %s
            AND abstract IS NOT NULL
            AND length(abstract) > 0
            """
            cursor.execute(query, (document_id,))
            result = cursor.fetchone()
            return result

    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        return None


def process_document(document: Dict[str, Any], chunker: AdaptiveTextChunker,
                    strategy_id: int, chunking_db: ChunkingDatabaseManager) -> int:
    """
    Process a single document and create chunks.

    Args:
        document: Document dictionary with id, title, abstract
        chunker: Text chunker instance
        strategy_id: The ID of the chunking strategy
        chunking_db: Database manager for chunking operations

    Returns:
        Number of chunks created
    """
    doc_id = document['id']
    title = document['title'] or "Untitled"
    abstract = document['abstract']

    # Skip documents without abstracts
    if not abstract or len(abstract.strip()) == 0:
        logger.warning(f"Skipping document {doc_id} with empty abstract")
        return 0

    # Check if chunks already exist and delete them
    deleted_count = chunking_db.delete_chunks_by_document_strategy_type(
        document_id=doc_id,
        chunking_strategy_id=strategy_id,
        chunktype_id=CHUNKTYPE_ID
    )

    if deleted_count > 0:
        logger.debug(f"Deleted {deleted_count} existing chunks for document {doc_id}")

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
            chunk_ids = chunking_db.batch_insert_chunks(db_chunks)
            return len(chunk_ids)
        else:
            logger.warning(f"No chunks created for document {doc_id}")
            return 0

    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
        raise


def process_batch_optimized(task_batch: List[Tuple[int, int]], chunker: AdaptiveTextChunker,
                           strategy_id: int, chunking_db: ChunkingDatabaseManager,
                           task_manager: TaskQueueManager, args) -> Tuple[int, int]:
    """
    Process a batch of tasks with maximum optimization.

    This version minimizes database round trips by:
    1. Batch retrieving all documents
    2. Bulk deleting existing chunks
    3. Bulk inserting new chunks
    4. Batch updating task statuses

    Args:
        task_batch: List of (processing_queue_id, document_id) tuples
        chunker: Text chunker instance
        strategy_id: The ID of the chunking strategy
        chunking_db: Database manager for chunking operations
        task_manager: Task queue manager
        args: Command line arguments

    Returns:
        Tuple of (processed_count, total_chunks)
    """
    if not task_batch:
        return 0, 0

    processed_count = 0
    total_chunks = 0

    # Get all document IDs for batch retrieval
    document_ids = [doc_id for _, doc_id in task_batch]

    # Batch retrieve document details
    documents = {}
    try:
        with get_cursor() as cursor:
            # Use ANY() for efficient batch retrieval
            query = """
            SELECT id, title, abstract
            FROM document
            WHERE id = ANY(%s)
            AND abstract IS NOT NULL
            AND length(abstract) > 0
            """
            cursor.execute(query, (document_ids,))
            results = cursor.fetchall()

            for result in results:
                documents[result['id']] = result

    except Exception as e:
        logger.error(f"Error batch retrieving documents: {e}")
        # Fall back to individual processing
        return process_batch_fallback(task_batch, chunker, strategy_id, chunking_db, task_manager, args)

    # Bulk delete existing chunks for all documents in the batch
    valid_document_ids = list(documents.keys())
    if valid_document_ids:
        try:
            with get_cursor(commit=True) as cursor:
                delete_query = """
                DELETE FROM chunks
                WHERE document_id = ANY(%s)
                AND chunking_strategy_id = %s
                AND chunktype_id = %s
                """
                cursor.execute(delete_query, (valid_document_ids, strategy_id, CHUNKTYPE_ID))
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.debug(f"Bulk deleted {deleted_count} existing chunks for {len(valid_document_ids)} documents")
        except Exception as e:
            logger.error(f"Error bulk deleting chunks: {e}")
            # Fall back to individual processing
            return process_batch_fallback(task_batch, chunker, strategy_id, chunking_db, task_manager, args)

    # Process all documents and collect chunks for bulk insertion
    all_chunks = []
    successful_tasks = []
    failed_tasks = []

    for processing_queue_id, document_id in task_batch:
        try:
            document = documents.get(document_id)
            if not document:
                logger.warning(f"Document {document_id} not found or has no abstract")
                failed_tasks.append((processing_queue_id, "Document not found or has no abstract"))
                continue

            doc_id = document['id']
            title = document['title'] or "Untitled"
            abstract = document['abstract']

            # Skip documents without abstracts
            if not abstract or len(abstract.strip()) == 0:
                logger.warning(f"Skipping document {doc_id} with empty abstract")
                failed_tasks.append((processing_queue_id, "Empty abstract"))
                continue

            # Create metadata with title
            metadata = {
                'title': title,
                'source': 'abstract',
                'document_id': doc_id
            }

            # Chunk the abstract
            chunks = chunker.chunk(abstract, metadata=metadata)

            # Convert to database chunks
            doc_chunks = []
            for i, chunk in enumerate(chunks):
                db_chunk = chunk.to_db_chunk(
                    document_id=doc_id,
                    chunking_strategy_id=strategy_id,
                    chunktype_id=CHUNKTYPE_ID,
                    document_title=title,
                    chunk_no=i
                )
                doc_chunks.append(db_chunk)

            if doc_chunks:
                all_chunks.extend(doc_chunks)
                successful_tasks.append((processing_queue_id, document_id, len(doc_chunks)))
                total_chunks += len(doc_chunks)
                processed_count += 1

                if args.verbose:
                    print(f"Processed document {document_id}: {len(doc_chunks)} chunks created")
            else:
                logger.warning(f"No chunks created for document {doc_id}")
                failed_tasks.append((processing_queue_id, "No chunks created"))

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            failed_tasks.append((processing_queue_id, str(e)))
            continue

    # Bulk insert all chunks
    if all_chunks:
        try:
            chunk_ids = chunking_db.batch_insert_chunks(all_chunks)
            logger.debug(f"Bulk inserted {len(chunk_ids)} chunks for {len(successful_tasks)} documents")
        except Exception as e:
            logger.error(f"Error bulk inserting chunks: {e}")
            # Mark all tasks as failed
            for processing_queue_id, document_id, _ in successful_tasks:
                failed_tasks.append((processing_queue_id, f"Chunk insertion failed: {e}"))
            successful_tasks = []

    # Batch update task statuses
    for processing_queue_id, document_id, chunks_created in successful_tasks:
        try:
            # Mark task as completed and optionally transition to next task
            if args.no_next_task:
                task_manager.task_done(processing_queue_id)
            else:
                task_manager.task_done(processing_queue_id, next_task=args.next_task)
        except Exception as e:
            logger.error(f"Error marking task {processing_queue_id} as done: {e}")

    # Mark failed tasks
    for processing_queue_id, error_message in failed_tasks:
        try:
            task_manager.task_error(processing_queue_id, error_message)
        except Exception as e:
            logger.error(f"Error marking task {processing_queue_id} as failed: {e}")

    return processed_count, total_chunks


def process_batch_fallback(task_batch: List[Tuple[int, int]], chunker: AdaptiveTextChunker,
                          strategy_id: int, chunking_db: ChunkingDatabaseManager,
                          task_manager: TaskQueueManager, args) -> Tuple[int, int]:
    """
    Improved batch processing that uses batch document retrieval but individual chunk processing.
    This avoids duplicate key issues while still providing some performance benefits.
    """
    if not task_batch:
        return 0, 0

    processed_count = 0
    total_chunks = 0

    # Get all document IDs for batch retrieval
    document_ids = [doc_id for _, doc_id in task_batch]

    # Batch retrieve document details for better performance
    documents = {}
    try:
        with get_cursor() as cursor:
            # Use ANY() for efficient batch retrieval
            query = """
            SELECT id, title, abstract
            FROM document
            WHERE id = ANY(%s)
            AND abstract IS NOT NULL
            AND length(abstract) > 0
            """
            cursor.execute(query, (document_ids,))
            results = cursor.fetchall()

            for result in results:
                documents[result['id']] = result

    except Exception as e:
        logger.error(f"Error batch retrieving documents: {e}")
        # Fall back to individual document retrieval
        pass

    # Process each task individually to avoid duplicate key issues
    for processing_queue_id, document_id in task_batch:
        try:
            # Try to get document from batch retrieval first, then individual retrieval
            document = documents.get(document_id)
            if not document:
                document = get_document_details(document_id)

            if not document:
                logger.warning(f"Document {document_id} not found or has no abstract")
                task_manager.task_error(processing_queue_id, "Document not found or has no abstract")
                continue

            # Process the document individually (this handles chunk deletion and insertion safely)
            chunks_created = process_document(document, chunker, strategy_id, chunking_db)
            total_chunks += chunks_created

            # Mark task as completed and optionally transition to next task
            if args.no_next_task:
                task_manager.task_done(processing_queue_id)
            else:
                task_manager.task_done(processing_queue_id, next_task=args.next_task)

            processed_count += 1
            if args.verbose:
                print(f"Processed document {document_id}: {chunks_created} chunks created")

        except Exception as e:
            logger.error(f"Error processing task {processing_queue_id} for document {document_id}: {e}")
            task_manager.task_error(processing_queue_id, str(e))
            continue

    return processed_count, total_chunks


# Use the safer fallback version by default to avoid errors
process_batch = process_batch_fallback


def main():
    """Main function."""
    global shutdown_requested

    parser = argparse.ArgumentParser(description="Process task queue for chunking operations")
    parser.add_argument("--max-tasks", type=int, default=None,
                        help="Maximum number of tasks to process (default: process until queue is empty)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show more detailed logging (default: False)")
    parser.add_argument("--progress", action="store_true",
                        help="Show progress bar (default: False)")
    parser.add_argument("--next-task", type=int, default=NEXT_TASK_ID,
                        help=f"Task ID to transition to after successful chunking (default: {NEXT_TASK_ID})")
    parser.add_argument("--no-next-task", action="store_true",
                        help="Don't transition to next task, just mark as finished")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Number of documents to process in each batch (default: 10)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (default: 1)")
    args = parser.parse_args()

    # Enable verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.chunker").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.task_queue").setLevel(logging.INFO)
        logging.getLogger("localknowledge.textprocessing.chunking").setLevel(logging.INFO)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load environment variables
    load_environment()

    print("Starting task queue processor for chunking operations...")

    # Initialize managers
    task_manager = TaskQueueManager()
    chunking_db = ChunkingDatabaseManager()

    # Get or create chunking strategy
    strategy_id = get_or_create_chunking_strategy()

    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=1500,
        overlap=100,
        min_chunk_size=100
    )

    # Get initial queue stats
    stats = task_manager.get_queue_stats(CHUNKING_TASK_ID)
    print(f"Queue stats for task {CHUNKING_TASK_ID}: {stats}")

    if stats['pending'] == 0:
        print("No pending tasks found. Exiting.")
        return

    # Process tasks
    processed_count = 0
    total_chunks = 0
    start_time = time.time()

    # Set up progress bar if requested
    pbar = None
    if args.progress:
        pbar = tqdm(total=stats['pending'], desc="Processing tasks", unit="task")

    try:
        # Collect tasks in batches for more efficient processing
        task_batch = []

        for processing_queue_id, document_id in task_manager.get_pending_tasks(CHUNKING_TASK_ID):
            if shutdown_requested:
                print("Shutdown requested. Stopping processing...")
                break

            if args.max_tasks and processed_count >= args.max_tasks:
                print(f"Reached maximum task limit ({args.max_tasks}). Stopping.")
                break

            # Add to current batch
            task_batch.append((processing_queue_id, document_id))

            # Process batch when it reaches the desired size
            if len(task_batch) >= args.batch_size:
                batch_processed, batch_chunks = process_batch(
                    task_batch, chunker, strategy_id, chunking_db, task_manager, args
                )

                processed_count += batch_processed
                total_chunks += batch_chunks

                # Update progress bar
                if pbar:
                    pbar.update(batch_processed)
                    pbar.set_postfix({
                        "chunks": total_chunks,
                        "chunks/doc": round(total_chunks / max(1, processed_count), 2),
                        "batch_size": len(task_batch)
                    })

                # Clear the batch
                task_batch = []

                # Check if we've reached the max tasks limit
                if args.max_tasks and processed_count >= args.max_tasks:
                    break

        # Process any remaining tasks in the final batch
        if task_batch and not shutdown_requested:
            batch_processed, batch_chunks = process_batch(
                task_batch, chunker, strategy_id, chunking_db, task_manager, args
            )

            processed_count += batch_processed
            total_chunks += batch_chunks

            # Update progress bar
            if pbar:
                pbar.update(batch_processed)
                pbar.set_postfix({
                    "chunks": total_chunks,
                    "chunks/doc": round(total_chunks / max(1, processed_count), 2),
                    "batch_size": len(task_batch)
                })

    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting gracefully...")
    finally:
        if pbar:
            pbar.close()

    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    # Print summary with performance metrics
    print(f"\nProcessed {processed_count} tasks in {elapsed_time:.2f} seconds")
    print(f"Created {total_chunks} chunks ({total_chunks / max(1, processed_count):.2f} chunks per document)")

    if processed_count > 0:
        tasks_per_second = processed_count / elapsed_time
        chunks_per_second = total_chunks / elapsed_time
        print(f"Performance: {tasks_per_second:.2f} tasks/sec, {chunks_per_second:.2f} chunks/sec")

        if args.batch_size > 1:
            print(f"Batch processing: {args.batch_size} tasks per batch")

    # Show final queue stats
    final_stats = task_manager.get_queue_stats(CHUNKING_TASK_ID)
    print(f"Final queue stats for task {CHUNKING_TASK_ID}: {final_stats}")


if __name__ == "__main__":
    main()
