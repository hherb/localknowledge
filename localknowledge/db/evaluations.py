"""
Evaluations database functionality for the LocalKnowledge library.

This module provides database operations for managing evaluations of document chunks
against research questions by different evaluators (human or AI).
"""
from typing import List, Dict, Any, Optional, Tuple, Iterator
import logging
from datetime import datetime
from localknowledge.db.base import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluationsDatabaseManager(DatabaseManager):
    """Database manager for evaluations data."""

    def __init__(self):
        """Initialize the evaluations database manager."""
        super().__init__()

    def create_evaluation(
        self,
        research_question_id: int,
        chunk_id: int,
        evaluator_id: int,
        document_id: int,
        is_human_evaluator: bool,
        rating: int,
        confidence_level: float,
        rating_reason: Optional[str] = None
    ) -> bool:
        """
        Create a new evaluation in the database.

        Args:
            research_question_id: ID of the research question
            chunk_id: ID of the document chunk
            evaluator_id: ID of the evaluator (human or AI)
            document_id: ID of the document (denormalized for performance)
            is_human_evaluator: Whether the evaluator is human
            rating: Rating value (0-5)
            confidence_level: Confidence level (0.0-1.0)
            rating_reason: Optional explanation for the rating

        Returns:
            True if successful, False if failed
        """
        try:
            # Validate rating range
            if not 0 <= rating <= 5:
                logger.error(f"Invalid rating value: {rating}. Must be between 0 and 5.")
                return False

            # Validate confidence level range
            if not 0.0 <= confidence_level <= 1.0:
                logger.error(f"Invalid confidence level: {confidence_level}. Must be between 0.0 and 1.0.")
                return False

            query = """
            INSERT INTO evaluations (
                research_question_id, chunk_id, evaluator_id, document_id,
                is_human_evaluator, rating, rating_reason, confidence_level
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (research_question_id, chunk_id, evaluator_id)
            DO UPDATE SET
                document_id = EXCLUDED.document_id,
                is_human_evaluator = EXCLUDED.is_human_evaluator,
                rating = EXCLUDED.rating,
                rating_reason = EXCLUDED.rating_reason,
                confidence_level = EXCLUDED.confidence_level
            """

            self.execute(
                query,
                (
                    research_question_id, chunk_id, evaluator_id, document_id,
                    is_human_evaluator, rating, rating_reason, confidence_level
                ),
                commit=True
            )

            return True
        except Exception as e:
            logger.error(f"Error creating evaluation: {e}")
            return False

    def get_evaluation(
        self,
        research_question_id: int,
        chunk_id: int,
        evaluator_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific evaluation by its composite primary key.

        Args:
            research_question_id: ID of the research question
            chunk_id: ID of the document chunk
            evaluator_id: ID of the evaluator

        Returns:
            Evaluation data if found, None otherwise
        """
        query = """
        SELECT *
        FROM evaluations
        WHERE research_question_id = %s AND chunk_id = %s AND evaluator_id = %s
        """

        result = self.execute(query, (research_question_id, chunk_id, evaluator_id))

        if result and len(result) > 0:
            return result[0]
        return None

    def get_evaluations_by_research_question(
        self,
        research_question_id: int,
        min_rating: Optional[int] = None,
        human_only: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get evaluations for a specific research question.

        Args:
            research_question_id: ID of the research question
            min_rating: Optional minimum rating to filter by
            human_only: If True, only return evaluations by human evaluators
            limit: Optional limit on the number of results
            offset: Optional offset for pagination

        Returns:
            List of evaluation data dictionaries
        """
        query = """
        SELECT e.*, c.text as chunk_text, c.document_title, ev.name as evaluator_name
        FROM evaluations e
        JOIN chunks c ON e.chunk_id = c.id
        JOIN evaluators ev ON e.evaluator_id = ev.id
        WHERE e.research_question_id = %s
        """

        params = [research_question_id]

        if min_rating is not None:
            query += " AND e.rating >= %s"
            params.append(min_rating)

        if human_only:
            query += " AND e.is_human_evaluator = TRUE"

        query += " ORDER BY e.rating DESC, e.confidence_level DESC"

        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        if offset is not None:
            query += " OFFSET %s"
            params.append(offset)

        result = self.execute(query, tuple(params))
        return result or []

    def get_evaluations_by_document(
        self,
        document_id: int,
        research_question_id: Optional[int] = None,
        min_rating: Optional[int] = None,
        human_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get evaluations for a specific document.

        Args:
            document_id: ID of the document
            research_question_id: Optional research question ID to filter by
            min_rating: Optional minimum rating to filter by
            human_only: If True, only return evaluations by human evaluators

        Returns:
            List of evaluation data dictionaries
        """
        query = """
        SELECT e.*, c.text as chunk_text, c.document_title, ev.name as evaluator_name,
               rq.question as research_question
        FROM evaluations e
        JOIN chunks c ON e.chunk_id = c.id
        JOIN evaluators ev ON e.evaluator_id = ev.id
        JOIN research_questions rq ON e.research_question_id = rq.id
        WHERE e.document_id = %s
        """

        params = [document_id]

        if research_question_id is not None:
            query += " AND e.research_question_id = %s"
            params.append(research_question_id)

        if min_rating is not None:
            query += " AND e.rating >= %s"
            params.append(min_rating)

        if human_only:
            query += " AND e.is_human_evaluator = TRUE"

        query += " ORDER BY e.research_question_id, e.rating DESC, e.confidence_level DESC"

        result = self.execute(query, tuple(params))
        return result or []

    def get_evaluations_by_chunk(
        self,
        chunk_id: int,
        research_question_id: Optional[int] = None,
        min_rating: Optional[int] = None,
        human_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get evaluations for a specific chunk.

        Args:
            chunk_id: ID of the chunk
            research_question_id: Optional research question ID to filter by
            min_rating: Optional minimum rating to filter by
            human_only: If True, only return evaluations by human evaluators

        Returns:
            List of evaluation data dictionaries
        """
        query = """
        SELECT e.*, ev.name as evaluator_name, rq.question as research_question
        FROM evaluations e
        JOIN evaluators ev ON e.evaluator_id = ev.id
        JOIN research_questions rq ON e.research_question_id = rq.id
        WHERE e.chunk_id = %s
        """

        params = [chunk_id]

        if research_question_id is not None:
            query += " AND e.research_question_id = %s"
            params.append(research_question_id)

        if min_rating is not None:
            query += " AND e.rating >= %s"
            params.append(min_rating)

        if human_only:
            query += " AND e.is_human_evaluator = TRUE"

        query += " ORDER BY e.research_question_id, e.rating DESC, e.confidence_level DESC"

        result = self.execute(query, tuple(params))
        return result or []

    def get_evaluations_by_evaluator(
        self,
        evaluator_id: int,
        research_question_id: Optional[int] = None,
        min_rating: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get evaluations by a specific evaluator.

        Args:
            evaluator_id: ID of the evaluator
            research_question_id: Optional research question ID to filter by
            min_rating: Optional minimum rating to filter by
            limit: Optional limit on the number of results
            offset: Optional offset for pagination

        Returns:
            List of evaluation data dictionaries
        """
        query = """
        SELECT e.*, c.text as chunk_text, c.document_title, rq.question as research_question
        FROM evaluations e
        JOIN chunks c ON e.chunk_id = c.id
        JOIN research_questions rq ON e.research_question_id = rq.id
        WHERE e.evaluator_id = %s
        """

        params = [evaluator_id]

        if research_question_id is not None:
            query += " AND e.research_question_id = %s"
            params.append(research_question_id)

        if min_rating is not None:
            query += " AND e.rating >= %s"
            params.append(min_rating)

        query += " ORDER BY e.research_question_id, e.rating DESC, e.confidence_level DESC"

        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        if offset is not None:
            query += " OFFSET %s"
            params.append(offset)

        result = self.execute(query, tuple(params))
        return result or []

    def update_evaluation(
        self,
        research_question_id: int,
        chunk_id: int,
        evaluator_id: int,
        rating: Optional[int] = None,
        confidence_level: Optional[float] = None,
        rating_reason: Optional[str] = None
    ) -> bool:
        """
        Update an existing evaluation.

        Args:
            research_question_id: ID of the research question
            chunk_id: ID of the document chunk
            evaluator_id: ID of the evaluator
            rating: New rating value (0-5)
            confidence_level: New confidence level (0.0-1.0)
            rating_reason: New explanation for the rating

        Returns:
            True if successful, False if failed
        """
        try:
            # Build the update query dynamically based on provided parameters
            update_parts = []
            params = []

            if rating is not None:
                # Validate rating range
                if not 0 <= rating <= 5:
                    logger.error(f"Invalid rating value: {rating}. Must be between 0 and 5.")
                    return False
                update_parts.append("rating = %s")
                params.append(rating)

            if confidence_level is not None:
                # Validate confidence level range
                if not 0.0 <= confidence_level <= 1.0:
                    logger.error(f"Invalid confidence level: {confidence_level}. Must be between 0.0 and 1.0.")
                    return False
                update_parts.append("confidence_level = %s")
                params.append(confidence_level)

            if rating_reason is not None:
                update_parts.append("rating_reason = %s")
                params.append(rating_reason)

            if not update_parts:
                logger.warning("No fields to update in evaluation")
                return False

            query = f"""
            UPDATE evaluations
            SET {", ".join(update_parts)}
            WHERE research_question_id = %s AND chunk_id = %s AND evaluator_id = %s
            """

            params.extend([research_question_id, chunk_id, evaluator_id])

            result = self.execute(query, tuple(params), commit=True)
            return result is not None

        except Exception as e:
            logger.error(f"Error updating evaluation: {e}")
            return False

    def delete_evaluation(
        self,
        research_question_id: int,
        chunk_id: int,
        evaluator_id: int
    ) -> bool:
        """
        Delete an evaluation.

        Args:
            research_question_id: ID of the research question
            chunk_id: ID of the document chunk
            evaluator_id: ID of the evaluator

        Returns:
            True if successful, False if failed
        """
        try:
            query = """
            DELETE FROM evaluations
            WHERE research_question_id = %s AND chunk_id = %s AND evaluator_id = %s
            """

            self.execute(query, (research_question_id, chunk_id, evaluator_id), commit=True)
            return True

        except Exception as e:
            logger.error(f"Error deleting evaluation: {e}")
            return False

    def get_evaluation_stats_by_question(
        self,
        research_question_id: int
    ) -> Dict[str, Any]:
        """
        Get statistics about evaluations for a specific research question.

        Args:
            research_question_id: ID of the research question

        Returns:
            Dictionary with statistics
        """
        query = """
        SELECT
            COUNT(*) as total_evaluations,
            AVG(rating) as average_rating,
            AVG(confidence_level) as average_confidence,
            COUNT(DISTINCT document_id) as unique_documents,
            COUNT(DISTINCT chunk_id) as unique_chunks,
            COUNT(DISTINCT evaluator_id) as unique_evaluators,
            SUM(CASE WHEN is_human_evaluator THEN 1 ELSE 0 END) as human_evaluations,
            SUM(CASE WHEN NOT is_human_evaluator THEN 1 ELSE 0 END) as ai_evaluations
        FROM evaluations
        WHERE research_question_id = %s
        """

        result = self.execute(query, (research_question_id,))

        if result and len(result) > 0:
            return result[0]
        return {
            "total_evaluations": 0,
            "average_rating": 0,
            "average_confidence": 0,
            "unique_documents": 0,
            "unique_chunks": 0,
            "unique_evaluators": 0,
            "human_evaluations": 0,
            "ai_evaluations": 0
        }

    def get_top_rated_chunks_for_question(
        self,
        research_question_id: int,
        min_rating: int = 3,
        limit: int = 10,
        human_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get the top-rated chunks for a specific research question.

        Args:
            research_question_id: ID of the research question
            min_rating: Minimum rating to include
            limit: Maximum number of results to return
            human_only: If True, only consider evaluations by human evaluators

        Returns:
            List of chunk data with evaluation information
        """
        query = """
        SELECT
            e.chunk_id, e.document_id, c.text as chunk_text, c.document_title,
            AVG(e.rating) as average_rating,
            AVG(e.confidence_level) as average_confidence,
            COUNT(e.evaluator_id) as evaluator_count,
            STRING_AGG(ev.name, ', ' ORDER BY e.rating DESC) as evaluators
        FROM evaluations e
        JOIN chunks c ON e.chunk_id = c.id
        JOIN evaluators ev ON e.evaluator_id = ev.id
        WHERE e.research_question_id = %s AND e.rating >= %s
        """

        params = [research_question_id, min_rating]

        if human_only:
            query += " AND e.is_human_evaluator = TRUE"

        query += """
        GROUP BY e.chunk_id, e.document_id, c.text, c.document_title
        ORDER BY average_rating DESC, average_confidence DESC
        LIMIT %s
        """

        params.append(limit)

        result = self.execute(query, tuple(params))
        return result or []

    def get_document_relevance_for_question(
        self,
        research_question_id: int,
        document_id: int
    ) -> Dict[str, Any]:
        """
        Get the overall relevance of a document for a specific research question.

        Args:
            research_question_id: ID of the research question
            document_id: ID of the document

        Returns:
            Dictionary with relevance information
        """
        query = """
        SELECT
            AVG(e.rating) as average_rating,
            MAX(e.rating) as max_rating,
            AVG(e.confidence_level) as average_confidence,
            COUNT(DISTINCT e.chunk_id) as evaluated_chunks,
            COUNT(DISTINCT e.evaluator_id) as evaluator_count,
            SUM(CASE WHEN e.is_human_evaluator THEN 1 ELSE 0 END) as human_evaluations,
            SUM(CASE WHEN NOT e.is_human_evaluator THEN 1 ELSE 0 END) as ai_evaluations
        FROM evaluations e
        WHERE e.research_question_id = %s AND e.document_id = %s
        """

        result = self.execute(query, (research_question_id, document_id))

        if result and len(result) > 0:
            return result[0]
        return {
            "average_rating": 0,
            "max_rating": 0,
            "average_confidence": 0,
            "evaluated_chunks": 0,
            "evaluator_count": 0,
            "human_evaluations": 0,
            "ai_evaluations": 0
        }

    def documents_by_rating_for_question(
        self,
        rating: int,
        question_id: int,
        evaluator_id: Optional[int] = None
    ) -> List[int]:
        """
        Get all unique document IDs that have at least one chunk with the specified rating
        for the given research question.

        Args:
            rating: The exact rating value to filter by (0-5)
            question_id: ID of the research question
            evaluator_id: Optional ID of the evaluator to filter by

        Returns:
            List of unique document IDs
        """
        try:
            # Validate rating range
            if not 0 <= rating <= 5:
                logger.error(f"Invalid rating value: {rating}. Must be between 0 and 5.")
                return []

            query = """
            SELECT DISTINCT document_id
            FROM evaluations
            WHERE research_question_id = %s AND rating = %s
            """

            params = [question_id, rating]

            if evaluator_id is not None:
                query += " AND evaluator_id = %s"
                params.append(evaluator_id)

            query += " ORDER BY document_id"

            result = self.execute(query, tuple(params))

            if not result:
                return []

            # Extract just the document IDs into a list
            return [row['document_id'] for row in result]

        except Exception as e:
            logger.error(f"Error getting documents by rating: {e}")
            return []

    def get_evaluations_by_batch(
        self,
        batch_size: int = 100,
        offset: int = 0
    ) -> Iterator[Dict[str, Any]]:
        """
        Get evaluations in batches for efficient processing of large datasets.

        Args:
            batch_size: Number of evaluations to retrieve per batch
            offset: Starting offset

        Returns:
            Iterator of evaluation data dictionaries
        """
        current_offset = offset

        while True:
            query = """
            SELECT e.*, c.text as chunk_text, c.document_title,
                   ev.name as evaluator_name, rq.question as research_question
            FROM evaluations e
            JOIN chunks c ON e.chunk_id = c.id
            JOIN evaluators ev ON e.evaluator_id = ev.id
            JOIN research_questions rq ON e.research_question_id = rq.id
            ORDER BY e.research_question_id, e.document_id, e.chunk_id
            LIMIT %s OFFSET %s
            """

            result = self.execute(query, (batch_size, current_offset))

            if not result:
                break

            for row in result:
                yield row

            if len(result) < batch_size:
                break

            current_offset += batch_size
