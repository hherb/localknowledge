#!/usr/bin/env python3
"""
Example of integrating the QA Widget into an existing application.

This example shows how to add the QA Widget to an application
with a plugin-based architecture.
"""

import sys
import os

# Add the parent directory to the path so we can import localknowledge
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PySide6.QtCore import Qt
from localknowledge.ui.qa_widget import QAWidget


class QAPlugin:
    """Example plugin class for the QA Widget."""
    
    def __init__(self):
        """Initialize the plugin."""
        self.plugin_name = "QA Search"
        self.main_widget = QAWidget()
    
    def get_title(self):
        """Get the plugin title."""
        return "QA Search"
    
    def get_main_widget(self):
        """Get the main widget for the plugin."""
        return self.main_widget
    
    def get_actions(self):
        """Get actions for the plugin."""
        return []  # No actions for this plugin


class ExampleMainWindow(QMainWindow):
    """Example main window with a tab widget for plugins."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("Example Application")
        self.resize(1200, 800)
        
        # Create a tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Load plugins
        self.load_plugins()
    
    def load_plugins(self):
        """Load plugins."""
        # Create and load the QA plugin
        qa_plugin = QAPlugin()
        self.tab_widget.addTab(qa_plugin.get_main_widget(), qa_plugin.get_title())


def main():
    """Main function."""
    app = QApplication(sys.argv)
    
    window = ExampleMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
