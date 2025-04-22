#!/usr/bin/env python3
"""
Test the unified document access module.

This script tests the DocumentClient class for accessing documents from
different sources using the new unified document structure.
"""

import unittest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.document import DocumentClient, Document


class TestDocumentClient(unittest.TestCase):
    """Test the DocumentClient class."""

    def setUp(self):
        """Set up the test environment."""
        self.client = DocumentClient()

    def tearDown(self):
        """Clean up after the test."""
        self.client.close()

    def test_get_document(self):
        """Test getting a document by source and external ID."""
        # Get a sample document from the database
        query = """
        SELECT s.name as source_name, d.external_id
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LIMIT 1
        """
        result = self.client.document_db.execute(query)
        
        if not result:
            self.skipTest("No documents found in the database")
            return
        
        source = result[0]['source_name']
        external_id = result[0]['external_id']
        
        # Get the document
        doc = self.client.get_document(source, external_id)
        
        # Verify that the document was retrieved
        self.assertIsNotNone(doc)
        self.assertEqual(doc.source, source)
        self.assertEqual(doc.external_id, external_id)
        self.assertIsNotNone(doc.title)

    def test_search(self):
        """Test searching for documents."""
        # Search for documents
        results = self.client.search("covid", max_results=5)
        
        # Verify that documents were found
        self.assertIsInstance(results, list)
        if results:
            self.assertIsInstance(results[0], Document)
            self.assertIsNotNone(results[0].title)
            self.assertIsNotNone(results[0].source)

    def test_search_with_sources(self):
        """Test searching for documents with specific sources."""
        # Search for documents from a specific source
        results = self.client.search("covid", max_results=5, sources=["medrxiv"])
        
        # Verify that documents were found
        self.assertIsInstance(results, list)
        if results:
            self.assertIsInstance(results[0], Document)
            self.assertEqual(results[0].source, "medrxiv")

    def test_get_recent_documents(self):
        """Test getting recent documents."""
        # Get recent documents
        results = self.client.get_recent_documents(max_results=5, days=365)
        
        # Verify that documents were found
        self.assertIsInstance(results, list)
        if results:
            self.assertIsInstance(results[0], Document)
            self.assertIsNotNone(results[0].title)
            self.assertIsNotNone(results[0].publication_date)
            
            # Verify that the documents are recent
            one_year_ago = datetime.now() - timedelta(days=365)
            self.assertGreaterEqual(results[0].publication_date, one_year_ago)

    def test_document_to_dict(self):
        """Test converting a document to a dictionary."""
        # Get a sample document
        query = """
        SELECT s.name as source_name, d.external_id
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LIMIT 1
        """
        result = self.client.document_db.execute(query)
        
        if not result:
            self.skipTest("No documents found in the database")
            return
        
        source = result[0]['source_name']
        external_id = result[0]['external_id']
        
        # Get the document
        doc = self.client.get_document(source, external_id)
        
        # Convert to dictionary
        doc_dict = doc.to_dict()
        
        # Verify the dictionary
        self.assertIsInstance(doc_dict, dict)
        self.assertEqual(doc_dict['source'], source)
        self.assertEqual(doc_dict['external_id'], external_id)
        self.assertEqual(doc_dict['title'], doc.title)


if __name__ == "__main__":
    unittest.main()
