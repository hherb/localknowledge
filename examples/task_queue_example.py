#!/usr/bin/env python3
"""
Example usage of the TaskQueueManager for parallel task processing.

This script demonstrates how to use the task queue system to process
documents with multiple workers running in parallel.
"""

import threading
import time
import logging
from typing import Dict, Any

from localknowledge.db.task_queue import TaskQueueManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def worker_thread(worker_id: int, task_id: int, max_tasks: int = 10):
    """
    Worker thread that processes tasks from the queue.
    
    Args:
        worker_id: Unique identifier for this worker
        task_id: The task type to process
        max_tasks: Maximum number of tasks to process before stopping
    """
    logger.info(f"Worker {worker_id} starting for task {task_id}")
    
    try:
        # Each worker gets its own database connection
        queue_manager = TaskQueueManager()
        processed_count = 0
        
        # Process tasks until no more are available or max reached
        for processing_queue_id, document_id in queue_manager.get_pending_tasks(task_id):
            if processed_count >= max_tasks:
                logger.info(f"Worker {worker_id} reached max tasks limit ({max_tasks})")
                break
                
            logger.info(f"Worker {worker_id} processing document {document_id} (queue ID: {processing_queue_id})")
            
            try:
                # Simulate some work
                work_time = 0.5 + (worker_id % 3) * 0.2  # Vary work time by worker
                time.sleep(work_time)
                
                # Simulate occasional failures
                if document_id % 13 == 0:  # Fail every 13th document
                    raise Exception(f"Simulated processing error for document {document_id}")
                
                # Mark task as completed
                # For this example, we'll just mark as finished
                # In real usage, you might pass next_task to chain tasks
                queue_manager.task_done(processing_queue_id)
                
                processed_count += 1
                logger.info(f"Worker {worker_id} completed document {document_id}")
                
            except Exception as e:
                # Mark task as failed
                queue_manager.task_error(processing_queue_id, str(e))
                logger.error(f"Worker {worker_id} failed on document {document_id}: {e}")
                
        logger.info(f"Worker {worker_id} finished. Processed {processed_count} tasks.")
        
    except Exception as e:
        logger.error(f"Worker {worker_id} encountered fatal error: {e}")
    finally:
        if 'queue_manager' in locals():
            queue_manager.close()


def setup_example_data():
    """Set up example tasks and queue some documents for processing."""
    logger.info("Setting up example data...")
    
    queue_manager = TaskQueueManager()
    
    try:
        # Create example task types
        chunking_task_id = queue_manager.add_task("Document Chunking")
        embedding_task_id = queue_manager.add_task("Generate Embeddings")
        summary_task_id = queue_manager.add_task("Generate Summary")
        
        logger.info(f"Created tasks: chunking={chunking_task_id}, embedding={embedding_task_id}, summary={summary_task_id}")
        
        # Queue some documents for chunking (assuming document IDs 1-50 exist)
        for doc_id in range(1, 51):
            queue_manager.queue_document_for_task(doc_id, chunking_task_id)
        
        logger.info("Queued 50 documents for chunking")
        
        # Show initial stats
        stats = queue_manager.get_queue_stats(chunking_task_id)
        logger.info(f"Initial queue stats for chunking: {stats}")
        
        return chunking_task_id, embedding_task_id, summary_task_id
        
    finally:
        queue_manager.close()


def run_parallel_processing_example():
    """Run an example of parallel task processing."""
    logger.info("Starting parallel processing example...")
    
    # Set up example data
    chunking_task_id, embedding_task_id, summary_task_id = setup_example_data()
    
    # Create multiple worker threads
    num_workers = 3
    threads = []
    
    for i in range(num_workers):
        thread = threading.Thread(
            target=worker_thread,
            args=(i + 1, chunking_task_id, 20),  # Each worker processes up to 20 tasks
            name=f"Worker-{i + 1}"
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all workers to complete
    for thread in threads:
        thread.join()
    
    # Show final stats
    queue_manager = TaskQueueManager()
    try:
        stats = queue_manager.get_queue_stats(chunking_task_id)
        logger.info(f"Final queue stats for chunking: {stats}")
        
        # Show any failed tasks
        failed_tasks = queue_manager.get_failed_tasks(chunking_task_id, limit=10)
        if failed_tasks:
            logger.info(f"Found {len(failed_tasks)} failed tasks:")
            for task in failed_tasks:
                logger.info(f"  Document {task['document_id']}: {task['error']}")
        
    finally:
        queue_manager.close()
    
    logger.info("Parallel processing example completed")


def demonstrate_task_chaining():
    """Demonstrate chaining tasks together."""
    logger.info("Demonstrating task chaining...")
    
    queue_manager = TaskQueueManager()
    
    try:
        # Get task IDs (assuming they exist from previous example)
        tasks = queue_manager.get_all_tasks()
        if len(tasks) < 2:
            logger.warning("Need at least 2 tasks for chaining demo")
            return
        
        task1_id = tasks[0]['id']
        task2_id = tasks[1]['id']
        
        logger.info(f"Chaining task {task1_id} -> task {task2_id}")
        
        # Queue a document for the first task
        queue_id = queue_manager.queue_document_for_task(document_id=999, task_id=task1_id)
        
        # Process the first task and chain to the second
        for processing_queue_id, document_id in queue_manager.get_pending_tasks(task1_id):
            if document_id == 999:  # Our test document
                logger.info(f"Processing document {document_id} for task {task1_id}")
                
                # Simulate work
                time.sleep(0.1)
                
                # Complete first task and create second task
                queue_manager.task_done(processing_queue_id, next_task=task2_id)
                logger.info(f"Completed task {task1_id} and queued for task {task2_id}")
                break
        
        # Show that the document is now queued for the second task
        stats1 = queue_manager.get_queue_stats(task1_id)
        stats2 = queue_manager.get_queue_stats(task2_id)
        
        logger.info(f"Task {task1_id} stats: {stats1}")
        logger.info(f"Task {task2_id} stats: {stats2}")
        
    finally:
        queue_manager.close()


if __name__ == "__main__":
    try:
        # Run the parallel processing example
        run_parallel_processing_example()
        
        # Demonstrate task chaining
        demonstrate_task_chaining()
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise
