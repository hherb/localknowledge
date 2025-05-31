"""
Unit tests for the TaskQueueManager.

These tests verify the thread-safe functionality of the task queue system.
"""

import unittest
import threading
import time
from unittest.mock import patch, MagicMock

from localknowledge.db.task_queue import TaskQueueManager


class TestTaskQueueManager(unittest.TestCase):
    """Test cases for TaskQueueManager."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the database connection for testing
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_connection.cursor.return_value = self.mock_cursor

        # Create manager with mocked connection
        with patch('localknowledge.db.task_queue.DatabaseManager.__init__') as mock_init:
            mock_init.return_value = None
            self.manager = TaskQueueManager()
            self.manager.connection = self.mock_connection

    def test_add_task(self):
        """Test adding a new task type."""
        # Mock the execute method to return a task ID
        self.manager.execute = MagicMock(return_value=[{'id': 1}])
        
        task_id = self.manager.add_task("Test Task")
        
        self.assertEqual(task_id, 1)
        self.manager.execute.assert_called_once()
        
        # Verify the SQL query
        call_args = self.manager.execute.call_args
        self.assertIn("INSERT INTO task", call_args[0][0])
        self.assertEqual(call_args[0][1], ("Test Task",))

    def test_get_task_by_id(self):
        """Test retrieving a task by ID."""
        # Mock the execute method to return task data
        self.manager.execute = MagicMock(return_value=[{'id': 1, 'description': 'Test Task'}])
        
        task = self.manager.get_task_by_id(1)
        
        self.assertIsNotNone(task)
        self.assertEqual(task['id'], 1)
        self.assertEqual(task['description'], 'Test Task')

    def test_get_task_by_id_not_found(self):
        """Test retrieving a non-existent task."""
        # Mock the execute method to return empty result
        self.manager.execute = MagicMock(return_value=[])
        
        task = self.manager.get_task_by_id(999)
        
        self.assertIsNone(task)

    def test_queue_document_for_task(self):
        """Test queuing a document for processing."""
        # Mock the execute method to return a queue ID
        self.manager.execute = MagicMock(return_value=[{'id': 100}])
        
        queue_id = self.manager.queue_document_for_task(document_id=42, task_id=1)
        
        self.assertEqual(queue_id, 100)
        self.manager.execute.assert_called_once()
        
        # Verify the SQL query
        call_args = self.manager.execute.call_args
        self.assertIn("INSERT INTO processing_queue", call_args[0][0])
        self.assertEqual(call_args[0][1], (42, 1))

    def test_get_pending_tasks_empty(self):
        """Test getting pending tasks when none exist."""
        # Mock the execute method to return empty result
        self.manager.execute = MagicMock(return_value=[])
        
        tasks = list(self.manager.get_pending_tasks(task_id=1))
        
        self.assertEqual(len(tasks), 0)

    def test_get_pending_tasks_with_data(self):
        """Test getting pending tasks with data."""
        # Mock the execute method to return task data, then empty
        self.manager.execute = MagicMock(side_effect=[
            [{'id': 100, 'document_id': 42}],  # First call returns a task
            [],  # Second call for UPDATE
            []   # Third call returns empty (no more tasks)
        ])
        
        tasks = list(self.manager.get_pending_tasks(task_id=1))
        
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0], (100, 42))

    def test_task_done_finished(self):
        """Test marking a task as finished."""
        self.manager.execute = MagicMock()
        
        self.manager.task_done(processing_queue_id=100)
        
        self.manager.execute.assert_called_once()
        
        # Verify the SQL query
        call_args = self.manager.execute.call_args
        self.assertIn("UPDATE processing_queue", call_args[0][0])
        self.assertIn("status = 2", call_args[0][0])
        self.assertEqual(call_args[0][1], (100,))

    def test_task_done_with_next_task(self):
        """Test marking a task as finished and creating next task."""
        # Mock the execute method to return document_id, then handle updates
        self.manager.execute = MagicMock(side_effect=[
            [{'document_id': 42}],  # First call returns document_id
            [],  # Second call for UPDATE
            []   # Third call for INSERT
        ])
        
        self.manager.task_done(processing_queue_id=100, next_task=2)
        
        # Should be called 3 times: SELECT, UPDATE, INSERT
        self.assertEqual(self.manager.execute.call_count, 3)

    def test_task_error(self):
        """Test marking a task as failed."""
        self.manager.execute = MagicMock()
        
        self.manager.task_error(processing_queue_id=100, error_message="Test error")
        
        self.manager.execute.assert_called_once()
        
        # Verify the SQL query
        call_args = self.manager.execute.call_args
        self.assertIn("UPDATE processing_queue", call_args[0][0])
        self.assertIn("status = 3", call_args[0][0])
        self.assertEqual(call_args[0][1], ("Test error", 100))

    def test_get_queue_stats(self):
        """Test getting queue statistics."""
        # Mock the execute method to return stats
        self.manager.execute = MagicMock(return_value=[{
            'total': 100,
            'pending': 20,
            'processing': 5,
            'finished': 70,
            'error': 5
        }])
        
        stats = self.manager.get_queue_stats()
        
        self.assertEqual(stats['total'], 100)
        self.assertEqual(stats['pending'], 20)
        self.assertEqual(stats['processing'], 5)
        self.assertEqual(stats['finished'], 70)
        self.assertEqual(stats['error'], 5)

    def test_reset_processing_tasks(self):
        """Test resetting stuck processing tasks."""
        # Mock the cursor rowcount
        self.mock_cursor.rowcount = 3
        self.manager.execute = MagicMock()
        
        reset_count = self.manager.reset_processing_tasks()
        
        self.assertEqual(reset_count, 3)
        self.manager.execute.assert_called_once()
        
        # Verify the SQL query
        call_args = self.manager.execute.call_args
        self.assertIn("UPDATE processing_queue", call_args[0][0])
        self.assertIn("status = NULL", call_args[0][0])
        self.assertIn("WHERE status = 1", call_args[0][0])

    def test_get_failed_tasks(self):
        """Test getting failed tasks."""
        # Mock the execute method to return failed tasks
        self.manager.execute = MagicMock(return_value=[
            {
                'id': 100,
                'document_id': 42,
                'task_id': 1,
                'error': 'Test error',
                'updated': '2023-01-01 12:00:00',
                'description': 'Test Task'
            }
        ])
        
        failed_tasks = self.manager.get_failed_tasks()
        
        self.assertEqual(len(failed_tasks), 1)
        self.assertEqual(failed_tasks[0]['id'], 100)
        self.assertEqual(failed_tasks[0]['error'], 'Test error')


if __name__ == '__main__':
    unittest.main()
