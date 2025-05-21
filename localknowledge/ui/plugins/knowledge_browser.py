#!/usr/bin/env python3
"""
Knowledge Browser Plugin for RWB

This plugin integrates the standalone KnowledgeBrowser with the plugin system.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the standalone KnowledgeBrowser and settings widget
from localknowledge.ui.knowledgebrowser import KnowledgeBrowser
from localknowledge.ui.knowledgebrowser_settings import KnowledgeBrowserSettings
from localknowledge.ui.rwb_main import PluginBase  # Use the correct import path
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

        # Current settings
        self.settings = {}

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

        # Create settings widget (not added to layout)
        self.settings_widget = KnowledgeBrowserSettings(self)
        self.settings_widget.settingsChanged.connect(self._on_settings_changed)

    def get_config_widget(self) -> QWidget:
        """
        Get the configuration widget for this plugin.

        Returns:
            QWidget: Configuration widget
        """
        # Return the settings widget
        return self.settings_widget

    @Slot(dict)
    def _on_settings_changed(self, settings: Dict[str, Any]) -> None:
        """
        Handle settings changes.

        Args:
            settings: New settings dictionary
        """
        logger.info("Knowledge Browser settings changed")
        self.settings = settings

        # Update the knowledge browser with new settings
        if hasattr(self.knowledge_browser, 'search_settings'):
            # Update search settings
            self.knowledge_browser.search_settings.update({
                'similarity_threshold': settings['semantic_settings']['similarity_threshold'],
                'max_results': settings['semantic_settings']['max_results'],
                'use_reranker': settings['semantic_settings']['use_reranker'],
                'reranker_model': settings['semantic_settings']['reranker_model'],
                'hybrid_weight': settings['hybrid_settings']['semantic_weight'],
                'embedding_model': settings['semantic_settings']['embedding_model'],
                'use_hyde': settings['semantic_settings']['use_hyde'],
                'hyde_model': settings['semantic_settings']['hyde_model']
            })

            # Update search sources
            if hasattr(self.knowledge_browser, 'search_sources'):
                self.knowledge_browser.search_sources = settings['sources']

            # Update search strategies
            if hasattr(self.knowledge_browser, 'search_strategies'):
                self.knowledge_browser.search_strategies = settings['search_strategies']

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
