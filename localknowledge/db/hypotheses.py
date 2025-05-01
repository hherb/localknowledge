"""
Hypotheses management database functionality for the LocalKnowledge library.

This module provides database operations for managing research hypotheses
and their associations with projects.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from localknowledge.db.base import DatabaseManager


class HypothesesDatabaseManager(DatabaseManager):
    """Database manager for hypotheses data and project associations."""

    def __init__(self):
        """Initialize the hypotheses database manager."""
        super().__init__()

    def create_hypothesis(self, hypothesis: str, counterhypothesis: Optional[str] = None) -> Optional[int]:
        """
        Create a new hypothesis in the database.

        Args:
            hypothesis: The main hypothesis statement
            counterhypothesis: Optional counter-hypothesis statement

        Returns:
            Hypothesis ID if successful, None if failed
        """
        try:
            query = """
            INSERT INTO hypotheses (hypothesis, counterhypothesis)
            VALUES (%s, %s)
            RETURNING id
            """
            result = self.execute(query, (hypothesis, counterhypothesis), commit=True)

            if result and len(result) > 0:
                return result[0]['id']
            return None
        except Exception as e:
            print(f"Error creating hypothesis: {e}")
            return None

    def get_hypothesis(self, hypothesis_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a hypothesis by ID.

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            Hypothesis data if found, None otherwise
        """
        query = """
        SELECT *
        FROM hypotheses
        WHERE id = %s
        """
        result = self.execute(query, (hypothesis_id,))

        if result and len(result) > 0:
            return result[0]
        return None

    def update_hypothesis(self, hypothesis_id: int, data: Dict[str, Any]) -> bool:
        """
        Update a hypothesis.

        Args:
            hypothesis_id: Hypothesis ID
            data: Dictionary containing fields to update (hypothesis, counterhypothesis)

        Returns:
            True if successful, False otherwise
        """
        try:
            allowed_fields = ['hypothesis', 'counterhypothesis']
            update_fields = []
            params = []
            
            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    params.append(data[field])
            
            if not update_fields:
                return False
            
            query = f"""
            UPDATE hypotheses
            SET {", ".join(update_fields)}
            WHERE id = %s
            """
            params.append(hypothesis_id)
            
            self.execute(query, tuple(params), commit=True)
            return True
        except Exception as e:
            print(f"Error updating hypothesis: {e}")
            return False

    def delete_hypothesis(self, hypothesis_id: int) -> bool:
        """
        Delete a hypothesis.

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM hypotheses WHERE id = %s", (hypothesis_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting hypothesis: {e}")
            return False

    def associate_with_project(self, hypothesis_id: int, project_id: int) -> bool:
        """
        Associate a hypothesis with a project.

        Args:
            hypothesis_id: Hypothesis ID
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT INTO hypotheses_projects (project_id, hypothesis_id)
            VALUES (%s, %s)
            ON CONFLICT (project_id, hypothesis_id) DO NOTHING
            """
            self.execute(query, (project_id, hypothesis_id), commit=True)
            return True
        except Exception as e:
            print(f"Error associating hypothesis with project: {e}")
            return False

    def remove_from_project(self, hypothesis_id: int, project_id: int) -> bool:
        """
        Remove a hypothesis from a project.

        Args:
            hypothesis_id: Hypothesis ID
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            DELETE FROM hypotheses_projects
            WHERE project_id = %s AND hypothesis_id = %s
            """
            self.execute(query, (project_id, hypothesis_id), commit=True)
            return True
        except Exception as e:
            print(f"Error removing hypothesis from project: {e}")
            return False

    def get_project_hypotheses(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get all hypotheses associated with a project.

        Args:
            project_id: Project ID

        Returns:
            List of hypothesis data dictionaries
        """
        query = """
        SELECT h.*
        FROM hypotheses h
        JOIN hypotheses_projects hp ON h.id = hp.hypothesis_id
        WHERE hp.project_id = %s
        ORDER BY h.created_at DESC
        """
        result = self.execute(query, (project_id,))
        return result or []

    def get_projects_for_hypothesis(self, hypothesis_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects associated with a hypothesis.

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            List of project data dictionaries
        """
        query = """
        SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
               u.surname as manager_surname
        FROM projects p
        JOIN hypotheses_projects hp ON p.id = hp.project_id
        LEFT JOIN users u ON p.manager_id = u.id
        WHERE hp.hypothesis_id = %s
        ORDER BY p.last_worked_on DESC
        """
        result = self.execute(query, (hypothesis_id,))
        return result or []

    def search_hypotheses(self, search_term: str, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for hypotheses by content.

        Args:
            search_term: Search term
            project_id: Optional project ID to limit results to hypotheses associated with a specific project

        Returns:
            List of hypothesis data dictionaries
        """
        if project_id is not None:
            # Search only hypotheses associated with the specified project
            query = """
            SELECT h.*
            FROM hypotheses h
            JOIN hypotheses_projects hp ON h.id = hp.hypothesis_id
            WHERE hp.project_id = %s
            AND (h.hypothesis ILIKE %s OR h.counterhypothesis ILIKE %s)
            ORDER BY h.created_at DESC
            """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (project_id, search_pattern, search_pattern))
        else:
            # Search all hypotheses
            query = """
            SELECT h.*
            FROM hypotheses h
            WHERE h.hypothesis ILIKE %s OR h.counterhypothesis ILIKE %s
            ORDER BY h.created_at DESC
            """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (search_pattern, search_pattern))

        return result or []
