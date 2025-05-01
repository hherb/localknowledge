#!/usr/bin/env python3
"""
Test Configuration Plugin for RWB

This plugin is a simple test to verify that configuration widgets work correctly.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the plugin base and registration
from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin


@register_plugin
class TestConfigPlugin(PluginBase):
    """Test plugin with a configuration widget."""

    plugin_name = "Test Config"
    plugin_description = "Test plugin to verify configuration widgets work correctly"
    plugin_icon = None

    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Title
        title_label = QLabel("<h2>Test Configuration Plugin</h2>")
        main_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "This is a test plugin to verify that configuration widgets work correctly. "
            "Click the settings icon in the toolbar to open the configuration panel."
        )
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        # Status
        self.status_label = QLabel("Configuration panel is not open")
        main_layout.addWidget(self.status_label)

        # Button to test configuration
        test_btn = QPushButton("Test Configuration")
        test_btn.clicked.connect(self._on_test_clicked)
        main_layout.addWidget(test_btn)

        # Add stretch to push content to the top
        main_layout.addStretch()

    def get_config_widget(self):
        """Get the configuration widget for this plugin."""
        # Debug print
        print("TestConfigPlugin.get_config_widget() called")

        # Create a simple configuration widget
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(10, 10, 10, 10)
        config_layout.setSpacing(10)

        # Title
        title_label = QLabel("<h3>Test Configuration</h3>")
        config_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "This is a test configuration widget. "
            "If you can see this, then configuration widgets are working correctly."
        )
        desc_label.setWordWrap(True)
        config_layout.addWidget(desc_label)

        # Add some test controls
        test_btn = QPushButton("Test Button")
        test_btn.clicked.connect(lambda: self._on_config_test_clicked())
        config_layout.addWidget(test_btn)

        # Add stretch to push content to the top
        config_layout.addStretch()

        # Debug print
        print(f"Returning config widget: {config_widget}")

        return config_widget

    def _on_test_clicked(self):
        """Handle test button click."""
        self.status_label.setText("Test button clicked. Check if configuration panel is open.")

    def _on_config_test_clicked(self):
        """Handle configuration test button click."""
        self.status_label.setText("Configuration test button clicked!")
