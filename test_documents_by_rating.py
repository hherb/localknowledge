#!/usr/bin/env python3
"""
Test script for the documents_by_rating_for_question function.

This script demonstrates how to use the documents_by_rating_for_question function
to retrieve document IDs with specific ratings for a research question.
"""

import sys
import os
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.db.evaluations import EvaluationsDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.document import DocumentDatabaseManager


def test_documents_by_rating(
    question_id: int,
    rating: int,
    evaluator_id: Optional[int] = None
) -> None:
    """
    Test the documents_by_rating_for_question function.

    Args:
        question_id: ID of the research question
        rating: Rating value to filter by (0-5)
        evaluator_id: Optional ID of the evaluator to filter by
    """
    # Create database managers
    evaluations_db = EvaluationsDatabaseManager()
    questions_db = ResearchQuestionsManager()
    document_db = DocumentDatabaseManager()

    # Get the research question details
    question = questions_db.get_question(question_id)
    if not question:
        logger.error(f"Research question with ID {question_id} not found")
        return

    logger.info(f"Research Question: {question['question']}")

    # Get document IDs with the specified rating
    document_ids = evaluations_db.documents_by_rating_for_question(
        rating=rating,
        question_id=question_id,
        evaluator_id=evaluator_id
    )

    logger.info(f"Found {len(document_ids)} documents with rating {rating}")

    # Get document details for each ID
    for doc_id in document_ids:
        document = document_db.get_document(doc_id)
        if document:
            logger.info(f"Document ID: {doc_id}, Title: {document['title']}")
        else:
            logger.warning(f"Document with ID {doc_id} not found")


def main() -> None:
    """Main function to run the test."""
    import argparse

    parser = argparse.ArgumentParser(description='Test documents_by_rating_for_question function')
    parser.add_argument('question_id', type=int, help='ID of the research question')
    parser.add_argument('rating', type=int, choices=range(6), help='Rating value (0-5)')
    parser.add_argument('--evaluator', type=int, help='Optional evaluator ID')

    args = parser.parse_args()

    test_documents_by_rating(
        question_id=args.question_id,
        rating=args.rating,
        evaluator_id=args.evaluator
    )


if __name__ == '__main__':
    main()
