#!/usr/bin/env python3
"""
RWB - Researcher's Workbench

Main application window with plugin system for researcher tools.
Each plugin can be a PySide6 widget that integrates into the main interface.

Features:
- Slide-in/slide-out configuration panel
- Plugin system for adding new tools
- Toolbar and menu system
- Modern UI with docking widgets
"""

import os
import sys
import importlib
from typing import Dict, List, Optional, Type, Any

from PySide6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve,
    QObject, Signal, Property, QSettings, Signal, Slot
)
from PySide6.QtGui import (
    QIcon, QAction, QPixmap, QPainter, QColor,
    QFontMetrics, QPalette, QKeySequence
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDockWidget,
    QToolBar, QMenuBar, QStatusBar, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSplitter,
    QFrame, QTabWidget, QMenu, QToolButton, QSizePolicy,
    QMessageBox, QFileDialog, QDialog
)


class PluginBase(QWidget):
    """Base class for all plugins."""

    plugin_name = "Base Plugin"
    plugin_description = "Base plugin class that all plugins should inherit from"
    plugin_icon = None  # Default icon path

    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)

    def initialize(self) -> bool:
        """
        Initialize the plugin. Called when the plugin is loaded.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        return True

    def get_main_widget(self) -> QWidget:
        """
        Get the main widget of this plugin.

        Returns:
            QWidget: The main widget to be displayed in the central area
        """
        return self

    def get_config_widget(self) -> Optional[QWidget]:
        """
        Get the configuration widget for this plugin.

        Returns:
            Optional[QWidget]: Configuration widget or None if no configuration is needed
        """
        return None

    def get_title(self) -> str:
        """
        Get the display title for this plugin.

        Returns:
            str: Display title
        """
        return self.plugin_name

    def get_actions(self) -> List[QAction]:
        """
        Get a list of actions this plugin provides for menus/toolbars.

        Returns:
            List[QAction]: List of actions
        """
        return []

    def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the plugin.

        Returns:
            Dict[str, Any]: Dictionary containing state data
        """
        return {}

    def restore_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore a previously saved state.

        Args:
            state: Dictionary containing state data

        Returns:
            bool: True if state was restored successfully, False otherwise
        """
        return True

    def close_plugin(self) -> bool:
        """
        Perform cleanup when closing the plugin.

        Returns:
            bool: True if plugin can be safely closed, False otherwise
        """
        return True


class ConfigPanel(QWidget):
    """Slide-in configuration panel."""

    def __init__(self, parent=None):
        """Initialize the configuration panel."""
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("Configuration")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        # Content area - scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch(1)

        scroll_area.setWidget(self.content_widget)

        # Add to main layout
        layout.addWidget(header)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        layout.addWidget(scroll_area)

        # Set default style
        self.setStyleSheet("""
            ConfigPanel {
                background-color: #f5f5f5;
                border-right: 1px solid #cccccc;
            }
        """)

        self.setMinimumWidth(250)
        self.setMaximumWidth(400)

    def set_content(self, widget):
        """
        Set the content widget in the configuration panel.

        Args:
            widget: Widget to display in the configuration panel
        """
        # Clear existing content
        while self.content_layout.count() > 1:  # Keep stretch at the end
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if widget:
            self.content_layout.insertWidget(0, widget)


class PluginManager(QObject):
    """Manages loading and unloading of plugins."""

    plugin_loaded = Signal(str)
    plugin_unloaded = Signal(str)

    def __init__(self, plugin_dirs: List[str] = None):
        """
        Initialize the plugin manager.

        Args:
            plugin_dirs: List of directories to search for plugins
        """
        super().__init__()

        if plugin_dirs is None:
            # Default plugin directories
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.plugin_dirs = [
                os.path.join(base_dir, "plugins"),
            ]
        else:
            self.plugin_dirs = plugin_dirs

        self.plugins: Dict[str, Type[PluginBase]] = {}
        self.active_plugins: Dict[str, PluginBase] = {}

    def discover_plugins(self) -> Dict[str, Type[PluginBase]]:
        """
        Discover available plugins in the plugin directories.

        Returns:
            Dict[str, Type[PluginBase]]: Dictionary of plugin classes
        """
        print(f"Looking for plugins in directories: {self.plugin_dirs}")

        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                os.makedirs(plugin_dir, exist_ok=True)
                print(f"Created plugin directory: {plugin_dir}")
                continue
            else:
                print(f"Plugin directory exists: {plugin_dir}")

            sys.path.insert(0, plugin_dir)
            print(f"Added {plugin_dir} to Python path")

            # Check if finder module exists, if not, skip this directory
            finder_path = os.path.join(plugin_dir, "plugin_finder.py")
            if not os.path.exists(finder_path):
                print(f"Warning: plugin_finder.py not found in {plugin_dir}")
                continue

            try:
                # Import the plugin_finder module
                print("Loading plugin finder module...")
                # Try absolute import first
                try:
                    from localknowledge.ui.plugins.plugin_finder import get_plugin_classes
                    print("Imported plugin finder using absolute import")
                except ImportError:
                    # Fall back to direct import
                    sys.path.insert(0, os.path.dirname(plugin_dir))
                    from plugins.plugin_finder import get_plugin_classes
                    print("Imported plugin finder using relative import")

                # Get registered plugin classes
                registered_plugins = get_plugin_classes()
                print(f"Found {len(registered_plugins)} registered plugins: {list(registered_plugins.keys())}")
                self.plugins.update(registered_plugins)
            except Exception as e:
                print(f"Error loading plugins via plugin_finder: {e}")

        print(f"Discovered plugins: {list(self.plugins.keys())}")
        return self.plugins

    def load_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Load a plugin by name.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Optional[PluginBase]: Plugin instance or None if loading failed
        """
        if plugin_name not in self.plugins:
            print(f"Plugin '{plugin_name}' not found")
            return None

        if plugin_name in self.active_plugins:
            return self.active_plugins[plugin_name]

        try:
            plugin_class = self.plugins[plugin_name]
            plugin = plugin_class()

            if plugin.initialize():
                self.active_plugins[plugin_name] = plugin
                self.plugin_loaded.emit(plugin_name)
                return plugin
            else:
                print(f"Plugin '{plugin_name}' failed to initialize")
                return None

        except Exception as e:
            print(f"Error initializing plugin '{plugin_name}': {e}")
            return None

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin by name.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            bool: True if unloaded successfully, False otherwise
        """
        if plugin_name not in self.active_plugins:
            return False

        plugin = self.active_plugins[plugin_name]

        if plugin.close_plugin():
            del self.active_plugins[plugin_name]
            self.plugin_unloaded.emit(plugin_name)
            return True

        return False

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Get an active plugin instance by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Optional[PluginBase]: Plugin instance or None if not loaded
        """
        return self.active_plugins.get(plugin_name)

    def get_available_plugins(self) -> Dict[str, Type[PluginBase]]:
        """
        Get all available plugins.

        Returns:
            Dict[str, Type[PluginBase]]: Dictionary of available plugin classes
        """
        return self.plugins

    def get_active_plugins(self) -> Dict[str, PluginBase]:
        """
        Get all active plugins.

        Returns:
            Dict[str, PluginBase]: Dictionary of active plugin instances
        """
        return self.active_plugins


