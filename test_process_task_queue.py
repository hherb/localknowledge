#!/usr/bin/env python3
"""
Test script for process_task_queue.py

This script tests the task queue processing functionality in READ-ONLY mode.
It does NOT modify the live task queue data, but simulates the processing
to verify the functionality works correctly.

WARNING: This script is READ-ONLY for the task queue table to protect live data.
"""

import logging
from typing import List, Dict, Any
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.task_queue import TaskQueueManager
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.db.connection_pool import get_cursor
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sample_documents(limit=3):
    """Get a few sample documents with abstracts for testing."""
    try:
        with get_cursor() as cursor:
            query = """
            SELECT id, title, abstract
            FROM document
            WHERE abstract IS NOT NULL
            AND length(abstract) > 100
            ORDER BY id
            LIMIT %s
            """
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting sample documents: {e}")
        return []

def simulate_task_processing(documents: List[Dict[str, Any]], strategy_id: int, chunktype_id: int = 1):
    """Simulate the task processing without modifying the task queue."""
    print("\n=== SIMULATING TASK PROCESSING (READ-ONLY) ===")

    chunking_db = ChunkingDatabaseManager()
    chunker = AdaptiveTextChunker(
        max_chunk_size=1500,
        overlap=100,
        min_chunk_size=100
    )

    for doc in documents:
        doc_id = doc['id']
        title = doc['title'] or "Untitled"
        abstract = doc['abstract']

        print(f"\nProcessing document {doc_id}: {title[:50]}...")

        # Check existing chunks
        existing_chunks = chunking_db.get_chunks_by_document_and_chunking_strategy(doc_id, strategy_id)
        existing_count = len([c for c in existing_chunks if c.chunktype_id == chunktype_id])
        print(f"  Existing chunks: {existing_count}")

        # Simulate chunking
        metadata = {
            'title': title,
            'source': 'abstract',
            'document_id': doc_id
        }

        try:
            chunks = chunker.chunk(abstract, metadata=metadata)
            print(f"  Would create {len(chunks)} new chunks")

            # Show first chunk as example
            if chunks:
                first_chunk = chunks[0]
                print(f"  First chunk preview: {first_chunk.text[:100]}...")

        except Exception as e:
            print(f"  Error during chunking: {e}")

def check_queue_stats():
    """Check current task queue statistics (READ-ONLY)."""
    print("\n=== CURRENT TASK QUEUE STATS (READ-ONLY) ===")

    task_manager = TaskQueueManager()

    # Get stats for chunking tasks (task_id=1)
    stats = task_manager.get_queue_stats(task_id=1)
    print(f"Chunking tasks (task_id=1): {stats}")

    # Get overall stats
    overall_stats = task_manager.get_queue_stats()
    print(f"All tasks: {overall_stats}")

    # Show some pending tasks (without claiming them)
    try:
        with get_cursor() as cursor:
            query = """
            SELECT pq.id, pq.document_id, pq.task_id, pq.created, d.title
            FROM processing_queue pq
            JOIN document d ON pq.document_id = d.id
            WHERE pq.task_id = 1 AND pq.status IS NULL
            ORDER BY pq.created
            LIMIT 5
            """
            cursor.execute(query)
            pending_tasks = cursor.fetchall()

            if pending_tasks:
                print(f"\nSample pending chunking tasks:")
                for task in pending_tasks:
                    print(f"  Queue ID {task['id']}: Document {task['document_id']} - {task['title'][:50]}...")
            else:
                print("\nNo pending chunking tasks found.")

    except Exception as e:
        logger.error(f"Error checking pending tasks: {e}")

def main():
    """Main test function - READ-ONLY mode."""
    load_environment()

    print("=== TASK QUEUE PROCESSING TEST (READ-ONLY MODE) ===")
    print("WARNING: This script does NOT modify the live task queue data!")

    # Get sample documents
    print("\n1. Getting sample documents...")
    documents = get_sample_documents(3)
    if not documents:
        print("No sample documents found. Exiting.")
        return

    document_ids = [doc['id'] for doc in documents]
    print(f"Found {len(documents)} sample documents: {document_ids}")

    # Get chunking strategy ID
    chunking_db = ChunkingDatabaseManager()
    strategy_id = chunking_db.get_or_create_chunking_strategy(
        strategy_name="adaptive_text_chunker_1500",
        parameters={
            "max_chunk_size": 1500,
            "overlap": 100,
            "min_chunk_size": 100,
            "includes_title": True,
            "boundary_aware": True,
            "description": "AdaptiveTextChunker with max_chunk_size=1500, overlap=100"
        }
    )
    print(f"Using chunking strategy ID: {strategy_id}")

    # Check current queue stats
    check_queue_stats()

    # Simulate processing the sample documents
    simulate_task_processing(documents, strategy_id)

    print("\n=== TEST COMPLETE ===")
    print("To run the actual processor on live data:")
    print("  python process_task_queue.py --verbose --progress")
    print("\nTo run with limited tasks:")
    print("  python process_task_queue.py --max-tasks 10 --verbose")

if __name__ == "__main__":
    main()
