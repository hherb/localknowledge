#!/usr/bin/env python3
"""
Chat Interface Plugin for LocalKnowledge.

This plugin integrates the ChatInterface widget into the main application
as a plugin, providing AI chat functionality through the plugin system.
"""

import os
import logging
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QGroupBox, QFormLayout, QSpinBox,
    QTextEdit, QMessageBox, QSizePolicy
)

# Import the plugin system
try:
    # Try the direct import first (for plugin finder compatibility)
    from rwb_main import PluginBase
except ImportError:
    # Fall back to the full path import
    from localknowledge.ui.rwb_main import PluginBase

from localknowledge.ui.plugins.plugin_finder import register_plugin

# Import our chat interface
from localknowledge.ui.chatinterface import ChatInterface

# Configure logging
logger = logging.getLogger(__name__)


class ChatConfigWidget(QWidget):
    """
    Configuration widget for the chat interface plugin.
    
    Allows users to configure AI model, reasoning mode, and other settings.
    """
    
    # Signals
    model_changed = Signal(str)  # Model name changed
    reasoning_toggled = Signal(bool)  # Extended reasoning toggled
    settings_changed = Signal(dict)  # General settings changed
    
    def __init__(self, chat_interface: ChatInterface, parent=None):
        """
        Initialize the configuration widget.
        
        Args:
            chat_interface: The ChatInterface instance to configure
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.chat_interface = chat_interface
        self.setup_ui()
        self.setup_connections()
        
        # Load current settings
        self.load_current_settings()
        
        logger.info("Chat configuration widget initialized")
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # AI Model Configuration
        model_group = QGroupBox("AI Model Configuration")
        model_layout = QFormLayout(model_group)
        
        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "qwen3:8b",
            "llama3.2:3b", 
            "gemma2:2b",
            "mistral:7b",
            "deepseek-r1:1.5b",
            "qwq:32b"
        ])
        self.model_combo.setCurrentText("qwen3:8b")
        model_layout.addRow("Model:", self.model_combo)
        
        # Extended reasoning
        self.reasoning_checkbox = QCheckBox("Enable Extended Reasoning")
        self.reasoning_checkbox.setToolTip(
            "Enable extended reasoning for more thorough but slower responses"
        )
        model_layout.addRow("Reasoning:", self.reasoning_checkbox)
        
        layout.addWidget(model_group)
        
        # Search Configuration
        search_group = QGroupBox("Search Configuration")
        search_layout = QFormLayout(search_group)
        
        # Web search
        self.web_search_checkbox = QCheckBox("Enable Web Search")
        self.web_search_checkbox.setChecked(True)
        self.web_search_checkbox.setToolTip("Allow the AI to search the web for current information")
        search_layout.addRow("Web Search:", self.web_search_checkbox)
        
        # Local search
        self.local_search_checkbox = QCheckBox("Enable Local Search")
        self.local_search_checkbox.setChecked(True)
        self.local_search_checkbox.setToolTip("Allow the AI to search the local knowledge database")
        search_layout.addRow("Local Search:", self.local_search_checkbox)
        
        # Max results
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 20)
        self.max_results_spin.setValue(5)
        self.max_results_spin.setToolTip("Maximum number of search results to consider")
        search_layout.addRow("Max Results:", self.max_results_spin)
        
        layout.addWidget(search_group)
        
        # Chat Configuration
        chat_group = QGroupBox("Chat Configuration")
        chat_layout = QFormLayout(chat_group)
        
        # Auto-scroll
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll to new messages")
        self.auto_scroll_checkbox.setChecked(True)
        chat_layout.addRow("Auto-scroll:", self.auto_scroll_checkbox)
        
        layout.addWidget(chat_group)
        
        # Action Buttons
        buttons_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2962ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e50f7;
            }
        """)
        buttons_layout.addWidget(self.apply_button)
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #2962ff;
                border: 1px solid #2962ff;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        buttons_layout.addWidget(self.reset_button)
        
        self.clear_chat_button = QPushButton("Clear Chat")
        self.clear_chat_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        buttons_layout.addWidget(self.clear_chat_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    
    def setup_connections(self):
        """Set up signal-slot connections."""
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        self.reasoning_checkbox.toggled.connect(self.on_reasoning_toggled)
        self.apply_button.clicked.connect(self.apply_settings)
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.clear_chat_button.clicked.connect(self.clear_chat)
    
    def load_current_settings(self):
        """Load current settings from the chat interface."""
        if self.chat_interface and self.chat_interface.agent:
            # Set model if available
            model_name = getattr(self.chat_interface.agent, 'model_name', 'qwen3:8b')
            index = self.model_combo.findText(model_name)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            
            # Set reasoning mode
            extended_reasoning = getattr(self.chat_interface.agent, 'enable_extended_reasoning', False)
            self.reasoning_checkbox.setChecked(extended_reasoning)
            
            # Set search settings
            web_search = getattr(self.chat_interface.agent, 'enable_web_search', True)
            self.web_search_checkbox.setChecked(web_search)
            
            local_search = getattr(self.chat_interface.agent, 'enable_local_search', True)
            self.local_search_checkbox.setChecked(local_search)

    @Slot(str)
    def on_model_changed(self, model_name: str):
        """Handle model selection change."""
        self.model_changed.emit(model_name)
        logger.info(f"Model changed to: {model_name}")

    @Slot(bool)
    def on_reasoning_toggled(self, enabled: bool):
        """Handle reasoning mode toggle."""
        self.reasoning_toggled.emit(enabled)
        logger.info(f"Extended reasoning {'enabled' if enabled else 'disabled'}")

    @Slot()
    def apply_settings(self):
        """Apply current settings to the chat interface."""
        try:
            # Apply model change
            model_name = self.model_combo.currentText()
            if self.chat_interface:
                self.chat_interface.set_agent_model(model_name)

            # Apply reasoning mode
            reasoning_enabled = self.reasoning_checkbox.isChecked()
            if self.chat_interface:
                self.chat_interface.toggle_extended_reasoning(reasoning_enabled)

            # Emit settings changed signal
            settings = {
                'model': model_name,
                'extended_reasoning': reasoning_enabled,
                'web_search': self.web_search_checkbox.isChecked(),
                'local_search': self.local_search_checkbox.isChecked(),
                'max_results': self.max_results_spin.value(),
                'auto_scroll': self.auto_scroll_checkbox.isChecked()
            }
            self.settings_changed.emit(settings)

            # Show confirmation
            QMessageBox.information(
                self,
                "Settings Applied",
                "Chat interface settings have been applied successfully."
            )

            logger.info("Chat settings applied successfully")

        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            QMessageBox.warning(
                self,
                "Settings Error",
                f"Failed to apply settings: {str(e)}"
            )

    @Slot()
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.model_combo.setCurrentText("qwen3:8b")
        self.reasoning_checkbox.setChecked(False)
        self.web_search_checkbox.setChecked(True)
        self.local_search_checkbox.setChecked(True)
        self.max_results_spin.setValue(5)
        self.auto_scroll_checkbox.setChecked(True)

        logger.info("Chat settings reset to defaults")

    @Slot()
    def clear_chat(self):
        """Clear the chat history."""
        if self.chat_interface:
            reply = QMessageBox.question(
                self,
                "Clear Chat",
                "Are you sure you want to clear all chat messages?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.chat_interface.clear_chat()
                logger.info("Chat history cleared")


@register_plugin
class ChatInterfacePlugin(PluginBase):
    """
    Chat Interface Plugin for LocalKnowledge.

    Provides AI chat functionality through the plugin system with
    configuration options and integration with the main application.
    """

    plugin_name = "AI Chat"
    plugin_description = "Chat with AI assistant using LocalKnowledge and web search"
    plugin_icon = None  # Could add a chat icon here

    def __init__(self, parent=None):
        """Initialize the chat interface plugin."""
        super().__init__(parent)

        # Initialize components
        self.chat_interface = None
        self.config_widget = None

        # Setup UI
        self.setup_ui()
        self.setup_connections()

        logger.info("Chat Interface Plugin initialized")

    def setup_ui(self):
        """Set up the plugin user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create chat interface
        self.chat_interface = ChatInterface()
        layout.addWidget(self.chat_interface)

        # Add welcome message
        self.chat_interface.add_system_message(
            "Welcome to LocalKnowledge AI Chat!\n\n"
            "I can help you with:\n"
            "• Medical and scientific literature questions\n"
            "• Current research and news\n"
            "• Document analysis and summarization\n"
            "• General knowledge questions\n\n"
            "Use the configuration panel to adjust AI model and settings."
        )

        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setup_connections(self):
        """Set up signal-slot connections."""
        if self.chat_interface:
            # Connect chat interface signals
            self.chat_interface.message_sent.connect(self.on_message_sent)
            self.chat_interface.response_received.connect(self.on_response_received)

    def initialize(self) -> bool:
        """
        Initialize the plugin.

        Returns:
            bool: True if initialization was successful
        """
        try:
            # Create configuration widget
            if self.chat_interface:
                self.config_widget = ChatConfigWidget(self.chat_interface)

                # Connect configuration signals
                self.config_widget.model_changed.connect(self.on_model_changed)
                self.config_widget.reasoning_toggled.connect(self.on_reasoning_toggled)
                self.config_widget.settings_changed.connect(self.on_settings_changed)

            logger.info("Chat Interface Plugin initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Chat Interface Plugin: {e}")
            return False

    def get_main_widget(self) -> QWidget:
        """
        Get the main widget for this plugin.

        Returns:
            QWidget: The chat interface widget
        """
        return self

    def get_config_widget(self) -> Optional[QWidget]:
        """
        Get the configuration widget for this plugin.

        Returns:
            Optional[QWidget]: Configuration widget or None
        """
        return self.config_widget

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

        # Clear chat action
        clear_action = QAction("Clear Chat", self)
        clear_action.setToolTip("Clear all chat messages")
        clear_action.triggered.connect(self.clear_chat)
        actions.append(clear_action)

        # Toggle reasoning action
        reasoning_action = QAction("Toggle Reasoning", self)
        reasoning_action.setToolTip("Toggle extended reasoning mode")
        reasoning_action.setCheckable(True)
        reasoning_action.triggered.connect(self.toggle_reasoning)
        actions.append(reasoning_action)

        return actions

    # Signal handlers
    @Slot(str)
    def on_message_sent(self, message: str):
        """Handle message sent signal from chat interface."""
        logger.info(f"User message sent: {message[:50]}...")

    @Slot(str)
    def on_response_received(self, response: str):
        """Handle response received signal from chat interface."""
        logger.info(f"AI response received: {response[:50]}...")

    @Slot(str)
    def on_model_changed(self, model_name: str):
        """Handle model change from configuration."""
        logger.info(f"Model changed via config: {model_name}")

    @Slot(bool)
    def on_reasoning_toggled(self, enabled: bool):
        """Handle reasoning toggle from configuration."""
        logger.info(f"Reasoning toggled via config: {enabled}")

    @Slot(dict)
    def on_settings_changed(self, settings: Dict[str, Any]):
        """Handle settings change from configuration."""
        logger.info(f"Settings changed: {settings}")

    # Action handlers
    @Slot()
    def clear_chat(self):
        """Clear chat action handler."""
        if self.chat_interface:
            self.chat_interface.clear_chat()

    @Slot(bool)
    def toggle_reasoning(self, enabled: bool):
        """Toggle reasoning action handler."""
        if self.chat_interface:
            self.chat_interface.toggle_extended_reasoning(enabled)

        # Update config widget if available
        if self.config_widget:
            self.config_widget.reasoning_checkbox.setChecked(enabled)

    # Plugin lifecycle methods
    def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the plugin.

        Returns:
            Dict[str, Any]: State data
        """
        state = {}

        # Save configuration settings
        if self.config_widget:
            state.update({
                'model': self.config_widget.model_combo.currentText(),
                'extended_reasoning': self.config_widget.reasoning_checkbox.isChecked(),
                'web_search': self.config_widget.web_search_checkbox.isChecked(),
                'local_search': self.config_widget.local_search_checkbox.isChecked(),
                'max_results': self.config_widget.max_results_spin.value(),
                'auto_scroll': self.config_widget.auto_scroll_checkbox.isChecked()
            })

        # Save chat interface state (could include message history in the future)
        if self.chat_interface:
            state['chat_initialized'] = True

        logger.info("Chat plugin state saved")
        return state

    def restore_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore a previously saved state.

        Args:
            state: Dictionary containing state data

        Returns:
            bool: True if state was restored successfully
        """
        try:
            # Restore configuration settings
            if self.config_widget and state:
                if 'model' in state:
                    index = self.config_widget.model_combo.findText(state['model'])
                    if index >= 0:
                        self.config_widget.model_combo.setCurrentIndex(index)

                if 'extended_reasoning' in state:
                    self.config_widget.reasoning_checkbox.setChecked(state['extended_reasoning'])

                if 'web_search' in state:
                    self.config_widget.web_search_checkbox.setChecked(state['web_search'])

                if 'local_search' in state:
                    self.config_widget.local_search_checkbox.setChecked(state['local_search'])

                if 'max_results' in state:
                    self.config_widget.max_results_spin.setValue(state['max_results'])

                if 'auto_scroll' in state:
                    self.config_widget.auto_scroll_checkbox.setChecked(state['auto_scroll'])

                # Apply the restored settings
                self.config_widget.apply_settings()

            logger.info("Chat plugin state restored successfully")
            return True

        except Exception as e:
            logger.error(f"Error restoring chat plugin state: {e}")
            return False

    def close_plugin(self) -> bool:
        """
        Perform cleanup when closing the plugin.

        Returns:
            bool: True if plugin can be safely closed
        """
        try:
            # Cancel any ongoing agent operations
            if self.chat_interface and self.chat_interface.agent_worker:
                if self.chat_interface.agent_worker.isRunning():
                    self.chat_interface.agent_worker.cancel()
                    self.chat_interface.agent_worker.wait()

            # Close agent
            if self.chat_interface and self.chat_interface.agent:
                self.chat_interface.agent.close()

            logger.info("Chat Interface Plugin closed successfully")
            return True

        except Exception as e:
            logger.error(f"Error closing Chat Interface Plugin: {e}")
            return False


# Example usage for testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Chat Interface Plugin Test")
    window.setGeometry(100, 100, 1000, 700)

    # Create plugin
    plugin = ChatInterfacePlugin()
    plugin.initialize()

    # Set as central widget
    window.setCentralWidget(plugin.get_main_widget())

    window.show()
    sys.exit(app.exec())
