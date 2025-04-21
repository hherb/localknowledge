"""
Unit tests for the QA finder functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import logging
import json
import os
from localknowledge.ai.qafinder import (
    find_questions,
    find_questions_and_answers,
    create_embedding,
    QAEmbeddingManager
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestQAFinder(unittest.TestCase):
    """Test the QA finder functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample text for testing
        self.sample_text = """
        Background: Traumatic brain injury (TBI) is a leading cause of death and disability worldwide.
        Methods: We conducted a retrospective study of 1,000 TBI patients.
        Results: We found that early intervention improved outcomes.
        Conclusion: Early intervention is critical for TBI patients.
        """

        # Sample QA pairs
        self.sample_qa_pairs = [
            {"question": "What is a leading cause of death and disability worldwide?", "answer": "Traumatic brain injury (TBI)."},
            {"question": "How many patients were included in the study?", "answer": "1,000 TBI patients."},
            {"question": "What improved outcomes for TBI patients?", "answer": "Early intervention."},
            {"question": "What is critical for TBI patients?", "answer": "Early intervention."}
        ]

        # Sample embedding
        self.sample_embedding = [0.1] * 1024  # 1024-dimensional embedding

    def test_find_questions(self):
        """Test finding questions in text."""
        # Mock the ollama.generate function
        with patch('ollama.generate') as mock_generate:
            # Set up the mock to return a response with questions
            mock_response = MagicMock()
            mock_response.response = json.dumps(["Question 1?", "Question 2?"])
            mock_generate.return_value = mock_response

            # Call the function
            result = find_questions(self.sample_text)

            # Verify that ollama.generate was called with the correct parameters
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            self.assertEqual(kwargs['model'], "gemma3:4b")
            self.assertIn(self.sample_text, kwargs['prompt'])

            # Verify that the result is as expected
            self.assertEqual(result, ["Question 1?", "Question 2?"])

    def test_find_questions_and_answers(self):
        """Test finding questions and answers in text."""
        # Mock the ollama.generate function
        with patch('ollama.generate') as mock_generate:
            # Set up the mock to return a response with QA pairs
            mock_response = MagicMock()
            mock_response.response = json.dumps(self.sample_qa_pairs)
            mock_generate.return_value = mock_response

            # Call the function
            result = find_questions_and_answers(self.sample_text)

            # Verify that ollama.generate was called with the correct parameters
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            self.assertEqual(kwargs['model'], "gemma3:4b")
            self.assertIn(self.sample_text, kwargs['prompt'])

            # Verify that the result is as expected
            self.assertEqual(result, self.sample_qa_pairs)

    def test_create_embedding(self):
        """Test creating an embedding."""
        # Mock the ollama.embeddings function
        with patch('ollama.embeddings') as mock_embeddings:
            # Set up the mock to return a response with an embedding
            mock_embeddings.return_value = {'embedding': self.sample_embedding}

            # Call the function
            result = create_embedding(self.sample_text)

            # Verify that ollama.embeddings was called with the correct parameters
            mock_embeddings.assert_called_once()
            args, kwargs = mock_embeddings.call_args
            self.assertEqual(kwargs['model'], "snowflake-arctic-embed2:latest")
            self.assertEqual(kwargs['prompt'], self.sample_text)

            # Verify that the result is as expected
            self.assertEqual(result, self.sample_embedding)

    def test_qa_embedding_manager_init(self):
        """Test initializing the QA embedding manager."""
        # Mock the QAEmbeddingDatabaseManager
        with patch('localknowledge.db.qafinder.QAEmbeddingDatabaseManager') as mock_db_manager:
            # Mock the _verify_models method
            with patch('localknowledge.ai.qafinder.QAEmbeddingManager._verify_models') as mock_verify_models:
                # Create a QA embedding manager
                manager = QAEmbeddingManager()

                # Verify that the database manager was initialized
                mock_db_manager.assert_called_once()

                # Verify that _verify_models was called
                mock_verify_models.assert_called_once()

                # Verify that the manager has the correct attributes
                self.assertEqual(manager.model_name, "gemma3:4b")
                self.assertEqual(manager.embedding_model, "snowflake-arctic-embed2:latest")

    def test_qa_embedding_manager_process_text(self):
        """Test processing text with the QA embedding manager."""
        # Mock the QAEmbeddingDatabaseManager
        with patch('localknowledge.db.qafinder.QAEmbeddingDatabaseManager') as mock_db_manager:
            # Mock the _verify_models method
            with patch('localknowledge.ai.qafinder.QAEmbeddingManager._verify_models'):
                # Mock the find_questions_and_answers function
                with patch('localknowledge.ai.qafinder.find_questions_and_answers') as mock_find_qa:
                    # Set up the mock to return QA pairs
                    mock_find_qa.return_value = self.sample_qa_pairs

                    # Mock the create_embedding function
                    with patch('localknowledge.ai.qafinder.create_embedding') as mock_create_embedding:
                        # Set up the mock to return an embedding
                        mock_create_embedding.return_value = self.sample_embedding

                        # Create a QA embedding manager
                        manager = QAEmbeddingManager()

                        # Mock the store_qa_embedding method
                        manager.db.store_qa_embedding = MagicMock(return_value=123)

                        # Process text
                        result = manager.process_text(
                            source_id="test-source",
                            document_id="test-doc-123",
                            text=self.sample_text,
                            chunk_no=1,
                            page_no=1
                        )

                        # Verify that find_questions_and_answers was called with the correct parameters
                        mock_find_qa.assert_called_once_with(self.sample_text, model=manager.model_name)

                        # Verify that create_embedding was called with the correct parameters
                        mock_create_embedding.assert_called_once_with(self.sample_text, model=manager.embedding_model)

                        # Verify that store_qa_embedding was called with the correct parameters
                        manager.db.store_qa_embedding.assert_called_once()
                        args, kwargs = manager.db.store_qa_embedding.call_args
                        self.assertEqual(kwargs['source_id'], "test-source")
                        self.assertEqual(kwargs['document_id'], "test-doc-123")
                        self.assertEqual(kwargs['chunk_no'], 1)
                        self.assertEqual(kwargs['page_no'], 1)

                        self.assertEqual(kwargs['qa_pairs'], json.dumps(self.sample_qa_pairs))
                        self.assertEqual(kwargs['embedding'], self.sample_embedding)
                        self.assertEqual(kwargs['model_name'], manager.model_name)

                        # Verify that the result is as expected
                        self.assertEqual(result, 123)

    def test_qa_embedding_manager_search(self):
        """Test searching with the QA embedding manager."""
        # Mock the QAEmbeddingDatabaseManager
        with patch('localknowledge.db.qafinder.QAEmbeddingDatabaseManager') as mock_db_manager:
            # Mock the _verify_models method
            with patch('localknowledge.ai.qafinder.QAEmbeddingManager._verify_models'):
                # Mock the create_embedding function
                with patch('localknowledge.ai.qafinder.create_embedding') as mock_create_embedding:
                    # Set up the mock to return an embedding
                    mock_create_embedding.return_value = self.sample_embedding

                    # Create a QA embedding manager
                    manager = QAEmbeddingManager()

                    # Mock the search_similar method
                    manager.db.search_similar = MagicMock(return_value=[
                        {
                            'id': 1,
                            'source_id': "test-source",
                            'document_id': "test-doc-123",
                            'chunk_no': 1,
                            'page_no': 1,
                            'qa_pairs': json.dumps(self.sample_qa_pairs),
                            'model_name': manager.model_name,
                            'similarity': 0.95
                        }
                    ])

                    # Search for similar QA pairs
                    results = manager.search(
                        query="What is TBI?",
                        limit=10,
                        threshold=0.7,
                        source_id="test-source"
                    )

                    # Verify that create_embedding was called with the correct parameters
                    mock_create_embedding.assert_called_once_with("What is TBI?", model=manager.embedding_model)

                    # Verify that search_similar was called with the correct parameters
                    manager.db.search_similar.assert_called_once()
                    args, kwargs = manager.db.search_similar.call_args
                    self.assertEqual(kwargs['query_embedding'], self.sample_embedding)
                    self.assertEqual(kwargs['limit'], 10)
                    self.assertEqual(kwargs['threshold'], 0.7)
                    self.assertEqual(kwargs['source_id'], "test-source")

                    # Verify that the result is as expected
                    self.assertEqual(len(results), 1)
                    self.assertEqual(results[0]['id'], 1)
                    self.assertEqual(results[0]['similarity'], 0.95)
                    self.assertEqual(results[0]['qa_pairs'], self.sample_qa_pairs)


if __name__ == '__main__':
    unittest.main()
