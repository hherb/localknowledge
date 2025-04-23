#!/usr/bin/env python3
"""
Test script for the QA Widget.

This script demonstrates how to use the QA Widget in a standalone application.
"""

import sys
import os

# Add the parent directory to the path so we can import localknowledge
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow
from localknowledge.ui.qa_widget import QAWidget


class TestWindow(QMainWindow):
    """Test window for the QA Widget."""
    
    def __init__(self):
        """Initialize the test window."""
        super().__init__()
        
        self.setWindowTitle("QA Widget Test")
        self.resize(1200, 800)
        
        # Create the QA widget
        self.qa_widget = QAWidget()
        
        # Set as central widget
        self.setCentralWidget(self.qa_widget)


def main():
    """Main function."""
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
