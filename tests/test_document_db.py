#!/usr/bin/env python3
"""
Unit tests for the unified document database manager.

These tests verify that the DocumentDatabaseManager correctly handles
document operations across different data sources.
"""

import unittest
import os
import sys
from datetime import datetime, date
from pathlib import Path
import random
import string

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.db.document import DocumentDatabaseManager


class TestDocumentDatabaseManager(unittest.TestCase):
    """Test cases for the DocumentDatabaseManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = DocumentDatabaseManager()
        
        # Create tables if they don't exist
        self.db.create_tables()
        self.db.create_indices()
        
        # Start a transaction that we'll roll back at the end
        self.db.begin_transaction()
        
        # Generate random test data
        self.test_data = self._generate_test_data()

    def tearDown(self):
        """Tear down test fixtures."""
        # Roll back the transaction to avoid affecting other tests
        self.db.rollback_transaction()
        self.db.close()

    def _generate_test_data(self):
        """Generate random test data."""
        # Generate a random string to ensure uniqueness
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        return {
            'medrxiv': {
                'source_name': 'medrxiv',
                'external_id': f'10.1101/2023.test.{random_str}',
                'doi': f'10.1101/2023.test.{random_str}',
                'title': f'Test MedRxiv Preprint {random_str}',
                'abstract': f'This is a test abstract for a MedRxiv preprint {random_str}.',
                'category_name': 'Infectious Diseases',
                'keywords': ['covid-19', 'test', 'preprint'],
                'authors': ['John Doe', 'Jane Smith'],
                'publication_date': '2023-01-15',
                'pdf_url': f'https://www.medrxiv.org/content/10.1101/2023.test.{random_str}.pdf',
                'pdf_filename': f'/path/to/pdfs/medrxiv/2023.test.{random_str}.pdf'
            },
            'pubmed': {
                'source_name': 'pubmed',
                'external_id': f'PMC{random_str}',
                'doi': f'10.1016/j.test.2023.{random_str}',
                'title': f'Test PubMed Article {random_str}',
                'abstract': f'This is a test abstract for a PubMed article {random_str}.',
                'mesh_terms': ['Humans', 'Male', 'Female', 'Adult'],
                'keywords': ['research', 'medicine', 'test'],
                'authors': ['Robert Johnson', 'Susan Williams'],
                'publication': 'Journal of Test Medicine',
                'publication_date': '2023-02-20',
                'pdf_filename': f'/path/to/pdfs/pubmed/PMC{random_str}.pdf'
            }
        }

    def test_add_document(self):
        """Test adding documents to the database."""
        # Add MedRxiv document
        medrxiv_id = self.db.add_document(self.test_data['medrxiv'])
        self.assertIsNotNone(medrxiv_id, "Failed to add MedRxiv document")
        
        # Add PubMed document
        pubmed_id = self.db.add_document(self.test_data['pubmed'])
        self.assertIsNotNone(pubmed_id, "Failed to add PubMed document")
        
        # Verify documents were added
        medrxiv_doc = self.db.get_document_by_external_id(
            'medrxiv', 
            self.test_data['medrxiv']['external_id']
        )
        self.assertIsNotNone(medrxiv_doc, "Failed to retrieve MedRxiv document")
        self.assertEqual(
            medrxiv_doc['title'], 
            self.test_data['medrxiv']['title'], 
            "MedRxiv document title mismatch"
        )
        
        pubmed_doc = self.db.get_document_by_external_id(
            'pubmed', 
            self.test_data['pubmed']['external_id']
        )
        self.assertIsNotNone(pubmed_doc, "Failed to retrieve PubMed document")
        self.assertEqual(
            pubmed_doc['title'], 
            self.test_data['pubmed']['title'], 
            "PubMed document title mismatch"
        )

    def test_get_document_by_doi(self):
        """Test retrieving a document by DOI."""
        # Add a document
        doc_id = self.db.add_document(self.test_data['medrxiv'])
        self.assertIsNotNone(doc_id, "Failed to add document")
        
        # Retrieve by DOI
        doc = self.db.get_document_by_doi(self.test_data['medrxiv']['doi'])
        self.assertIsNotNone(doc, "Failed to retrieve document by DOI")
        self.assertEqual(
            doc['title'], 
            self.test_data['medrxiv']['title'], 
            "Document title mismatch"
        )

    def test_search_documents(self):
        """Test searching for documents."""
        # Add documents
        self.db.add_document(self.test_data['medrxiv'])
        self.db.add_document(self.test_data['pubmed'])
        
        # Search for a unique term in the MedRxiv document
        unique_term = self.test_data['medrxiv']['title'].split()[-1]
        results = self.db.search_documents(unique_term)
        self.assertEqual(len(results), 1, "Expected exactly one search result")
        self.assertEqual(
            results[0]['title'], 
            self.test_data['medrxiv']['title'], 
            "Search result title mismatch"
        )
        
        # Search with source filter
        results = self.db.search_documents(
            'test', 
            source_name='pubmed'
        )
        self.assertGreaterEqual(len(results), 1, "Expected at least one search result")
        for result in results:
            self.assertEqual(
                result['source_name'], 
                'pubmed', 
                "Search result source mismatch"
            )

    def test_get_recent_documents(self):
        """Test retrieving recent documents."""
        # Add documents
        self.db.add_document(self.test_data['medrxiv'])
        self.db.add_document(self.test_data['pubmed'])
        
        # Get recent documents
        results = self.db.get_recent_documents(limit=10)
        self.assertGreaterEqual(len(results), 2, "Expected at least two recent documents")
        
        # Get recent documents with source filter
        results = self.db.get_recent_documents(
            limit=10, 
            source_name='medrxiv'
        )
        self.assertGreaterEqual(len(results), 1, "Expected at least one recent MedRxiv document")
        for result in results:
            self.assertEqual(
                result['source_name'], 
                'medrxiv', 
                "Recent document source mismatch"
            )

    def test_mark_document_withdrawn(self):
        """Test marking a document as withdrawn."""
        # Add a document
        self.db.add_document(self.test_data['medrxiv'])
        
        # Mark as withdrawn
        reason = "Test withdrawal reason"
        success = self.db.mark_document_withdrawn(
            'medrxiv', 
            self.test_data['medrxiv']['external_id'], 
            reason
        )
        self.assertTrue(success, "Failed to mark document as withdrawn")
        
        # Verify document is marked as withdrawn
        doc = self.db.get_document_by_external_id(
            'medrxiv', 
            self.test_data['medrxiv']['external_id']
        )
        self.assertIsNotNone(doc, "Failed to retrieve document")
        self.assertIsNotNone(doc['withdrawn_date'], "Document not marked as withdrawn")
        self.assertEqual(doc['withdrawn_reason'], reason, "Withdrawal reason mismatch")

    def test_add_and_get_tags(self):
        """Test adding and retrieving tags."""
        # Add a document
        self.db.add_document(self.test_data['medrxiv'])
        
        # Add tags
        user_id = 1
        tag1 = "important"
        tag2 = "follow-up"
        
        success1 = self.db.add_tag(
            'medrxiv', 
            self.test_data['medrxiv']['external_id'], 
            user_id, 
            tag1
        )
        self.assertTrue(success1, "Failed to add first tag")
        
        success2 = self.db.add_tag(
            'medrxiv', 
            self.test_data['medrxiv']['external_id'], 
            user_id, 
            tag2
        )
        self.assertTrue(success2, "Failed to add second tag")
        
        # Get tags
        tags = self.db.get_document_tags(
            'medrxiv', 
            self.test_data['medrxiv']['external_id'], 
            user_id
        )
        self.assertEqual(len(tags), 2, "Expected exactly two tags")
        tag_texts = [tag['tag'] for tag in tags]
        self.assertIn(tag1, tag_texts, "First tag not found")
        self.assertIn(tag2, tag_texts, "Second tag not found")
        
        # Remove a tag
        tag_id = tags[0]['id']
        success = self.db.remove_tag(tag_id)
        self.assertTrue(success, "Failed to remove tag")
        
        # Verify tag was removed
        tags = self.db.get_document_tags(
            'medrxiv', 
            self.test_data['medrxiv']['external_id'], 
            user_id
        )
        self.assertEqual(len(tags), 1, "Expected exactly one tag after removal")


if __name__ == '__main__':
    unittest.main()
