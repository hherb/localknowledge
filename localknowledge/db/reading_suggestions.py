"""
Reading suggestions database manager for the LocalKnowledge library.

This module provides functionality for managing reading suggestions,
which are recommendations for users to read specific documents.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class ReadingSuggestionsManager(DatabaseManager):
    """Database manager for reading suggestions."""

    def __init__(self):
        """Initialize the reading suggestions database manager."""
        super().__init__()

    def add_evaluator(self,
                     name: str,
                     user_id: Optional[int] = None,
                     model_id: Optional[str] = None,
                     parameters: Optional[Dict[str, Any]] = None,
                     prompt: Optional[str] = None) -> Optional[int]:
        """
        Add a new evaluator to the database.

        Args:
            name: Name of the evaluator
            user_id: ID of the user (if the evaluator is a user)
            model_id: ID of the model (if the evaluator is an LLM)
            parameters: Model parameters (if the evaluator is an LLM)
            prompt: Prompt used for evaluation (if the evaluator is an LLM)

        Returns:
            ID of the new evaluator or None if the operation failed
        """
        query = """
        INSERT INTO evaluators (name, user_id, model_id, parameters, prompt)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        try:
            result = self.execute(query, (name, user_id, model_id, parameters, prompt), commit=True)
            if result:
                return result[0]['id']
            return None
        except Exception as e:
            logger.error(f"Error adding evaluator: {e}")
            return None

    def get_evaluator(self, evaluator_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an evaluator by ID.

        Args:
            evaluator_id: ID of the evaluator

        Returns:
            Evaluator data or None if not found
        """
        query = """
        SELECT * FROM evaluators
        WHERE id = %s
        """
        try:
            result = self.execute(query, (evaluator_id,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting evaluator: {e}")
            return None

    def get_evaluators(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all evaluators, optionally filtered by user ID.

        Args:
            user_id: ID of the user to filter by

        Returns:
            List of evaluator data
        """
        if user_id:
            query = """
            SELECT * FROM evaluators
            WHERE user_id = %s
            ORDER BY name
            """
            params = (user_id,)
        else:
            query = """
            SELECT * FROM evaluators
            ORDER BY name
            """
            params = ()

        try:
            result = self.execute(query, params)
            return result or []
        except Exception as e:
            logger.error(f"Error getting evaluators: {e}")
            return []

    def update_evaluator(self,
                        evaluator_id: int,
                        name: Optional[str] = None,
                        model_id: Optional[str] = None,
                        parameters: Optional[Dict[str, Any]] = None,
                        prompt: Optional[str] = None) -> bool:
        """
        Update an existing evaluator.

        Args:
            evaluator_id: ID of the evaluator to update
            name: New name for the evaluator (if None, keeps existing)
            model_id: New model ID (if None, keeps existing)
            parameters: New parameters (if None, keeps existing)
            prompt: New prompt (if None, keeps existing)

        Returns:
            True if the update was successful, False otherwise
        """
        # Get current evaluator data
        current = self.get_evaluator(evaluator_id)
        if not current:
            logger.error(f"Evaluator with ID {evaluator_id} not found")
            return False

        # Use current values for any parameters that weren't provided
        name = name if name is not None else current.get('name')
        model_id = model_id if model_id is not None else current.get('model_id')
        parameters = parameters if parameters is not None else current.get('parameters')
        prompt = prompt if prompt is not None else current.get('prompt')

        # Update the evaluator
        query = """
        UPDATE evaluators
        SET name = %s, model_id = %s, parameters = %s, prompt = %s, updated_at = NOW()
        WHERE id = %s
        """
        try:
            self.execute(query, (name, model_id, parameters, prompt, evaluator_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error updating evaluator: {e}")
            return False

    def delete_evaluator(self, evaluator_id: int) -> bool:
        """
        Delete an evaluator.

        Args:
            evaluator_id: ID of the evaluator to delete

        Returns:
            True if the deletion was successful, False otherwise
        """
        # Check if there are any reading suggestions using this evaluator
        check_query = """
        SELECT COUNT(*) as count FROM reading_suggestions
        WHERE evaluator_id = %s
        """
        try:
            result = self.execute(check_query, (evaluator_id,))
            if result and result[0]['count'] > 0:
                logger.warning(f"Cannot delete evaluator {evaluator_id} because it has {result[0]['count']} reading suggestions")
                return False

            # Delete the evaluator
            delete_query = """
            DELETE FROM evaluators
            WHERE id = %s
            """
            self.execute(delete_query, (evaluator_id,), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error deleting evaluator: {e}")
            return False

    def add_reading_suggestion(self,
                              document_id: int,
                              user_id: int,
                              evaluator_id: int,
                              recommendation_strength: int,
                              confidence_level: Optional[float] = None,
                              comment: Optional[str] = None) -> Optional[int]:
        """
        Add a new reading suggestion to the database.

        Args:
            document_id: ID of the document
            user_id: ID of the user the suggestion is for
            evaluator_id: ID of the evaluator making the suggestion
            recommendation_strength: Strength of the recommendation (0-5)
            confidence_level: Confidence level of the recommendation (0-1)
            comment: Comment about the recommendation

        Returns:
            ID of the new reading suggestion or None if the operation failed
        """
        # Validate recommendation strength
        if recommendation_strength < 0 or recommendation_strength > 5:
            logger.error(f"Invalid recommendation strength: {recommendation_strength}")
            return None

        # Check if a suggestion already exists for this document, user, and evaluator
        check_query = """
        SELECT id FROM reading_suggestions
        WHERE document_id = %s AND user_id = %s AND evaluator_id = %s
        """
        try:
            existing = self.execute(check_query, (document_id, user_id, evaluator_id))
            if existing:
                # Update existing suggestion
                update_query = """
                UPDATE reading_suggestions
                SET recommendation_strength = %s, confidence_level = %s, comment = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id
                """
                result = self.execute(update_query, (recommendation_strength, confidence_level, comment, existing[0]['id']), commit=True)
                return result[0]['id'] if result else None
            else:
                # Insert new suggestion
                insert_query = """
                INSERT INTO reading_suggestions
                (document_id, user_id, evaluator_id, recommendation_strength, confidence_level, comment)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """
                result = self.execute(insert_query, (document_id, user_id, evaluator_id, recommendation_strength, confidence_level, comment), commit=True)
                return result[0]['id'] if result else None
        except Exception as e:
            logger.error(f"Error adding reading suggestion: {e}")
            return None

    def update_user_agreement(self, suggestion_id: int, user_agreement: bool) -> bool:
        """
        Update the user agreement for a reading suggestion.

        Args:
            suggestion_id: ID of the reading suggestion
            user_agreement: Whether the user agrees with the suggestion

        Returns:
            True if the update was successful, False otherwise
        """
        query = """
        UPDATE reading_suggestions
        SET user_agreement = %s, updated_at = NOW()
        WHERE id = %s
        """
        try:
            self.execute(query, (user_agreement, suggestion_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error updating user agreement: {e}")
            return False

    def get_reading_suggestions(self,
                               user_id: int,
                               include_read: bool = False,
                               min_strength: int = 0,
                               evaluator_id: Optional[int] = None,
                               limit: int = 100,
                               offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get reading suggestions for a user.

        Args:
            user_id: ID of the user
            include_read: Whether to include suggestions for documents that have been read
            min_strength: Minimum recommendation strength to include
            evaluator_id: ID of the evaluator to filter by
            limit: Maximum number of suggestions to return
            offset: Offset for pagination

        Returns:
            List of reading suggestions with document data
        """
        # Build the query based on parameters
        query = """
        SELECT rs.*, d.*, s.name as source_name, c.name as category_name, e.name as evaluator_name
        FROM reading_suggestions rs
        JOIN document d ON rs.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        JOIN evaluators e ON rs.evaluator_id = e.id
        WHERE rs.user_id = %s
        """
        params = [user_id]

        # Add filter for recommendation strength
        if min_strength > 0:
            query += " AND rs.recommendation_strength >= %s"
            params.append(min_strength)

        # Add filter for evaluator
        if evaluator_id:
            query += " AND rs.evaluator_id = %s"
            params.append(evaluator_id)

        # Add filter for read status if needed
        if not include_read:
            query += """
            AND NOT EXISTS (
                SELECT 1 FROM reading_records rr
                WHERE rr.document_id = rs.document_id
                AND rr.user_id = rs.user_id
            )
            """

        # Add ordering and limit
        query += """
        ORDER BY rs.recommendation_strength DESC, d.publication_date DESC
        LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        try:
            result = self.execute(query, tuple(params))
            print(f"Query returned {len(result) if result else 0} rows")
            if result and len(result) > 0:
                print(f"First row keys: {result[0].keys()}")
            print("=== End Debug ===\n")
            return result or []
        except Exception as e:
            logger.error(f"Error getting reading suggestions: {e}")
            return []

    def get_suggestion_by_document(self, document_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a reading suggestion for a specific document and user.

        Args:
            document_id: ID of the document
            user_id: ID of the user

        Returns:
            Reading suggestion data or None if not found
        """
        query = """
        SELECT rs.*, e.name as evaluator_name
        FROM reading_suggestions rs
        JOIN evaluators e ON rs.evaluator_id = e.id
        WHERE rs.document_id = %s AND rs.user_id = %s
        ORDER BY rs.recommendation_strength DESC
        LIMIT 1
        """
        try:
            result = self.execute(query, (document_id, user_id))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting suggestion by document: {e}")
            return None

    def delete_suggestion(self, suggestion_id: int) -> bool:
        """
        Delete a reading suggestion.

        Args:
            suggestion_id: ID of the reading suggestion

        Returns:
            True if the deletion was successful, False otherwise
        """
        query = """
        DELETE FROM reading_suggestions
        WHERE id = %s
        """
        try:
            self.execute(query, (suggestion_id,), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error deleting suggestion: {e}")
            return False

    def get_evaluator_performance(self, evaluator_id: int) -> Dict[str, Any]:
        """
        Get performance metrics for an evaluator.

        Args:
            evaluator_id: ID of the evaluator

        Returns:
            Dictionary with performance metrics
        """
        query = """
        SELECT
            COUNT(*) as total_suggestions,
            COUNT(CASE WHEN user_agreement = TRUE THEN 1 END) as agreed,
            COUNT(CASE WHEN user_agreement = FALSE THEN 1 END) as disagreed,
            COUNT(CASE WHEN user_agreement IS NULL THEN 1 END) as unrated,
            AVG(CASE WHEN user_agreement = TRUE THEN recommendation_strength END) as avg_strength_agreed,
            AVG(CASE WHEN user_agreement = FALSE THEN recommendation_strength END) as avg_strength_disagreed,
            AVG(confidence_level) as avg_confidence
        FROM reading_suggestions
        WHERE evaluator_id = %s
        """
        try:
            result = self.execute(query, (evaluator_id,))
            return result[0] if result else {
                'total_suggestions': 0,
                'agreed': 0,
                'disagreed': 0,
                'unrated': 0,
                'avg_strength_agreed': 0,
                'avg_strength_disagreed': 0,
                'avg_confidence': 0
            }
        except Exception as e:
            logger.error(f"Error getting evaluator performance: {e}")
            return {
                'total_suggestions': 0,
                'agreed': 0,
                'disagreed': 0,
                'unrated': 0,
                'avg_strength_agreed': 0,
                'avg_strength_disagreed': 0,
                'avg_confidence': 0
            }
