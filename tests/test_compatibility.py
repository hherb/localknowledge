#!/usr/bin/env python3
"""
Test the compatibility layer for the unified document structure.

This script tests that the compatibility layer correctly provides access to
documents in the new unified document structure using the original API.
"""

import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.db.compatibility import MedRxivCompatibilityAdapter, PubMedCompatibilityAdapter
from localknowledge.db.document import DocumentDatabaseManager


class TestCompatibilityLayer(unittest.TestCase):
    """Test the compatibility layer for the unified document structure."""

    def setUp(self):
        """Set up the test environment."""
        self.document_db = DocumentDatabaseManager()
        self.medrxiv_adapter = MedRxivCompatibilityAdapter()
        self.pubmed_adapter = PubMedCompatibilityAdapter()

    def test_medrxiv_get_preprint(self):
        """Test getting a preprint through the compatibility layer."""
        # Get a sample DOI from the document table
        query = """
        SELECT d.external_id
        FROM document d
        JOIN sources s ON d.source_id = s.id
        WHERE s.name = 'medrxiv'
        LIMIT 1
        """
        result = self.document_db.execute(query)
        
        if not result:
            self.skipTest("No medrxiv documents found in the database")
            return
        
        doi = result[0]['external_id']
        
        # Get the preprint through the compatibility layer
        preprint = self.medrxiv_adapter.get_preprint_by_doi(doi)
        
        # Verify that the preprint was retrieved
        self.assertIsNotNone(preprint)
        self.assertEqual(preprint['doi'], doi)
        self.assertIn('title', preprint)
        self.assertIn('abstract', preprint)

    def test_medrxiv_search(self):
        """Test searching preprints through the compatibility layer."""
        # Search for preprints
        preprints = self.medrxiv_adapter.search_preprints("covid", limit=5)
        
        # Verify that preprints were found
        self.assertIsInstance(preprints, list)
        if preprints:
            self.assertIn('doi', preprints[0])
            self.assertIn('title', preprints[0])
            self.assertIn('abstract', preprints[0])

    def test_pubmed_get_article(self):
        """Test getting a PubMed article through the compatibility layer."""
        # Get a sample PMID from the document table
        query = """
        SELECT d.external_id
        FROM document d
        JOIN sources s ON d.source_id = s.id
        WHERE s.name = 'pubmed'
        LIMIT 1
        """
        result = self.document_db.execute(query)
        
        if not result:
            self.skipTest("No pubmed documents found in the database")
            return
        
        pmid = result[0]['external_id']
        
        # Get the article through the compatibility layer
        article = self.pubmed_adapter.get_article_by_pmid(pmid)
        
        # Verify that the article was retrieved
        self.assertIsNotNone(article)
        self.assertEqual(article['pmid'], pmid)
        self.assertIn('title', article)
        self.assertIn('abstract', article)

    def test_pubmed_search(self):
        """Test searching PubMed articles through the compatibility layer."""
        # Search for articles
        articles = self.pubmed_adapter.search_articles("cancer", limit=5)
        
        # Verify that articles were found
        self.assertIsInstance(articles, list)
        if articles:
            self.assertIn('pmid', articles[0])
            self.assertIn('title', articles[0])
            self.assertIn('abstract', articles[0])

    def test_recent_preprints(self):
        """Test getting recent preprints through the compatibility layer."""
        # Get recent preprints
        preprints = self.medrxiv_adapter.get_recent_preprints(limit=5)
        
        # Verify that preprints were found
        self.assertIsInstance(preprints, list)
        if preprints:
            self.assertIn('doi', preprints[0])
            self.assertIn('title', preprints[0])
            self.assertIn('abstract', preprints[0])

    def test_recent_articles(self):
        """Test getting recent PubMed articles through the compatibility layer."""
        # Get recent articles
        articles = self.pubmed_adapter.get_recent_articles(limit=5)
        
        # Verify that articles were found
        self.assertIsInstance(articles, list)
        if articles:
            self.assertIn('pmid', articles[0])
            self.assertIn('title', articles[0])
            self.assertIn('abstract', articles[0])


if __name__ == "__main__":
    unittest.main()
