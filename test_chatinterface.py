#!/usr/bin/env python3
"""
Test script for the ChatInterface widget.

This script creates a simple application to test the chat interface functionality.
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMenuBar, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from localknowledge.ui.chatinterface import ChatInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class ChatTestWindow(QMainWindow):
    """Test window for the chat interface."""
    
    def __init__(self):
        """Initialize the test window."""
        super().__init__()
        
        self.setWindowTitle("LocalKnowledge Chat Interface Test")
        self.setGeometry(100, 100, 900, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create chat interface
        self.chat_interface = ChatInterface()
        layout.addWidget(self.chat_interface)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Add welcome message
        self.chat_interface.add_system_message(
            "Welcome to LocalKnowledge Chat Interface Test!\n\n"
            "Features to test:\n"
            "• Type messages and send them\n"
            "• Attach files using the paperclip button\n"
            "• Drag and drop files onto the interface\n"
            "• Cancel ongoing requests\n"
            "• Try different models from the menu\n\n"
            "Note: Make sure Ollama is running with qwen3:8b model for full functionality."
        )
        
        logger.info("Chat test window initialized")
    
    def create_menu_bar(self):
        """Create the menu bar with test options."""
        menubar = self.menuBar()
        
        # Chat menu
        chat_menu = menubar.addMenu("Chat")
        
        # Clear chat action
        clear_action = QAction("Clear Chat", self)
        clear_action.triggered.connect(self.chat_interface.clear_chat)
        chat_menu.addAction(clear_action)
        
        chat_menu.addSeparator()
        
        # Model menu
        model_menu = chat_menu.addMenu("Change Model")
        
        models = ["qwen3:8b", "llama3.2:3b", "gemma2:2b", "mistral:7b"]
        for model in models:
            action = QAction(model, self)
            action.triggered.connect(lambda checked, m=model: self.change_model(m))
            model_menu.addAction(action)
        
        chat_menu.addSeparator()
        
        # Reasoning mode
        reasoning_action = QAction("Toggle Extended Reasoning", self)
        reasoning_action.setCheckable(True)
        reasoning_action.triggered.connect(self.toggle_reasoning)
        chat_menu.addAction(reasoning_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def change_model(self, model_name: str):
        """Change the AI model."""
        self.chat_interface.set_agent_model(model_name)
        logger.info(f"Changed model to: {model_name}")
    
    def toggle_reasoning(self, checked: bool):
        """Toggle extended reasoning mode."""
        self.chat_interface.toggle_extended_reasoning(checked)
        logger.info(f"Extended reasoning: {'enabled' if checked else 'disabled'}")
    
    def show_about(self):
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox
        
        QMessageBox.about(
            self,
            "About Chat Interface Test",
            "LocalKnowledge Chat Interface Test\n\n"
            "This is a test application for the chat interface widget.\n"
            "It demonstrates the chat functionality with AI agent integration.\n\n"
            "Requirements:\n"
            "• Ollama server running on localhost:11434\n"
            "• qwen3:8b model (or other compatible models)\n"
            "• LocalKnowledge database (optional for local search)"
        )


def main():
    """Main function to run the test application."""
    # Create application
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("LocalKnowledge Chat Test")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("LocalKnowledge")
    
    # Create and show main window
    window = ChatTestWindow()
    window.show()
    
    # Run application
    logger.info("Starting chat interface test application")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
