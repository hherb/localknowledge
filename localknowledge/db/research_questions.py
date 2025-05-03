"""
Research questions management database functionality for the LocalKnowledge library.

This module provides database operations for managing research questions
and their associations with projects.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class ResearchQuestionsManager(DatabaseManager):
    """Database manager for research questions and project associations."""

    def __init__(self):
        """Initialize the research questions database manager."""
        super().__init__()

    def create_question(self, question: str, details: Optional[str] = None) -> Optional[int]:
        """
        Create a new research question in the database.

        Args:
            question: The research question text
            details: Optional additional details or context for the question

        Returns:
            Question ID if successful, None if failed
        """
        try:
            query = """
            INSERT INTO research_questions (question, details)
            VALUES (%s, %s)
            RETURNING id
            """
            result = self.execute(query, (question, details), commit=True)

            if result and len(result) > 0:
                return result[0]['id']
            return None
        except Exception as e:
            print(f"Error creating research question: {e}")
            return None

    def get_question(self, question_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a research question by ID.

        Args:
            question_id: Research question ID

        Returns:
            Research question data if found, None otherwise
        """
        query = """
        SELECT *
        FROM research_questions
        WHERE id = %s
        """
        result = self.execute(query, (question_id,))

        if result and len(result) > 0:
            return result[0]
        return None

    def update_question(self, question_id: int, data: Dict[str, Any]) -> bool:
        """
        Update a research question.

        Args:
            question_id: Research question ID
            data: Dictionary containing fields to update (question, details)

        Returns:
            True if successful, False otherwise
        """
        try:
            allowed_fields = ['question', 'details']
            update_fields = []
            params = []

            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    params.append(data[field])

            if not update_fields:
                return False

            query = f"""
            UPDATE research_questions
            SET {", ".join(update_fields)}
            WHERE id = %s
            """
            params.append(question_id)

            self.execute(query, tuple(params), commit=True)
            return True
        except Exception as e:
            print(f"Error updating research question: {e}")
            return False

    def delete_question(self, question_id: int) -> bool:
        """
        Delete a research question.

        Args:
            question_id: Research question ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM research_questions WHERE id = %s", (question_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting research question: {e}")
            return False

    def associate_with_project(self, question_id: int, project_id: int, is_active: bool = True) -> bool:
        """
        Associate a research question with a project.

        Args:
            question_id: Research question ID
            project_id: Project ID
            is_active: Whether the question is active for the project (default: True)

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT INTO project_research_questions (project_id, question_id, is_active)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, question_id) DO UPDATE SET is_active = EXCLUDED.is_active
            """
            self.execute(query, (project_id, question_id, is_active), commit=True)
            return True
        except Exception as e:
            print(f"Error associating research question with project: {e}")
            return False

    def remove_from_project(self, question_id: int, project_id: int) -> bool:
        """
        Remove a research question from a project.

        Args:
            question_id: Research question ID
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            DELETE FROM project_research_questions
            WHERE project_id = %s AND question_id = %s
            """
            self.execute(query, (project_id, question_id), commit=True)
            return True
        except Exception as e:
            print(f"Error removing research question from project: {e}")
            return False

    def get_project_questions(self, project_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all research questions associated with a project.

        Args:
            project_id: Project ID
            active_only: If True, only return active questions (default: True)

        Returns:
            List of research question data dictionaries
        """
        if active_only:
            query = """
            SELECT rq.*, prq.is_active
            FROM research_questions rq
            JOIN project_research_questions prq ON rq.id = prq.question_id
            WHERE prq.project_id = %s AND prq.is_active = TRUE
            ORDER BY rq.id
            """
        else:
            query = """
            SELECT rq.*, prq.is_active
            FROM research_questions rq
            JOIN project_research_questions prq ON rq.id = prq.question_id
            WHERE prq.project_id = %s
            ORDER BY rq.id
            """
        result = self.execute(query, (project_id,))
        return result or []

    def get_projects_for_question(self, question_id: int, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all projects associated with a research question.

        Args:
            question_id: Research question ID
            active_only: If True, only return projects where the question is active (default: False)

        Returns:
            List of project data dictionaries
        """
        if active_only:
            query = """
            SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
                   u.surname as manager_surname, prq.is_active
            FROM projects p
            JOIN project_research_questions prq ON p.id = prq.project_id
            LEFT JOIN users u ON p.manager_id = u.id
            WHERE prq.question_id = %s AND prq.is_active = TRUE
            ORDER BY p.last_worked_on DESC
            """
        else:
            query = """
            SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
                   u.surname as manager_surname, prq.is_active
            FROM projects p
            JOIN project_research_questions prq ON p.id = prq.project_id
            LEFT JOIN users u ON p.manager_id = u.id
            WHERE prq.question_id = %s
            ORDER BY p.last_worked_on DESC
            """
        result = self.execute(query, (question_id,))
        return result or []

    def get_all_questions(self) -> List[Dict[str, Any]]:
        """
        Get all research questions from the database.

        Returns:
            List of research question data dictionaries
        """
        query = """
        SELECT *
        FROM research_questions
        ORDER BY id
        """
        result = self.execute(query)
        return result or []

    def search_questions(self, search_term: str, project_id: Optional[int] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Search for research questions by content.

        Args:
            search_term: Search term
            project_id: Optional project ID to limit results to questions associated with a specific project
            active_only: If True and project_id is provided, only return active questions (default: True)

        Returns:
            List of research question data dictionaries
        """
        if project_id is not None:
            # Search only questions associated with the specified project
            if active_only:
                query = """
                SELECT rq.*, prq.is_active
                FROM research_questions rq
                JOIN project_research_questions prq ON rq.id = prq.question_id
                WHERE prq.project_id = %s AND prq.is_active = TRUE
                AND (rq.question ILIKE %s OR rq.details ILIKE %s)
                ORDER BY rq.id
                """
            else:
                query = """
                SELECT rq.*, prq.is_active
                FROM research_questions rq
                JOIN project_research_questions prq ON rq.id = prq.question_id
                WHERE prq.project_id = %s
                AND (rq.question ILIKE %s OR rq.details ILIKE %s)
                ORDER BY rq.id
                """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (project_id, search_pattern, search_pattern))
        else:
            # Search all research questions
            query = """
            SELECT rq.*
            FROM research_questions rq
            WHERE rq.question ILIKE %s OR rq.details ILIKE %s
            ORDER BY rq.id
            """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (search_pattern, search_pattern))

        return result or []

    def get_question_statistics(self, question_id: int, project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics for a research question.

        Args:
            question_id: Research question ID
            project_id: Optional project ID to limit statistics to a specific project

        Returns:
            Dictionary with statistics including:
            - bookmark_count: Number of bookmarks for this question
            - evaluation_count: Number of evaluations for this question
            - human_evaluation_count: Number of human evaluations for this question
        """
        try:
            # Get bookmark count for this project
            if project_id is not None:
                bookmark_query = """
                SELECT COUNT(DISTINCT b.id) as bookmark_count
                FROM bookmarks b
                WHERE b.project_id = %s
                """
                bookmark_result = self.execute(bookmark_query, (project_id,))
                bookmark_count = bookmark_result[0]['bookmark_count'] if bookmark_result else 0
            else:
                bookmark_count = 0

            # Get evaluation counts
            eval_query = """
            SELECT
                COUNT(*) as evaluation_count,
                SUM(CASE WHEN is_human_evaluator THEN 1 ELSE 0 END) as human_evaluation_count
            FROM evaluations
            WHERE research_question_id = %s
            """

            # Add project filter if provided
            params = [question_id]

            eval_result = self.execute(eval_query, tuple(params))

            evaluation_count = 0
            human_evaluation_count = 0

            if eval_result:
                evaluation_count = eval_result[0]['evaluation_count'] or 0
                human_evaluation_count = eval_result[0]['human_evaluation_count'] or 0

            return {
                'bookmark_count': bookmark_count,
                'evaluation_count': evaluation_count,
                'human_evaluation_count': human_evaluation_count
            }
        except Exception as e:
            logger.error(f"Error getting question statistics: {e}")
            return {
                'bookmark_count': 0,
                'evaluation_count': 0,
                'human_evaluation_count': 0
            }
