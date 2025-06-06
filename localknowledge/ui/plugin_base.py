#!/usr/bin/env python3
"""
Plugin Base Module

This module contains the PluginBase class that all plugins should inherit from.
It provides a common interface and functionality for plugins in the RWB system.
"""

from typing import Dict, List, Optional, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QSplitter


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
                    else:
                        success = False
                except Exception as e:
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
                    except Exception as e2:
                        success = False

            # Try to restore orientation
            if f"{name}_orientation" in state:
                try:
                    orientation_value = int(state[f"{name}_orientation"])
                    # Convert int to Qt.Orientation
                    orientation = Qt.Orientation.Horizontal if orientation_value == 1 else Qt.Orientation.Vertical
                    splitter.setOrientation(orientation)
                except Exception as e:
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
