#!/usr/bin/env python3
"""
Unit tests for the embedding integrity verification script.

This test module verifies that the embedding integrity checker works correctly
and can identify various types of integrity issues.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the current directory to the path so we can import the script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_embedding_integrity import EmbeddingIntegrityVerifier, IntegrityIssue


class TestEmbeddingIntegrityVerifier(unittest.TestCase):
    """Test cases for the EmbeddingIntegrityVerifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the database manager to avoid actual database connections
        with patch('verify_embedding_integrity.DatabaseManager') as mock_db_class:
            self.mock_db = Mock()
            mock_db_class.return_value = self.mock_db
            self.verifier = EmbeddingIntegrityVerifier(verbose=False)
    
    def test_init(self):
        """Test verifier initialization."""
        self.assertIsNotNone(self.verifier)
        self.assertEqual(len(self.verifier.issues), 0)
        self.assertFalse(self.verifier.verbose)
    
    def test_count_embeddings(self):
        """Test counting embeddings."""
        # Mock the database response
        self.mock_db.execute.return_value = [{'count': 1000}]
        
        count = self.verifier._count_embeddings()
        
        self.assertEqual(count, 1000)
        self.mock_db.execute.assert_called_once_with("SELECT COUNT(*) as count FROM emb_1024")
    
    def test_verify_single_embedding_success(self):
        """Test successful verification of a single embedding."""
        embedding_data = {
            'embedding_id': 1,
            'chunk_id': 100,
            'model_id': 1,
            'chunk_table_id': 100,  # Chunk exists
            'text': 'This is a valid chunk text',
            'model_name': 'test-model',
            'chunktype': 'abstract',
            'chunktype_id': 1
        }
        
        result = self.verifier._verify_single_embedding(embedding_data)
        
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(len(self.verifier.issues), 0)
    
    def test_verify_single_embedding_missing_chunk(self):
        """Test verification with missing chunk."""
        embedding_data = {
            'embedding_id': 1,
            'chunk_id': 100,
            'model_id': 1,
            'chunk_table_id': None,  # Chunk doesn't exist
            'text': None,
            'model_name': 'test-model',
            'chunktype': None,
            'chunktype_id': None
        }
        
        result = self.verifier._verify_single_embedding(embedding_data)
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(self.verifier.issues), 1)
        self.assertEqual(self.verifier.issues[0].issue_type, 'missing_chunk')
        self.assertEqual(self.verifier.issues[0].severity, 'ERROR')
    
    def test_verify_single_embedding_empty_text(self):
        """Test verification with empty chunk text."""
        embedding_data = {
            'embedding_id': 1,
            'chunk_id': 100,
            'model_id': 1,
            'chunk_table_id': 100,  # Chunk exists
            'text': '',  # Empty text
            'model_name': 'test-model',
            'chunktype': 'abstract',
            'chunktype_id': 1
        }
        
        result = self.verifier._verify_single_embedding(embedding_data)
        
        self.assertEqual(result['status'], 'warning')
        self.assertEqual(len(self.verifier.issues), 1)
        self.assertEqual(self.verifier.issues[0].issue_type, 'empty_chunk_text')
        self.assertEqual(self.verifier.issues[0].severity, 'WARNING')
    
    def test_verify_single_embedding_missing_model(self):
        """Test verification with missing model."""
        embedding_data = {
            'embedding_id': 1,
            'chunk_id': 100,
            'model_id': 1,
            'chunk_table_id': 100,  # Chunk exists
            'text': 'Valid text',
            'model_name': None,  # Model doesn't exist
            'chunktype': 'abstract',
            'chunktype_id': 1
        }
        
        result = self.verifier._verify_single_embedding(embedding_data)
        
        self.assertEqual(result['status'], 'warning')
        self.assertEqual(len(self.verifier.issues), 1)
        self.assertEqual(self.verifier.issues[0].issue_type, 'missing_model')
        self.assertEqual(self.verifier.issues[0].severity, 'WARNING')
    
    def test_verify_single_embedding_missing_chunktype(self):
        """Test verification with missing chunk type."""
        embedding_data = {
            'embedding_id': 1,
            'chunk_id': 100,
            'model_id': 1,
            'chunk_table_id': 100,  # Chunk exists
            'text': 'Valid text',
            'model_name': 'test-model',
            'chunktype': None,  # Chunk type doesn't exist
            'chunktype_id': 999
        }
        
        result = self.verifier._verify_single_embedding(embedding_data)
        
        self.assertEqual(result['status'], 'warning')
        self.assertEqual(len(self.verifier.issues), 1)
        self.assertEqual(self.verifier.issues[0].issue_type, 'missing_chunktype')
        self.assertEqual(self.verifier.issues[0].severity, 'WARNING')
    
    def test_verify_embedding_batch(self):
        """Test batch verification."""
        # Mock the database response for a batch
        mock_embeddings = [
            {
                'embedding_id': 1,
                'chunk_id': 100,
                'model_id': 1,
                'chunk_table_id': 100,
                'text': 'Valid text 1',
                'model_name': 'test-model',
                'chunktype': 'abstract',
                'chunktype_id': 1
            },
            {
                'embedding_id': 2,
                'chunk_id': 200,
                'model_id': 1,
                'chunk_table_id': None,  # Missing chunk
                'text': None,
                'model_name': 'test-model',
                'chunktype': None,
                'chunktype_id': None
            }
        ]
        
        self.mock_db.execute.return_value = mock_embeddings
        
        result = self.verifier._verify_embedding_batch(0, 2)
        
        self.assertEqual(result['verified'], 1)
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['warnings'], 0)
        self.assertEqual(len(self.verifier.issues), 1)
    
    def test_export_issues_to_file(self):
        """Test exporting issues to CSV file."""
        # Add some test issues
        self.verifier.issues = [
            IntegrityIssue(
                issue_type='missing_chunk',
                embedding_id=1,
                chunk_id=100,
                model_id=1,
                description='Test issue 1',
                severity='ERROR'
            ),
            IntegrityIssue(
                issue_type='empty_chunk_text',
                embedding_id=2,
                chunk_id=200,
                model_id=1,
                description='Test issue 2',
                severity='WARNING'
            )
        ]
        
        # Mock the file operations
        with patch('builtins.open', create=True) as mock_open:
            with patch('csv.DictWriter') as mock_writer_class:
                mock_writer = Mock()
                mock_writer_class.return_value = mock_writer
                
                self.verifier.export_issues_to_file('test.csv')
                
                # Verify file was opened for writing
                mock_open.assert_called_once_with('test.csv', 'w', newline='')
                
                # Verify CSV writer was created and used
                mock_writer_class.assert_called_once()
                mock_writer.writeheader.assert_called_once()
                self.assertEqual(mock_writer.writerow.call_count, 2)


class TestIntegrityIssue(unittest.TestCase):
    """Test cases for the IntegrityIssue dataclass."""
    
    def test_create_issue(self):
        """Test creating an integrity issue."""
        issue = IntegrityIssue(
            issue_type='missing_chunk',
            embedding_id=1,
            chunk_id=100,
            model_id=1,
            description='Test description',
            severity='ERROR'
        )
        
        self.assertEqual(issue.issue_type, 'missing_chunk')
        self.assertEqual(issue.embedding_id, 1)
        self.assertEqual(issue.chunk_id, 100)
        self.assertEqual(issue.model_id, 1)
        self.assertEqual(issue.description, 'Test description')
        self.assertEqual(issue.severity, 'ERROR')


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
