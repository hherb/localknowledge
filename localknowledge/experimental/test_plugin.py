#!/usr/bin/env python3
"""Simple test plugin for the RWB application."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
import sys
import os

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin

@register_plugin
class TestPlugin(PluginBase):
    """A simple test plugin."""
    
    plugin_name = "Test Plugin"
    plugin_description = "A simple test plugin to verify plugin loading"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up a simple UI
        layout = QVBoxLayout(self)
        label = QLabel("Test plugin loaded successfully!", self)
        label.setStyleSheet("font-size: 24px; color: green;")
        layout.addWidget(label)
        
    def get_config_widget(self):
        """Return a simple configuration widget."""
        widget = QLabel("Test plugin configuration")
        return widget
