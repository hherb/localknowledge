"""
Project detail widget for displaying and managing project details.

This module provides a widget for displaying project details, hypotheses,
and research questions.
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot, QSize, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QScrollArea, QFrame, QSplitter, QTextEdit, QLineEdit, QMessageBox,
    QSizePolicy
)
from PySide6.QtGui import QFont

from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.db.hypotheses import HypothesesDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.context import (
    get_context, set_context, register_context_listener,
    CURRENT_USER, CURRENT_PROJECT
)

from localknowledge.ui.hypothesis_widget import HypothesisWidget
from localknowledge.ui.research_question_widget import ResearchQuestionWidget
from localknowledge.ui.bookmark_widget import BookmarkWidget


class ProjectDetailWidget(QWidget):
    """Widget for displaying and managing project details."""

    # Signal emitted when project details are updated
    projectUpdated = Signal(int)

    def __init__(self, parent=None):
        """Initialize the project detail widget."""
        super().__init__(parent)

        # Set up database managers
        self.project_db = ProjectDatabaseManager()
        self.hypotheses_db = HypothesesDatabaseManager()
        self.questions_db = ResearchQuestionsManager()
        self.user_db = UserDatabaseManager()

        # Current project ID and user ID
        self.project_id = None
        self.project_data = None
        self.user_id = None

        # Get current user from context
        current_user = get_context(CURRENT_USER)
        if current_user and isinstance(current_user, dict):
            self.user_id = current_user.get('id')

        # Settings for saving UI state
        self.settings = QSettings("LocalKnowledge", "ProjectDetailWidget")

        # Set up the UI
        self.setup_ui()

        # Register for context updates
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)
        register_context_listener(CURRENT_USER, self._on_user_changed)

        # Load current project if available
        current_project = get_context(CURRENT_PROJECT)
        if current_project:
            self.load_project(current_project)

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Project header
        self.header_widget = QWidget()
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)

        # Project title
        self.title_layout = QHBoxLayout()
        self.title_label = QLabel("Manage current project (title)")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title_layout.addWidget(self.title_label)

        # Edit project details button
        self.edit_button = QPushButton("Edit project details")
        self.edit_button.clicked.connect(self._on_edit_project)
        self.title_layout.addWidget(self.edit_button)

        header_layout.addLayout(self.title_layout)

        # Add header to main layout
        layout.addWidget(self.header_widget)

        # Main vertical splitter between hypothesis and tabs
        self.main_splitter = QSplitter(Qt.Vertical)
        layout.addWidget(self.main_splitter)

        # Hypothesis section
        self.hypothesis_widget = HypothesisWidget()
        self.main_splitter.addWidget(self.hypothesis_widget)

        # Container for tabs
        tabs_container = QWidget()
        tabs_layout = QVBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)

        # Tab widget for questions, bookmarks, citations, drafts
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)  # Cleaner look
        tabs_layout.addWidget(self.tab_widget)

        # Add tabs container to splitter
        self.main_splitter.addWidget(tabs_container)

        # Questions tab
        self.questions_tab = QWidget()
        questions_layout = QVBoxLayout(self.questions_tab)
        questions_layout.setContentsMargins(0, 0, 0, 0)

        # Research questions widget
        self.questions_widget = ResearchQuestionWidget()
        questions_layout.addWidget(self.questions_widget)

        self.tab_widget.addTab(self.questions_tab, "Questions")

        # Bookmarks tab
        self.bookmarks_tab = QWidget()
        bookmarks_layout = QVBoxLayout(self.bookmarks_tab)
        bookmarks_layout.setContentsMargins(0, 0, 0, 0)

        # Bookmarks widget
        self.bookmarks_widget = BookmarkWidget()
        bookmarks_layout.addWidget(self.bookmarks_widget)

        self.tab_widget.addTab(self.bookmarks_tab, "Bookmarks")

        # Citations tab (placeholder)
        self.citations_tab = QWidget()
        self.tab_widget.addTab(self.citations_tab, "Citations")

        # Drafts tab (placeholder)
        self.drafts_tab = QWidget()
        self.tab_widget.addTab(self.drafts_tab, "Drafts")

        # Set initial splitter sizes (1:3 ratio - hypothesis gets 1/4 of the space)
        self.main_splitter.setSizes([1, 3])

        # Load saved splitter state if available
        self.load_splitter_state()

    def load_project(self, project_id: int):
        """
        Load project data from the database.

        Args:
            project_id: Project ID
        """
        self.project_id = project_id
        self.project_data = self.project_db.get_project(project_id)

        if not self.project_data:
            self.title_label.setText("Project not found")
            return

        # Update UI with project data
        self.title_label.setText(f"Manage current project: {self.project_data['title']}")

        # Load hypotheses for this project
        self.hypothesis_widget.load_project(project_id)

        # Load research questions for this project
        self.questions_widget.load_project(project_id)

        # Load bookmarks for this project
        if self.user_id:
            self.bookmarks_widget.load_project(project_id, self.user_id)

        # Update last_worked_on timestamp
        self.project_db.update_project(project_id, {})

    def _on_project_changed(self, project_id: int):
        """
        Handle project changed event.

        Args:
            project_id: New project ID
        """
        if project_id:
            self.load_project(project_id)

    def _on_user_changed(self, user_data):
        """
        Handle user changed event.

        Args:
            user_data: New user data
        """
        if user_data and isinstance(user_data, dict):
            self.user_id = user_data.get('id')

            # Reload bookmarks if we have a project
            if self.project_id and self.user_id:
                self.bookmarks_widget.load_project(self.project_id, self.user_id)

    def _on_edit_project(self):
        """Handle edit project button click."""
        if not self.project_data:
            return

        # TODO: Implement project editing dialog
        QMessageBox.information(self, "Edit Project",
                               f"Editing project {self.project_data['title']} (ID: {self.project_id})")

    def save_splitter_state(self):
        """Save the splitter state to settings."""
        self.settings.setValue("main_splitter_state", self.main_splitter.saveState())

    def load_splitter_state(self):
        """Load the splitter state from settings."""
        state = self.settings.value("main_splitter_state")
        if state:
            self.main_splitter.restoreState(state)

    def closeEvent(self, event):
        """Handle close event to save splitter state."""
        self.save_splitter_state()
        super().closeEvent(event)


# For testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the project detail widget
    project_detail = ProjectDetailWidget()
    layout.addWidget(project_detail)

    # Set a test project ID
    project_detail.load_project(1)  # Assuming project ID 1 exists

    # Show the window
    window.setGeometry(100, 100, 800, 600)
    window.show()

    sys.exit(app.exec())
