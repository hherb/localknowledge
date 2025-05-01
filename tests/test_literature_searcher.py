"""Unit tests for the literature_searcher module."""

import unittest
from unittest.mock import patch, MagicMock
from localknowledge.ai.literature_searcher import (
    DocumentEvaluator, 
    DocumentOfInterest,
    FoundDocuments,
    search_literature
)

class TestLiteratureSearcher(unittest.TestCase):
    """Test cases for the literature_searcher module."""

    @patch('localknowledge.ai.literature_searcher.DocumentSearchManager')
    @patch('localknowledge.ai.literature_searcher.DocumentDatabaseManager')
    def test_search_literature(self, mock_db_manager, mock_search_manager):
        """Test the search_literature function."""
        # Set up mock return values
        mock_search_instance = mock_search_manager.return_value
        mock_search_instance.semantic.return_value = [
            {'id': 1, 'similarity': 0.9},
            {'id': 2, 'similarity': 0.8},
            {'id': 3, 'similarity': 0.7}
        ]
        
        # Call the function
        results = search_literature(
            question="Test question",
            max_results=3,
            similarity_threshold=0.5
        )
        
        # Verify the results
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].document_id, 1)
        self.assertEqual(results[0].similarity, 0.9)
        self.assertEqual(results[1].document_id, 2)
        self.assertEqual(results[1].similarity, 0.8)
        
        # Verify the search_manager was called correctly
        mock_search_instance.semantic.assert_called_once_with(
            question="Test question",
            similarity_threshold=0.5,
            max_results=3,
            source_name=None
        )
        
        # Verify connections were closed
        mock_search_instance.close.assert_called_once()
        mock_db_manager.return_value.close.assert_called_once()

    @patch('localknowledge.ai.literature_searcher.ollama')
    @patch('localknowledge.ai.literature_searcher.DocumentDatabaseManager')
    def test_document_evaluator(self, mock_db_manager, mock_ollama):
        """Test the DocumentEvaluator class."""
        # Set up mock return values
        mock_db_instance = mock_db_manager.return_value
        mock_db_instance.get_document.return_value = {
            'id': 1,
            'title': 'Test Document',
            'abstract': 'This is a test abstract.'
        }
        
        # Mock the ollama.generate response
        mock_response = MagicMock()
        mock_response.response = '{"rating": 2, "reason": "This is a test reason."}'
        mock_ollama.generate.return_value = mock_response
        
        # Create an evaluator and evaluate a document
        evaluator = DocumentEvaluator()
        result = evaluator.evaluate(
            question="Test question",
            document_id=1
        )
        
        # Verify the result
        self.assertEqual(result.document_id, 1)
        self.assertEqual(result.rating, 2)
        self.assertEqual(result.reason_for_rating, "This is a test reason.")
        
        # Verify the database was queried correctly
        mock_db_instance.get_document.assert_called_once_with(1)
        
        # Verify ollama.generate was called correctly
        mock_ollama.generate.assert_called_once()
        
    @patch('localknowledge.ai.literature_searcher.ollama')
    @patch('localknowledge.ai.literature_searcher.DocumentDatabaseManager')
    def test_document_evaluator_error_handling(self, mock_db_manager, mock_ollama):
        """Test error handling in the DocumentEvaluator class."""
        # Test document not found
        mock_db_instance = mock_db_manager.return_value
        mock_db_instance.get_document.return_value = None
        
        evaluator = DocumentEvaluator()
        result = evaluator.evaluate(
            question="Test question",
            document_id=999
        )
        
        # Verify the result contains error information
        self.assertEqual(result.document_id, 999)
        self.assertEqual(result.rating, 0)
        self.assertEqual(result.reason_for_rating, "Document not found in database")
        
        # Test JSON parsing error
        mock_db_instance.get_document.return_value = {
            'id': 1,
            'title': 'Test Document',
            'abstract': 'This is a test abstract.'
        }
        
        # Mock an invalid JSON response
        mock_response = MagicMock()
        mock_response.response = 'This is not valid JSON'
        mock_ollama.generate.return_value = mock_response
        
        result = evaluator.evaluate(
            question="Test question",
            document_id=1
        )
        
        # Verify the result contains error information
        self.assertEqual(result.document_id, 1)
        self.assertEqual(result.rating, 0)
        self.assertTrue("Error parsing evaluation" in result.reason_for_rating)


if __name__ == '__main__':
    unittest.main()
