"""This module searches for documents that might be helpful to answer a research question.
It uses a combination of keyword search and semantic search to find relevant documents."""

import json
import logging
import ollama
from pprint import pprint
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.document_search import DocumentSearchManager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class FoundDocuments:
    """Represents the result of a literature search."""
    document_id: int  # document id in the database
    similarity: float = 0.0

@dataclass
class DocumentOfInterest:
    """Represents a document that has been evaluated with regards to a question"""
    document_id: int #the id of the document in the database
    rating: int #0= not suited,
        #1 maybe contrinuting a little to answer the question
        #2= likely to contrubute to answer the question,
        #3= answers the question
    reason_for_rating: str  #reason for the rating provided by the evaluator
    #evaluator: int # id in the evaluators table
    similarity: float = 0.0

class DocumentEvaluator:
    """Evaluates documents for their relevance to a research question."""
    def __init__(self, model_name: str = "gemma3:4b", model_options = None):
        """
        Initialize the DocumentEvaluator.

        Args:
            model_name: Name of the Ollama model to use for evaluation
            model_options: Optional parameters for the Ollama model
        """
        self.model_name = model_name
        self.model_options = model_options
        self.evaluator_id = None #TODO: get the evaluator id from the database based on model and parameters
        self.db = DocumentDatabaseManager()

        self.prompt = """
        You are a medical expert. You are evaluating a text for its relevance to a research question.
        Consider carefully how likely the provided text will contribute towards answering the question.
        The research question is: {question}
        The text is: {document}
        Please rate the text on a scale of 0 to 3, where 0 means the document is not relevant at all,
        1 means the document is somewhat relevant, tangentially related to the question.
        2 means the document is very likely relevant to answer the question, it should not be missed.
        3 means the document answers the question, it is essential and must be included in the reading list.
        Provide a brief reason for your rating in no more than 3 brief sentences. Keep it short.
        Answer in json format in the form of {{"rating": <rating>, "reason": "<reason>"}}.
        """

    def evaluate(self, question: str, document_id: int) -> DocumentOfInterest:
        """Evaluate the document for its relevance to the research question.

        Args:
            question: The research question
            document_id: The ID of the document to evaluate

        Returns:
            DocumentOfInterest object with the rating and reason for the rating
        """
        # Get the document from the database
        document = self.db.get_document(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return DocumentOfInterest(
                document_id=document_id,
                rating=0,
                reason_for_rating="Document not found in database",
                similarity=0.0
            )

        # Format the prompt with the question and document abstract
        prompt = self.prompt.format(question=question, document=document.get('abstract', ''))

        # Generate the evaluation using Ollama
        try:
            if self.model_options:
                response = ollama.generate(model=self.model_name, prompt=prompt, options=self.model_options)
            else:
                response = ollama.generate(model=self.model_name, prompt=prompt)

            try:
                # Extract and parse the JSON response
                json_str = response.response

                # Clean up the response to handle potential formatting issues
                json_str = json_str.replace('```json', '').replace('```', '').strip()

                # Parse the JSON
                result = json.loads(json_str)

                # Create and return the DocumentOfInterest object
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=int(result.get('rating', 0)),
                    reason_for_rating=result.get('reason', "No reason provided"),
                    similarity=0.0  # This will be set later if needed
                )
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response: {e}")
                logger.debug(f"Raw response: {response.response}")

                # Return a default object with error information
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=0,
                    reason_for_rating=f"Error parsing evaluation: {str(e)}",
                    similarity=0.0
                )
        except Exception as e:
            logger.error(f"Error generating evaluation with Ollama: {e}")

            # Try with a different model if the first one fails
            try:
                fallback_model = "gemma3:4b"  # Use a different model as fallback
                logger.info(f"Trying fallback model: {fallback_model}")
                response = ollama.generate(model=fallback_model, prompt=prompt)

                # Extract and parse the JSON response
                json_str = response.response

                # Clean up the response to handle potential formatting issues
                json_str = json_str.replace('```json', '').replace('```', '').strip()

                # Parse the JSON
                result = json.loads(json_str)

                # Create and return the DocumentOfInterest object
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=int(result.get('rating', 0)),
                    reason_for_rating=result.get('reason', "No reason provided"),
                    similarity=0.0  # This will be set later if needed
                )
            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")

                # Return a default object with error information
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=0,
                    reason_for_rating=f"Evaluation error: {str(e)}. Fallback also failed: {str(fallback_error)}",
                    similarity=0.0
                )



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
