"""
Project creation form for creating and editing projects.

This module provides a form for creating and editing projects with
fields for title, description, and contributor selection.
"""
from typing import Dict, Any, List, Optional, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox, QScrollArea,
    QFrame, QApplication, QMessageBox, QComboBox
)

from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.context import get_context, CURRENT_USER, register_context_listener


class ContributorItem(QListWidgetItem):
    """List widget item for displaying user information."""

    def __init__(self, user: Dict[str, Any]):
        """
        Initialize the contributor item.

        Args:
            user: User data dictionary
        """
        super().__init__()
        self.user = user
        self.user_id = user['id']

        # Set the display text
        display_name = f"{user['firstname']} {user['surname']} ({user['username']})"
        self.setText(display_name)

        # Make the item checkable
        self.setFlags(self.flags() | Qt.ItemIsUserCheckable)
        self.setCheckState(Qt.Unchecked)


class ProjectForm(QWidget):
    """Form for creating and editing projects."""

    projectCreated = Signal(int)  # Signal emitted when a project is created

    def __init__(self, parent=None):
        """Initialize the project form."""
        super().__init__(parent)

        # Set up database managers
        self.project_db = ProjectDatabaseManager()
        self.user_db = UserDatabaseManager()

        # Current user ID (manager)
        self.manager_id = None

        # Set up the UI
        self.setup_ui()

        # Register for context updates
        register_context_listener(CURRENT_USER, self._on_user_changed)

        # Set manager ID from current user if available
        current_user = get_context(CURRENT_USER)
        if current_user and 'id' in current_user:
            self.set_manager_id(current_user['id'])

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("Create new project:")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Form layout
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # Project title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("New project name")
        form_layout.addWidget(self.title_edit)

        # Project description
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("A paragraph of text.\nA second row of text.")
        self.desc_edit.setMinimumHeight(150)
        form_layout.addWidget(self.desc_edit)

        # Contributors section
        contributors_layout = QHBoxLayout()

        # Contributors list
        contributors_container = QWidget()
        contributors_container_layout = QVBoxLayout(contributors_container)
        contributors_container_layout.setContentsMargins(0, 0, 0, 0)
        contributors_container_layout.setSpacing(5)

        contributors_label = QLabel("Contributors:")
        contributors_container_layout.addWidget(contributors_label)

        # Contributors dropdown and list
        self.contributors_combo = QComboBox()
        self.contributors_combo.setEditable(False)
        self.contributors_combo.setMinimumWidth(150)
        contributors_container_layout.addWidget(self.contributors_combo)

        self.contributors_list = QListWidget()
        self.contributors_list.setAlternatingRowColors(True)
        self.contributors_list.setMinimumHeight(150)
        contributors_container_layout.addWidget(self.contributors_list)

        contributors_layout.addWidget(contributors_container)
        form_layout.addLayout(contributors_layout)

        # Create button layout (right-aligned)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        self.create_button = QPushButton("Create!")
        self.create_button.clicked.connect(self.create_project)
        self.create_button.setMinimumWidth(100)
        button_layout.addWidget(self.create_button)

        form_layout.addLayout(button_layout)

        # Add form layout to main layout
        layout.addLayout(form_layout)

        # Add stretch to push everything to the top
        layout.addStretch(1)

    def set_manager_id(self, manager_id: int):
        """
        Set the manager ID for the project.

        Args:
            manager_id: User ID of the manager
        """
        self.manager_id = manager_id

        # Load potential contributors
        self.load_contributors()

    def load_contributors(self):
        """Load potential contributors from the database."""
        self.contributors_list.clear()
        self.contributors_combo.clear()

        # Get all users
        users = self.user_db.execute("SELECT * FROM users ORDER BY username")

        for user in users:
            # Skip the current manager
            if user['id'] == self.manager_id:
                continue

            # Add to dropdown
            display_name = f"{user['firstname']} {user['surname']} ({user['username']})"
            self.contributors_combo.addItem(display_name, user['id'])

            # Add to list
            item = ContributorItem(user)
            self.contributors_list.addItem(item)

    def create_project(self):
        """Create a new project with the form data."""
        # Validate form data
        title = self.title_edit.text().strip()
        description = self.desc_edit.toPlainText().strip()

        if not title:
            QMessageBox.warning(self, "Validation Error", "Project title is required.")
            return

        if not self.manager_id:
            # Try to get the current user from context
            current_user = get_context(CURRENT_USER)
            if current_user and 'id' in current_user:
                self.manager_id = current_user['id']
            else:
                QMessageBox.warning(self, "Error", "No manager ID set. Please log in first.")
                return

        # Create the project
        project_id = self.project_db.create_project(
            title=title,
            description=description,
            manager_id=self.manager_id
        )

        if not project_id:
            QMessageBox.critical(self, "Error", "Failed to create project.")
            return

        # Add contributors
        for i in range(self.contributors_list.count()):
            item = self.contributors_list.item(i)
            if isinstance(item, ContributorItem) and item.checkState() == Qt.Checked:
                self.project_db.add_contributor(project_id, item.user_id)

        # Clear the form
        self.title_edit.clear()
        self.desc_edit.clear()

        # Reset contributor checkboxes
        for i in range(self.contributors_list.count()):
            item = self.contributors_list.item(i)
            if isinstance(item, ContributorItem):
                item.setCheckState(Qt.Unchecked)

        # Emit signal
        self.projectCreated.emit(project_id)

        # Show success message
        QMessageBox.information(self, "Success", f"Project '{title}' created successfully.")

    def _on_user_changed(self, user: Dict[str, Any]):
        """
        Handle user changed event.

        Args:
            user: New user data
        """
        if user and 'id' in user:
            self.set_manager_id(user['id'])


# For testing
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the project form
    project_form = ProjectForm()
    layout.addWidget(project_form)

    # Set a test manager ID
    project_form.set_manager_id(2)  # Replace with a valid user ID

    # Show the window
    window.setGeometry(100, 100, 500, 600)
    window.show()

    sys.exit(app.exec())
