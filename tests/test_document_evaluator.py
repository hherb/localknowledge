"""Unit tests for the document_evaluator module."""

import unittest
from unittest.mock import patch, MagicMock
from localknowledge.ai.document_evaluator import DocumentEvaluator, DocumentOfInterest

class TestDocumentEvaluator(unittest.TestCase):
    """Test cases for the DocumentEvaluator class."""

    @patch('localknowledge.ai.document_evaluator.ollama')
    @patch('localknowledge.ai.document_evaluator.DocumentDatabaseManager')
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
        
    @patch('localknowledge.ai.document_evaluator.ollama')
    @patch('localknowledge.ai.document_evaluator.DocumentDatabaseManager')
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

    @patch('localknowledge.ai.document_evaluator.ollama')
    @patch('localknowledge.ai.document_evaluator.DocumentDatabaseManager')
    def test_document_evaluator_fallback(self, mock_db_manager, mock_ollama):
        """Test fallback mechanism in the DocumentEvaluator class."""
        # Set up mock return values
        mock_db_instance = mock_db_manager.return_value
        mock_db_instance.get_document.return_value = {
            'id': 1,
            'title': 'Test Document',
            'abstract': 'This is a test abstract.'
        }
        
        # Mock the ollama.generate to fail on first call and succeed on second call
        mock_ollama.generate.side_effect = [
            Exception("Test error"),  # First call fails
            MagicMock(response='{"rating": 2, "reason": "This is a fallback reason."}')  # Second call succeeds
        ]
        
        # Create an evaluator and evaluate a document
        evaluator = DocumentEvaluator()
        result = evaluator.evaluate(
            question="Test question",
            document_id=1
        )
        
        # Verify the result
        self.assertEqual(result.document_id, 1)
        self.assertEqual(result.rating, 2)
        self.assertEqual(result.reason_for_rating, "This is a fallback reason.")
        
        # Verify ollama.generate was called twice
        self.assertEqual(mock_ollama.generate.call_count, 2)


if __name__ == '__main__':
    unittest.main()
