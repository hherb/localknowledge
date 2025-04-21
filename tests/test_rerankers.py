"""
Unit tests for the rerankers module.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.ai.rerankers import (
    get_available_rerankers,
    get_reranker,
    CrossEncoderReranker
)


class TestRerankers(unittest.TestCase):
    """Test the rerankers module."""

    def test_get_available_rerankers(self):
        """Test that get_available_rerankers returns a list of rerankers."""
        rerankers = get_available_rerankers()
        self.assertIsInstance(rerankers, list)
        self.assertTrue(len(rerankers) > 0)
        
        # Check that each reranker has the required fields
        for reranker in rerankers:
            self.assertIn('id', reranker)
            self.assertIn('name', reranker)
            self.assertIn('description', reranker)
    
    def test_get_reranker(self):
        """Test that get_reranker returns a reranker instance."""
        # Test with a valid model name
        reranker = get_reranker("BAAI/bge-reranker-base")
        self.assertIsNotNone(reranker)
        self.assertIsInstance(reranker, CrossEncoderReranker)
        
        # Test with an invalid model name
        reranker = get_reranker("invalid-model-name")
        self.assertIsNone(reranker)
    
    @patch('localknowledge.ai.rerankers.CrossEncoder')
    def test_cross_encoder_reranker(self, mock_cross_encoder):
        """Test the CrossEncoderReranker class."""
        # Mock the CrossEncoder class
        mock_instance = MagicMock()
        mock_instance.predict.return_value = [0.8, 0.6, 0.9]
        mock_cross_encoder.return_value = mock_instance
        
        # Create a reranker
        reranker = CrossEncoderReranker("BAAI/bge-reranker-base")
        
        # Test reranking
        documents = [
            {'text': 'Document 1', 'similarity': 0.7},
            {'text': 'Document 2', 'similarity': 0.5},
            {'text': 'Document 3', 'similarity': 0.6}
        ]
        
        reranked_docs = reranker.rerank("test query", documents)
        
        # Check that the documents were reranked
        self.assertEqual(len(reranked_docs), 3)
        
        # Check that the documents are sorted by the new scores
        self.assertEqual(reranked_docs[0]['text'], 'Document 3')  # Score 0.9
        self.assertEqual(reranked_docs[1]['text'], 'Document 1')  # Score 0.8
        self.assertEqual(reranked_docs[2]['text'], 'Document 2')  # Score 0.6
        
        # Check that the original similarity scores were preserved
        self.assertEqual(reranked_docs[0]['original_similarity'], 0.6)
        self.assertEqual(reranked_docs[1]['original_similarity'], 0.7)
        self.assertEqual(reranked_docs[2]['original_similarity'], 0.5)
        
        # Check that the new similarity scores were set
        self.assertEqual(reranked_docs[0]['similarity'], 0.9)
        self.assertEqual(reranked_docs[1]['similarity'], 0.8)
        self.assertEqual(reranked_docs[2]['similarity'], 0.6)
        
        # Check that the reranked flag was set
        self.assertTrue(reranked_docs[0]['reranked'])
        self.assertTrue(reranked_docs[1]['reranked'])
        self.assertTrue(reranked_docs[2]['reranked'])


if __name__ == '__main__':
    unittest.main()
