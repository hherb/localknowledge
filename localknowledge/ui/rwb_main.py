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
from typing import Dict, List, Optional, Type, Any, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

    def find_splitters(self) -> Dict[str, QSplitter]:
        """
        Find all splitters in this plugin.

        Returns:
            Dict[str, QSplitter]: Dictionary of splitters with their object names as keys
        """
        splitters = {}

        # Find all splitters in this plugin
        for splitter in self.findChildren(QSplitter):
            # Use object name as key, or generate one if not set
            name = splitter.objectName()
            if not name:
                name = f"splitter_{id(splitter)}"
                splitter.setObjectName(name)

            splitters[name] = splitter

        return splitters

    def save_splitter_states(self) -> Dict[str, Any]:
        """
        Save the states of all splitters in this plugin.

        Returns:
            Dict[str, Any]: Dictionary containing splitter states
        """
        splitter_states = {}

        # Find all splitters
        splitters = self.find_splitters()

        # Save state for each splitter
        for name, splitter in splitters.items():
            # Save as list of integers for better compatibility
            sizes = splitter.sizes()
            splitter_states[f"{name}_sizes"] = sizes

            # Also save as individual values
            for i, size in enumerate(sizes):
                splitter_states[f"{name}_size_{i}"] = size

            # Save orientation
            orientation = splitter.orientation()
            # Convert Qt.Orientation enum to int
            orientation_value = 1 if orientation == Qt.Orientation.Horizontal else 2
            splitter_states[f"{name}_orientation"] = orientation_value

            print(f"Saving splitter {name} with sizes {sizes}")

        return splitter_states

    def restore_splitter_states(self, state: Dict[str, Any]) -> bool:
        """
        Restore the states of all splitters in this plugin.

        Args:
            state: Dictionary containing splitter states

        Returns:
            bool: True if states were restored successfully, False otherwise
        """
        # Find all splitters
        splitters = self.find_splitters()

        # Track success
        success = True

        # Restore state for each splitter
        for name, splitter in splitters.items():
            # Try to restore sizes
            if f"{name}_sizes" in state:
                try:
                    sizes = state[f"{name}_sizes"]
                    if isinstance(sizes, list):
                        # Convert to integers if needed
                        sizes = [int(size) for size in sizes]
                        splitter.setSizes(sizes)
                        print(f"Restored splitter {name} with sizes {sizes}")
                    else:
                        print(f"Invalid splitter sizes for {name}: {sizes}")
                        success = False
                except Exception as e:
                    print(f"Error restoring splitter {name} sizes: {e}")
                    success = False

                    # Try individual sizes as fallback
                    try:
                        sizes = []
                        i = 0
                        while f"{name}_size_{i}" in state:
                            sizes.append(int(state[f"{name}_size_{i}"]))
                            i += 1

                        if sizes:
                            splitter.setSizes(sizes)
                            print(f"Restored splitter {name} with individual sizes {sizes}")
                    except Exception as e2:
                        print(f"Error restoring individual sizes for {name}: {e2}")
                        success = False

            # Try to restore orientation
            if f"{name}_orientation" in state:
                try:
                    orientation_value = int(state[f"{name}_orientation"])
                    # Convert int to Qt.Orientation
                    orientation = Qt.Orientation.Horizontal if orientation_value == 1 else Qt.Orientation.Vertical
                    splitter.setOrientation(orientation)
                except Exception as e:
                    print(f"Error restoring splitter {name} orientation: {e}")
                    success = False

        return success

    def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the plugin.

        Returns:
            Dict[str, Any]: Dictionary containing state data
        """
        # Start with splitter states
        state = self.save_splitter_states()

        # Add any other plugin-specific state here

        return state

    def restore_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore a previously saved state.

        Args:
            state: Dictionary containing state data

        Returns:
            bool: True if state was restored successfully, False otherwise
        """
        # Restore splitter states
        success = self.restore_splitter_states(state)

        # Add any other plugin-specific state restoration here

        return success

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

        # Print settings file location for debugging
        print(f"Settings file location: {self.settings.fileName()}")

        # Import context management
        from localknowledge.context import register_context_listener, CURRENT_USER, CURRENT_PROJECT

        # Register listeners for user and project changes
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)

        # Set up plugin manager
        self.plugin_manager = PluginManager()
        self.plugin_manager.discover_plugins()

        # Set up UI
        self.setup_ui()

        # Store window state restoration for after window is shown
        self.window_state_restored = False

        # Show login dialog before loading plugins
        self.handle_login()

    def handle_login(self):
        """Show login dialog and handle authentication."""
        from localknowledge.ui.login_dialog import LoginDialog
        from localknowledge.context import get_context, CURRENT_USER

        dialog = LoginDialog(self)

        # Connect login signal
        dialog.loginSuccessful.connect(self.on_login_successful)

        if dialog.exec() == QDialog.Accepted:
            # Login successful, get user from context
            self.current_user = get_context(CURRENT_USER)

            # Update window title is handled in on_login_successful

            # Auto-load discovered plugins
            self.load_discovered_plugins()
        else:
            # User canceled login, close application
            QTimer.singleShot(0, self.close)

    @Slot(dict)
    def on_login_successful(self, user_data):
        """Handle successful login."""
        from localknowledge.context import get_current_user

        # Get user from context (should be set by login dialog)
        current_user = get_current_user()
        if current_user:
            self.statusBar().showMessage(f"Welcome, {current_user['firstname']} {current_user['surname']}")

        # Update window title with user and project info
        self._update_window_title()

        # Restore window state after login if not already done
        if not self.window_state_restored:
            # Use a timer to ensure the window is fully shown before restoring state
            QTimer.singleShot(100, self.delayed_restore_window_state)

    def delayed_restore_window_state(self):
        """Restore window state after a short delay to ensure window is fully shown."""
        print("Delayed window state restoration...")
        self.restore_window_state()
        self.window_state_restored = True

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
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
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

        # Check if current plugin has a config widget
        if not self.has_config_widget_for_current_tab():
            # No config widget available, don't show panel
            self.statusBar().showMessage("No configuration available for this plugin", 3000)
            self.config_button.setChecked(False)
            self.toggle_config_action.setChecked(False)
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

    def on_tab_changed(self, index):
        """Handle tab change event.

        Args:
            index: Index of the newly selected tab
        """
        # Update the configuration panel with the settings widget for the current tab
        self.update_config_panel_for_current_tab()

        # Update the config button state
        self.update_config_button_state()

    def update_config_panel_for_current_tab(self):
        """Update the configuration panel with the settings widget for the current tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index < 0:
            # No tabs open
            print("update_config_panel_for_current_tab: No tabs open")
            return

        current_widget = self.tab_widget.widget(current_index)
        print(f"update_config_panel_for_current_tab: Current widget = {current_widget}")
        print(f"Current tab text: {self.tab_widget.tabText(current_index)}")

        # Find the plugin for this widget
        for plugin_name, plugin in self.plugin_manager.get_active_plugins().items():
            print(f"Checking plugin: {plugin_name}, class: {plugin.__class__.__name__}")

            # Check if plugin has a main widget
            main_widget = plugin.get_main_widget()
            print(f"Plugin main widget: {main_widget}")

            if main_widget == current_widget:
                # Found the plugin, get its config widget
                print(f"Found matching plugin: {plugin_name}")

                try:
                    config_widget = plugin.get_config_widget()
                    print(f"Plugin {plugin_name} get_config_widget() returned: {config_widget}")

                    if config_widget:
                        print(f"Setting config panel content to widget: {config_widget}")
                        self.config_panel.set_content(config_widget)
                    else:
                        print(f"Plugin {plugin_name} returned None for config widget")
                except Exception as e:
                    print(f"Error calling get_config_widget() on plugin {plugin_name}: {e}")
                    import traceback
                    traceback.print_exc()

                break
        else:
            print("update_config_panel_for_current_tab: No matching plugin found")

    def update_config_button_state(self):
        """Update the config button state based on whether the current tab has a config widget."""
        has_config = self.has_config_widget_for_current_tab()

        # Debug print
        print(f"update_config_button_state: has_config = {has_config}")

        # Get current tab info for debugging
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            tab_text = self.tab_widget.tabText(current_index)
            print(f"Current tab: {tab_text} (index {current_index})")

            # Find the plugin for this tab
            current_widget = self.tab_widget.widget(current_index)
            for plugin_name, plugin in self.plugin_manager.get_active_plugins().items():
                if plugin.get_main_widget() == current_widget:
                    print(f"Plugin: {plugin_name}, has config widget: {plugin.get_config_widget() is not None}")
                    break

        # Enable/disable the config button
        self.config_button.setEnabled(has_config)
        self.toggle_config_action.setEnabled(has_config)

        # If config panel is visible but current tab has no config, hide it
        if self.config_panel.isVisible() and not has_config:
            self.toggle_config_panel()

    def has_config_widget_for_current_tab(self) -> bool:
        """Check if the current tab has a configuration widget.

        Returns:
            bool: True if the current tab has a configuration widget, False otherwise
        """
        current_index = self.tab_widget.currentIndex()
        if current_index < 0:
            # No tabs open
            print("has_config_widget_for_current_tab: No tabs open")
            return False

        current_widget = self.tab_widget.widget(current_index)
        print(f"has_config_widget_for_current_tab: Current widget = {current_widget}")
        print(f"Current tab text: {self.tab_widget.tabText(current_index)}")

        # Find the plugin for this widget
        for plugin_name, plugin in self.plugin_manager.get_active_plugins().items():
            print(f"Checking plugin: {plugin_name}, class: {plugin.__class__.__name__}")

            # Check if plugin has a main widget
            main_widget = plugin.get_main_widget()
            print(f"Plugin main widget: {main_widget}")

            if main_widget == current_widget:
                # Found the plugin, check if it has a config widget
                print(f"Found matching plugin: {plugin_name}")

                # Check if plugin has a has_config_widget method
                if hasattr(plugin, 'has_config_widget'):
                    has_config = plugin.has_config_widget()
                    print(f"Plugin {plugin_name} has_config_widget() returned: {has_config}")
                    if has_config:
                        return True

                # Try to get the config widget
                try:
                    config_widget = plugin.get_config_widget()
                    print(f"Plugin {plugin_name} get_config_widget() returned: {config_widget}")
                    return config_widget is not None
                except Exception as e:
                    print(f"Error calling get_config_widget() on plugin {plugin_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

        print("has_config_widget_for_current_tab: No matching plugin found")
        return False

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

    def find_all_splitters(self) -> Dict[str, QSplitter]:
        """
        Find all splitters in the main window and its children.

        Returns:
            Dict[str, QSplitter]: Dictionary of splitters with their object names as keys
        """
        splitters = {}

        # Find all splitters in the main window
        for splitter in self.findChildren(QSplitter):
            # Skip splitters that belong to plugins
            parent_plugin = None
            parent = splitter.parent()
            while parent:
                if isinstance(parent, PluginBase):
                    parent_plugin = parent
                    break
                parent = parent.parent()

            if parent_plugin:
                # This splitter belongs to a plugin, skip it
                continue

            # Use object name as key, or generate one if not set
            name = splitter.objectName()
            if not name:
                name = f"splitter_{id(splitter)}"
                splitter.setObjectName(name)

            splitters[name] = splitter

        return splitters

    def save_all_splitter_states(self) -> Dict[str, Any]:
        """
        Save the states of all splitters in the main window.

        Returns:
            Dict[str, Any]: Dictionary containing splitter states
        """
        splitter_states = {}

        # Find all splitters
        splitters = self.find_all_splitters()

        # Save state for each splitter
        for name, splitter in splitters.items():
            # Save as list of integers for better compatibility
            sizes = splitter.sizes()
            splitter_states[f"{name}_sizes"] = sizes

            # Also save as individual values
            for i, size in enumerate(sizes):
                splitter_states[f"{name}_size_{i}"] = size

            # Save orientation
            orientation = splitter.orientation()
            # Convert Qt.Orientation enum to int
            orientation_value = 1 if orientation == Qt.Orientation.Horizontal else 2
            splitter_states[f"{name}_orientation"] = orientation_value

            print(f"Saving main window splitter {name} with sizes {sizes}")

        return splitter_states

    def restore_all_splitter_states(self, state: Dict[str, Any]) -> bool:
        """
        Restore the states of all splitters in the main window.

        Args:
            state: Dictionary containing splitter states

        Returns:
            bool: True if states were restored successfully, False otherwise
        """
        # Find all splitters
        splitters = self.find_all_splitters()

        # Track success
        success = True

        # Restore state for each splitter
        for name, splitter in splitters.items():
            # Try to restore sizes
            if f"{name}_sizes" in state:
                try:
                    sizes = state[f"{name}_sizes"]
                    if isinstance(sizes, list):
                        # Convert to integers if needed
                        sizes = [int(size) for size in sizes]
                        splitter.setSizes(sizes)
                        print(f"Restored main window splitter {name} with sizes {sizes}")
                    else:
                        print(f"Invalid splitter sizes for {name}: {sizes}")
                        success = False
                except Exception as e:
                    print(f"Error restoring splitter {name} sizes: {e}")
                    success = False

                    # Try individual sizes as fallback
                    try:
                        sizes = []
                        i = 0
                        while f"{name}_size_{i}" in state:
                            sizes.append(int(state[f"{name}_size_{i}"]))
                            i += 1

                        if sizes:
                            splitter.setSizes(sizes)
                            print(f"Restored main window splitter {name} with individual sizes {sizes}")
                    except Exception as e2:
                        print(f"Error restoring individual sizes for {name}: {e2}")
                        success = False

            # Try to restore orientation
            if f"{name}_orientation" in state:
                try:
                    orientation_value = int(state[f"{name}_orientation"])
                    # Convert int to Qt.Orientation
                    orientation = Qt.Orientation.Horizontal if orientation_value == 1 else Qt.Orientation.Vertical
                    splitter.setOrientation(orientation)
                except Exception as e:
                    print(f"Error restoring splitter {name} orientation: {e}")
                    success = False

        return success

    def save_window_state(self):
        """Save window state to settings."""
        # Add debug output
        print("Saving window state to settings...")

        # Save window geometry and state
        geometry = self.saveGeometry()
        print(f"Saving geometry: {type(geometry)}")
        self.settings.setValue("geometry", geometry)

        state = self.saveState()
        print(f"Saving window state: {type(state)}")
        self.settings.setValue("windowState", state)

        # Save window size and position explicitly
        size = self.size()
        pos = self.pos()
        print(f"Saving window size: {size.width()}x{size.height()}")
        print(f"Saving window position: {pos.x()},{pos.y()}")
        self.settings.setValue("windowWidth", size.width())
        self.settings.setValue("windowHeight", size.height())
        self.settings.setValue("windowX", pos.x())
        self.settings.setValue("windowY", pos.y())
        self.settings.setValue("windowMaximized", self.isMaximized())

        # Save main splitter sizes
        splitter_sizes = self.main_splitter.sizes()
        print(f"Saving main splitter sizes: {splitter_sizes}")
        self.settings.setValue("mainSplitterSizes", splitter_sizes)

        # Also save as individual values for better compatibility
        if len(splitter_sizes) >= 2:
            self.settings.setValue("splitterSize1", splitter_sizes[0])
            self.settings.setValue("splitterSize2", splitter_sizes[1])

        # Save all splitter states
        splitter_states = self.save_all_splitter_states()
        for key, value in splitter_states.items():
            self.settings.setValue(f"splitter/{key}", value)

        # Save active plugins
        active_plugins = list(self.plugin_manager.get_active_plugins().keys())
        print(f"Saving active plugins: {active_plugins}")
        self.settings.setValue("activePlugins", active_plugins)

        # Force settings to be written to disk
        self.settings.sync()
        print(f"Settings saved to: {self.settings.fileName()}")

        # Save plugin states
        for name, plugin in self.plugin_manager.get_active_plugins().items():
            state = plugin.save_state()
            self.settings.setValue(f"pluginState/{name}", state)

    def restore_window_state(self):
        """Restore window state from settings."""
        # Add debug output
        print("Restoring window state from settings...")

        # First try to restore using explicit size and position
        if (self.settings.contains("windowWidth") and
            self.settings.contains("windowHeight") and
            self.settings.contains("windowX") and
            self.settings.contains("windowY")):

            width = self.settings.value("windowWidth", type=int)
            height = self.settings.value("windowHeight", type=int)
            x = self.settings.value("windowX", type=int)
            y = self.settings.value("windowY", type=int)
            maximized = self.settings.value("windowMaximized", False, type=bool)

            print(f"Restoring window size: {width}x{height}")
            print(f"Restoring window position: {x},{y}")
            print(f"Window maximized: {maximized}")

            # Set window size and position
            print(f"Current window size before resize: {self.width()}x{self.height()}")
            print(f"Current window position before move: {self.pos().x()},{self.pos().y()}")

            # Force the window to be visible
            self.show()

            # Apply size and position
            self.resize(width, height)
            self.move(x, y)

            # Update the window
            self.update()
            self.repaint()

            # Process events to ensure changes take effect
            QApplication.processEvents()

            print(f"Window size after resize: {self.width()}x{self.height()}")
            print(f"Window position after move: {self.pos().x()},{self.pos().y()}")

            # Set maximized state if needed
            if maximized:
                self.showMaximized()

        # Then try to restore using geometry and state
        elif self.settings.contains("geometry"):
            geometry = self.settings.value("geometry")
            print(f"Restoring geometry: {type(geometry)}")
            self.restoreGeometry(geometry)

            if self.settings.contains("windowState"):
                state = self.settings.value("windowState")
                print(f"Restoring window state: {type(state)}")
                self.restoreState(state)

        # Restore main splitter sizes
        splitter_sizes = None

        # First try using individual values
        if self.settings.contains("splitterSize1") and self.settings.contains("splitterSize2"):
            size1 = self.settings.value("splitterSize1", type=int)
            size2 = self.settings.value("splitterSize2", type=int)
            splitter_sizes = [size1, size2]
            print(f"Restored main splitter sizes from individual values: {splitter_sizes}")

        # If that failed, try the regular way
        elif self.settings.contains("mainSplitterSizes"):
            # Get the saved splitter sizes and convert to list of integers
            splitter_sizes = self.settings.value("mainSplitterSizes")
            print(f"Raw main splitter sizes: {splitter_sizes}, type: {type(splitter_sizes)}")

            # Convert to list of integers if needed
            if isinstance(splitter_sizes, list):
                try:
                    # Convert each item to int
                    splitter_sizes = [int(size) for size in splitter_sizes]
                    print(f"Converted list main splitter sizes: {splitter_sizes}")
                except (TypeError, ValueError):
                    print(f"Error converting list main splitter sizes: {splitter_sizes}")
                    splitter_sizes = None
            else:
                # Not a list, try other methods
                splitter_sizes = None

        # If all else fails, use default
        if splitter_sizes is None or len(splitter_sizes) < 2:
            splitter_sizes = [0, self.width()]
            print(f"Using default main splitter sizes: {splitter_sizes}")

        # Apply the splitter sizes
        print(f"Setting main splitter sizes to: {splitter_sizes}")
        self.main_splitter.setSizes(splitter_sizes)

        # Restore all other splitter states
        splitter_states = {}

        # Collect all splitter state settings
        for key in self.settings.allKeys():
            if key.startswith("splitter/"):
                # Extract the actual key (remove the "splitter/" prefix)
                actual_key = key[len("splitter/"):]
                splitter_states[actual_key] = self.settings.value(key)

        # Restore all splitter states
        if splitter_states:
            print(f"Restoring {len(splitter_states)} splitter states")
            self.restore_all_splitter_states(splitter_states)

        # Ensure config panel is hidden on start
        print("Ensuring config panel is hidden on start")
        self.config_panel.setVisible(False)
        self.config_button.setChecked(False)
        self.toggle_config_action.setChecked(False)

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

        # Update config button state after loading plugins
        self.update_config_button_state()

    def closeEvent(self, event):
        """
        Handle the window close event.

        Args:
            event: Close event
        """
        print("Window closing, saving state...")

        # Save window state
        self.save_window_state()

        # Force settings to be written to disk again
        self.settings.sync()

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

    def _on_user_changed(self, _):
        """
        Handle user change from context system.

        Args:
            _: User information dictionary (unused)
        """
        # Update window title when user changes
        self._update_window_title()

    def _on_project_changed(self, _):
        """
        Handle project change from context system.

        Args:
            _: Project ID (unused)
        """
        # Update window title when project changes
        self._update_window_title()

    def _update_window_title(self):
        """Update the window title with current project and user information."""
        from localknowledge.context import get_current_user, get_current_project_name

        title = "RWB - Researcher's Workbench"

        # Add user name if available
        current_user = get_current_user()
        if current_user:
            user_name = f"{current_user.get('firstname', '')} {current_user.get('surname', '')}"
            title += f" - {user_name}"

        # Add project name if available
        project_name = get_current_project_name()
        if project_name:
            title += f" - Project: {project_name}"

        self.setWindowTitle(title)

    def logout(self):
        """Log out the current user and show the login dialog."""
        from localknowledge.context import set_current_user, set_current_project

        # Clear current user and project in context
        set_current_user(None)
        set_current_project(None)

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


def check_database_migrations() -> Tuple[bool, int, int]:
    """
    Check for pending database migrations.

    Returns:
        Tuple[bool, int, int]: (has_pending, current_version, pending_count)
    """
    try:
        # Import the migrations system
        from localknowledge.db.migrations_system.check_migrations import check_migrations

        # Check for pending migrations
        has_pending, current_version, pending_count = check_migrations(auto_migrate=False)

        if has_pending:
            logger.warning(f"There are {pending_count} pending migrations. Database is at version {current_version}.")
            logger.warning("Run 'python -m localknowledge.db.migrations_system.run_migrations' to apply them.")
        else:
            logger.info(f"Database is up to date at version {current_version}.")

        return has_pending, current_version, pending_count
    except ImportError:
        logger.warning("Migrations system not available. Skipping migrations check.")
        return False, 0, 0
    except Exception as e:
        logger.error(f"Error checking migrations: {e}")
        return False, 0, 0


def show_migrations_dialog(parent, pending_count: int, current_version: int) -> bool:
    """
    Show a dialog about pending migrations.

    Args:
        parent: Parent widget
        pending_count: Number of pending migrations
        current_version: Current database version

    Returns:
        bool: True if user wants to run migrations, False otherwise
    """
    message = f"There are {pending_count} pending database migrations.\n\n"
    message += f"Current database version: {current_version}\n\n"
    message += "Would you like to run these migrations now?\n\n"
    message += "Note: Running migrations may take some time and require\n"
    message += "the application to restart afterward."

    result = QMessageBox.question(
        parent,
        "Database Migrations",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )

    return result == QMessageBox.Yes


def run_migrations_and_restart():
    """
    Run migrations and restart the application.
    """
    try:
        # Import the migrations system
        from localknowledge.db.migrations_system.manager import MigrationsManager

        # Create a migrations manager
        migrations_manager = MigrationsManager()

        # Run migrations
        success = migrations_manager.run_pending_migrations(use_gui_tqdm=True)

        if success:
            new_version = migrations_manager.get_current_version()
            logger.info(f"Migrations completed successfully. New database version: {new_version}")

            # Show success message
            QMessageBox.information(
                None,
                "Migrations Complete",
                f"Migrations completed successfully.\n\nNew database version: {new_version}\n\nThe application will now restart."
            )

            # Restart the application
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            logger.error("Migration process failed")

            # Show error message
            QMessageBox.critical(
                None,
                "Migration Failed",
                "The migration process failed. Please check the logs for details."
            )
    except Exception as e:
        logger.error(f"Error running migrations: {e}")

        # Show error message
        QMessageBox.critical(
            None,
            "Migration Error",
            f"An error occurred while running migrations:\n\n{str(e)}"
        )


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    # Set application details
    app.setApplicationName("RWB")
    app.setApplicationDisplayName("Researcher's Workbench")
    app.setOrganizationName("RWB")
    app.setOrganizationDomain("rwb.org")

    # Check for pending migrations
    has_pending, current_version, pending_count = check_database_migrations()

    if has_pending:
        # Create a minimal window to show the migrations dialog
        temp_window = QWidget()
        temp_window.setWindowTitle("RWB - Database Migrations")
        temp_window.resize(400, 200)

        # Show the migrations dialog
        if show_migrations_dialog(temp_window, pending_count, current_version):
            # User wants to run migrations
            run_migrations_and_restart()
            return

    # Create the main window
    main_window = MainWindow()

    # Show the main window
    main_window.show()

    # Process events to ensure window is fully shown
    app.processEvents()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
