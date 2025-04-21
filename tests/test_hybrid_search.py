"""
Unit tests for the hybrid search functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.ui.knowledgebrowser import HybridSearchWorker


class TestHybridSearch(unittest.TestCase):
    """Test the hybrid search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.db_manager = MagicMock()
        self.embedding_manager = MagicMock()
        self.search_settings = {
            'similarity_threshold': 0.3,
            'max_results': 20,
            'use_reranker': False,
            'hybrid_weight': 0.5
        }

    def test_combine_results(self):
        """Test the _combine_results method."""
        # Create a worker
        worker = HybridSearchWorker(
            db_manager=self.db_manager,
            embedding_manager=self.embedding_manager,
            query="test query",
            search_settings=self.search_settings
        )

        # Create test data
        keyword_results = [
            {'doi': '10.1101/2021.01.01.123456', 'title': 'Paper 1', 'date': '2021-01-01', 'search_source': 'keyword'},
            {'doi': '10.1101/2021.02.02.123457', 'title': 'Paper 2', 'date': '2021-02-02', 'search_source': 'keyword'},
            {'doi': '10.1101/2021.03.03.123458', 'title': 'Paper 3', 'date': '2021-03-03', 'search_source': 'keyword'}
        ]

        semantic_results = [
            {'doi': '10.1101/2021.01.01.123456', 'title': 'Paper 1', 'date': '2021-01-01',
             'similarity': '85.0%', 'similarity_value': 0.85, 'matched_text': 'Some text', 'search_source': 'semantic'},
            {'doi': '10.1101/2021.04.04.123459', 'title': 'Paper 4', 'date': '2021-04-04',
             'similarity': '75.0%', 'similarity_value': 0.75, 'matched_text': 'Some text', 'search_source': 'semantic'}
        ]

        # Call the method
        combined_results = worker._combine_results(keyword_results, semantic_results)

        # Check that we have the expected number of results
        self.assertEqual(len(combined_results), 4)

        # Check that duplicates were merged
        paper1 = next((p for p in combined_results if p['doi'] == '10.1101/2021.01.01.123456'), None)
        self.assertIsNotNone(paper1)
        self.assertEqual(paper1['search_source'], 'both')
        self.assertEqual(paper1['similarity'], '85.0%')
        self.assertEqual(paper1['similarity_value'], 0.85)
        self.assertEqual(paper1['matched_text'], 'Some text')

        # Check that unique results were preserved
        paper2 = next((p for p in combined_results if p['doi'] == '10.1101/2021.02.02.123457'), None)
        self.assertIsNotNone(paper2)
        self.assertEqual(paper2['search_source'], 'keyword')

        paper4 = next((p for p in combined_results if p['doi'] == '10.1101/2021.04.04.123459'), None)
        self.assertIsNotNone(paper4)
        self.assertEqual(paper4['search_source'], 'semantic')
        self.assertEqual(paper4['similarity'], '75.0%')

    def test_sort_order_with_hybrid_weight(self):
        """Test that results are sorted correctly based on hybrid weight."""
        # Create workers with different hybrid weights
        worker_semantic = HybridSearchWorker(
            db_manager=self.db_manager,
            embedding_manager=self.embedding_manager,
            query="test query",
            search_settings={'hybrid_weight': 0.9}  # Heavily favor semantic
        )

        worker_keyword = HybridSearchWorker(
            db_manager=self.db_manager,
            embedding_manager=self.embedding_manager,
            query="test query",
            search_settings={'hybrid_weight': 0.1}  # Heavily favor keyword
        )

        # Create test data
        keyword_results = [
            {'doi': 'keyword_only', 'title': 'Keyword Only', 'date': '2021-01-01', 'search_source': 'keyword'},
        ]

        semantic_results = [
            {'doi': 'semantic_only', 'title': 'Semantic Only', 'date': '2021-01-01',
             'similarity': '60.0%', 'similarity_value': 0.6, 'matched_text': 'Some text', 'search_source': 'semantic'},
        ]

        # Test with semantic weight
        semantic_combined = worker_semantic._combine_results(keyword_results, semantic_results)

        # With high semantic weight, semantic result should come first
        self.assertEqual(semantic_combined[0]['doi'], 'semantic_only')
        self.assertEqual(semantic_combined[1]['doi'], 'keyword_only')

        # Test with keyword weight
        keyword_combined = worker_keyword._combine_results(keyword_results, semantic_results)

        # With high keyword weight, keyword result should come first
        self.assertEqual(keyword_combined[0]['doi'], 'keyword_only')
        self.assertEqual(keyword_combined[1]['doi'], 'semantic_only')

    @patch('localknowledge.ai.rerankers.get_reranker')
    def test_reranking(self, mock_get_reranker):
        """Test that reranking is applied correctly."""
        # Mock the reranker
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            {'doi': 'reranked1', 'similarity': '95.0%', 'similarity_value': 0.95, 'reranked': True},
            {'doi': 'reranked2', 'similarity': '85.0%', 'similarity_value': 0.85, 'reranked': True}
        ]
        mock_get_reranker.return_value = mock_reranker

        # Create a worker with reranking enabled
        worker = HybridSearchWorker(
            db_manager=self.db_manager,
            embedding_manager=self.embedding_manager,
            query="test query",
            search_settings={
                'use_reranker': True,
                'reranker_model': 'test-model'
            }
        )

        # Mock the run method to test reranking
        with patch.object(worker, '_combine_results') as mock_combine:
            mock_combine.return_value = [
                {'doi': 'original1', 'similarity': '70.0%', 'similarity_value': 0.7},
                {'doi': 'original2', 'similarity': '60.0%', 'similarity_value': 0.6}
            ]

            # Mock the RERANKERS_AVAILABLE global
            with patch('localknowledge.ui.knowledgebrowser.RERANKERS_AVAILABLE', True):
                # Call the run method
                worker.signals = MagicMock()
                worker.run()

                # Check that reranking was called
                mock_get_reranker.assert_called_once_with('test-model')
                mock_reranker.rerank.assert_called_once()

                # Check that the reranked results were emitted
                args, _ = worker.signals.result.emit.call_args
                result = args[0]
                self.assertTrue(result['reranked'])
                self.assertEqual(result['combined_results'][0]['doi'], 'reranked1')
                self.assertEqual(result['combined_results'][1]['doi'], 'reranked2')


if __name__ == '__main__':
    unittest.main()
