#!/usr/bin/env python3
"""
Test script for the DocumentEvaluator class.

This script evaluates documents for a specific project using the DocumentEvaluator
and stores the evaluations in the database.
"""

import logging
import argparse
import json
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from localknowledge.ai.document_evaluator import DocumentEvaluator
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk
from localknowledge.db.evaluations import EvaluationsDatabaseManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Silence httpx (used by ollama) INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_evaluator_id(model_name: str, user_id: Optional[int] = None) -> int:
    """
    Get or create an evaluator ID for the specified model.

    Args:
        model_name: Name of the model to use
        user_id: Optional user ID to associate with the evaluator

    Returns:
        Evaluator ID
    """
    suggestions_db = ReadingSuggestionsManager()

    # Check if an evaluator for this model already exists
    evaluators = suggestions_db.get_evaluators()
    for evaluator in evaluators:
        if evaluator.get('model_id') == model_name:
            logger.info(f"Using existing evaluator ID {evaluator['id']} for model {model_name}")
            return evaluator['id']

    # Create a new evaluator
    evaluator_name = f"DocumentEvaluator Test ({model_name})"
    parameters = json.dumps({"type": "test"})  # Convert dict to JSON string
    prompt = "Evaluate document relevance to research questions"

    evaluator_id = suggestions_db.add_evaluator(
        name=evaluator_name,
        user_id=user_id,  # Can be None for system evaluators
        model_id=model_name,
        parameters=parameters,
        prompt=prompt
    )

    if evaluator_id:
        logger.info(f"Created new evaluator ID {evaluator_id} for model {model_name}")
        return evaluator_id
    else:
        logger.error(f"Failed to create evaluator for model {model_name}")
        # Return a default ID as fallback
        return 1


