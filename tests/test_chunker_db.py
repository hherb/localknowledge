"""
Tests for the ChunkingDatabaseManager class.
"""
import unittest
import json
from unittest.mock import patch, MagicMock

from localknowledge.db.chunker import ChunkingDatabaseManager


class TestChunkingDatabaseManager(unittest.TestCase):
    """Test cases for the ChunkingDatabaseManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock for the database connection
        self.patcher = patch('localknowledge.db.base.DatabaseManager.__init__')
        self.mock_db_init = self.patcher.start()
        self.mock_db_init.return_value = None

        # Create an instance of ChunkingDatabaseManager with mocked connection
        self.chunking_db = ChunkingDatabaseManager()
        self.chunking_db.execute = MagicMock()

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()

    def test_list_chunking_strategies(self):
        """Test listing chunking strategies."""
        # Mock the execute method to return a list of strategies
        mock_strategies = [
            {'id': 1, 'strategy_name': 'simple_splitter', 'modelname': None, 'parameters': {'chunk_size': 500, 'overlap': 50}},
            {'id': 2, 'strategy_name': 'adaptive_splitter', 'modelname': None, 'parameters': {'max_chunk_size': 1000, 'overlap': 100}}
        ]
        self.chunking_db.execute.return_value = mock_strategies

        # Call the method
        result = self.chunking_db.list_chunking_strategies()

        # Verify the result
        self.assertEqual(result, mock_strategies)
        self.chunking_db.execute.assert_called_once()

    def test_get_or_create_chunking_strategy_existing(self):
        """Test getting an existing chunking strategy."""
        # Mock the execute method to return an existing strategy
        strategy_name = 'simple_splitter'
        parameters = {'chunk_size': 500, 'overlap': 50}
        self.chunking_db.execute.return_value = [{'id': 1}]

        # Call the method
        result = self.chunking_db.get_or_create_chunking_strategy(strategy_name, parameters)

        # Verify the result
        self.assertEqual(result, 1)
        # Just check that execute was called once, without checking exact SQL formatting
        self.chunking_db.execute.assert_called_once()

    def test_get_or_create_chunking_strategy_new(self):
        """Test creating a new chunking strategy."""
        # Mock the execute method to first return empty list (not found), then return new ID
        strategy_name = 'new_splitter'
        parameters = {'chunk_size': 800, 'overlap': 100}
        self.chunking_db.execute.side_effect = [
            [],  # First call returns empty (not found)
            [{'id': 3}]  # Second call returns new ID
        ]

        # Call the method
        result = self.chunking_db.get_or_create_chunking_strategy(strategy_name, parameters)

        # Verify the result
        self.assertEqual(result, 3)
        # Just check that execute was called twice
        self.assertEqual(self.chunking_db.execute.call_count, 2)

    def test_get_or_create_chunk(self):
        """Test creating a new chunk."""
        # Mock the execute method to first return empty list (not found), then return new ID
        document_id = 1
        chunking_strategy_id = 2
        chunktype_id = 1
        text = "This is a test chunk"
        document_title = "Test Document"
        chunklength = len(text)
        chunk_no = 1
        page_start = 1
        page_end = 1
        metadata = {'source': 'test'}

        self.chunking_db.execute.side_effect = [
            [],  # First call returns empty (not found)
            [{'id': 5}]  # Second call returns new ID
        ]

        # Call the method
        result = self.chunking_db.get_or_create_chunk(
            document_id, chunking_strategy_id, chunktype_id, text,
            document_title, chunklength, chunk_no, page_start, page_end, metadata
        )

        # Verify the result
        self.assertEqual(result, 5)

        # Just check that execute was called twice
        self.assertEqual(self.chunking_db.execute.call_count, 2)

    def test_get_chunks_by_document(self):
        """Test getting chunks by document ID."""
        # Mock the execute method to return chunks
        document_id = 1
        mock_chunks = [
            {'id': 1, 'document_id': 1, 'chunk_no': 1, 'text': 'Chunk 1', 'strategy_name': 'simple_splitter', 'chunktype': 'abstract'},
            {'id': 2, 'document_id': 1, 'chunk_no': 2, 'text': 'Chunk 2', 'strategy_name': 'simple_splitter', 'chunktype': 'abstract'}
        ]
        self.chunking_db.execute.return_value = mock_chunks

        # Call the method
        result = self.chunking_db.get_chunks_by_document(document_id)

        # Verify the result
        self.assertEqual(result, mock_chunks)
        self.chunking_db.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
