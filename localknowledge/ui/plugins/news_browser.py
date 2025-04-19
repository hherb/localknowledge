#!/usr/bin/env python3
"""
News Browser Plugin for RWB

This plugin integrates the existing NewsBrowser component from localknowledge.ui.newsbrowser.
"""

import os
import sys
import traceback
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QCheckBox, QLabel
)

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin

# Import the existing NewsBrowser
try:
    from localknowledge.ui.newsbrowser import NewsBrowser
    NEWSBROWSER_IMPORTED = True
    print("Successfully imported NewsBrowser")
except Exception as e:
    print(f"Error importing NewsBrowser: {e}")
    traceback.print_exc()
    NEWSBROWSER_IMPORTED = False


@register_plugin
class NewsBrowserPlugin(PluginBase):
    """News browser plugin for RWB that reuses the existing NewsBrowser component."""
    
    plugin_name = "News Browser"
    plugin_description = "Browse recent scientific news and preprints"
    plugin_icon = ":/icons/news.png"
    
    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)
        print("Initializing NewsBrowserPlugin")
        
        # Now that NewsBrowser is a QWidget, we can directly create and add it to our layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the NewsBrowser widget
        if NEWSBROWSER_IMPORTED:
            try:
                print("Creating NewsBrowser widget...")
                self.news_browser = NewsBrowser()
                layout.addWidget(self.news_browser)
                print("NewsBrowser widget added successfully")
            except Exception as e:
                print(f"Error creating NewsBrowser: {e}")
                traceback.print_exc()
                
                # Show an error message if we couldn't create the NewsBrowser
                error_label = QLabel(f"Error loading News Browser: {str(e)}")
                error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
                layout.addWidget(error_label)
        else:
            # Show an error message if we couldn't import the NewsBrowser
            error_label = QLabel("Error: Could not import NewsBrowser module")
            error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
            layout.addWidget(error_label)
    
    def get_config_widget(self):
        """Return configuration widget for this plugin."""
        # Create a simple wrapper config widget
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        
        # Add settings relevant to the NewsBrowser
        update_freq_group = QGroupBox("Update Frequency")
        update_layout = QVBoxLayout(update_freq_group)
        
        # Update frequency options
        daily_check = QCheckBox("Check for updates daily")
        daily_check.setChecked(True)
        update_layout.addWidget(daily_check)
        
        # Add sources configuration
        sources_group = QGroupBox("News Sources")
        sources_layout = QVBoxLayout(sources_group)
        
        # Source checkboxes
        medrxiv_check = QCheckBox("medRxiv")
        medrxiv_check.setChecked(True)
        sources_layout.addWidget(medrxiv_check)
        
        biorxiv_check = QCheckBox("bioRxiv")
        biorxiv_check.setChecked(True)
        sources_layout.addWidget(biorxiv_check)
        
        pubmed_check = QCheckBox("PubMed")
        pubmed_check.setChecked(True)
        sources_layout.addWidget(pubmed_check)
        
        # Add groups to main layout
        layout.addWidget(update_freq_group)
        layout.addWidget(sources_group)
        layout.addStretch(1)
        
        return config_widget
    
    def get_actions(self):
        """Get actions for the toolbar."""
        actions = []
        
        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh News", self)
        refresh_action.setStatusTip("Refresh publication news")
        if hasattr(self, 'news_browser'):
            refresh_action.triggered.connect(self.news_browser._load_summaries)
        actions.append(refresh_action)
        
        return actions
        
    def close_plugin(self):
        """Perform cleanup when closing the plugin."""
        # Close database connections
        if hasattr(self, 'news_browser'):
            self.news_browser.close_database()
        return True
