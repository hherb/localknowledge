"""This module searches for documents that might be helpful to answer a research question.
It uses a combination of keyword search and semantic search to find relevant documents."""

import logging
from typing import List, Optional
from dataclasses import dataclass
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.document_search import DocumentSearchManager
from localknowledge.ai.document_evaluator import DocumentEvaluator

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class FoundDocuments:
    """Represents the result of a literature search."""
    document_id: int  # document id in the database
    similarity: float = 0.0


def search_literature(question: str, research_question_id: Optional[int] = None,
                   max_results: int = 10, similarity_threshold: float = 0.5,
                   source_name: Optional[str] = None,
                   model_name: str = "snowflake-arctic-embed2:latest",
                   unique_document_ids: bool = True) -> List[FoundDocuments]:
    """Search for documents that might be helpful to answer a research question.
    It uses a combination of keyword search and semantic search to find relevant documents.

    Args:
        question: The research question
        research_question_id: The ID of the research question in the database (optional).
                              If provided, all found documents will be linked with the research question
        max_results: Maximum number of results to return
        similarity_threshold: Minimum similarity score (0-1) for results
        source_name: Filter by source name (optional)
        model_name: Name of the embedding model to use (default: snowflake-arctic-embed2:latest)
        unique_document_ids: If True, deduplicate results to return only unique document IDs.
                            If False, may return multiple chunks from the same document.

    Returns:
        List of FoundDocuments objects with document IDs and similarity scores
    """
    logger.info(f"Searching literature for question: {question}")

    # Initialize the document search manager
    search_manager = DocumentSearchManager()
    db_manager = DocumentDatabaseManager()

    # Set the embedding model
    search_manager.embedding_model = model_name

    # Perform semantic search
    results = []
    try:
        # Use the semantic search method from DocumentSearchManager
        semantic_results = list(search_manager.semantic(
            question=question,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
            source_name=source_name
        ))

        logger.info(f"Found {len(semantic_results)} chunks with semantic search")

        # Convert to FoundDocuments objects
        if unique_document_ids:
            # Deduplicate by document ID, keeping the highest similarity score
            doc_similarities = {}

            # Extract document IDs and similarities
            for doc in semantic_results:
                # The document ID might be in 'id' or 'document_id' depending on the query
                doc_id = doc.get('document_id', doc.get('id'))
                if doc_id:
                    similarity = doc.get('similarity', 0.0)
                    # If we've seen this document before, keep the highest similarity score
                    if doc_id in doc_similarities:
                        if similarity > doc_similarities[doc_id]:
                            doc_similarities[doc_id] = similarity
                    else:
                        doc_similarities[doc_id] = similarity

            # Create FoundDocuments objects from the deduplicated results
            for doc_id, similarity in doc_similarities.items():
                results.append(FoundDocuments(
                    document_id=doc_id,
                    similarity=similarity
                ))

            logger.info(f"After deduplication, found {len(results)} unique documents from {len(semantic_results)} chunks")
        else:
            # Return all chunks, which may include multiple chunks from the same document
            for doc in semantic_results:
                doc_id = doc.get('document_id', doc.get('id'))
                if doc_id:
                    results.append(FoundDocuments(
                        document_id=doc_id,
                        similarity=doc.get('similarity', 0.0)
                    ))

            logger.info(f"Returning all {len(results)} chunks without deduplication")

        # If research_question_id is provided, link the documents with the research question
        if research_question_id is not None:
            for found_doc in results:
                try:
                    # Link the document with the research question
                    # This would typically involve inserting a record into a linking table
                    # such as research_question_documents
                    logger.debug(f"Linking document {found_doc.document_id} with research question {research_question_id}")
                    # TODO: Implement the linking functionality when the schema is available
                    # db_manager.link_document_to_research_question(found_doc.document_id, research_question_id)
                except Exception as e:
                    logger.error(f"Error linking document {found_doc.document_id} with research question {research_question_id}: {e}")

    except Exception as e:
        logger.error(f"Error during literature search: {e}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        # Close the connections
        search_manager.close()
        db_manager.close()

    return results


if __name__ == "__main__":
    # Example usage of the module
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Search for and evaluate literature related to a research question")
    parser.add_argument("--question", "-q", type=str, default="Is machine learning able to predict in-hospital mortality?",
                        help="The research question to search for")
    parser.add_argument("--max-results", "-m", type=int, default=5,
                        help="Maximum number of results to return")
    parser.add_argument("--threshold", "-t", type=float, default=0.5,
                        help="Minimum similarity threshold (0-1)")
    parser.add_argument("--source", "-s", type=str, default=None,
                        help="Filter by source name (e.g., 'pubmed', 'medrxiv')")
    parser.add_argument("--model", type=str, default="snowflake-arctic-embed2:latest",
                        help="Embedding model to use")
    parser.add_argument("--evaluate", "-e", action="store_true",
                        help="Evaluate the top document")

    # Parse arguments
    args = parser.parse_args()

    # 1. Search for relevant literature
    print(f"\nSearching for documents related to: {args.question}")
    print(f"Using model: {args.model}")
    found_documents = search_literature(
        question=args.question,
        max_results=args.max_results,
        similarity_threshold=args.threshold,
        source_name=args.source,
        model_name=args.model
    )

    print(f"Found {len(found_documents)} documents")
    for i, doc in enumerate(found_documents):
        print(f"{i+1}. Document ID: {doc.document_id}, Similarity: {doc.similarity:.4f}")

    # 2. Evaluate the relevance of documents if requested
    if args.evaluate and found_documents:
        print("\nEvaluating the top document:")
        evaluator = DocumentEvaluator(model_name="gemma3:4b")  # Use gemma3:4b as it's more reliable for this task

        # Evaluate the top document
        top_doc_id = found_documents[0].document_id
        evaluation = evaluator.evaluate(question=args.question, document_id=top_doc_id)

        print(f"Document ID: {evaluation.document_id}")
        print(f"Rating: {evaluation.rating}/3")
        print(f"Reason: {evaluation.reason_for_rating}")

        # 3. Try with different questions on the same document
        print("\nEvaluating the same document with different questions:")

        questions = [
            "Are administrators the best predictors of in-hospital mortality?",
            "Does chocolate taste good?"
        ]

        for q in questions:
            print(f"\nQuestion: {q}")
            evaluation = evaluator.evaluate(question=q, document_id=top_doc_id)
            print(f"Rating: {evaluation.rating}/3")
            print(f"Reason: {evaluation.reason_for_rating}")
