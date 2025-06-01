#!/usr/bin/env python3
"""
Simple Chat Interface Plugin for LocalKnowledge.

This is a simplified version of the chat plugin that avoids potential
import issues by lazy-loading the chat interface.
"""

import os
import logging
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QSizePolicy, QTextEdit
)

# Import the plugin system
try:
    # Try the direct import first (for plugin finder compatibility)
    from rwb_main import PluginBase
except ImportError:
    # Fall back to the full path import
    from localknowledge.ui.rwb_main import PluginBase

from localknowledge.ui.plugins.plugin_finder import register_plugin

# Configure logging
logger = logging.getLogger(__name__)


@register_plugin
class SimpleChatPlugin(PluginBase):
    """
    Simple Chat Interface Plugin for LocalKnowledge.
    
    This plugin provides a basic chat interface that lazy-loads
    the full chat functionality to avoid import issues.
    """
    
    plugin_name = "AI Chat"
    plugin_description = "Chat with AI assistant using LocalKnowledge and web search"
    plugin_icon = None
    
    def __init__(self, parent=None):
        """Initialize the simple chat plugin."""
        super().__init__(parent)
        
        # Initialize components
        self.chat_interface = None
        self.config_widget = None
        self.is_chat_loaded = False
        
        # Setup UI
        self.setup_ui()
        
        logger.info("Simple Chat Plugin initialized")
    
    def setup_ui(self):
        """Set up the plugin user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Welcome message
        welcome_label = QLabel("Welcome to LocalKnowledge AI Chat!")
        welcome_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2962ff;
                text-align: center;
            }
        """)
        welcome_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(welcome_label)
        
        # Description
        desc_label = QLabel(
            "This plugin provides AI chat functionality with:\n\n"
            "• Medical and scientific literature questions\n"
            "• Current research and news via web search\n"
            "• Document analysis and summarization\n"
            "• General knowledge questions\n\n"
            "Click 'Load Chat Interface' to start chatting!"
        )
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333;
                background-color: #f9f9f9;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Load button
        self.load_button = QPushButton("Load Chat Interface")
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: #2962ff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e50f7;
            }
            QPushButton:pressed {
                background-color: #0039cb;
            }
        """)
        self.load_button.clicked.connect(self.load_chat_interface)
        layout.addWidget(self.load_button)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Add stretch
        layout.addStretch()
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    
    @Slot()
    def load_chat_interface(self):
        """Load the full chat interface."""
        if self.is_chat_loaded:
            return
        
        try:
            self.status_label.setText("Loading chat interface...")
            self.load_button.setEnabled(False)
            
            # Import and create chat interface
            from localknowledge.ui.chatinterface import ChatInterface
            
            # Clear current layout
            layout = self.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # Create chat interface
            self.chat_interface = ChatInterface()
            layout.addWidget(self.chat_interface)
            
            # Add welcome message
            self.chat_interface.add_system_message(
                "Welcome to LocalKnowledge AI Chat!\n\n"
                "I can help you with medical and scientific literature questions, "
                "current research, and general knowledge. Use the configuration "
                "panel to adjust AI model and settings."
            )
            
            self.is_chat_loaded = True
            logger.info("Chat interface loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load chat interface: {e}")
            self.status_label.setText(f"Error loading chat interface: {str(e)}")
            self.load_button.setEnabled(True)
            
            QMessageBox.warning(
                self,
                "Load Error",
                f"Failed to load chat interface:\n{str(e)}\n\n"
                "Make sure Ollama is running and the required dependencies are installed."
            )
    
    def initialize(self) -> bool:
        """
        Initialize the plugin.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("Simple Chat Plugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Simple Chat Plugin: {e}")
            return False
    
    def get_main_widget(self) -> QWidget:
        """
        Get the main widget for this plugin.
        
        Returns:
            QWidget: The plugin widget
        """
        return self
    
    def get_config_widget(self) -> Optional[QWidget]:
        """
        Get the configuration widget for this plugin.
        
        Returns:
            Optional[QWidget]: Configuration widget or None
        """
        if self.is_chat_loaded and self.chat_interface:
            # Create a simple config widget
            if not self.config_widget:
                self.config_widget = QWidget()
                layout = QVBoxLayout(self.config_widget)
                
                label = QLabel("Chat Interface Configuration")
                label.setStyleSheet("font-weight: bold; font-size: 14px;")
                layout.addWidget(label)
                
                clear_button = QPushButton("Clear Chat")
                clear_button.clicked.connect(self.clear_chat)
                layout.addWidget(clear_button)
                
                layout.addStretch()
            
            return self.config_widget
        
        return None
    
    def get_title(self) -> str:
        """
        Get the display title for this plugin.
        
        Returns:
            str: Display title
        """
        return self.plugin_name
    
    def get_actions(self) -> List[QAction]:
        """
        Get toolbar actions for this plugin.
        
        Returns:
            List[QAction]: List of actions
        """
        actions = []
        
        if self.is_chat_loaded:
            # Clear chat action
            clear_action = QAction("Clear Chat", self)
            clear_action.setToolTip("Clear all chat messages")
            clear_action.triggered.connect(self.clear_chat)
            actions.append(clear_action)
        
        return actions
    
    @Slot()
    def clear_chat(self):
        """Clear chat action handler."""
        if self.is_chat_loaded and self.chat_interface:
            self.chat_interface.clear_chat()
    
    def close_plugin(self) -> bool:
        """
        Perform cleanup when closing the plugin.
        
        Returns:
            bool: True if plugin can be safely closed
        """
        try:
            if self.is_chat_loaded and self.chat_interface:
                # Cancel any ongoing operations
                if hasattr(self.chat_interface, 'agent_worker') and self.chat_interface.agent_worker:
                    if self.chat_interface.agent_worker.isRunning():
                        self.chat_interface.agent_worker.cancel()
                        self.chat_interface.agent_worker.wait()
                
                # Close agent
                if hasattr(self.chat_interface, 'agent') and self.chat_interface.agent:
                    self.chat_interface.agent.close()
            
            logger.info("Simple Chat Plugin closed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error closing Simple Chat Plugin: {e}")
            return False


# Example usage for testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Simple Chat Plugin Test")
    window.setGeometry(100, 100, 800, 600)
    
    # Create plugin
    plugin = SimpleChatPlugin()
    plugin.initialize()
    
    # Set as central widget
    window.setCentralWidget(plugin.get_main_widget())
    
    window.show()
    sys.exit(app.exec())
