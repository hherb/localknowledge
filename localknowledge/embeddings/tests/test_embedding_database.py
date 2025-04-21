"""
Unit tests for the EmbeddingDatabaseManager class.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import logging
import psycopg2
from typing import List, Dict, Any

from localknowledge.embeddings.database import EmbeddingDatabaseManager


class TestEmbeddingDatabaseManager(unittest.TestCase):
    """Test cases for the EmbeddingDatabaseManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a patcher for the DatabaseManager superclass
        self.db_manager_patcher = patch('localknowledge.embeddings.database.DatabaseManager.__init__')
        self.mock_db_manager_init = self.db_manager_patcher.start()
        self.mock_db_manager_init.return_value = None

        # Create patchers for the execute and execute_many methods
        self.execute_patcher = patch('localknowledge.embeddings.database.DatabaseManager.execute')
        self.mock_execute = self.execute_patcher.start()

        self.execute_many_patcher = patch('localknowledge.embeddings.database.DatabaseManager.execute_many')
        self.mock_execute_many = self.execute_many_patcher.start()

        # Sample embedding data for tests
        self.sample_embedding = [0.1] * 1024  # 1024-dimensional embedding
        self.sample_embedding_str = f"[{','.join(map(str, self.sample_embedding))}]"

        # Sample document data
        self.source_id = "test-source"
        self.document_id = "test-doc-123"
        self.chunk_no = 1
        self.page_no = 1
        self.text = "This is a test text for embedding."
        self.keywords = ["test", "embedding"]
        self.model_name = "test-model"

    def tearDown(self):
        """Tear down test fixtures."""
        self.db_manager_patcher.stop()
        self.execute_patcher.stop()
        self.execute_many_patcher.stop()

    def test_init(self):
        """Test initialization."""
        # Mock the create_tables and create_indices methods
        with patch.object(EmbeddingDatabaseManager, 'create_tables') as mock_create_tables, \
             patch.object(EmbeddingDatabaseManager, 'create_indices') as mock_create_indices:

            manager = EmbeddingDatabaseManager()

            # Verify that the superclass __init__ was called
            self.mock_db_manager_init.assert_called_once()

            # Verify that create_tables and create_indices were called
            mock_create_tables.assert_called_once()
            mock_create_indices.assert_called_once()

    def test_create_tables(self):
        """Test creating tables."""
        manager = EmbeddingDatabaseManager()

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

        # Verify that the second call creates the embeddings table
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS embeddings",
            self.mock_execute.call_args_list[1][0][0]
        )

    def test_create_tables_error(self):
        """Test error handling when creating tables."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Make the first execute call raise an exception
        self.mock_execute.side_effect = psycopg2.Error("Test error")

        # Call create_tables and expect an exception
        with self.assertRaises(psycopg2.Error):
            manager.create_tables()

        # Verify that execute was called once
        self.mock_execute.assert_called_once()

    def test_create_indices(self):
        """Test creating indices."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Call create_indices
        manager.create_indices()

        # Verify that execute was called three times (once for each index)
        self.assertEqual(self.mock_execute.call_count, 3)

        # Verify that the calls create the expected indices
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_embeddings_source_id",
            self.mock_execute.call_args_list[0][0][0]
        )
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_embeddings_document_id",
            self.mock_execute.call_args_list[1][0][0]
        )
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_embeddings_vector",
            self.mock_execute.call_args_list[2][0][0]
        )

    def test_store_embedding(self):
        """Test storing an embedding."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return an ID
        self.mock_execute.return_value = [{'id': 123}]

        # Store an embedding
        result = manager.store_embedding(
            source_id=self.source_id,
            document_id=self.document_id,
            chunk_no=self.chunk_no,
            text=self.text,
            embedding=self.sample_embedding,
            model_name=self.model_name,
            page_no=self.page_no,
            keywords=self.keywords
        )

        # Verify that the result is the ID from the execute result
        self.assertEqual(result, 123)

        # Verify that execute was called with the correct parameters
        self.mock_execute.assert_called_once()
        args, kwargs = self.mock_execute.call_args

        # Check the query
        self.assertIn("INSERT INTO embeddings", args[0])
        self.assertIn("ON CONFLICT", args[0])

        # Check the parameters
        params = args[1]
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)
        self.assertEqual(params[2], self.chunk_no)
        self.assertEqual(params[3], self.page_no)
        self.assertEqual(params[4], self.text)
        self.assertEqual(params[5], self.keywords)
        self.assertEqual(params[6], self.sample_embedding_str)
        self.assertEqual(params[7], self.model_name)

        # Check that commit was False
        self.assertEqual(kwargs.get('commit'), False)

    def test_store_embedding_error(self):
        """Test error handling when storing an embedding."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Make execute raise an exception
        self.mock_execute.side_effect = psycopg2.Error("Test error")

        # Store an embedding and expect an exception
        with self.assertRaises(psycopg2.Error):
            manager.store_embedding(
                source_id=self.source_id,
                document_id=self.document_id,
                chunk_no=self.chunk_no,
                text=self.text,
                embedding=self.sample_embedding,
                model_name=self.model_name
            )

        # Verify that execute was called
        self.mock_execute.assert_called_once()

    def test_store_embeddings_batch(self):
        """Test storing multiple embeddings in a batch."""
        manager = EmbeddingDatabaseManager()

        # Reset the mocks to clear the calls from __init__
        self.mock_execute.reset_mock()
        self.mock_execute_many.reset_mock()

        # Create a batch of embeddings
        embeddings = [
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'page_no': 1,
                'text': "Text 1",
                'keywords': ["keyword1", "keyword2"],
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            },
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 2,
                'page_no': 1,
                'text': "Text 2",
                'keywords': ["keyword3", "keyword4"],
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            }
        ]

        # Store the batch
        result = manager.store_embeddings_batch(embeddings)

        # Verify that the result is the number of embeddings
        self.assertEqual(result, 2)

        # Verify that execute_many was called with the correct parameters
        self.mock_execute_many.assert_called_once()
        args, kwargs = self.mock_execute_many.call_args

        # Check that commit was False
        self.assertEqual(kwargs.get('commit'), False)

        # Check the query
        self.assertIn("INSERT INTO embeddings", args[0])
        self.assertIn("ON CONFLICT", args[0])

        # Check the parameters list
        params_list = args[1]
        self.assertEqual(len(params_list), 2)

        # Check the first set of parameters
        params1 = params_list[0]
        self.assertEqual(params1[0], self.source_id)
        self.assertEqual(params1[1], self.document_id)
        self.assertEqual(params1[2], 1)
        self.assertEqual(params1[3], 1)
        self.assertEqual(params1[4], "Text 1")
        self.assertEqual(params1[5], ["keyword1", "keyword2"])
        self.assertEqual(params1[6], self.sample_embedding_str)
        self.assertEqual(params1[7], self.model_name)

        # Check the second set of parameters
        params2 = params_list[1]
        self.assertEqual(params2[0], self.source_id)
        self.assertEqual(params2[1], self.document_id)
        self.assertEqual(params2[2], 2)
        self.assertEqual(params2[3], 1)
        self.assertEqual(params2[4], "Text 2")
        self.assertEqual(params2[5], ["keyword3", "keyword4"])
        self.assertEqual(params2[6], self.sample_embedding_str)
        self.assertEqual(params2[7], self.model_name)

    def test_store_embeddings_batch_empty(self):
        """Test storing an empty batch of embeddings."""
        manager = EmbeddingDatabaseManager()

        # Reset the mocks to clear the calls from __init__
        self.mock_execute_many.reset_mock()

        # Store an empty batch
        result = manager.store_embeddings_batch([])

        # Verify that the result is 0
        self.assertEqual(result, 0)

        # Verify that execute_many was not called
        self.mock_execute_many.assert_not_called()

    def test_store_embeddings_batch_error_fallback(self):
        """Test error handling and fallback when storing a batch of embeddings."""
        manager = EmbeddingDatabaseManager()

        # Reset the mocks to clear the calls from __init__
        self.mock_execute_many.reset_mock()
        self.mock_execute.reset_mock()

        # Make execute_many raise an exception
        self.mock_execute_many.side_effect = psycopg2.Error("Test error")

        # Make execute return a success for the fallback
        self.mock_execute.return_value = [{'id': 123}]

        # Create a batch of embeddings
        embeddings = [
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'text': "Text 1",
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            },
            {
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 2,
                'text': "Text 2",
                'embedding': self.sample_embedding,
                'model_name': self.model_name
            }
        ]

        # Store the batch
        result = manager.store_embeddings_batch(embeddings)

        # Verify that the result is the number of embeddings
        self.assertEqual(result, 2)

        # Verify that execute_many was called
        self.mock_execute_many.assert_called_once()

        # Verify that execute was called twice (once for each embedding)
        self.assertEqual(self.mock_execute.call_count, 2)

    def test_search_similar(self):
        """Test searching for similar documents."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return search results
        mock_results = [
            {
                'id': 1,
                'source_id': self.source_id,
                'document_id': 'doc1',
                'text': 'Result 1',
                'similarity': 0.9
            },
            {
                'id': 2,
                'source_id': self.source_id,
                'document_id': 'doc2',
                'text': 'Result 2',
                'similarity': 0.85
            }
        ]
        self.mock_execute.return_value = mock_results

        # Search for similar documents
        results = manager.search_similar(
            query_embedding=self.sample_embedding,
            limit=5,
            threshold=0.8,
            source_id=self.source_id
        )

        # Verify that the results are correct
        self.assertEqual(results, mock_results)

        # Verify that execute was called with the correct parameters
        self.mock_execute.assert_called_once()
        args, kwargs = self.mock_execute.call_args

        # Check the query
        self.assertIn("SELECT id, source_id, document_id", args[0])
        self.assertIn("1 - (embedding <=> %s::vector) AS similarity", args[0])
        self.assertIn("WHERE source_id = %s", args[0])
        self.assertIn("WHERE 1 - (embedding <=> %s::vector) > 0.8", args[0])
        self.assertIn("ORDER BY similarity DESC", args[0])
        self.assertIn("LIMIT 5", args[0])

        # Check the parameters
        params = args[1]
        self.assertEqual(params[0], self.sample_embedding_str)
        self.assertEqual(params[1], self.source_id)

    def test_search_similar_no_source_id(self):
        """Test searching for similar documents without a source_id filter."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return search results
        self.mock_execute.return_value = []

        # Search for similar documents without a source_id
        results = manager.search_similar(
            query_embedding=self.sample_embedding,
            limit=5,
            threshold=0.8
        )

        # Verify that the results are correct
        self.assertEqual(results, [])

        # Verify that execute was called with the correct parameters
        self.mock_execute.assert_called_once()
        args, kwargs = self.mock_execute.call_args

        # Check the query
        self.assertIn("SELECT id, source_id, document_id", args[0])
        self.assertNotIn("WHERE source_id = %s", args[0])

        # Check the parameters
        params = args[1]
        self.assertEqual(params[0], self.sample_embedding_str)
        self.assertEqual(len(params), 1)  # Only the embedding, no source_id

    def test_search_similar_error(self):
        """Test error handling when searching for similar documents."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Make execute raise an exception
        self.mock_execute.side_effect = psycopg2.Error("Test error")

        # Search for similar documents
        results = manager.search_similar(
            query_embedding=self.sample_embedding,
            limit=5,
            threshold=0.8
        )

        # Verify that an empty list is returned on error
        self.assertEqual(results, [])

        # Verify that execute was called
        self.mock_execute.assert_called_once()

    def test_get_document_embeddings(self):
        """Test getting all embeddings for a document."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return embeddings
        mock_embeddings = [
            {
                'id': 1,
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 1,
                'text': 'Chunk 1'
            },
            {
                'id': 2,
                'source_id': self.source_id,
                'document_id': self.document_id,
                'chunk_no': 2,
                'text': 'Chunk 2'
            }
        ]
        self.mock_execute.return_value = mock_embeddings

        # Get document embeddings
        embeddings = manager.get_document_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that the embeddings are correct
        self.assertEqual(embeddings, mock_embeddings)

        # Verify that execute was called with the correct parameters
        self.mock_execute.assert_called_once()
        args, kwargs = self.mock_execute.call_args

        # Check the query
        self.assertIn("SELECT id, source_id, document_id", args[0])
        self.assertIn("WHERE source_id = %s AND document_id = %s", args[0])

        # Check the parameters
        params = args[1]
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)

    def test_get_document_embeddings_error(self):
        """Test error handling when getting document embeddings."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Make execute raise an exception
        self.mock_execute.side_effect = psycopg2.Error("Test error")

        # Get document embeddings
        embeddings = manager.get_document_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that an empty list is returned on error
        self.assertEqual(embeddings, [])

        # Verify that execute was called
        self.mock_execute.assert_called_once()

    def test_delete_document_embeddings(self):
        """Test deleting all embeddings for a document."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Mock the execute result to return deleted IDs
        self.mock_execute.return_value = [{'id': 1}, {'id': 2}]

        # Delete document embeddings
        deleted = manager.delete_document_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that the correct number of embeddings was deleted
        self.assertEqual(deleted, 2)

        # Verify that execute was called with the correct parameters
        self.mock_execute.assert_called_once()
        args, kwargs = self.mock_execute.call_args

        # Check the query
        self.assertIn("DELETE FROM embeddings", args[0])
        self.assertIn("WHERE source_id = %s AND document_id = %s", args[0])

        # Check the parameters
        params = args[1]
        self.assertEqual(params[0], self.source_id)
        self.assertEqual(params[1], self.document_id)

    def test_delete_document_embeddings_error(self):
        """Test error handling when deleting document embeddings."""
        manager = EmbeddingDatabaseManager()

        # Reset the mock to clear the calls from __init__
        self.mock_execute.reset_mock()

        # Make execute raise an exception
        self.mock_execute.side_effect = psycopg2.Error("Test error")

        # Delete document embeddings
        deleted = manager.delete_document_embeddings(
            source_id=self.source_id,
            document_id=self.document_id
        )

        # Verify that 0 is returned on error
        self.assertEqual(deleted, 0)

        # Verify that execute was called
        self.mock_execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