def get_or_create_document_chunks(document_id: int) -> List[Dict[str, Any]]:
    """
    Get all chunks for a document. If no chunks exist, create a simple chunk.

    Args:
        document_id: ID of the document

    Returns:
        List of chunk dictionaries
    """
    chunker_db = ChunkingDatabaseManager()
    doc_db = DocumentDatabaseManager()

    # Try to get existing chunks
    chunks = chunker_db.get_chunks_by_document(document_id)

    # If no chunks exist, create a simple chunk
    if not chunks:
        logger.info(f"No chunks found for document ID {document_id}, creating a simple chunk")

        # Get document details
        document = doc_db.get_document(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return []

        # Get or create chunking strategy and chunktype
        chunking_strategy_id = chunker_db.get_or_create_chunking_strategy(
            strategy_name="simple",
            parameters={"type": "full_abstract"}
        )

        chunktype_id = chunker_db.get_or_create_chunktype("abstract")

        # Create a chunk for the abstract
        abstract = document.get('abstract', '')
        title = document.get('title', '')

        if not abstract:
            logger.warning(f"Document ID {document_id} has no abstract")
            return []

        # Create a new chunk
        chunk = Chunk(
            chunk_id=0,  # Will be assigned by the database
            document_id=document_id,
            chunking_strategy_id=chunking_strategy_id,
            chunktype_id=chunktype_id,
            document_title=title,
            text=abstract,
            chunklength=len(abstract),
            chunk_no=1,
            page_start=0,
            page_end=0,
            metadata={}
        )

        # Save the chunk to the database
        chunk_id = chunker_db.get_or_create_chunk(chunk)

        # Get the chunk with the assigned ID
        chunk.chunk_id = chunk_id
        chunks = [chunk]

    # Convert Chunk objects to dictionaries
    return [chunk.to_dict() for chunk in chunks]


def evaluate_document_for_question(
    document_id: int,
    question_id: int,
    question_text: str,
    evaluator_id: int,
    model_name: str,
    is_human_evaluator: bool = False
) -> List[Dict[str, Any]]:
    """
    Evaluate a document for a specific research question.

    Args:
        document_id: ID of the document to evaluate
        question_id: ID of the research question
        question_text: Text of the research question
        evaluator_id: ID of the evaluator
        model_name: Name of the model to use
        is_human_evaluator: Whether the evaluator is human

    Returns:
        List of evaluation results
    """
    # Get document chunks
    chunks = get_or_create_document_chunks(document_id)
    if not chunks:
        logger.warning(f"No chunks found for document ID {document_id}")
        return []

    # Create evaluator
    evaluator = DocumentEvaluator(model_name=model_name)

    # Evaluate the document
    logger.info(f"Evaluating document ID {document_id} for question: {question_text[:50]}...")
    evaluation = evaluator.evaluate(question=question_text, document_id=document_id)

    # Store evaluations for each chunk
    evaluations_db = EvaluationsDatabaseManager()
    results = []

    for chunk in chunks:
        # Create evaluation in the database
        success = evaluations_db.create_evaluation(
            research_question_id=question_id,
            chunk_id=chunk['chunk_id'],
            evaluator_id=evaluator_id,
            document_id=document_id,
            is_human_evaluator=is_human_evaluator,
            rating=evaluation.rating,
            confidence_level=evaluation.similarity,
            rating_reason=evaluation.reason_for_rating
        )

        if success:
            logger.info(f"Created evaluation for chunk ID {chunk['chunk_id']}, rating: {evaluation.rating}")
            results.append({
                'chunk_id': chunk['chunk_id'],
                'document_id': document_id,
                'rating': evaluation.rating,
                'reason': evaluation.reason_for_rating
            })
        else:
            logger.error(f"Failed to create evaluation for chunk ID {chunk['chunk_id']}")

    return results


def evaluate_documents_for_project(
    project_id: int,
    user_id: int,
    model_name: str,
    max_documents: int = 5,
    min_publication_year: int = 2020
) -> Dict[str, Any]:
    """
    Evaluate documents for all research questions in a project.

    Args:
        project_id: ID of the project
        user_id: ID of the user
        model_name: Name of the model to use
        max_documents: Maximum number of documents to evaluate
        min_publication_year: Minimum publication year for documents

    Returns:
        Dictionary with evaluation statistics
    """
    # Get research questions for the project
    questions_db = ResearchQuestionsManager()
    project_questions = questions_db.get_project_questions(project_id)

    if not project_questions:
        logger.error(f"No research questions found for project ID {project_id}")
        return {'error': 'No research questions found for project'}

    # Get evaluator ID
    evaluator_id = get_evaluator_id(model_name, user_id)

    # Get recent documents
    doc_db = DocumentDatabaseManager()
    query = f"""
    SELECT id, title, publication_date
    FROM document
    WHERE EXTRACT(YEAR FROM publication_date) >= {min_publication_year}
    ORDER BY publication_date DESC
    LIMIT {max_documents}
    """
    documents = doc_db.execute(query) or []

    if not documents:
        logger.error(f"No documents found with publication year >= {min_publication_year}")
        return {'error': 'No documents found'}

    # Track statistics
    stats = {
        'project_id': project_id,
        'user_id': user_id,
        'model_name': model_name,
        'questions_evaluated': len(project_questions),
        'documents_evaluated': len(documents),
        'total_evaluations': 0,
        'evaluations_by_rating': {0: 0, 1: 0, 2: 0, 3: 0},
        'documents': []
    }

    # Evaluate each document for each question
    for document in tqdm(documents, desc="Evaluating documents"):
        document_stats = {
            'document_id': document['id'],
            'title': document['title'],
            'publication_date': document['publication_date'].isoformat() if document['publication_date'] else None,
            'evaluations': []
        }

        for question in project_questions:
            question_id = question['id']
            question_text = question['question']

            evaluations = evaluate_document_for_question(
                document_id=document['id'],
                question_id=question_id,
                question_text=question_text,
                evaluator_id=evaluator_id,
                model_name=model_name,
                is_human_evaluator=False
            )

            # Update statistics
            for eval_result in evaluations:
                stats['total_evaluations'] += 1
                stats['evaluations_by_rating'][eval_result['rating']] += 1

                document_stats['evaluations'].append({
                    'question_id': question_id,
                    'question_text': question_text,
                    'rating': eval_result['rating'],
                    'reason': eval_result['reason']
                })

        stats['documents'].append(document_stats)

    return stats


def main():
    """Main function to run the test."""
    parser = argparse.ArgumentParser(description="Test the DocumentEvaluator with real documents")
    parser.add_argument("--project", "-p", type=int, default=3, help="Project ID")
    parser.add_argument("--user", "-u", type=int, default=2, help="User ID")
    parser.add_argument("--model", "-m", type=str, default="qwen3:1.7b-q8_0", help="Model name")
    parser.add_argument("--max-docs", "-d", type=int, default=5, help="Maximum number of documents to evaluate")
    parser.add_argument("--min-year", "-y", type=int, default=2020, help="Minimum publication year")

    args = parser.parse_args()

    # Run the evaluation
    stats = evaluate_documents_for_project(
        project_id=args.project,
        user_id=args.user,
        model_name=args.model,
        max_documents=args.max_docs,
        min_publication_year=args.min_year
    )

    # Print statistics
    print("\n=== Evaluation Statistics ===")
    print(f"Project ID: {stats['project_id']}")
    print(f"User ID: {stats['user_id']}")
    print(f"Model: {stats['model_name']}")
    print(f"Questions evaluated: {stats['questions_evaluated']}")
    print(f"Documents evaluated: {stats['documents_evaluated']}")
    print(f"Total evaluations: {stats['total_evaluations']}")
    print("\nRating distribution:")
    for rating, count in stats['evaluations_by_rating'].items():
        print(f"  Rating {rating}: {count} evaluations")

    print("\n=== Document Evaluations ===")
    for doc in stats['documents']:
        print(f"\nDocument ID: {doc['document_id']}")
        print(f"Title: {doc['title']}")
        print(f"Publication Date: {doc['publication_date']}")

        for eval_result in doc['evaluations']:
            print(f"\n  Question: {eval_result['question_text'][:50]}...")
            print(f"  Rating: {eval_result['rating']}/3")
            print(f"  Reason: {eval_result['reason']}")


if __name__ == "__main__":
    main()
