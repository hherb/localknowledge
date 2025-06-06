"""
Project Manager Plugin for the Researcher's Workbench.

This plugin provides project management functionality for the RWB,
allowing users to create, view, and manage research projects.
"""
import os
import sys
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
    QLabel, QApplication, QMainWindow, QTabWidget
)

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import from plugin_base if available, otherwise use a dummy class
try:
    from localknowledge.ui.plugin_base import PluginBase
    PLUGIN_BASE_AVAILABLE = True
except ImportError:
    # Fallback for standalone mode
    class PluginBase:
        """Dummy base class for standalone mode."""
        plugin_name = "Base Plugin"
        plugin_description = "Base plugin class"
        plugin_icon = None

        def __init__(self, parent=None):
            """Initialize the plugin."""
            self.parent = parent

    PLUGIN_BASE_AVAILABLE = False

# Import plugin registration if available
try:
    from localknowledge.ui.plugins.plugin_finder import register_plugin
    REGISTER_PLUGIN_AVAILABLE = True
except ImportError:
    # Dummy decorator for standalone mode
    def register_plugin(cls):
        """Dummy decorator for standalone mode."""
        return cls

    REGISTER_PLUGIN_AVAILABLE = False

# Import our custom widgets
from localknowledge.ui.project_list import ProjectListWidget
from localknowledge.ui.project_form import ProjectForm
from localknowledge.ui.recent_projects import RecentProjectsWidget
from localknowledge.ui.project_detail_widget import ProjectDetailWidget

# Import context management
from localknowledge.context import (
    set_current_user, set_current_project, get_current_user,
    CURRENT_USER, CURRENT_PROJECT
)


# Register the plugin if the registration function is available
if REGISTER_PLUGIN_AVAILABLE:
    @register_plugin
    class ProjectManagerPlugin(PluginBase):
        """Project manager plugin for the Researcher's Workbench."""

        plugin_name = "Project Manager"
        plugin_description = "Manage research projects"
        plugin_icon = ":/icons/project.png"  # Replace with actual icon path

        def __init__(self, parent=None):
            """Initialize the plugin."""
            super().__init__(parent)

            # Set up UI
            self.setup_ui()

        def setup_ui(self):
            """Set up the user interface."""
            # Main layout
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # Tab widget for "My Projects" and "Current Project"
            self.tab_widget = QTabWidget()
            layout.addWidget(self.tab_widget)

            # My Projects tab
            self.projects_tab = QWidget()
            self.tab_widget.addTab(self.projects_tab, "My Projects")

            # Current Project tab
            self.current_project_tab = QWidget()
            current_project_layout = QVBoxLayout(self.current_project_tab)
            current_project_layout.setContentsMargins(0, 0, 0, 0)
            current_project_layout.setSpacing(0)

            # Project detail widget
            self.project_detail = ProjectDetailWidget()
            current_project_layout.addWidget(self.project_detail)

            # Add tab and disable it until a project is selected
            self.tab_widget.addTab(self.current_project_tab, "Current Project")
            self.tab_widget.setTabEnabled(1, False)

            # Projects tab layout
            projects_layout = QVBoxLayout(self.projects_tab)
            projects_layout.setContentsMargins(0, 0, 0, 0)
            projects_layout.setSpacing(0)

            # Main splitter
            self.main_splitter = QSplitter(Qt.Horizontal)
            projects_layout.addWidget(self.main_splitter)

            # Left side - project list
            self.project_list = ProjectListWidget()
            self.project_list.projectSelected.connect(self.on_project_selected)
            self.main_splitter.addWidget(self.project_list)

            # Right side - container widget
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            right_layout.setContentsMargins(10, 10, 10, 10)
            right_layout.setSpacing(10)
            self.main_splitter.addWidget(right_widget)

            # Recent projects section
            self.recent_projects = RecentProjectsWidget()
            self.recent_projects.projectSelected.connect(self.on_project_selected)
            right_layout.addWidget(self.recent_projects)

            # Horizontal divider
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setFrameShadow(QFrame.Sunken)
            right_layout.addWidget(divider)

            # Project creation form
            self.project_form = ProjectForm()
            self.project_form.projectCreated.connect(self.on_project_created)
            right_layout.addWidget(self.project_form)

            # Set splitter sizes (1:2 ratio)
            self.main_splitter.setSizes([1, 2])

            # Current Project tab (placeholder for now)
            self.current_project_tab = QWidget()
            self.tab_widget.addTab(self.current_project_tab, "Current Project")

            # Disable the Current Project tab until a project is selected
            self.tab_widget.setTabEnabled(1, False)

        def initialize(self) -> bool:
            """
            Initialize the plugin. Called when the plugin is loaded.

            Returns:
                bool: True if initialization was successful, False otherwise
            """
            # Try to get the current user from the main window
            main_window = self.parent()
            if hasattr(main_window, 'current_user') and main_window.current_user:
                # Store the user in the context
                set_current_user(main_window.current_user)

            return True

        @Slot(int)
        def on_project_selected(self, project_id: int):
            """
            Handle project selection.

            Args:
                project_id: ID of the selected project
            """
            # Store the selected project ID in the context
            set_current_project(project_id)

            # Load the project in the detail widget
            self.project_detail.load_project(project_id)

            # Enable the Current Project tab
            self.tab_widget.setTabEnabled(1, True)

            # Switch to the Current Project tab
            self.tab_widget.setCurrentIndex(1)

        def refresh_projects(self):
            """Refresh the project list and recent projects."""
            current_user = get_current_user()
            if current_user and 'id' in current_user:
                self.project_list.load_projects(current_user['id'])
                self.recent_projects.load_projects(current_user['id'])

        @Slot(int)
        def on_project_created(self, project_id: int):
            """
            Handle project creation.

            Args:
                project_id: ID of the created project
            """
            # Refresh the project list and recent projects
            self.refresh_projects()

            # Select the new project
            self.on_project_selected(project_id)

        def get_config_widget(self) -> Optional[QWidget]:
            """
            Get the configuration widget for this plugin.

            Returns:
                Optional[QWidget]: Configuration widget or None if not available
            """
            # This plugin doesn't have a configuration widget
            return None


