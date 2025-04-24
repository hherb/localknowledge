#!/usr/bin/env python3
"""
Test script for the updated MedRxiv database module.

This script tests the basic operations of the MedRxiv database module
to ensure it works correctly with the new document-centric structure.
"""

import sys
import logging
from datetime import datetime

from localknowledge.db.medrxiv import MedRxivDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set specific loggers to DEBUG level
logging.getLogger('localknowledge.db.document').setLevel(logging.DEBUG)
logging.getLogger('localknowledge.db.medrxiv').setLevel(logging.DEBUG)
logging.getLogger('localknowledge.db.base').setLevel(logging.DEBUG)

def test_store_preprint():
    """Test storing a preprint in the document table."""
    logger.info("Testing store_preprint...")

    # Create a test preprint
    test_preprint = {
        'doi': 'test.doi/12345',
        'title': 'Test Preprint Title',
        'abstract': 'This is a test abstract for testing the MedRxiv module.',
        'authors': 'John Doe, Jane Smith',
        'date_posted': datetime.now().date(),  # Use a proper date object
        'category': 'Test Category',
        'pdf_url': 'https://example.com/test.pdf',
        'local_pdf_path': 'test.pdf',
        'full_text': 'This is the full text of the test preprint.'
    }

    # Store the preprint
    try:
        db = MedRxivDatabaseManager()
        logger.info(f"MedRxiv source ID: {db.source_id}")
        document_id = db.store_preprint(test_preprint)

        if document_id:
            logger.info(f"Successfully stored test preprint with document ID: {document_id}")
            return document_id
        else:
            logger.error("Failed to store test preprint")
            return None
    except Exception as e:
        logger.error(f"Exception while storing preprint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def test_get_preprint(doi):
    """Test retrieving a preprint by DOI."""
    logger.info(f"Testing get_preprint_by_doi with DOI: {doi}...")

    db = MedRxivDatabaseManager()
    preprint = db.get_preprint_by_doi(doi)

    if preprint:
        logger.info(f"Successfully retrieved preprint: {preprint['title']}")
        logger.info(f"Document ID: {preprint['id']}")
        logger.info(f"Source: {preprint['source_name']}")
        logger.info(f"Abstract: {preprint['abstract'][:50]}...")
        return preprint
    else:
        logger.error(f"Failed to retrieve preprint with DOI: {doi}")
        return None

def test_search_preprints(search_text):
    """Test searching for preprints."""
    logger.info(f"Testing search_preprints with query: {search_text}...")

    db = MedRxivDatabaseManager()
    results = db.search_preprints(search_text=search_text, max_results=5)

    if results:
        logger.info(f"Found {len(results)} preprints matching the query")
        for i, result in enumerate(results):
            logger.info(f"Result {i+1}: {result['title']}")
        return results
    else:
        logger.info("No preprints found matching the query")
        return []

def test_update_pdf_path(doi, pdf_path):
    """Test updating the PDF path for a preprint."""
    logger.info(f"Testing update_pdf_path for DOI: {doi}...")

    db = MedRxivDatabaseManager()
    success = db.update_pdf_path(doi, pdf_path, "Updated full text")

    if success:
        logger.info(f"Successfully updated PDF path for DOI: {doi}")
        # Verify the update
        preprint = db.get_preprint_by_doi(doi)
        if preprint and preprint['pdf_filename'] == pdf_path:
            logger.info("Verified PDF path was updated correctly")
            return True
        else:
            logger.error("PDF path was not updated correctly")
            return False
    else:
        logger.error(f"Failed to update PDF path for DOI: {doi}")
        return False

def test_get_preprints_without_pdfs():
    """Test getting preprints without PDFs."""
    logger.info("Testing get_preprints_without_pdfs...")

    db = MedRxivDatabaseManager()
    preprints = db.get_preprints_without_pdfs(limit=5)

    if preprints:
        logger.info(f"Found {len(preprints)} preprints without PDFs")
        for i, preprint in enumerate(preprints):
            logger.info(f"Preprint {i+1}: {preprint['title']}")
        return preprints
    else:
        logger.info("No preprints found without PDFs")
        return []

def main():
    """Run all tests."""
    try:
        # Test storing a preprint
        document_id = test_store_preprint()
        if not document_id:
            logger.error("Test failed: Could not store preprint")
            return 1

        # Test retrieving the preprint
        test_doi = 'test.doi/12345'
        preprint = test_get_preprint(test_doi)
        if not preprint:
            logger.error("Test failed: Could not retrieve preprint")
            return 1

        # Test updating the PDF path
        updated = test_update_pdf_path(test_doi, 'updated_test.pdf')
        if not updated:
            logger.error("Test failed: Could not update PDF path")
            return 1

        # Test searching for preprints
        results = test_search_preprints('test')

        # Test getting preprints without PDFs
        preprints_without_pdfs = test_get_preprints_without_pdfs()

        logger.info("All tests completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
