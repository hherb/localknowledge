"""
Unit tests for the QA embeddings database functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import logging
import json
from localknowledge.db.qafinder import QAEmbeddingDatabaseManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestQAEmbeddingDatabaseManager(unittest.TestCase):
    """Test the QA embedding database manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the database connection
        self.patcher = patch('localknowledge.db.base.DatabaseManager.connect')
        self.mock_connect = self.patcher.start()

        # Mock the execute method
        self.patcher_execute = patch('localknowledge.db.base.DatabaseManager.execute')
        self.mock_execute = self.patcher_execute.start()

        # Mock the execute_many method
        self.patcher_execute_many = patch('localknowledge.db.base.DatabaseManager.execute_many')
        self.mock_execute_many = self.patcher_execute_many.start()

        # Sample data for tests
        self.source_id = "test-source"
        self.document_id = "test-doc-123"
        self.chunk_no = 1
        self.page_no = 1
        self.text = "This is a test text for QA embedding."
        self.qa_pairs = json.dumps([
            {"question": "What is this?", "answer": "A test text."},
            {"question": "What is it for?", "answer": "QA embedding."}
        ])
        self.model_name = "test-model"
        self.sample_embedding = [0.1] * 1024  # 1024-dimensional embedding

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()
        self.patcher_execute.stop()
        self.patcher_execute_many.stop()

    def test_create_tables(self):
        """Test creating tables."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Call create_tables
        manager.create_tables()

        # Verify that execute was called twice (once for extension, once for table)
        self.assertEqual(self.mock_execute.call_count, 2)

        # Verify that the first call creates the pgvector extension
        self.assertEqual(
            self.mock_execute.call_args_list[0][0][0],
            "CREATE EXTENSION IF NOT EXISTS vector"
        )

        # Verify that the second call creates the qaembeddings table
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS qaembeddings",
            self.mock_execute.call_args_list[1][0][0]
        )

    def test_create_indices(self):
        """Test creating indices."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Call create_indices
        manager.create_indices()

        # Verify that execute was called three times (once for each index)
        self.assertEqual(self.mock_execute.call_count, 3)

        # Verify that the calls create the expected indices
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_source_id",
            self.mock_execute.call_args_list[0][0][0]
        )
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_document_id",
            self.mock_execute.call_args_list[1][0][0]
        )
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_vector",
            self.mock_execute.call_args_list[2][0][0]
        )

    def test_store_qa_embedding(self):
        """Test storing a QA embedding."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return an ID
        self.mock_execute.return_value = [{'id': 123}]

        # Store a QA embedding
        result = manager.store_qa_embedding(
            source_id=self.source_id,
            document_id=self.document_id,
            chunk_no=self.chunk_no,
            qa_pairs=self.qa_pairs,
            embedding=self.sample_embedding,
            model_name=self.model_name,
            page_no=self.page_no
        )

        # Verify that the result is the ID returned by execute
        self.assertEqual(result, 123)

        # Verify that execute was called with the correct query and parameters
        self.mock_execute.assert_called_once()
        query, params = self.mock_execute.call_args[0]
        self.assertIn("INSERT INTO qaembeddings", query)
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)
        self.assertEqual(params[2], self.chunk_no)
        self.assertEqual(params[3], self.page_no)
        self.assertEqual(params[4], self.qa_pairs)
        self.assertEqual(params[7], self.model_name)

    def test_store_qa_embeddings_batch(self):
        """Test storing multiple QA embeddings in a batch."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mocks to clear the calls from __init__
        self.mock_execute.reset_mock()
        self.mock_execute_many.reset_mock()

        # Create a batch of QA embeddings
        embeddings = [
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'page_no': 1,
                'qa_pairs': self.qa_pairs,
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            },
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 2,
                'page_no': 1,
                'qa_pairs': self.qa_pairs,
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            }
        ]

        # Store the batch
        result = manager.store_qa_embeddings_batch(embeddings)

        # Verify that the result is the number of embeddings
        self.assertEqual(result, 2)

        # Verify that execute_many was called with the correct query and parameters
        self.mock_execute_many.assert_called_once()
        query, params_list = self.mock_execute_many.call_args[0]
        self.assertIn("INSERT INTO qaembeddings", query)
        self.assertEqual(len(params_list), 2)

    def test_search_similar(self):
        """Test searching for similar QA embeddings."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return some results
        self.mock_execute.return_value = [
            {
                'id': 1,
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'page_no': 1,
                'qa_pairs': self.qa_pairs,
                'model_name': self.model_name,
                'similarity': 0.95
            }
        ]

        # Search for similar QA embeddings
        results = manager.search_similar(
            query_embedding=self.sample_embedding,
            limit=10,
            threshold=0.7,
            source_id=self.source_id
        )

        # Verify that the results are as expected
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], 1)
        self.assertEqual(results[0]['similarity'], 0.95)

        # Verify that execute was called with the correct query and parameters
        self.mock_execute.assert_called_once()
        query, params = self.mock_execute.call_args[0]
        self.assertIn("SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, model_name", query)
        self.assertIn("1 - (embedding <=> %s::vector) AS similarity", query)
        self.assertEqual(params[-1], 10)  # Limit parameter

    def test_get_document_qa_embeddings(self):
        """Test getting all QA embeddings for a document."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return some results
        self.mock_execute.return_value = [
            {
                'id': 1,
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'page_no': 1,
                'qa_pairs': self.qa_pairs,
                'model_name': self.model_name
            },
            {
                'id': 2,
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 2,
                'page_no': 1,
                'qa_pairs': self.qa_pairs,
                'model_name': self.model_name
            }
        ]

        # Get document QA embeddings
        results = manager.get_document_qa_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that the results are as expected
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], 1)
        self.assertEqual(results[1]['id'], 2)

        # Verify that execute was called with the correct query and parameters
        self.mock_execute.assert_called_once()
        query, params = self.mock_execute.call_args[0]
        self.assertIn("SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, model_name", query)
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)

    def test_delete_document_qa_embeddings(self):
        """Test deleting all QA embeddings for a document."""
        manager = QAEmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return some results
        self.mock_execute.return_value = [{'id': 1}, {'id': 2}]

        # Delete document QA embeddings
        result = manager.delete_document_qa_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that the result is the number of deleted embeddings
        self.assertEqual(result, 2)

        # Verify that execute was called with the correct query and parameters
        self.mock_execute.assert_called_once()
        query, params = self.mock_execute.call_args[0]
        self.assertIn("DELETE FROM qaembeddings", query)
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)


if __name__ == '__main__':
    unittest.main()