# Standalone mode
class ProjectManager(QWidget):
    """Standalone project manager widget."""

    def __init__(self, parent=None):
        """Initialize the project manager."""
        super().__init__(parent)

        # Current user ID
        self.current_user_id = None

        # Set up UI
        self.setup_ui()

        # Set window properties
        self.setWindowTitle("Project Manager")
        self.resize(1000, 600)

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.main_splitter)

        # Left side - project list
        self.project_list = ProjectListWidget()
        self.project_list.projectSelected.connect(self.on_project_selected)
        self.main_splitter.addWidget(self.project_list)

        # Right side - container widget
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)
        self.main_splitter.addWidget(right_widget)

        # Recent projects section
        self.recent_projects = RecentProjectsWidget()
        self.recent_projects.projectSelected.connect(self.on_project_selected)
        right_layout.addWidget(self.recent_projects)

        # Horizontal divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(divider)

        # Project creation form
        self.project_form = ProjectForm()
        self.project_form.projectCreated.connect(self.on_project_created)
        right_layout.addWidget(self.project_form)

        # Set splitter sizes (1:2 ratio)
        self.main_splitter.setSizes([1, 2])

    def set_current_user(self, user_id: int):
        """
        Set the current user ID.

        Args:
            user_id: User ID
        """
        self.current_user_id = user_id

        # Update the project form
        self.project_form.set_manager_id(self.current_user_id)

        # Load projects
        self.refresh_projects()

    def refresh_projects(self):
        """Refresh the project list and recent projects."""
        if self.current_user_id:
            self.project_list.load_projects(self.current_user_id)
            self.recent_projects.load_projects(self.current_user_id)

    @Slot(int)
    def on_project_selected(self, project_id: int):
        """
        Handle project selection.

        Args:
            project_id: ID of the selected project
        """
        # Store the selected project ID in the context
        set_current_project(project_id)

        # Create a new window to display the project details
        detail_window = QMainWindow()
        detail_window.setWindowTitle(f"Project Details - ID: {project_id}")

        # Create the project detail widget
        project_detail = ProjectDetailWidget()
        detail_window.setCentralWidget(project_detail)

        # Load the project
        project_detail.load_project(project_id)

        # Show the window
        detail_window.resize(800, 600)
        detail_window.show()

    @Slot(int)
    def on_project_created(self, project_id: int):
        """
        Handle project creation.

        Args:
            project_id: ID of the created project
        """
        # Refresh the project list and recent projects
        self.refresh_projects()

        # Select the new project
        self.on_project_selected(project_id)


# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create the main window
    window = QMainWindow()
    window.setWindowTitle("Project Manager")

    # Create the project manager
    project_manager = ProjectManager()
    window.setCentralWidget(project_manager)

    # Set a test user ID
    project_manager.set_current_user(2)  # Replace with a valid user ID

    # Show the window
    window.resize(1000, 600)
    window.show()

    sys.exit(app.exec())
