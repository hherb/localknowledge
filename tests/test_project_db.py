"""
Test script for the ProjectDatabaseManager.

This script tests the basic functionality of the ProjectDatabaseManager class.
It assumes that migration 003_add_project_management has been applied.
"""
import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.db.migrations_system import MigrationsManager


def test_project_management():
    """Test basic project management functionality."""
    # Ensure migrations are up to date
    migrations_manager = MigrationsManager()
    current_version = migrations_manager.get_current_version()
    print(f"Current database version: {current_version}")

    if current_version < 3:
        print("Running pending migrations...")
        success = migrations_manager.run_pending_migrations()
        if success:
            print(f"Migrations completed successfully. New database version: {migrations_manager.get_current_version()}")
        else:
            print("Migration process failed")
            return

    # Create database managers
    user_db = UserDatabaseManager()
    project_db = ProjectDatabaseManager()

    # Create test users if they don't exist
    try:
        manager_id = user_db.create_user(
            username="test_manager",
            firstname="Test",
            surname="Manager",
            email="test_manager@example.com",
            password="password123"
        )
    except ValueError:
        # User already exists, get the ID
        result = user_db.execute("SELECT id FROM users WHERE username = %s", ("test_manager",))
        manager_id = result[0]['id'] if result else None

    try:
        contributor_id = user_db.create_user(
            username="test_contributor",
            firstname="Test",
            surname="Contributor",
            email="test_contributor@example.com",
            password="password123"
        )
    except ValueError:
        # User already exists, get the ID
        result = user_db.execute("SELECT id FROM users WHERE username = %s", ("test_contributor",))
        contributor_id = result[0]['id'] if result else None

    if not manager_id or not contributor_id:
        print("Failed to create or retrieve test users")
        return

    # Create a test project
    project_id = project_db.create_project(
        title="Test Project",
        description="This is a test project for the ProjectDatabaseManager",
        manager_id=manager_id
    )

    if not project_id:
        print("Failed to create test project")
        return

    print(f"Created project with ID: {project_id}")

    # Get the project
    project = project_db.get_project(project_id)
    print(f"Retrieved project: {project['title']} - {project['description']}")

    # Update the project
    update_success = project_db.update_project(
        project_id=project_id,
        data={
            "title": "Updated Test Project",
            "description": "This project has been updated"
        }
    )

    if update_success:
        print("Project updated successfully")
    else:
        print("Failed to update project")

    # Get the updated project
    updated_project = project_db.get_project(project_id)
    print(f"Updated project: {updated_project['title']} - {updated_project['description']}")

    # Add a contributor
    add_success = project_db.add_contributor(project_id, contributor_id)
    if add_success:
        print(f"Added contributor with ID {contributor_id} to project")
    else:
        print("Failed to add contributor")

    # Get contributors
    contributors = project_db.get_contributors(project_id)
    print(f"Project has {len(contributors)} contributors:")
    for contributor in contributors:
        print(f"  - {contributor['username']} ({contributor['firstname']} {contributor['surname']})")

    # Get projects by manager
    manager_projects = project_db.get_projects_by_manager(manager_id)
    print(f"Manager has {len(manager_projects)} projects")

    # Get projects by contributor
    contributor_projects = project_db.get_projects_by_contributor(contributor_id)
    print(f"Contributor has {len(contributor_projects)} projects")

    # Get all user projects
    all_projects = project_db.get_all_user_projects(contributor_id)
    print(f"User has access to {len(all_projects)} projects")

    # Search for projects
    search_results = project_db.search_projects("test")
    print(f"Found {len(search_results)} projects matching 'test'")

    # Clean up (uncomment to delete the test project)
    # delete_success = project_db.delete_project(project_id)
    # if delete_success:
    #     print("Project deleted successfully")
    # else:
    #     print("Failed to delete project")


if __name__ == "__main__":
    test_project_management()
