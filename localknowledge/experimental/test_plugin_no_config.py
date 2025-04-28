#!/usr/bin/env python3
"""Test plugin without configuration for the RWB application."""

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
class TestPluginNoConfig(PluginBase):
    """A test plugin without configuration widget."""
    
    plugin_name = "Test Plugin No Config"
    plugin_description = "A test plugin that doesn't have a configuration widget"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up a simple UI
        layout = QVBoxLayout(self)
        label = QLabel("This plugin has no configuration widget!", self)
        label.setStyleSheet("font-size: 24px; color: blue;")
        layout.addWidget(label)
        
    def get_config_widget(self):
        """Return None to indicate no configuration widget."""
        return None
