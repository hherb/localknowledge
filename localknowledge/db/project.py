"""
Project management database functionality for the LocalKnowledge library.

This module provides database operations for managing research projects
and their contributors.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from localknowledge.db.base import DatabaseManager


class ProjectDatabaseManager(DatabaseManager):
    """Database manager for project data and contributors."""

    def __init__(self):
        """Initialize the project database manager."""
        super().__init__()

    def create_project(self, title: str, description: str, manager_id: int) -> Optional[int]:
        """
        Create a new project in the database.

        Args:
            title: Project title
            description: Project description
            manager_id: User ID of the project manager

        Returns:
            Project ID if successful, None if failed
        """
        try:
            query = """
            INSERT INTO projects (title, description, manager_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """
            result = self.execute(query, (title, description, manager_id), commit=True)

            if result and len(result) > 0:
                return result[0]['id']
            return None
        except Exception as e:
            print(f"Error creating project: {e}")
            return None

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project data if found, None otherwise
        """
        query = """
        SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
               u.surname as manager_surname
        FROM projects p
        LEFT JOIN users u ON p.manager_id = u.id
        WHERE p.id = %s
        """
        result = self.execute(query, (project_id,))

        if result and len(result) > 0:
            return result[0]
        return None

    def get_projects_by_manager(self, manager_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects managed by a specific user.

        Args:
            manager_id: User ID of the manager

        Returns:
            List of project data dictionaries
        """
        query = """
        SELECT p.*, COUNT(pc.user_id) as contributor_count
        FROM projects p
        LEFT JOIN project_contributors pc ON p.id = pc.project_id
        WHERE p.manager_id = %s
        GROUP BY p.id
        ORDER BY p.last_worked_on DESC
        """
        result = self.execute(query, (manager_id,))
        return result or []

    def get_projects_by_contributor(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects where a user is a contributor.

        Args:
            user_id: User ID

        Returns:
            List of project data dictionaries
        """
        query = """
        SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
               u.surname as manager_surname
        FROM projects p
        JOIN project_contributors pc ON p.id = pc.project_id
        LEFT JOIN users u ON p.manager_id = u.id
        WHERE pc.user_id = %s
        ORDER BY p.last_worked_on DESC
        """
        result = self.execute(query, (user_id,))
        return result or []

    def get_all_user_projects(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects where a user is either a manager or a contributor.

        Args:
            user_id: User ID

        Returns:
            List of project data dictionaries
        """
        query = """
        SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
               u.surname as manager_surname,
               CASE WHEN p.manager_id = %s THEN TRUE ELSE FALSE END as is_manager
        FROM projects p
        LEFT JOIN users u ON p.manager_id = u.id
        LEFT JOIN project_contributors pc ON p.id = pc.project_id
        WHERE p.manager_id = %s OR pc.user_id = %s
        GROUP BY p.id, u.username, u.firstname, u.surname
        ORDER BY p.last_worked_on DESC
        """
        result = self.execute(query, (user_id, user_id, user_id))
        return result or []

    def update_project(self, project_id: int, data: Dict[str, Any]) -> bool:
        """
        Update project data.

        Args:
            project_id: Project ID
            data: Dictionary with fields to update (title, description, manager_id)

        Returns:
            True if successful, False otherwise
        """
        try:
            allowed_fields = ['title', 'description', 'manager_id']
            update_fields = []
            params = []

            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    params.append(data[field])

            # Always update last_worked_on timestamp
            update_fields.append("last_worked_on = CURRENT_TIMESTAMP")

            if not update_fields:
                return False

            query = f"""
            UPDATE projects
            SET {", ".join(update_fields)}
            WHERE id = %s
            """
            params.append(project_id)

            self.execute(query, tuple(params), commit=True)
            return True
        except Exception as e:
            print(f"Error updating project: {e}")
            return False

    def update_last_worked_on(self, project_id: int) -> bool:
        """
        Update the last_worked_on timestamp for a project.

        Args:
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            UPDATE projects
            SET last_worked_on = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            self.execute(query, (project_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error updating project timestamp: {e}")
            return False

    def delete_project(self, project_id: int) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM projects WHERE id = %s", (project_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting project: {e}")
            return False

    def add_contributor(self, project_id: int, user_id: int) -> bool:
        """
        Add a contributor to a project.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT INTO project_contributors (project_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (project_id, user_id) DO NOTHING
            """
            self.execute(query, (project_id, user_id), commit=True)
            return True
        except Exception as e:
            print(f"Error adding contributor: {e}")
            return False

    def remove_contributor(self, project_id: int, user_id: int) -> bool:
        """
        Remove a contributor from a project.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            DELETE FROM project_contributors
            WHERE project_id = %s AND user_id = %s
            """
            self.execute(query, (project_id, user_id), commit=True)
            return True
        except Exception as e:
            print(f"Error removing contributor: {e}")
            return False

    def get_contributors(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get all contributors for a project.

        Args:
            project_id: Project ID

        Returns:
            List of user data dictionaries
        """
        query = """
        SELECT u.id, u.username, u.firstname, u.surname, u.email
        FROM users u
        JOIN project_contributors pc ON u.id = pc.user_id
        WHERE pc.project_id = %s
        ORDER BY u.username
        """
        result = self.execute(query, (project_id,))
        return result or []

    def search_projects(self, search_term: str, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for projects by title or description.

        Args:
            search_term: Search term
            user_id: Optional user ID to limit results to projects the user has access to

        Returns:
            List of project data dictionaries
        """
        if user_id is not None:
            # Search only projects the user has access to
            query = """
            SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
                   u.surname as manager_surname,
                   CASE WHEN p.manager_id = %s THEN TRUE ELSE FALSE END as is_manager
            FROM projects p
            LEFT JOIN users u ON p.manager_id = u.id
            LEFT JOIN project_contributors pc ON p.id = pc.project_id
            WHERE (p.title ILIKE %s OR p.description ILIKE %s)
            AND (p.manager_id = %s OR pc.user_id = %s)
            GROUP BY p.id, u.username, u.firstname, u.surname
            ORDER BY p.last_worked_on DESC
            """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (user_id, search_pattern, search_pattern, user_id, user_id))
        else:
            # Search all projects
            query = """
            SELECT p.*, u.username as manager_username, u.firstname as manager_firstname,
                   u.surname as manager_surname
            FROM projects p
            LEFT JOIN users u ON p.manager_id = u.id
            WHERE p.title ILIKE %s OR p.description ILIKE %s
            ORDER BY p.last_worked_on DESC
            """
            search_pattern = f"%{search_term}%"
            result = self.execute(query, (search_pattern, search_pattern))

        return result or []
