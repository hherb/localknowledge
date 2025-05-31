"""
Task Queue Database Manager

This module provides thread-safe functionality for managing a task queue system
where multiple workers can process tasks in parallel. The system uses two tables:
- task: Contains task definitions (id, description)
- processing_queue: Contains work items linking documents to tasks with status tracking

Status values:
- NULL: unprocessed
- 1: processing
- 2: finished
- 3: error
"""

import logging
from datetime import datetime
from typing import Generator, Tuple, Optional, List, Dict, Any
from contextlib import contextmanager

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger(__name__)


class TaskQueueManager(DatabaseManager):
    """
    Thread-safe manager for the task queue system.
    
    This class provides methods to safely retrieve pending tasks and mark them
    as completed, allowing multiple workers to process tasks concurrently without
    conflicts.
    """

    def __init__(self):
        """Initialize the task queue manager."""
        super().__init__()

    def get_pending_tasks(self, task_id: int) -> Generator[Tuple[int, int], None, None]:
        """
        Get pending tasks for a specific task type in a thread-safe manner.
        
        This method uses SELECT FOR UPDATE SKIP LOCKED to ensure that multiple
        workers can safely claim tasks without conflicts. Each call returns one
        task at a time and immediately marks it as processing.
        
        Args:
            task_id: The task type ID to get pending work for
            
        Yields:
            Tuple of (processing_queue_id, document_id) for each pending task
        """
        try:
            while True:
                # Use SELECT FOR UPDATE SKIP LOCKED for thread-safe task claiming
                results = self.execute("""
                SELECT id, document_id 
                FROM processing_queue 
                WHERE task_id = %s AND status IS NULL
                ORDER BY created ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """, (task_id,))
                
                if not results:
                    # No more pending tasks
                    break
                    
                result = results[0]
                processing_queue_id = result['id']
                document_id = result['document_id']
                
                # Mark as processing (status = 1) and update timestamp
                self.execute("""
                UPDATE processing_queue 
                SET status = 1, updated = CURRENT_TIMESTAMP 
                WHERE id = %s
                """, (processing_queue_id,), commit=True)
                
                logger.debug(f"Claimed task {processing_queue_id} for document {document_id}")
                yield (processing_queue_id, document_id)
                
        except Exception as e:
            logger.error(f"Error getting pending tasks for task_id {task_id}: {e}")
            raise

    def task_done(self, processing_queue_id: int, next_task: Optional[int] = None) -> None:
        """
        Mark a task as completed or transition to next task in a thread-safe manner.
        
        Args:
            processing_queue_id: The processing queue entry ID to update
            next_task: If provided, the task_id for the next task to create.
                      If None, marks the current task as finished (status = 2)
        """
        try:
            if next_task is None:
                # Mark as finished (status = 2)
                self.execute("""
                UPDATE processing_queue 
                SET status = 2, updated = CURRENT_TIMESTAMP 
                WHERE id = %s
                """, (processing_queue_id,), commit=True)
                
                logger.debug(f"Marked task {processing_queue_id} as finished")
            else:
                # Get the document_id from the current task
                results = self.execute("""
                SELECT document_id FROM processing_queue WHERE id = %s
                """, (processing_queue_id,))
                
                if not results:
                    raise ValueError(f"Processing queue entry {processing_queue_id} not found")
                
                document_id = results[0]['document_id']
                
                # Use a transaction to ensure atomicity
                # Mark current task as finished and create next task
                self.execute("""
                UPDATE processing_queue 
                SET status = 2, updated = CURRENT_TIMESTAMP 
                WHERE id = %s
                """, (processing_queue_id,))
                
                # Insert the next task
                self.execute("""
                INSERT INTO processing_queue (document_id, task_id, created, updated)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (document_id, next_task), commit=True)
                
                logger.debug(f"Marked task {processing_queue_id} as finished and created next task for document {document_id}")
                
        except Exception as e:
            logger.error(f"Error marking task {processing_queue_id} as done: {e}")
            raise

    def task_error(self, processing_queue_id: int, error_message: str) -> None:
        """
        Mark a task as failed with an error message.
        
        Args:
            processing_queue_id: The processing queue entry ID to update
            error_message: Description of the error that occurred
        """
        try:
            self.execute("""
            UPDATE processing_queue 
            SET status = 3, error = %s, updated = CURRENT_TIMESTAMP 
            WHERE id = %s
            """, (error_message, processing_queue_id), commit=True)
            
            logger.debug(f"Marked task {processing_queue_id} as error: {error_message}")
            
        except Exception as e:
            logger.error(f"Error marking task {processing_queue_id} as error: {e}")
            raise

    def add_task(self, description: str) -> int:
        """
        Add a new task type to the task table.

        Args:
            description: Description of the task type

        Returns:
            The ID of the newly created task
        """
        try:
            results = self.execute("""
            INSERT INTO task (description)
            VALUES (%s)
            RETURNING id
            """, (description,), commit=True)

            if results:
                task_id = results[0]['id']
                logger.debug(f"Created new task type {task_id}: {description}")
                return task_id
            else:
                raise RuntimeError("Failed to create task - no ID returned")

        except Exception as e:
            logger.error(f"Error adding task '{description}': {e}")
            raise

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get task information by ID.

        Args:
            task_id: The task ID to look up

        Returns:
            Dictionary with task information or None if not found
        """
        try:
            results = self.execute("""
            SELECT id, description FROM task WHERE id = %s
            """, (task_id,))

            if results:
                return results[0]
            return None

        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            raise

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all available task types.

        Returns:
            List of dictionaries with task information
        """
        try:
            results = self.execute("""
            SELECT id, description FROM task ORDER BY id
            """)

            return results or []

        except Exception as e:
            logger.error(f"Error getting all tasks: {e}")
            raise

    def queue_document_for_task(self, document_id: int, task_id: int) -> int:
        """
        Queue a document for processing with a specific task.

        Args:
            document_id: The document ID to process
            task_id: The task type ID

        Returns:
            The processing queue entry ID
        """
        try:
            results = self.execute("""
            INSERT INTO processing_queue (document_id, task_id, created, updated)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """, (document_id, task_id), commit=True)

            if results:
                queue_id = results[0]['id']
                logger.debug(f"Queued document {document_id} for task {task_id} (queue ID: {queue_id})")
                return queue_id
            else:
                raise RuntimeError("Failed to queue document - no ID returned")

        except Exception as e:
            logger.error(f"Error queuing document {document_id} for task {task_id}: {e}")
            raise

    def get_queue_stats(self, task_id: Optional[int] = None) -> Dict[str, int]:
        """
        Get statistics about the processing queue.

        Args:
            task_id: If provided, get stats for specific task only

        Returns:
            Dictionary with queue statistics
        """
        try:
            if task_id is not None:
                results = self.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status IS NULL THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as processing,
                    COUNT(CASE WHEN status = 2 THEN 1 END) as finished,
                    COUNT(CASE WHEN status = 3 THEN 1 END) as error
                FROM processing_queue
                WHERE task_id = %s
                """, (task_id,))
            else:
                results = self.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status IS NULL THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as processing,
                    COUNT(CASE WHEN status = 2 THEN 1 END) as finished,
                    COUNT(CASE WHEN status = 3 THEN 1 END) as error
                FROM processing_queue
                """)

            if results:
                return dict(results[0])
            else:
                return {
                    'total': 0,
                    'pending': 0,
                    'processing': 0,
                    'finished': 0,
                    'error': 0
                }

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            raise

    def reset_processing_tasks(self, task_id: Optional[int] = None) -> int:
        """
        Reset tasks that are stuck in 'processing' status back to pending.
        This is useful for recovering from worker crashes.

        Args:
            task_id: If provided, only reset tasks for this specific task type

        Returns:
            Number of tasks that were reset
        """
        try:
            if task_id is not None:
                self.execute("""
                UPDATE processing_queue
                SET status = NULL, updated = CURRENT_TIMESTAMP
                WHERE status = 1 AND task_id = %s
                """, (task_id,), commit=True)
            else:
                self.execute("""
                UPDATE processing_queue
                SET status = NULL, updated = CURRENT_TIMESTAMP
                WHERE status = 1
                """, commit=True)

            # Get the number of affected rows
            cursor = self.connection.cursor()
            reset_count = cursor.rowcount
            cursor.close()

            logger.info(f"Reset {reset_count} processing tasks back to pending")
            return reset_count

        except Exception as e:
            logger.error(f"Error resetting processing tasks: {e}")
            raise

    def get_failed_tasks(self, task_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tasks that failed with error status.

        Args:
            task_id: If provided, only get failed tasks for this specific task type
            limit: Maximum number of failed tasks to return

        Returns:
            List of dictionaries with failed task information
        """
        try:
            if task_id is not None:
                results = self.execute("""
                SELECT pq.id, pq.document_id, pq.task_id, pq.error, pq.updated, t.description
                FROM processing_queue pq
                JOIN task t ON pq.task_id = t.id
                WHERE pq.status = 3 AND pq.task_id = %s
                ORDER BY pq.updated DESC
                LIMIT %s
                """, (task_id, limit))
            else:
                results = self.execute("""
                SELECT pq.id, pq.document_id, pq.task_id, pq.error, pq.updated, t.description
                FROM processing_queue pq
                JOIN task t ON pq.task_id = t.id
                WHERE pq.status = 3
                ORDER BY pq.updated DESC
                LIMIT %s
                """, (limit,))

            return results or []

        except Exception as e:
            logger.error(f"Error getting failed tasks: {e}")
            raise
