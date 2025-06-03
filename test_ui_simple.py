#!/usr/bin/env python3
"""
Simple test script to check if the configuration sidebar and splitter work correctly.
"""

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QLabel, QPushButton, QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt

class ConfigPanel(QWidget):
    """Simple configuration panel for testing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Configuration Panel")
        header.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px;")
        layout.addWidget(header)
        
        # Some config controls
        for i in range(5):
            btn = QPushButton(f"Config Option {i+1}")
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Style
        self.setStyleSheet("""
            ConfigPanel {
                background-color: #f0f0f0;
                border-right: 1px solid #ccc;
            }
        """)

class MainContent(QWidget):
    """Main content area for testing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Main Content Area")
        header.setStyleSheet("font-weight: bold; font-size: 18px; padding: 10px;")
        layout.addWidget(header)
        
        # Text area
        text_area = QTextEdit()
        text_area.setPlainText("This is the main content area.\n\nThe configuration panel should be on the left side and the splitter should allow you to resize both panels.\n\nTry dragging the splitter handle to test if it works correctly.")
        layout.addWidget(text_area)

class TestMainWindow(QMainWindow):
    """Test main window with splitter and config panel."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuration Sidebar Test")
        self.setGeometry(100, 100, 1000, 600)
        self.setup_ui()
    
    def setup_ui(self):
        # Central widget
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)
        
        # Create splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setOpaqueResize(True)
        
        # Style the splitter handle
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cccccc;
                border: 1px solid #999999;
                margin: 2px;
            }
            QSplitter::handle:hover {
                background-color: #aaaaaa;
            }
            QSplitter::handle:pressed {
                background-color: #888888;
            }
        """)
        
        # Create panels
        self.config_panel = ConfigPanel()
        self.main_content = MainContent()
        
        # Add panels to splitter
        self.main_splitter.addWidget(self.config_panel)
        self.main_splitter.addWidget(self.main_content)
        
        # Set initial sizes (config panel: 300px, main content: rest)
        self.main_splitter.setSizes([300, 700])
        
        # Add splitter to layout
        central_layout.addWidget(self.main_splitter)
        
        # Add toggle button
        toggle_button = QPushButton("Toggle Config Panel")
        toggle_button.clicked.connect(self.toggle_config_panel)
        central_layout.addWidget(toggle_button)
        
        # Connect splitter signal
        self.main_splitter.splitterMoved.connect(self.on_splitter_moved)
    
    def toggle_config_panel(self):
        """Toggle the configuration panel visibility."""
        sizes = self.main_splitter.sizes()
        total_width = sum(sizes)
        
        if sizes[0] > 50:  # Panel is expanded
            # Collapse panel
            self.main_splitter.setSizes([0, total_width])
        else:
            # Expand panel
            self.main_splitter.setSizes([300, total_width - 300])
    
    def on_splitter_moved(self, pos, index):
        """Handle splitter movement."""
        sizes = self.main_splitter.sizes()
        print(f"Splitter moved: sizes = {sizes}")

def main():
    app = QApplication(sys.argv)
    
    window = TestMainWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
