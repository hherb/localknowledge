#!/usr/bin/env python3
"""
Script to create test data for the reading suggestions system.

This script creates a test evaluator and adds reading suggestions
for recent documents.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Create test data for reading suggestions."""
    # Create managers
    suggestions_manager = ReadingSuggestionsManager()
    doc_manager = DocumentDatabaseManager()

    try:
        # Create a test evaluator (LLM)
        # Convert the parameters dict to JSON string
        import json
        parameters_json = json.dumps({"temperature": 0.7})

        evaluator_id = suggestions_manager.add_evaluator(
            name="GPT-4 Evaluator",
            model_id="gpt-4",
            parameters=parameters_json,
            prompt="Evaluate if this document is relevant for emergency medicine research."
        )

        logger.info(f"Created evaluator with ID: {evaluator_id}")

        # Get some recent documents
        documents = doc_manager.search_documents("", limit=10)

        # Create recommendations for these documents
        user_id = 2  # Use existing user ID (hherb)
        for i, doc in enumerate(documents):
            # Vary the recommendation strength
            strength = (i % 5) + 1  # 1-5

            # Add a suggestion with user_id
            query = """
            INSERT INTO reading_suggestions
            (document_id, user_id, evaluator_id, recommendation_strength, confidence_level, comment)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            result = suggestions_manager.execute(
                query,
                (
                    doc['id'],
                    user_id,
                    evaluator_id,
                    strength,
                    0.7 + (i * 0.02),  # Vary confidence
                    f"This document appears to be relevant for emergency medicine research. Strength: {strength}/5"
                ),
                commit=True
            )

            suggestion_id = result[0]['id'] if result else None

            logger.info(f"Created suggestion with ID: {suggestion_id} for document: {doc['title'][:50]}...")

        logger.info(f"Created {len(documents)} test recommendations")
    finally:
        # Close database connections
        suggestions_manager.close()
        doc_manager.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
