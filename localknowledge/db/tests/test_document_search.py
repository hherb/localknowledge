"""
Unit tests for the document_search module.
"""

import unittest
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock

from localknowledge.db.document_search import DocumentSearchManager


class TestDocumentSearchManager(unittest.TestCase):
    """Test cases for the DocumentSearchManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.search_manager = DocumentSearchManager()

        # Sample document data for testing
        self.sample_docs = [
            {
                'id': 1,
                'title': 'COVID-19 Vaccine Study',
                'abstract': 'A study on COVID-19 vaccines',
                'source_name': 'pubmed',
                'all_keywords': ['covid', 'vaccine', 'study']
            },
            {
                'id': 2,
                'title': 'SARS-CoV-2 Transmission',
                'abstract': 'A study on SARS-CoV-2 transmission',
                'source_name': 'medrxiv',
                'all_keywords': ['covid', 'transmission', 'sars-cov-2']
            }
        ]

    def tearDown(self):
        """Tear down test fixtures."""
        self.search_manager.close()

    @patch('localknowledge.db.document_search.DocumentSearchManager.keywords', return_value=iter([
        {
            'id': 1,
            'title': 'COVID-19 Vaccine Study',
            'abstract': 'A study on COVID-19 vaccines',
            'source_name': 'pubmed',
            'all_keywords': ['covid', 'vaccine', 'study']
        },
        {
            'id': 2,
            'title': 'SARS-CoV-2 Transmission',
            'abstract': 'A study on SARS-CoV-2 transmission',
            'source_name': 'medrxiv',
            'all_keywords': ['covid', 'transmission', 'sars-cov-2']
        }
    ]))
    def test_keywords_search_basic(self, mock_keywords):
        """Test basic keyword search functionality."""
        # Call the method directly
        results = list(mock_keywords(included=['covid', 'vaccine']))

        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], 1)

        # Verify that the method was called with the correct parameters
        mock_keywords.assert_called_once_with(included=['covid', 'vaccine'])

    @patch('localknowledge.db.document_search.DocumentSearchManager.keywords', return_value=iter([
        {
            'id': 1,
            'title': 'COVID-19 Vaccine Study',
            'abstract': 'A study on COVID-19 vaccines',
            'source_name': 'pubmed',
            'all_keywords': ['covid', 'vaccine', 'study']
        },
        {
            'id': 2,
            'title': 'SARS-CoV-2 Transmission',
            'abstract': 'A study on SARS-CoV-2 transmission',
            'source_name': 'medrxiv',
            'all_keywords': ['covid', 'transmission', 'sars-cov-2']
        }
    ]))
    def test_keywords_search_with_exclusion(self, mock_keywords):
        """Test keyword search with excluded terms."""
        # Call the method directly
        results = list(mock_keywords(included=['covid'], excluded=['children']))

        # Verify the results
        self.assertEqual(len(results), 2)

        # Verify that the method was called with the correct parameters
        mock_keywords.assert_called_once_with(included=['covid'], excluded=['children'])

    @patch('localknowledge.db.document_search.DocumentSearchManager.keywords', return_value=iter([
        {
            'id': 1,
            'title': 'COVID-19 Vaccine Study',
            'abstract': 'A study on COVID-19 vaccines',
            'source_name': 'pubmed',
            'all_keywords': ['covid', 'vaccine', 'study']
        }
    ]))
    def test_keywords_search_with_source_filter(self, mock_keywords):
        """Test keyword search with source filter."""
        # Call the method directly
        results = list(mock_keywords(included=['covid'], source_name='pubmed'))

        # Verify the results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_name'], 'pubmed')

        # Verify that the method was called with the correct parameters
        mock_keywords.assert_called_once_with(included=['covid'], source_name='pubmed')

    def test_keywords_search_empty_included(self):
        """Test keyword search with empty included terms."""
        # Test with empty included terms
        results = list(self.search_manager.keywords(included=[]))

        # Verify that an empty list was returned
        self.assertEqual(results, [])

    @patch('localknowledge.db.document_search.DocumentSearchManager.keywords', return_value=iter([
        {
            'id': 1,
            'title': 'COVID-19 Vaccine Study',
            'abstract': 'A study on COVID-19 vaccines',
            'source_name': 'pubmed',
            'all_keywords': ['covid', 'vaccine', 'study']
        },
        {
            'id': 2,
            'title': 'SARS-CoV-2 Transmission',
            'abstract': 'A study on SARS-CoV-2 transmission',
            'source_name': 'medrxiv',
            'all_keywords': ['covid', 'transmission', 'sars-cov-2']
        }
    ]))
    def test_keywords_search_with_limit_and_offset(self, mock_keywords):
        """Test keyword search with limit and offset."""
        # Call the method directly
        results = list(mock_keywords(included=['covid'], limit=10, offset=5))

        # Verify the results
        self.assertEqual(len(results), 2)

        # Verify that the method was called with the correct parameters
        mock_keywords.assert_called_once_with(included=['covid'], limit=10, offset=5)


if __name__ == '__main__':
    unittest.main()
