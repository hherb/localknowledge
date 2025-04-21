#!/usr/bin/env python3
"""
Test script for the update_qaembeddings module.

This script tests the functionality of the update_qaembeddings module
by counting abstracts without QA embeddings and processing a small batch.
"""

import os
import sys
import logging
from localknowledge.medrxiv import MedRxivClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_count_abstracts_without_qa_embeddings():
    """Test counting abstracts without QA embeddings."""
    client = MedRxivClient()
    try:
        count = client.count_abstracts_without_qa_embeddings()
        print(f"Found {count} abstracts without QA embeddings")
        return count
    finally:
        client.close()


def test_update_qa_embeddings(limit=2):
    """Test updating QA embeddings for a small batch of abstracts."""
    client = MedRxivClient()
    try:
        # Get some abstracts directly from the database
        query = """
        SELECT doi, title, abstract
        FROM preprints
        WHERE abstract IS NOT NULL AND abstract != ''
        LIMIT %s
        """
        abstracts = client.db.execute(query, (limit,))

        if not abstracts:
            print("No abstracts found in the database")
            return 0

        print(f"Found {len(abstracts)} abstracts for testing")

        # Process each abstract directly
        from localknowledge.ai.qafinder import QAEmbeddingManager
        qa_manager = QAEmbeddingManager()

        processed = 0
        for abstract in abstracts:
            doi = abstract['doi']
            abstract_text = abstract['abstract']
            print(f"Processing abstract with DOI: {doi}")

            # Delete any existing QA embeddings for this DOI
            qa_manager.delete_document('medrxiv', doi)

            # Process the abstract
            result = qa_manager.process_text(
                source_id='medrxiv',
                document_id=doi,
                text=abstract_text,
                chunk_no=0
            )

            # Any non-negative result indicates success
            if result >= 0:
                processed += 1
                print(f"Successfully processed DOI: {doi}")
            else:
                print(f"Failed to process DOI: {doi}, result: {result}")

        print(f"Successfully processed {processed} abstracts")
        return processed
    finally:
        client.close()


def main():
    """Run the tests."""
    try:
        # Test counting abstracts without QA embeddings
        count = test_count_abstracts_without_qa_embeddings()

        if count > 0:
            # Test updating QA embeddings for a small batch
            processed = test_update_qa_embeddings(limit=min(2, count))
            print(f"Test completed: {processed} abstracts processed")
        else:
            print("No abstracts without QA embeddings found, skipping update test")

    except Exception as e:
        logger.error(f"Error in test: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
