"""
Project list widget for displaying and selecting projects.

This module provides a custom list widget for displaying projects with
their title, description, and metadata.
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QTextDocument, QAbstractTextDocumentLayout
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QWidget,
    QVBoxLayout, QLabel, QApplication, QLineEdit, QHBoxLayout
)

from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.context import get_context, CURRENT_USER, register_context_listener


class ProjectItem(QListWidgetItem):
    """List widget item for displaying project information."""

    def __init__(self, project: Dict[str, Any]):
        """
        Initialize the project item.

        Args:
            project: Project data dictionary
        """
        super().__init__()
        self.project = project
        self.setSizeHint(QSize(300, 80))  # Set a reasonable default size

        # Store the project ID for easy access
        self.project_id = project['id']

        # Format the last_worked_on date for display
        if project.get('last_worked_on'):
            if isinstance(project['last_worked_on'], str):
                try:
                    last_worked_on = datetime.fromisoformat(project['last_worked_on'])
                    self.last_worked_on_str = last_worked_on.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    self.last_worked_on_str = project['last_worked_on']
            else:
                self.last_worked_on_str = project['last_worked_on'].strftime("%Y-%m-%d %H:%M")
        else:
            self.last_worked_on_str = "Never"


class ProjectItemDelegate(QStyledItemDelegate):
    """Delegate for rendering project items with rich text."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyle.State, index: QListWidgetItem):
        """
        Paint the project item.

        Args:
            painter: Painter to use
            option: Style options
            index: Item index
        """
        # Get the project item
        item = index.model().data(index, Qt.UserRole)
        if not isinstance(item, ProjectItem):
            return super().paint(painter, option, index)

        project = item.project

        # Draw the selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Set up the painter
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate text rectangles
        rect = option.rect
        title_rect = QRect(rect.left() + 10, rect.top() + 5, rect.width() - 20, 25)
        desc_rect = QRect(rect.left() + 10, rect.top() + 30, rect.width() - 20, 30)
        meta_rect = QRect(rect.left() + 10, rect.top() + 60, rect.width() - 20, 15)

        # Draw title with bold font
        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(11)
        painter.setFont(title_font)

        # Set text color based on selection state
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Draw title
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, project['title'])

        # Draw description with normal font
        desc_font = QFont(painter.font())
        desc_font.setBold(False)
        desc_font.setPointSize(9)
        painter.setFont(desc_font)

        # Truncate description if needed
        description = project.get('description', '')
        if description:
            if len(description) > 100:
                description = description[:97] + "..."

            # Draw description
            painter.drawText(desc_rect, Qt.AlignLeft | Qt.AlignTop, description)

        # Draw metadata with smaller font
        meta_font = QFont(painter.font())
        meta_font.setPointSize(8)
        painter.setFont(meta_font)

        # Format metadata
        contributor_count = project.get('contributor_count', 0)
        contributors_text = f"{contributor_count} contributor{'s' if contributor_count != 1 else ''}"

        # Get manager name
        manager_name = "Unknown"
        if project.get('manager_username'):
            manager_name = project['manager_username']
        elif project.get('manager_firstname') and project.get('manager_surname'):
            manager_name = f"{project['manager_firstname']} {project['manager_surname']}"

        # Format metadata text
        meta_text = f"Manager: {manager_name} | {contributors_text} | Last worked on: {item.last_worked_on_str}"

        # Draw metadata
        painter.setPen(QColor(120, 120, 120))
        painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, meta_text)

        painter.restore()

    def sizeHint(self, option: QStyle.State, index: QListWidgetItem) -> QSize:
        """
        Get the size hint for the item.

        Args:
            option: Style options
            index: Item index

        Returns:
            QSize: Size hint
        """
        return QSize(300, 80)


class ProjectListWidget(QWidget):
    """Widget for displaying and searching projects."""

    projectSelected = Signal(int)  # Signal emitted when a project is selected

    def __init__(self, parent=None):
        """Initialize the project list widget."""
        super().__init__(parent)

        # Set up the database manager
        self.db_manager = ProjectDatabaseManager()

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
        layout.setSpacing(5)

        # Header label
        header_label = QLabel("Projects available")
        header_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(header_label)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search")
        self.search_box.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_box)

        layout.addLayout(search_layout)

        # Project list
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)

        # Set the delegate for rendering items
        self.list_widget.setItemDelegate(ProjectItemDelegate(self.list_widget))

        # Connect signals
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)

        layout.addWidget(self.list_widget)

    def load_projects(self, user_id: int = None):
        """
        Load projects from the database.

        Args:
            user_id: Optional user ID to filter projects
        """
        self.list_widget.clear()

        if user_id:
            # Load projects for the specified user
            projects = self.db_manager.get_all_user_projects(user_id)
        else:
            # Load all projects
            projects = self.db_manager.execute("SELECT * FROM projects ORDER BY last_worked_on DESC")

        if not projects:
            return

        for project in projects:
            item = ProjectItem(project)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, None)  # Clear any existing widget

            # Store the item in the model
            index = self.list_widget.indexFromItem(item)
            self.list_widget.model().setData(index, item, Qt.UserRole)

    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """
        Handle current item changed event.

        Args:
            current: Current item
            previous: Previous item
        """
        if current and isinstance(current, ProjectItem):
            self.projectSelected.emit(current.project_id)

    def _on_search_text_changed(self, text: str):
        """
        Handle search text changed event.

        Args:
            text: New search text
        """
        # If text is empty, show all items
        if not text:
            for i in range(self.list_widget.count()):
                self.list_widget.item(i).setHidden(False)
            return

        # Filter items based on search text
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, ProjectItem):
                project = item.project
                title = project.get('title', '').lower()
                description = project.get('description', '').lower()

                # Show item if title or description contains search text
                item.setHidden(text not in title and text not in description)

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

    # Add a label
    label = QLabel("Project List")
    layout.addWidget(label)

    # Create the project list widget
    project_list = ProjectListWidget()
    layout.addWidget(project_list)

    # Load projects
    project_list.load_projects()

    # Show the window
    window.setGeometry(100, 100, 400, 600)
    window.show()

    sys.exit(app.exec())