class MainWindow(QMainWindow):
    """Main application window with plugin support."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        self.setWindowTitle("RWB - Researcher's Workbench")
        self.setMinimumSize(1000, 700)

        # Set up settings
        self.settings = QSettings("RWB", "ResearchersWorkbench")

        # Current logged-in user
        self.current_user = None

        # Set up plugin manager
        self.plugin_manager = PluginManager()
        self.plugin_manager.discover_plugins()

        # Set up UI
        self.setup_ui()

        # Restore window state from settings
        self.restore_window_state()

        # Show login dialog before loading plugins
        self.handle_login()

    def handle_login(self):
        """Show login dialog and handle authentication."""
        from localknowledge.ui.login_dialog import LoginDialog

        dialog = LoginDialog(self)

        # Connect login signal
        dialog.loginSuccessful.connect(self.on_login_successful)

        if dialog.exec() == QDialog.Accepted:
            # Login successful, load plugins
            self.current_user = dialog.get_current_user()

            # Update window title to show logged-in user
            if self.current_user:
                self.setWindowTitle(f"RWB - Researcher's Workbench - {self.current_user['firstname']} {self.current_user['surname']}")

            # Auto-load discovered plugins
            self.load_discovered_plugins()
        else:
            # User canceled login, close application
            QTimer.singleShot(0, self.close)

    @Slot(dict)
    def on_login_successful(self, user_data):
        """Handle successful login."""
        self.current_user = user_data
        self.statusBar().showMessage(f"Welcome, {user_data['firstname']} {user_data['surname']}")

    def setup_ui(self):
        """Set up the user interface."""
        # Set up central widget
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.main_splitter)

        # Configuration panel (initially hidden)
        self.config_panel = ConfigPanel()
        self.config_panel.setVisible(False)
        self.main_splitter.addWidget(self.config_panel)

        # Tab widget for plugins
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_plugin_tab)
        self.main_splitter.addWidget(self.tab_widget)

        # Set splitter sizes
        self.main_splitter.setSizes([0, self.width()])

        # Set up menus
        self.setup_menus()

        # Set up toolbar
        self.setup_toolbar()

        # Set up status bar
        self.statusBar().showMessage("Ready")

        # Configure animations
        self.config_animation = QPropertyAnimation(self, b"config_panel_width")
        self.config_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.config_animation.setDuration(250)

    def setup_menus(self):
        """Set up application menus."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = self.menuBar().addMenu("&View")

        toggle_config_action = QAction("&Configuration Panel", self)
        toggle_config_action.setShortcut("Ctrl+K")
        toggle_config_action.setCheckable(True)
        toggle_config_action.setStatusTip("Show or hide the configuration panel")
        toggle_config_action.triggered.connect(self.toggle_config_panel)
        view_menu.addAction(toggle_config_action)
        self.toggle_config_action = toggle_config_action

        # Plugins menu
        plugins_menu = self.menuBar().addMenu("&Plugins")

        # Dynamic plugin actions will be added here
        self.update_plugins_menu()

        # Help menu
        help_menu = self.menuBar().addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("Show the application's About box")
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def setup_toolbar(self):
        """Set up the main toolbar."""
        # Main toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("mainToolBar")  # Set an object name for the toolbar
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # Config panel toggle button - using settings.png icon from ui/icons directory
        settings_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "settings.png")
        config_button = QAction(QIcon(settings_icon_path), "", self)  # Empty text to show only the icon
        config_button.setCheckable(True)
        config_button.setStatusTip("Show or hide configuration panel")
        config_button.triggered.connect(self.toggle_config_panel)
        self.toolbar.addAction(config_button)
        self.config_button = config_button

        self.toolbar.addSeparator()

        # Add a spacer to push the logout button to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        # Add logout button to the right side of the toolbar
        logout_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "logout.png")
        logout_button = QAction(QIcon(logout_icon_path), "", self)  # Empty text to show only the icon
        logout_button.setStatusTip("Logout current user")
        logout_button.triggered.connect(self.logout)
        self.toolbar.addAction(logout_button)
        self.logout_button = logout_button

        # Plugin-specific actions will be added dynamically

    def update_plugins_menu(self):
        """Update the plugins menu with available plugins."""
        plugins_menu = None
        for menu in self.menuBar().findChildren(QMenu):
            if menu.title() == "&Plugins":
                plugins_menu = menu
                break

        if not plugins_menu:
            return

        plugins_menu.clear()

        load_menu = plugins_menu.addMenu("&Load Plugin")

        # Add available plugins
        available_plugins = self.plugin_manager.get_available_plugins()
        for name, plugin_class in available_plugins.items():
            plugin_action = QAction(plugin_class.plugin_name, self)
            plugin_action.setData(name)
            plugin_action.triggered.connect(lambda checked, n=name: self.load_plugin(n))
            load_menu.addAction(plugin_action)

    def load_plugin(self, plugin_name):
        """
        Load a plugin and add it to the interface.

        Args:
            plugin_name: Name of the plugin to load
        """
        plugin = self.plugin_manager.load_plugin(plugin_name)
        if plugin:
            # Add plugin to tab widget
            self.tab_widget.addTab(plugin.get_main_widget(), plugin.get_title())

            # Switch to the new tab
            self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

            # Show configuration panel if plugin has config widget
            config_widget = plugin.get_config_widget()
            if config_widget:
                self.config_panel.set_content(config_widget)
                if not self.config_panel.isVisible():
                    self.toggle_config_panel()

            # Update UI
            self.statusBar().showMessage(f"Loaded plugin: {plugin.plugin_name}")

            # Add plugin actions to toolbar if available
            plugin_actions = plugin.get_actions()
            if plugin_actions:
                for action in plugin_actions:
                    self.toolbar.addAction(action)

    def close_plugin_tab(self, index):
        """
        Close a plugin tab.

        Args:
            index: Index of the tab to close
        """
        widget = self.tab_widget.widget(index)

        # Find the plugin containing this widget
        plugin_name = None
        for name, plugin in self.plugin_manager.get_active_plugins().items():
            if plugin.get_main_widget() == widget:
                plugin_name = name
                break

        if plugin_name and self.plugin_manager.unload_plugin(plugin_name):
            self.tab_widget.removeTab(index)
            self.statusBar().showMessage(f"Unloaded plugin: {plugin_name}")

    def toggle_config_panel(self):
        """Toggle the configuration panel visibility."""
        if self.config_animation.state() == QPropertyAnimation.Running:
            return

        if self.config_panel.isVisible():
            # Hide panel
            self.config_animation.setStartValue(self.config_panel.width())
            self.config_animation.setEndValue(0)
            self.config_animation.finished.connect(self._hide_config_panel)
            self.config_button.setChecked(False)
            self.toggle_config_action.setChecked(False)
        else:
            # Show panel
            self.config_panel.setVisible(True)
            self.config_animation.setStartValue(0)
            self.config_animation.setEndValue(250)  # Default width
            self.config_button.setChecked(True)
            self.toggle_config_action.setChecked(True)

        self.config_animation.start()

    def _hide_config_panel(self):
        """Hide the configuration panel after animation completes."""
        self.config_panel.setVisible(False)
        self.config_animation.finished.disconnect(self._hide_config_panel)

    def get_config_panel_width(self):
        """
        Get the width of the configuration panel.

        Returns:
            int: Width of the configuration panel
        """
        return self.main_splitter.sizes()[0]

    def set_config_panel_width(self, width):
        """
        Set the width of the configuration panel.

        Args:
            width: Desired width
        """
        sizes = self.main_splitter.sizes()
        total_width = sum(sizes)

        if len(sizes) >= 2:
            self.main_splitter.setSizes([width, total_width - width])

    # Property for animation
    config_panel_width = Property(int, get_config_panel_width, set_config_panel_width)

    def show_about_dialog(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About RWB - Researcher's Workbench",
            "RWB - Researcher's Workbench\n\n"
            "A platform for research tools and knowledge management."
        )

    def save_window_state(self):
        """Save window state to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        # Save active plugins
        active_plugins = list(self.plugin_manager.get_active_plugins().keys())
        self.settings.setValue("activePlugins", active_plugins)

        # Save plugin states
        for name, plugin in self.plugin_manager.get_active_plugins().items():
            state = plugin.save_state()
            self.settings.setValue(f"pluginState/{name}", state)

    def restore_window_state(self):
        """Restore window state from settings."""
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))

        if self.settings.contains("windowState"):
            self.restoreState(self.settings.value("windowState"))

        # Load previously active plugins
        active_plugins = self.settings.value("activePlugins", [])
        if active_plugins:
            for plugin_name in active_plugins:
                plugin = self.plugin_manager.load_plugin(plugin_name)
                if plugin:
                    # Restore plugin state
                    if self.settings.contains(f"pluginState/{plugin_name}"):
                        state = self.settings.value(f"pluginState/{plugin_name}")
                        plugin.restore_state(state)

                    # Add to UI
                    self.tab_widget.addTab(plugin.get_main_widget(), plugin.get_title())

    def closeEvent(self, event):
        """
        Handle the window close event.

        Args:
            event: Close event
        """
        # Save window state
        self.save_window_state()

        # Close all plugins
        for plugin_name in list(self.plugin_manager.get_active_plugins().keys()):
            self.plugin_manager.unload_plugin(plugin_name)

        # Accept the event
        event.accept()

    def load_discovered_plugins(self):
        """
        Automatically load all discovered plugins.
        """
        available_plugins = self.plugin_manager.get_available_plugins()
        if not available_plugins:
            print("No plugins available to auto-load")
            return

        print(f"Auto-loading {len(available_plugins)} discovered plugins...")
        for plugin_name in available_plugins:
            print(f"Auto-loading plugin: {plugin_name}")
            self.load_plugin(plugin_name)

    def logout(self):
        """Log out the current user and show the login dialog."""
        # Clear current user
        self.current_user = None

        # Close all plugins
        for plugin_name in list(self.plugin_manager.get_active_plugins().keys()):
            self.plugin_manager.unload_plugin(plugin_name)

        # Clear all tabs
        self.tab_widget.clear()

        # Reset window title
        self.setWindowTitle("RWB - Researcher's Workbench")

        # We don't clear saved login info anymore to preserve the username
        # when "Remember me" was checked

        # Show login dialog
        self.handle_login()


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    # Set application details
    app.setApplicationName("RWB")
    app.setApplicationDisplayName("Researcher's Workbench")
    app.setOrganizationName("RWB")
    app.setOrganizationDomain("rwb.org")

    # Create and show the main window
    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
