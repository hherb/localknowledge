"""
Unit tests for the EmbeddingManager class.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import logging
import ollama
import numpy as np

from localknowledge.embeddings.embedding_manager import EmbeddingManager
from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker, BaseChunker
from localknowledge.textprocessing.chunking.base import Chunk


class TestEmbeddingManager(unittest.TestCase):
    """Test cases for the EmbeddingManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a patcher for the EmbeddingDatabaseManager
        self.db_patcher = patch('localknowledge.embeddings.embedding_manager.EmbeddingDatabaseManager')
        self.mock_db_class = self.db_patcher.start()
        self.mock_db = MagicMock()
        self.mock_db_class.return_value = self.mock_db

        # Create a patcher for ollama.embeddings
        self.ollama_patcher = patch('localknowledge.embeddings.embedding_manager.ollama.embeddings')
        self.mock_ollama_embeddings = self.ollama_patcher.start()

        # Set up a mock embedding response
        self.mock_embedding = [0.1] * 1536  # 1536-dimensional embedding
        self.mock_ollama_embeddings.return_value = {'embedding': self.mock_embedding}

        # Create a patcher for _verify_model to avoid actual API calls
        self.verify_model_patcher = patch.object(EmbeddingManager, '_verify_model')
        self.mock_verify_model = self.verify_model_patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.db_patcher.stop()
        self.ollama_patcher.stop()
        self.verify_model_patcher.stop()

    def test_init_default(self):
        """Test initialization with default parameters."""
        manager = EmbeddingManager()

        # Check default values
        self.assertEqual(manager.model_name, "snowflake-arctic-embed2:latest")
        self.assertIsInstance(manager.chunker, TextChunker)
        self.assertEqual(manager.db, self.mock_db)

        # Verify that _verify_model was called
        self.mock_verify_model.assert_called_once()

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        custom_model = "custom-model:v1"
        custom_chunker = MagicMock(spec=BaseChunker)

        manager = EmbeddingManager(model_name=custom_model, chunker=custom_chunker)

        # Check custom values
        self.assertEqual(manager.model_name, custom_model)
        self.assertEqual(manager.chunker, custom_chunker)

        # Verify that _verify_model was called
        self.mock_verify_model.assert_called_once()

    @patch('localknowledge.embeddings.embedding_manager.ollama.list')
    def test_verify_model_success(self, mock_ollama_list):
        """Test successful model verification."""
        # Remove the patcher for _verify_model to test the actual method
        self.verify_model_patcher.stop()

        # Set up mock response for ollama.list
        mock_ollama_list.return_value = {
            'models': [
                {'name': 'snowflake-arctic-embed2:latest'},
                {'name': 'other-model:v1'}
            ]
        }

        # This should not raise an exception
        manager = EmbeddingManager()

        # Verify that ollama.list was called
        mock_ollama_list.assert_called_once()

        # Restart the patcher for other tests
        self.verify_model_patcher = patch.object(EmbeddingManager, '_verify_model')
        self.mock_verify_model = self.verify_model_patcher.start()

    @patch('localknowledge.embeddings.embedding_manager.ollama.list')
    def test_verify_model_not_found(self, mock_ollama_list):
        """Test model verification when model is not found."""
        # Remove the patcher for _verify_model to test the actual method
        self.verify_model_patcher.stop()

        # Set up mock response for ollama.list
        mock_ollama_list.return_value = {
            'models': [
                {'name': 'other-model:v1'}
            ]
        }

        # This should log a warning but not raise an exception
        with self.assertLogs(level='WARNING'):
            manager = EmbeddingManager()

        # Verify that ollama.list was called
        mock_ollama_list.assert_called_once()

        # Restart the patcher for other tests
        self.verify_model_patcher = patch.object(EmbeddingManager, '_verify_model')
        self.mock_verify_model = self.verify_model_patcher.start()

    def test_create_embedding(self):
        """Test creating an embedding."""
        manager = EmbeddingManager()
        text = "This is a test text for embedding."

        embedding = manager.create_embedding(text)

        # Check that the embedding is correct
        self.assertEqual(embedding, self.mock_embedding)

        # Verify that ollama.embeddings was called with the correct parameters
        self.mock_ollama_embeddings.assert_called_once_with(
            model=manager.model_name,
            prompt=text
        )

    def test_create_embedding_error_retry(self):
        """Test that create_embedding retries on error."""
        # Set up the mock to raise an exception and then succeed
        self.mock_ollama_embeddings.side_effect = [
            Exception("API error"),
            {'embedding': self.mock_embedding}
        ]

        manager = EmbeddingManager()
        text = "This is a test text for embedding."

        # This should retry and succeed
        embedding = manager.create_embedding(text)

        # Check that the embedding is correct
        self.assertEqual(embedding, self.mock_embedding)

        # Verify that ollama.embeddings was called twice
        self.assertEqual(self.mock_ollama_embeddings.call_count, 2)

    def test_extract_keywords(self):
        """Test extracting keywords from text."""
        manager = EmbeddingManager()
        text = "This is a test text with some keywords. Keywords are important for search."

        keywords = manager.extract_keywords(text, max_keywords=3)

        # Check that keywords were extracted
        self.assertIsInstance(keywords, list)
        self.assertLessEqual(len(keywords), 3)

        # Keywords should include 'keywords' as it appears multiple times
        self.assertIn('keywords', keywords)

    def test_process_document_simple(self):
        """Test processing a simple document."""
        manager = EmbeddingManager()
        source_id = "test-source"
        document_id = "test-doc-123"
        text = "This is a test document for processing."

        # Mock the chunker to return a single chunk
        mock_chunk = Chunk(text=text, metadata={})
        manager.chunker.chunk = MagicMock(return_value=[mock_chunk])

        # Process the document
        chunks = manager.process_document(source_id, document_id, text)

        # Check that one chunk was processed
        self.assertEqual(chunks, 1)

        # Verify that the chunker was called
        manager.chunker.chunk.assert_called_once()

        # Verify that create_embedding was called
        self.mock_ollama_embeddings.assert_called_once()

        # Verify that store_embedding was called with the correct parameters
        self.mock_db.store_embedding.assert_called_once_with(
            source_id=source_id,
            document_id=document_id,
            chunk_no=0,
            page_no=None,
            text=text,
            embedding=self.mock_embedding,
            model_name=manager.model_name,
            keywords=manager.extract_keywords(text)
        )

    def test_process_document_with_pages(self):
        """Test processing a document with page information."""
        manager = EmbeddingManager()
        source_id = "test-source"
        document_id = "test-doc-123"

        # Create page info
        page_info = {
            1: "Page 1 content.",
            2: "Page 2 content."
        }

        # Mock the chunker to return a single chunk per page
        manager.chunker.chunk = MagicMock(side_effect=[
            [Chunk(text=page_info[1], metadata={})],
            [Chunk(text=page_info[2], metadata={})]
        ])

        # Process the document - use a non-empty text to avoid the early return
        chunks = manager.process_document(source_id, document_id, "dummy text", page_info=page_info)

        # Check that two chunks were processed (one per page)
        self.assertEqual(chunks, 2)

        # Verify that the chunker was called twice (once per page)
        self.assertEqual(manager.chunker.chunk.call_count, 2)

        # Verify that create_embedding was called twice
        self.assertEqual(self.mock_ollama_embeddings.call_count, 2)

        # Verify that store_embedding was called with the correct parameters for each page
        expected_calls = [
            call(
                source_id=source_id,
                document_id=document_id,
                chunk_no=1000,  # page_no * 1000 + i
                page_no=1,
                text=page_info[1],
                embedding=self.mock_embedding,
                model_name=manager.model_name,
                keywords=manager.extract_keywords(page_info[1])
            ),
            call(
                source_id=source_id,
                document_id=document_id,
                chunk_no=2000,  # page_no * 1000 + i
                page_no=2,
                text=page_info[2],
                embedding=self.mock_embedding,
                model_name=manager.model_name,
                keywords=manager.extract_keywords(page_info[2])
            )
        ]
        self.mock_db.store_embedding.assert_has_calls(expected_calls)

    def test_process_document_markdown(self):
        """Test processing a markdown document."""
        manager = EmbeddingManager()
        source_id = "test-source"
        document_id = "test-doc-123"
        markdown_text = "# Heading\n\nThis is a markdown document."

        # Mock the chunker to return a list of chunks
        mock_chunk = Chunk(text=markdown_text, metadata={})
        with patch('localknowledge.embeddings.embedding_manager.MarkdownChunker') as mock_markdown_chunker_class:
            mock_markdown_chunker = MagicMock()
            mock_markdown_chunker_class.return_value = mock_markdown_chunker
            mock_markdown_chunker.chunk.return_value = [mock_chunk]

            # Process the document with is_markdown=True
            chunks = manager.process_document(
                source_id=source_id,
                document_id=document_id,
                text=markdown_text,
                is_markdown=True
            )

            # Verify that a MarkdownChunker was created
            mock_markdown_chunker_class.assert_called_once()

            # Verify that the chunker's chunk method was called
            mock_markdown_chunker.chunk.assert_called_once()

            # One chunk should have been processed
            self.assertEqual(chunks, 1)

            # Verify that store_embedding was called once
            self.mock_db.store_embedding.assert_called_once()

    def test_search(self):
        """Test searching for similar documents."""
        manager = EmbeddingManager()
        query = "Test search query"
        limit = 5
        threshold = 0.8
        source_id = "test-source"

        # Mock search results
        mock_results = [
            {
                'id': 1,
                'source_id': source_id,
                'document_id': 'doc1',
                'text': 'Result 1',
                'similarity': 0.9
            },
            {
                'id': 2,
                'source_id': source_id,
                'document_id': 'doc2',
                'text': 'Result 2',
                'similarity': 0.85
            }
        ]
        self.mock_db.search_similar.return_value = mock_results

        # Perform the search
        results = manager.search(query, limit=limit, threshold=threshold, source_id=source_id)

        # Check that the results are correct
        self.assertEqual(results, mock_results)

        # Verify that create_embedding was called for the query
        self.mock_ollama_embeddings.assert_called_once_with(
            model=manager.model_name,
            prompt=query
        )

        # Verify that search_similar was called with the correct parameters
        self.mock_db.search_similar.assert_called_once_with(
            query_embedding=self.mock_embedding,
            limit=limit,
            threshold=threshold,
            source_id=source_id
        )

    def test_delete_document(self):
        """Test deleting document embeddings."""
        manager = EmbeddingManager()
        source_id = "test-source"
        document_id = "test-doc-123"

        # Mock deletion result
        self.mock_db.delete_document_embeddings.return_value = 5

        # Delete the document
        deleted = manager.delete_document(source_id, document_id)

        # Check that the correct number of embeddings was deleted
        self.assertEqual(deleted, 5)

        # Verify that delete_document_embeddings was called with the correct parameters
        self.mock_db.delete_document_embeddings.assert_called_once_with(source_id, document_id)

    def test_close(self):
        """Test closing the database connection."""
        manager = EmbeddingManager()

        # Close the manager
        manager.close()

        # Verify that the database connection was closed
        self.mock_db.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
