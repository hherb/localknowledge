#!/usr/bin/env python3
"""
Unit tests for the medrxiv abstract embedding module.
"""

import unittest
from unittest.mock import patch, MagicMock

from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder


class TestMedrxivAbstractEmbedder(unittest.TestCase):
    """Test cases for the MedrxivAbstractEmbedder class."""

    @patch('localknowledge.medrxiv.embed_abstracts.MedRxivDatabaseManager')
    @patch('localknowledge.medrxiv.embed_abstracts.EmbeddingDatabaseManager')
    @patch('localknowledge.medrxiv.embed_abstracts.EmbeddingManager')
    def setUp(self, mock_embedding_manager, mock_embedding_db, mock_medrxiv_db):
        """Set up test fixtures."""
        self.mock_medrxiv_db = mock_medrxiv_db.return_value
        self.mock_embedding_db = mock_embedding_db.return_value
        self.mock_embedding_manager = mock_embedding_manager.return_value
        
        self.embedder = MedrxivAbstractEmbedder()

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.embedder)
        self.assertEqual(self.embedder.medrxiv_db, self.mock_medrxiv_db)
        self.assertEqual(self.embedder.embedding_db, self.mock_embedding_db)
        self.assertEqual(self.embedder.embedding_manager, self.mock_embedding_manager)

    def test_close(self):
        """Test close method."""
        self.embedder.close()
        self.mock_medrxiv_db.close.assert_called_once()
        self.mock_embedding_db.close.assert_called_once()
        self.mock_embedding_manager.close.assert_called_once()

    def test_count_abstracts_without_embeddings(self):
        """Test counting abstracts without embeddings."""
        # Mock the database query result
        self.mock_medrxiv_db.execute.return_value = [{'count': 42}]
        
        # Call the method
        count = self.embedder.count_abstracts_without_embeddings()
        
        # Verify the result
        self.assertEqual(count, 42)
        self.mock_medrxiv_db.execute.assert_called_once()

    def test_get_abstracts_without_embeddings(self):
        """Test getting abstracts without embeddings."""
        # Mock data
        mock_abstracts = [
            {'doi': 'doi1', 'title': 'Title 1', 'abstract': 'Abstract 1'},
            {'doi': 'doi2', 'title': 'Title 2', 'abstract': 'Abstract 2'},
            {'doi': 'doi3', 'title': 'Title 3', 'abstract': 'Abstract 3'}
        ]
        
        # Mock the database query results
        self.mock_medrxiv_db.execute.return_value = mock_abstracts
        
        # Mock the embedding database to return embeddings for doi2 only
        def mock_get_embeddings(source_id, document_id):
            if document_id == 'doi2':
                return [{'id': 1}]  # Return some data for doi2
            return []  # Return empty for others
            
        self.mock_embedding_db.get_document_embeddings.side_effect = mock_get_embeddings
        
        # Call the method
        abstracts = self.embedder.get_abstracts_without_embeddings()
        
        # Verify the results
        self.assertEqual(len(abstracts), 2)  # Should only return doi1 and doi3
        self.assertEqual(abstracts[0]['doi'], 'doi1')
        self.assertEqual(abstracts[1]['doi'], 'doi3')
        
        # Verify the database calls
        self.mock_medrxiv_db.execute.assert_called_once()
        self.assertEqual(self.mock_embedding_db.get_document_embeddings.call_count, 3)

    @patch('localknowledge.medrxiv.embed_abstracts.tqdm')
    def test_embed_abstracts(self, mock_tqdm):
        """Test embedding abstracts."""
        # Mock data
        mock_abstracts = [
            {'doi': 'doi1', 'title': 'Title 1', 'abstract': 'Abstract 1'},
            {'doi': 'doi2', 'title': 'Title 2', 'abstract': 'Abstract 2'}
        ]
        
        # Mock the get_abstracts_without_embeddings method
        self.embedder.get_abstracts_without_embeddings = MagicMock(return_value=mock_abstracts)
        
        # Mock the tqdm iterator
        mock_tqdm.return_value = mock_abstracts
        
        # Mock the process_document method to return 1 chunk for each abstract
        self.mock_embedding_manager.process_document.return_value = 1
        
        # Call the method
        result = self.embedder.embed_abstracts(batch_size=1)
        
        # Verify the result
        self.assertEqual(result, 2)  # Should have embedded 2 abstracts
        
        # Verify the method calls
        self.embedder.get_abstracts_without_embeddings.assert_called_once()
        self.assertEqual(self.mock_embedding_manager.process_document.call_count, 2)
        
        # Verify the process_document calls
        calls = self.mock_embedding_manager.process_document.call_args_list
        self.assertEqual(calls[0][1]['source_id'], 'medrxiv')
        self.assertEqual(calls[0][1]['document_id'], 'doi1')
        self.assertEqual(calls[0][1]['text'], 'Abstract 1')
        self.assertEqual(calls[1][1]['source_id'], 'medrxiv')
        self.assertEqual(calls[1][1]['document_id'], 'doi2')
        self.assertEqual(calls[1][1]['text'], 'Abstract 2')


if __name__ == '__main__':
    unittest.main()
