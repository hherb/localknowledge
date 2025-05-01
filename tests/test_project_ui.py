#!/usr/bin/env python3
"""
Test script for the Project UI components.

This script tests the ProjectDetailWidget, HypothesisWidget, and ResearchQuestionWidget
classes in a standalone application.
"""

import sys
import os

# Add the parent directory to the path so we can import localknowledge
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from localknowledge.ui.project_detail_widget import ProjectDetailWidget
from localknowledge.ui.hypothesis_widget import HypothesisWidget
from localknowledge.ui.research_question_widget import ResearchQuestionWidget
from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.context import set_current_user, set_current_project


class TestWindow(QMainWindow):
    """Test window for the Project UI components."""

    def __init__(self):
        """Initialize the test window."""
        super().__init__()

        self.setWindowTitle("Project UI Test")
        self.resize(1000, 800)

        # Create a tab widget to test different components
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Create tabs for each component
        self.setup_project_detail_tab()
        self.setup_hypothesis_tab()
        self.setup_research_question_tab()

        # Set up test data
        self.setup_test_data()

    def setup_project_detail_tab(self):
        """Set up the project detail tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Create the project detail widget
        self.project_detail = ProjectDetailWidget()
        layout.addWidget(self.project_detail)

        self.tab_widget.addTab(tab, "Project Detail")

    def setup_hypothesis_tab(self):
        """Set up the hypothesis tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Create the hypothesis widget
        self.hypothesis_widget = HypothesisWidget()
        layout.addWidget(self.hypothesis_widget)

        self.tab_widget.addTab(tab, "Hypothesis")

    def setup_research_question_tab(self):
        """Set up the research question tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Create the research question widget
        self.research_question_widget = ResearchQuestionWidget()
        layout.addWidget(self.research_question_widget)

        self.tab_widget.addTab(tab, "Research Questions")

    def setup_test_data(self):
        """Set up test data for the UI components."""
        # Create database managers
        self.user_db = UserDatabaseManager()
        self.project_db = ProjectDatabaseManager()

        # Get or create a test user
        try:
            # Try to get the user 'hherb' first
            result = self.user_db.execute("SELECT id FROM users WHERE username = %s", ("hherb",))
            if result and len(result) > 0:
                self.user_id = result[0]['id']
            else:
                # Try to create a test user
                self.user_id = self.user_db.create_user(
                    username="test_user",
                    firstname="Test",
                    surname="User",
                    email="test@example.com",
                    password="password123"
                )
        except Exception as e:
            print(f"Error getting/creating user: {e}")
            # Use a default user ID as fallback
            self.user_id = 1

        # Set the current user in the context
        # Create a user dictionary as expected by the context system
        user_data = self.user_db.get_user(self.user_id)
        if user_data:
            set_current_user(user_data)
        else:
            # Fallback to just the ID if we can't get the user data
            set_current_user({'id': self.user_id})

        # Create a test project if needed
        try:
            # Check if we already have a test project
            result = self.project_db.execute(
                "SELECT id FROM projects WHERE title = %s",
                ("Test Project for UI",)
            )

            if result and len(result) > 0:
                self.project_id = result[0]['id']
            else:
                # Create a new test project
                self.project_id = self.project_db.create_project(
                    title="Test Project for UI",
                    description="This is a test project for the UI components",
                    manager_id=self.user_id
                )
        except Exception as e:
            print(f"Error getting/creating project: {e}")
            # Use a default project ID as fallback
            self.project_id = 1

        # Set the current project in the context
        set_current_project(self.project_id)

        # Load the project in each widget
        self.project_detail.load_project(self.project_id)
        self.hypothesis_widget.load_project(self.project_id)
        self.research_question_widget.load_project(self.project_id)

        print(f"Test setup complete. User ID: {self.user_id}, Project ID: {self.project_id}")


def main():
    """Main function to run the test."""
    app = QApplication(sys.argv)

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
