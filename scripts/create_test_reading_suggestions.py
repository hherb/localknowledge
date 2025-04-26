#!/usr/bin/env python3
"""Create test data for reading suggestions."""

import logging
import json
from typing import List, Dict, Any

from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_evaluator(suggestions_manager: ReadingSuggestionsManager) -> int:
    """Create a test evaluator and return its ID."""
    parameters = {
        "temperature": 0.7,
        "max_tokens": 150,
        "top_p": 0.9
    }
    
    evaluator_id = suggestions_manager.add_evaluator(
        name="GPT-4 Test Evaluator",
        model_id="gpt-4",
        parameters=json.dumps(parameters),
        prompt="Evaluate if this document is relevant for emergency medicine research."
    )
    
    if not evaluator_id:
        raise Exception("Failed to create evaluator")
        
    logger.info(f"Created evaluator with ID: {evaluator_id}")
    return evaluator_id

def get_test_documents(doc_manager: DocumentDatabaseManager, limit: int = 10) -> List[Dict[str, Any]]:
    """Get test documents from the database."""
    documents = doc_manager.search_documents("", limit=limit)
    if not documents:
        raise Exception("No documents found in database")
    
    logger.info(f"Found {len(documents)} documents for testing")
    return documents

def create_test_suggestions(suggestions_manager: ReadingSuggestionsManager, 
                          documents: List[Dict[str, Any]], 
                          evaluator_id: int,
                          user_id: int = 2) -> List[int]:
    """Create test suggestions for the given documents."""
    suggestion_ids = []
    
    for i, doc in enumerate(documents):
        # Vary the recommendation strength (1-5)
        strength = (i % 5) + 1
        confidence = 0.7 + (i * 0.02)  # Vary confidence between 0.7 and 0.88
        
        suggestion_id = suggestions_manager.add_reading_suggestion(
            document_id=doc['id'],
            user_id=user_id,
            evaluator_id=evaluator_id,
            recommendation_strength=strength,
            confidence_level=confidence,
            comment=f"Test suggestion for document {doc['id']}. Relevance score: {strength}/5"
        )
        
        if suggestion_id:
            suggestion_ids.append(suggestion_id)
            logger.info(f"Created suggestion {suggestion_id} for document {doc['id']} "
                       f"with strength {strength}/5")
        else:
            logger.error(f"Failed to create suggestion for document {doc['id']}")
    
    return suggestion_ids

def verify_suggestions(suggestions_manager: ReadingSuggestionsManager, user_id: int) -> None:
    """Verify that suggestions were created correctly."""
    suggestions = suggestions_manager.get_reading_suggestions(
        user_id=user_id,
        include_read=True,  # Include all suggestions for verification
        min_strength=0
    )
    
    logger.info(f"Verification: Found {len(suggestions)} suggestions for user {user_id}")
    
    if suggestions:
        logger.info("Sample suggestion details:")
        sample = suggestions[0]
        logger.info(f"Document ID: {sample.get('document_id')}")
        logger.info(f"Strength: {sample.get('recommendation_strength')}/5")
        logger.info(f"Confidence: {sample.get('confidence_level'):.2f}")
    else:
        logger.error("No suggestions found during verification!")

def main():
    """Create test data for reading suggestions."""
    suggestions_manager = ReadingSuggestionsManager()
    doc_manager = DocumentDatabaseManager()
    
    try:
        # Create test evaluator
        evaluator_id = create_test_evaluator(suggestions_manager)
        
        # Get test documents
        documents = get_test_documents(doc_manager)
        
        # Create test suggestions
        user_id = 2  # Test user ID (hherb)
        suggestion_ids = create_test_suggestions(
            suggestions_manager, 
            documents, 
            evaluator_id,
            user_id
        )
        
        logger.info(f"Created {len(suggestion_ids)} test suggestions")
        
        # Verify the suggestions were created
        verify_suggestions(suggestions_manager, user_id)
        
    except Exception as e:
        logger.error(f"Error creating test data: {e}")
        raise
    finally:
        suggestions_manager.close()
        doc_manager.close()

if __name__ == "__main__":
    main()
