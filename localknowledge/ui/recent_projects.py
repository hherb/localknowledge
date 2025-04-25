"""
Recent projects widget for displaying recent projects in a grid layout.

This module provides a widget for displaying recent projects in a grid layout
with project cards.
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QPushButton, QFrame, QApplication, QSizePolicy
)

from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.context import get_context, CURRENT_USER, register_context_listener


class ProjectCard(QFrame):
    """Card widget for displaying a project summary."""

    clicked = Signal(int)  # Signal emitted when the card is clicked

    def __init__(self, project: Dict[str, Any], parent=None):
        """
        Initialize the project card.

        Args:
            project: Project data dictionary
            parent: Parent widget
        """
        super().__init__(parent)

        # Store the project data
        self.project = project
        self.project_id = project['id']

        # Set up the UI
        self.setup_ui()

        # Make the card clickable
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)

        # Set minimum size
        self.setMinimumSize(200, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Style the card
        self.setStyleSheet("""
            ProjectCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
            }
            ProjectCard:hover {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
            }
        """)

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Project title
        title = self.project['title']
        if len(title) > 30:
            title = title[:27] + "..."

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Project description
        description = self.project.get('description', '')
        if description:
            if len(description) > 100:
                description = description[:97] + "..."

            desc_label = QLabel(description)
            desc_label.setStyleSheet("font-size: 10px; color: #505050;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Format the last_worked_on date for display
        last_worked_on_str = "Never"
        if self.project.get('last_worked_on'):
            if isinstance(self.project['last_worked_on'], str):
                try:
                    last_worked_on = datetime.fromisoformat(self.project['last_worked_on'])
                    last_worked_on_str = last_worked_on.strftime("%Y-%m-%d")
                except ValueError:
                    last_worked_on_str = self.project['last_worked_on']
            else:
                last_worked_on_str = self.project['last_worked_on'].strftime("%Y-%m-%d")

        # Project metadata
        meta_label = QLabel(f"Last worked on: {last_worked_on_str}")
        meta_label.setStyleSheet("font-size: 9px; color: #808080;")
        layout.addWidget(meta_label)

        # Add stretch to push everything to the top
        layout.addStretch(1)

    def mousePressEvent(self, event):
        """
        Handle mouse press event.

        Args:
            event: Mouse event
        """
        super().mousePressEvent(event)
        self.clicked.emit(self.project_id)


class RecentProjectsWidget(QWidget):
    """Widget for displaying recent projects in a grid layout."""

    projectSelected = Signal(int)  # Signal emitted when a project is selected

    def __init__(self, parent=None):
        """Initialize the recent projects widget."""
        super().__init__(parent)

        # Set up the database manager
        self.db_manager = ProjectDatabaseManager()

        # Maximum number of projects to display
        self.max_projects = 4

        # Set up the UI
        self.setup_ui()

        # Register for context updates
        register_context_listener(CURRENT_USER, self._on_user_changed)

        # Load projects for current user if available
        current_user = get_context(CURRENT_USER)
        if current_user and 'id' in current_user:
            self.load_projects(current_user['id'])

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("Recent projects:")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Grid layout for project cards
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(10)
        layout.addLayout(self.grid_layout)

        # Add stretch to push everything to the top
        layout.addStretch(1)

    def load_projects(self, user_id: int = None):
        """
        Load recent projects from the database.

        Args:
            user_id: Optional user ID to filter projects
        """
        # Clear the grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if user_id:
            # Load projects for the specified user
            projects = self.db_manager.get_all_user_projects(user_id)
        else:
            # Load all projects
            projects = self.db_manager.execute("SELECT * FROM projects ORDER BY last_worked_on DESC")

        # Limit to max_projects
        projects = projects[:self.max_projects] if projects else []

        # Add project cards to the grid
        for i, project in enumerate(projects):
            # Calculate row and column
            row = i // 2  # 2 columns
            col = i % 2

            # Create project card
            card = ProjectCard(project)
            card.clicked.connect(self.projectSelected)
            card.setStyleSheet("""
                ProjectCard {
                    background-color: #e6f2ff;
                    border: 1px solid #c0d9ff;
                    border-radius: 5px;
                }
                ProjectCard:hover {
                    background-color: #d9ebff;
                    border: 1px solid #a3c2ff;
                }
            """)

            # Add to grid
            self.grid_layout.addWidget(card, row, col)

        # If no projects, add a message
        if not projects:
            message = QLabel("No recent projects found.")
            message.setStyleSheet("font-style: italic; color: #808080;")
            self.grid_layout.addWidget(message, 0, 0, 1, 2)

    def _on_user_changed(self, user: Dict[str, Any]):
        """
        Handle user changed event.

        Args:
            user: New user data
        """
        if user and 'id' in user:
            self.load_projects(user['id'])


# For testing
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the recent projects widget
    recent_projects = RecentProjectsWidget()
    layout.addWidget(recent_projects)

    # Load projects
    recent_projects.load_projects()

    # Show the window
    window.setGeometry(100, 100, 800, 400)
    window.show()

    sys.exit(app.exec())
