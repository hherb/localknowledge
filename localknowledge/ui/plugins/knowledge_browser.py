#!/usr/bin/env python3
"""
Example Knowledge Browser Plugin for RWB

This plugin provides a simple knowledge browser interface.
"""

import os
import sys
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTableView, QLabel, QComboBox,
    QHeaderView, QSplitter
)

# Import the plugin base class
import sys
import os

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin


@register_plugin
class KnowledgeBrowserPlugin(PluginBase):
    """Knowledge browser plugin for RWB."""
    
    plugin_name = "Knowledge Browser"
    plugin_description = "Browse and search your knowledge base"
    plugin_icon = ":/icons/knowledge.png"  # We'll create icons later
    
    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)
        
        # Set up UI
        self.setup_ui()
        
        # Initialize data model and database connection
        self.init_data()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Search area
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search knowledge base...")
        self.search_input.returnPressed.connect(self.search)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search)
        
        # Sources dropdown
        source_label = QLabel("Source:")
        self.sources_combo = QComboBox()
        self.sources_combo.addItems(["All Sources", "PubMed", "medRxiv", "bioRxiv", "Local Files"])
        
        # Results per page dropdown
        results_label = QLabel("Results:")
        self.results_combo = QComboBox()
        self.results_combo.addItems(["10", "25", "50", "100"])
        self.results_combo.setCurrentIndex(1)  # Default to 25
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(source_label)
        search_layout.addWidget(self.sources_combo)
        search_layout.addWidget(results_label)
        search_layout.addWidget(self.results_combo)
        
        # Results area
        self.results_table = QTableView()
        self.results_table.setSelectionBehavior(QTableView.SelectRows)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Detail area
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        
        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.detail_content = QLabel("")
        self.detail_content.setWordWrap(True)
        
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_content)
        
        # Split view for results and details
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.results_table)
        splitter.addWidget(detail_widget)
        
        # Add everything to main layout
        layout.addWidget(search_widget)
        layout.addWidget(splitter)
    
    def init_data(self):
        """Initialize the data model and connections."""
        # This would connect to your knowledge database
        pass
    
    def search(self):
        """Perform a search in the knowledge base."""
        query = self.search_input.text()
        if not query:
            return
            
        # This would search your knowledge base
        # For now, we'll just print the query
        print(f"Searching for: {query}")
        
    def get_config_widget(self) -> QWidget:
        """
        Get the configuration widget for this plugin.
        
        Returns:
            QWidget: Configuration widget
        """
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        
        # Sources selection
        sources_label = QLabel("Knowledge Sources:")
        self.sources_combo = QComboBox()
        self.sources_combo.addItems(["All Sources", "PubMed", "medRxiv", "Local Files"])
        
        # Results per page
        results_label = QLabel("Results per page:")
        self.results_combo = QComboBox()
        self.results_combo.addItems(["10", "20", "50", "100"])
        
        layout.addWidget(sources_label)
        layout.addWidget(self.sources_combo)
        layout.addWidget(results_label)
        layout.addWidget(self.results_combo)
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
            "Refresh",
            self
        )
        refresh_action.setStatusTip("Refresh knowledge base")
        refresh_action.triggered.connect(self.refresh)
        
        export_action = QAction(
            QIcon.fromTheme("document-save", QIcon(":/icons/export.png")),
            "Export Results",
            self
        )
        export_action.setStatusTip("Export search results")
        export_action.triggered.connect(self.export_results)
        
        return [refresh_action, export_action]
    
    def refresh(self):
        """Refresh the knowledge base."""
        print("Refreshing knowledge base...")
    
    def export_results(self):
        """Export search results."""
        print("Exporting results...")
    
    def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the plugin.
        
        Returns:
            Dict[str, Any]: Dictionary containing state data
        """
        return {
            "search_text": self.search_input.text(),
            "source_index": self.sources_combo.currentIndex(),
            "results_per_page": self.results_combo.currentText()
        }
    
    def restore_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore a previously saved state.
        
        Args:
            state: Dictionary containing state data
            
        Returns:
            bool: True if state was restored successfully, False otherwise
        """
        if not state:
            return False
            
        if "search_text" in state:
            self.search_input.setText(state["search_text"])
            
        if "source_index" in state:
            self.sources_combo.setCurrentIndex(state["source_index"])
            
        if "results_per_page" in state:
            index = self.results_combo.findText(state["results_per_page"])
            if index >= 0:
                self.results_combo.setCurrentIndex(index)
                
        return True
