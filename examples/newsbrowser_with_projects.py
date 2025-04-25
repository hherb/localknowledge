#!/usr/bin/env python3
"""
Example of using the NewsBrowser with project selection.

This example demonstrates how to integrate the NewsBrowser with project selection
to enable project-specific bookmarks.
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel

from localknowledge.ui.newsbrowser import NewsBrowserWindow
from localknowledge.db.project import ProjectDatabaseManager


class NewsBrowserWithProjects(QMainWindow):
    """Main window that combines NewsBrowser with project selection."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Set window properties
        self.setWindowTitle("News Browser with Projects")
        self.resize(1400, 900)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create project selection widget
        project_widget = QWidget()
        project_layout = QHBoxLayout(project_widget)
        project_layout.addWidget(QLabel("Select Project:"))

        # Create project combo box
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        project_layout.addWidget(self.project_combo)
        project_layout.addStretch(1)

        # Add project widget to main layout
        main_layout.addWidget(project_widget)

        # Create news browser
        self.news_browser = NewsBrowserWindow()
        main_layout.addWidget(self.news_browser)

        # Set layout margins
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Load projects
        self._load_projects()

    def _load_projects(self):
        """Load projects from the database."""
        try:
            # Create project database manager
            project_db = ProjectDatabaseManager()

            # Get all projects for the current user (using default user ID 1)
            user_id = 1
            projects = project_db.get_all_user_projects(user_id)

            # Add "No Project" option
            self.project_combo.addItem("No Project", None)

            # Add projects to combo box
            for project in projects:
                self.project_combo.addItem(project['title'], project['id'])

            # Close database connection
            project_db.close()

        except Exception as e:
            print(f"Error loading projects: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_changed(self, index):
        """Handle project selection change."""
        # Get selected project ID
        project_id = self.project_combo.itemData(index)

        # Update news browser with selected project
        self.news_browser.set_current_project(project_id)

        # Update status bar
        if project_id:
            project_title = self.project_combo.itemText(index)
            self.statusBar().showMessage(f"Selected project: {project_title}")
            # Update window title to include project name
            self.setWindowTitle(f"Publication News Browser - Project: {project_title} - User: Default User")
        else:
            self.statusBar().showMessage("No project selected")
            self.setWindowTitle("Publication News Browser - User: Default User")

    def closeEvent(self, event):
        """Handle window close event."""
        # Close the news browser
        self.news_browser.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NewsBrowserWithProjects()
    window.show()
    sys.exit(app.exec())
