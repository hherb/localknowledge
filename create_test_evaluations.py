#!/usr/bin/env python3
"""
Script to create test evaluations in the database.

This script creates sample evaluations for testing the evaluations database manager.
"""

import sys
import os
import logging
import random
from typing import List, Dict, Any

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
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.db.base import DatabaseManager


def get_or_create_evaluator(db: DatabaseManager, name: str, is_human: bool = True, user_id: int = None) -> int:
    """
    Get or create an evaluator.

    Args:
        db: Database manager
        name: Name of the evaluator
        is_human: Whether the evaluator is human
        user_id: User ID if the evaluator is human

    Returns:
        Evaluator ID
    """
    # Check if evaluator exists
    result = db.execute("SELECT id FROM evaluators WHERE name = %s", (name,))
    if result and len(result) > 0:
        return result[0]['id']

    # Create evaluator - user_id being NULL indicates a non-human evaluator
    result = db.execute(
        "INSERT INTO evaluators (name, user_id, model_id) VALUES (%s, %s, %s) RETURNING id",
        (name, user_id if is_human else None, None if is_human else "test-model"),
        commit=True
    )

    if result and len(result) > 0:
        return result[0]['id']

    raise ValueError(f"Failed to create evaluator: {name}")


def create_test_evaluations(
    question_id: int,
    num_documents: int = 5,
    num_chunks_per_document: int = 3,
    num_evaluators: int = 2
) -> None:
    """
    Create test evaluations for a research question.

    Args:
        question_id: ID of the research question
        num_documents: Number of documents to create evaluations for
        num_chunks_per_document: Number of chunks per document
        num_evaluators: Number of evaluators to create
    """
    # Create database managers
    db = DatabaseManager()
    evaluations_db = EvaluationsDatabaseManager()
    questions_db = ResearchQuestionsManager()
    document_db = DocumentDatabaseManager()
    chunking_db = ChunkingDatabaseManager()

    # Get the research question
    question = questions_db.get_question(question_id)
    if not question:
        logger.error(f"Research question with ID {question_id} not found")
        return

    logger.info(f"Creating test evaluations for question: {question['question']}")

    # Get some documents
    documents = document_db.execute(
        "SELECT id, title FROM document ORDER BY id LIMIT %s",
        (num_documents,)
    )

    if not documents:
        logger.error("No documents found in the database")
        return

    logger.info(f"Found {len(documents)} documents")

    # Create evaluators - one human and the rest AI
    evaluator_ids = []
    evaluator_types = []  # Track if each evaluator is human

    # Create one human evaluator using hherb's user ID (2)
    human_evaluator_name = "Test Human Evaluator (hherb)"
    human_evaluator_id = get_or_create_evaluator(db, human_evaluator_name, is_human=True, user_id=2)
    evaluator_ids.append(human_evaluator_id)
    evaluator_types.append(True)  # True = human
    logger.info(f"Using human evaluator: {human_evaluator_name} (ID: {human_evaluator_id})")

    # Create AI evaluators
    for i in range(num_evaluators - 1):
        ai_evaluator_name = f"Test AI Evaluator {i+1}"
        ai_evaluator_id = get_or_create_evaluator(db, ai_evaluator_name, is_human=False)
        evaluator_ids.append(ai_evaluator_id)
        evaluator_types.append(False)  # False = AI
        logger.info(f"Using AI evaluator: {ai_evaluator_name} (ID: {ai_evaluator_id})")

    # Create evaluations
    total_evaluations = 0

    for document in documents:
        document_id = document['id']
        logger.info(f"Processing document: {document['title']} (ID: {document_id})")

        # Get or create chunks for the document
        chunks = chunking_db.execute(
            "SELECT id FROM chunks WHERE document_id = %s LIMIT %s",
            (document_id, num_chunks_per_document)
        )

        if not chunks:
            # Create some test chunks
            logger.info(f"No chunks found for document {document_id}, creating test chunks")
            chunks = []
            for i in range(num_chunks_per_document):
                result = chunking_db.execute(
                    """
                    INSERT INTO chunks (
                        document_id, chunking_strategy_id, chunktype_id,
                        document_title, text, chunklength, chunk_no
                    )
                    VALUES (%s, 1, 1, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        document_id,
                        document['title'],
                        f"Test chunk {i+1} for document {document_id}",
                        100,
                        i+1
                    ),
                    commit=True
                )
                if result and len(result) > 0:
                    chunks.append({'id': result[0]['id']})

        logger.info(f"Found/created {len(chunks)} chunks for document {document_id}")

        # Create evaluations for each chunk and evaluator
        for chunk in chunks:
            chunk_id = chunk['id']

            for idx, evaluator_id in enumerate(evaluator_ids):
                # Generate a random rating (0-5)
                rating = random.randint(0, 5)

                # Generate a random confidence level (0.5-1.0)
                confidence_level = round(random.uniform(0.5, 1.0), 2)

                # Get whether this is a human evaluator
                is_human = evaluator_types[idx]

                # Create the evaluation
                success = evaluations_db.create_evaluation(
                    research_question_id=question_id,
                    chunk_id=chunk_id,
                    evaluator_id=evaluator_id,
                    document_id=document_id,
                    is_human_evaluator=is_human,
                    rating=rating,
                    confidence_level=confidence_level,
                    rating_reason=f"Test {'human' if is_human else 'AI'} rating {rating} for chunk {chunk_id}"
                )

                if success:
                    total_evaluations += 1
                    logger.info(f"Created evaluation: question={question_id}, chunk={chunk_id}, evaluator={evaluator_id}, rating={rating}")
                else:
                    logger.error(f"Failed to create evaluation: question={question_id}, chunk={chunk_id}, evaluator={evaluator_id}")

    logger.info(f"Created {total_evaluations} test evaluations")


def main() -> None:
    """Main function to run the script."""
    import argparse

    parser = argparse.ArgumentParser(description='Create test evaluations')
    parser.add_argument('question_id', type=int, help='ID of the research question')
    parser.add_argument('--documents', type=int, default=5, help='Number of documents to create evaluations for')
    parser.add_argument('--chunks', type=int, default=3, help='Number of chunks per document')
    parser.add_argument('--evaluators', type=int, default=2, help='Number of evaluators to create')

    args = parser.parse_args()

    create_test_evaluations(
        question_id=args.question_id,
        num_documents=args.documents,
        num_chunks_per_document=args.chunks,
        num_evaluators=args.evaluators
    )


if __name__ == '__main__':
    main()
