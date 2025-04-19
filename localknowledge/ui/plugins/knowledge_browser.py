#!/usr/bin/env python3
"""
Knowledge Browser Plugin for RWB

This plugin integrates the standalone KnowledgeBrowser with the plugin system.
"""

import os
import sys
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the standalone KnowledgeBrowser
from localknowledge.ui.knowledgebrowser import KnowledgeBrowser
from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin


@register_plugin
class KnowledgeBrowserPlugin(PluginBase):
    """Knowledge browser plugin that integrates the standalone KnowledgeBrowser."""
    
    plugin_name = "Knowledge Browser"
    plugin_description = "Browse and search your knowledge base"
    plugin_icon = ":/icons/knowledge.png"
    
    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface by embedding the standalone KnowledgeBrowser."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create instance of the standalone KnowledgeBrowser
        self.knowledge_browser = KnowledgeBrowser(self)
        
        # Add the KnowledgeBrowser to the layout
        layout.addWidget(self.knowledge_browser)
    
    def get_config_widget(self) -> QWidget:
        """
        Get the configuration widget for this plugin.
        
        Returns:
            QWidget: Configuration widget
        """
        # We could add plugin-specific settings here if needed
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        layout.addWidget(QPushButton("Knowledge Browser Settings"))
        layout.addStretch(1)
        return config_widget
    
    def get_actions(self) -> List[QAction]:
        """
        Get a list of actions this plugin provides for menus/toolbars.
        
        Returns:
            List[QAction]: List of actions
        """
        refresh_action = QAction(
            QIcon.fromTheme("view-refresh", QIcon(":/icons/refresh.png")),
            "Refresh Knowledge Base",
            self
        )
        refresh_action.setStatusTip("Refresh knowledge base")
        refresh_action.triggered.connect(self.refresh)
        
        return [refresh_action]
    
    def refresh(self):
        """Refresh the knowledge browser."""
        # If we had refresh functionality in KnowledgeBrowser, we would call it here
        print("Refreshing knowledge base...")
    
    def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the plugin.
        
        Returns:
            Dict[str, Any]: Dictionary containing state data
        """
        # Basic state saving
        return {
            "active": True
        }
    
    def restore_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore a previously saved state.
        
        Args:
            state: Dictionary containing state data
            
        Returns:
            bool: True if state was restored successfully, False otherwise
        """
        # Nothing to restore currently
        return True
        
    def cleanup(self):
        """Clean up resources before plugin is unloaded."""
        if hasattr(self, 'knowledge_browser') and hasattr(self.knowledge_browser, 'close_database'):
            self.knowledge_browser.close_database()
