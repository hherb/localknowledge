"""
Chatbot Interface Widget for LocalKnowledge.

This module provides a chat interface widget with dialog cards and input controls.
The interface includes:
- Upper area with scrollable dialog cards (user and AI messages)
- Lower area with text input, file attachment, and control buttons
- Integration with LocalKnowledge AI agent for responses
- Support for streaming responses and file attachments
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont, QTextCursor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QScrollArea, QFrame, QLabel, QFileDialog, QMessageBox,
    QSizePolicy, QSpacerItem, QProgressBar, QApplication
)

from .styles import STYLE_SHEETS, COLORS, get_font, get_color
from ..ai.agent import LocalKnowledgeAgent, AgentContext

# Configure logging
logger = logging.getLogger(__name__)


class MessageCard(QFrame):
    """
    A card widget for displaying individual chat messages.
    
    Supports both user and AI messages with different styling.
    """
    
    def __init__(self, message: str, is_user: bool = True, parent=None):
        """
        Initialize a message card.
        
        Args:
            message: The message text to display
            is_user: True if this is a user message, False for AI message
            parent: Parent widget
        """
        super().__init__(parent)
        self.message = message
        self.is_user = is_user
        
        self.setup_ui()
        self.apply_styling()
    
    def setup_ui(self):
        """Set up the user interface for the message card."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Message label
        self.message_label = QLabel(self.message)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.message_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        # Set font
        font = get_font("normal", "normal")
        self.message_label.setFont(font)
        
        layout.addWidget(self.message_label)
        
        # Set size policy to expand horizontally
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    
    def apply_styling(self):
        """Apply styling based on message type (user vs AI)."""
        if self.is_user:
            # User message styling - right aligned, blue background
            self.setStyleSheet(f"""
                MessageCard {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border-radius: 12px;
                    margin: 4px 40px 4px 4px;
                }}
            """)
            self.message_label.setStyleSheet("color: white;")
        else:
            # AI message styling - left aligned, light background
            self.setStyleSheet(f"""
                MessageCard {{
                    background-color: {COLORS['alt_background']};
                    color: {COLORS['text']};
                    border-radius: 12px;
                    margin: 4px 4px 4px 40px;
                    border: 1px solid {COLORS['hover']};
                }}
            """)
            self.message_label.setStyleSheet(f"color: {COLORS['text']};")
    
    def update_message(self, message: str):
        """
        Update the message content.
        
        Args:
            message: New message text
        """
        self.message = message
        self.message_label.setText(message)


class ChatScrollArea(QScrollArea):
    """
    Custom scroll area for chat messages with auto-scroll functionality.
    """
    
    def __init__(self, parent=None):
        """Initialize the chat scroll area."""
        super().__init__(parent)
        
        # Configure scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()  # Push messages to top
        
        self.setWidget(self.content_widget)
        
        # Apply styling
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['hover']};
                border-radius: 8px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {COLORS['background']};
            }}
        """)
    
    def add_message(self, message: str, is_user: bool = True) -> MessageCard:
        """
        Add a message card to the chat area.
        
        Args:
            message: Message text
            is_user: True for user message, False for AI message
            
        Returns:
            The created MessageCard widget
        """
        # Remove the stretch item temporarily
        stretch_item = self.content_layout.takeAt(self.content_layout.count() - 1)
        
        # Create and add message card
        card = MessageCard(message, is_user)
        self.content_layout.addWidget(card)
        
        # Re-add stretch item
        self.content_layout.addItem(stretch_item)
        
        # Auto-scroll to bottom
        QTimer.singleShot(10, self.scroll_to_bottom)
        
        return card
    
    def scroll_to_bottom(self):
        """Scroll to the bottom of the chat area."""
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_messages(self):
        """Clear all messages from the chat area."""
        # Remove all widgets except the stretch item
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class AgentWorker(QThread):
    """
    Worker thread for running AI agent operations without blocking the UI.
    """
    
    # Signals
    response_ready = Signal(str)  # Full response ready
    response_chunk = Signal(str)  # Streaming chunk
    error_occurred = Signal(str)  # Error message
    finished = Signal()  # Operation completed
    
    def __init__(self, agent: LocalKnowledgeAgent, user_input: str, context: Optional[AgentContext] = None):
        """
        Initialize the agent worker.
        
        Args:
            agent: The LocalKnowledge agent instance
            user_input: User's input message
            context: Optional agent context
        """
        super().__init__()
        self.agent = agent
        self.user_input = user_input
        self.context = context or AgentContext()
        self.is_cancelled = False
    
    def cancel(self):
        """Cancel the current operation."""
        self.is_cancelled = True
    
    def run(self):
        """Run the agent in the worker thread."""
        try:
            # Use asyncio to run the streaming agent
            asyncio.run(self._run_streaming())
        except Exception as e:
            if not self.is_cancelled:
                logger.error(f"Agent worker error: {e}")
                self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()
    
    async def _run_streaming(self):
        """Run the agent with streaming support."""
        try:
            collected_response = ""
            
            # Use the streaming events interface
            async for event in self.agent.stream_events(self.user_input, self.context):
                if self.is_cancelled:
                    break
                
                if event.event_type == "text_delta":
                    collected_response += event.content
                    self.response_chunk.emit(event.content)
                elif event.event_type == "final_result":
                    # Emit the final complete response
                    final_answer = event.metadata.get("answer", collected_response)
                    self.response_ready.emit(final_answer)
                    break
                elif event.event_type == "error":
                    if not self.is_cancelled:
                        self.error_occurred.emit(event.content)
                    break
                    
        except Exception as e:
            if not self.is_cancelled:
                logger.error(f"Streaming error: {e}")
                self.error_occurred.emit(str(e))


class ChatInterface(QWidget):
    """
    Main chat interface widget with dialog area and input controls.

    Features:
    - Scrollable chat area with message cards
    - Text input with file attachment support
    - Send, Cancel, and Retry buttons
    - Integration with LocalKnowledge AI agent
    - Streaming response support
    """

    # Signals
    message_sent = Signal(str)  # User message sent
    response_received = Signal(str)  # AI response received

    def __init__(self, parent=None):
        """
        Initialize the chat interface.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize agent
        self.agent = None
        self.agent_worker = None
        self.current_ai_card = None
        self.attached_files = []

        # UI setup
        self.setup_ui()
        self.setup_connections()

        # Initialize agent
        self.initialize_agent()

        logger.info("ChatInterface initialized")

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Chat area (upper part)
        self.chat_area = ChatScrollArea()
        main_layout.addWidget(self.chat_area, 1)  # Stretch factor 1 to expand

        # Input area (lower part)
        self.setup_input_area()
        main_layout.addWidget(self.input_frame)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setup_input_area(self):
        """Set up the input area with text field and buttons."""
        # Input frame
        self.input_frame = QFrame()
        self.input_frame.setFrameStyle(QFrame.StyledPanel)
        self.input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['hover']};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        input_layout = QVBoxLayout(self.input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)

        # Text input row
        text_row = QHBoxLayout()
        text_row.setSpacing(8)

        # File attachment button (paperclip)
        self.attach_button = QPushButton()
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "paperclip.png")
        if os.path.exists(icon_path):
            self.attach_button.setIcon(QIcon(icon_path))
        else:
            self.attach_button.setText("📎")
        self.attach_button.setToolTip("Attach files (images, text files, etc.)")
        self.attach_button.setFixedSize(40, 40)
        self.attach_button.setStyleSheet(STYLE_SHEETS["BUTTON_SECONDARY"])
        text_row.addWidget(self.attach_button)

        # Text input (3 lines)
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(80)  # Approximately 3 lines
        self.text_input.setPlaceholderText("Type your message here...")
        self.text_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['hover']};
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border: 2px solid {COLORS['primary']};
            }}
        """)
        text_row.addWidget(self.text_input, 1)  # Stretch to fill available space

        input_layout.addLayout(text_row)

        # Attached files display
        self.files_label = QLabel()
        self.files_label.setVisible(False)
        self.files_label.setStyleSheet(f"color: {COLORS['light_text']}; font-size: 10px;")
        input_layout.addWidget(self.files_label)

        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        # Add stretch to push buttons to the right
        button_row.addStretch()

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(STYLE_SHEETS["BUTTON_SECONDARY"])
        self.cancel_button.setVisible(False)  # Hidden by default
        button_row.addWidget(self.cancel_button)

        # Retry button
        self.retry_button = QPushButton("Retry")
        self.retry_button.setStyleSheet(STYLE_SHEETS["BUTTON_SECONDARY"])
        self.retry_button.setVisible(False)  # Hidden by default
        button_row.addWidget(self.retry_button)

        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet(STYLE_SHEETS["BUTTON_PRIMARY"])
        button_row.addWidget(self.send_button)

        input_layout.addLayout(button_row)

    def setup_connections(self):
        """Set up signal-slot connections."""
        # Button connections
        self.send_button.clicked.connect(self.send_message)
        self.cancel_button.clicked.connect(self.cancel_request)
        self.retry_button.clicked.connect(self.retry_last_message)
        self.attach_button.clicked.connect(self.attach_files)

        # Text input connections
        self.text_input.textChanged.connect(self.on_text_changed)

        # Enable drag and drop for file attachments
        self.setAcceptDrops(True)

    def initialize_agent(self):
        """Initialize the LocalKnowledge agent."""
        try:
            self.agent = LocalKnowledgeAgent(
                enable_web_search=True,
                enable_local_search=True,
                enable_extended_reasoning=False  # Start with fast mode
            )
            logger.info("LocalKnowledge agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            QMessageBox.warning(
                self,
                "Agent Initialization Error",
                f"Failed to initialize AI agent: {str(e)}\n\nSome features may not work properly."
            )

    @Slot()
    def send_message(self):
        """Send the current message to the AI agent."""
        message_text = self.text_input.toPlainText().strip()

        if not message_text and not self.attached_files:
            return

        if not self.agent:
            QMessageBox.warning(self, "Error", "AI agent is not available.")
            return

        # Add user message to chat
        user_message = message_text
        if self.attached_files:
            file_names = [os.path.basename(f) for f in self.attached_files]
            user_message += f"\n\nAttached files: {', '.join(file_names)}"

        self.chat_area.add_message(user_message, is_user=True)

        # Clear input
        self.text_input.clear()
        self.clear_attached_files()

        # Update UI state
        self.set_sending_state(True)

        # Create AI response card (initially empty)
        self.current_ai_card = self.chat_area.add_message("", is_user=False)

        # Start agent worker
        self.start_agent_worker(message_text)

        # Emit signal
        self.message_sent.emit(message_text)

    def start_agent_worker(self, user_input: str):
        """Start the agent worker thread."""
        if self.agent_worker and self.agent_worker.isRunning():
            self.agent_worker.cancel()
            self.agent_worker.wait()

        # Create context with file attachments if any
        context = AgentContext()

        # TODO: Process attached files and add to context
        # For now, just include file information in the message
        if self.attached_files:
            file_info = []
            for file_path in self.attached_files:
                try:
                    if file_path.lower().endswith(('.txt', '.md', '.py', '.json')):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()[:1000]  # Limit content
                        file_info.append(f"File: {os.path.basename(file_path)}\nContent: {content}")
                    else:
                        file_info.append(f"File: {os.path.basename(file_path)} (binary file)")
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
                    file_info.append(f"File: {os.path.basename(file_path)} (error reading)")

            if file_info:
                user_input += "\n\nAttached file contents:\n" + "\n\n".join(file_info)

        # Create and start worker
        self.agent_worker = AgentWorker(self.agent, user_input, context)
        self.agent_worker.response_chunk.connect(self.on_response_chunk)
        self.agent_worker.response_ready.connect(self.on_response_ready)
        self.agent_worker.error_occurred.connect(self.on_agent_error)
        self.agent_worker.finished.connect(self.on_agent_finished)
        self.agent_worker.start()

    @Slot()
    def cancel_request(self):
        """Cancel the current AI request."""
        if self.agent_worker and self.agent_worker.isRunning():
            self.agent_worker.cancel()
            self.agent_worker.wait()

        # Update UI
        self.set_sending_state(False)

        # Update current AI card
        if self.current_ai_card:
            current_text = self.current_ai_card.message_label.text()
            if not current_text.strip():
                self.current_ai_card.update_message("Request cancelled.")
            else:
                self.current_ai_card.update_message(current_text + "\n\n[Request cancelled]")

    @Slot()
    def retry_last_message(self):
        """Retry the last message."""
        # Get the last user message from chat history
        # For simplicity, we'll just enable the retry button after errors
        # and let the user manually retry by typing again
        self.retry_button.setVisible(False)
        self.text_input.setFocus()

    @Slot()
    def attach_files(self):
        """Open file dialog to attach files."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "All supported files (*.txt *.md *.py *.json *.pdf *.png *.jpg *.jpeg);;Text files (*.txt *.md *.py *.json);;Images (*.png *.jpg *.jpeg);;PDF files (*.pdf);;All files (*)"
        )

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            self.attached_files.extend(selected_files)
            self.update_files_display()

    def update_files_display(self):
        """Update the display of attached files."""
        if self.attached_files:
            file_names = [os.path.basename(f) for f in self.attached_files]
            self.files_label.setText(f"Attached: {', '.join(file_names)}")
            self.files_label.setVisible(True)
        else:
            self.files_label.setVisible(False)

    def clear_attached_files(self):
        """Clear all attached files."""
        self.attached_files.clear()
        self.update_files_display()

    @Slot()
    def on_text_changed(self):
        """Handle text input changes."""
        # Enable/disable send button based on content
        has_text = bool(self.text_input.toPlainText().strip())
        has_files = bool(self.attached_files)
        self.send_button.setEnabled(has_text or has_files)

    def set_sending_state(self, is_sending: bool):
        """Update UI state for sending/not sending."""
        self.send_button.setVisible(not is_sending)
        self.cancel_button.setVisible(is_sending)
        self.retry_button.setVisible(False)
        self.text_input.setEnabled(not is_sending)
        self.attach_button.setEnabled(not is_sending)

    # Agent response handlers
    @Slot(str)
    def on_response_chunk(self, chunk: str):
        """Handle streaming response chunks from the agent."""
        if self.current_ai_card:
            current_text = self.current_ai_card.message_label.text()
            self.current_ai_card.update_message(current_text + chunk)

    @Slot(str)
    def on_response_ready(self, response: str):
        """Handle complete response from the agent."""
        if self.current_ai_card:
            self.current_ai_card.update_message(response)

        # Emit signal
        self.response_received.emit(response)

        logger.info("AI response received and displayed")

    @Slot(str)
    def on_agent_error(self, error_message: str):
        """Handle agent errors."""
        if self.current_ai_card:
            self.current_ai_card.update_message(f"Error: {error_message}")

        # Show retry button
        self.retry_button.setVisible(True)

        logger.error(f"Agent error: {error_message}")

    @Slot()
    def on_agent_finished(self):
        """Handle agent worker completion."""
        self.set_sending_state(False)
        self.current_ai_card = None

        # Clean up worker
        if self.agent_worker:
            self.agent_worker.deleteLater()
            self.agent_worker = None

    # Drag and drop support
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events for file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop events."""
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    files.append(file_path)

        if files:
            self.attached_files.extend(files)
            self.update_files_display()
            event.acceptProposedAction()
        else:
            event.ignore()

    # Public methods
    def clear_chat(self):
        """Clear all messages from the chat area."""
        self.chat_area.clear_messages()
        logger.info("Chat cleared")

    def add_system_message(self, message: str):
        """
        Add a system message to the chat.

        Args:
            message: System message text
        """
        # Create a special system message card
        card = MessageCard(message, is_user=False)
        card.setStyleSheet(f"""
            MessageCard {{
                background-color: {COLORS['info']};
                color: white;
                border-radius: 12px;
                margin: 4px;
                border: 1px solid {COLORS['primary']};
            }}
        """)
        card.message_label.setStyleSheet("color: white; font-style: italic;")

        # Add to chat area manually
        stretch_item = self.chat_area.content_layout.takeAt(self.chat_area.content_layout.count() - 1)
        self.chat_area.content_layout.addWidget(card)
        self.chat_area.content_layout.addItem(stretch_item)

        QTimer.singleShot(10, self.chat_area.scroll_to_bottom)

    def set_agent_model(self, model_name: str):
        """
        Change the AI agent model.

        Args:
            model_name: Name of the model to use
        """
        try:
            if self.agent:
                self.agent.close()

            self.agent = LocalKnowledgeAgent(
                model_name=model_name,
                enable_web_search=True,
                enable_local_search=True,
                enable_extended_reasoning=False
            )

            self.add_system_message(f"Switched to model: {model_name}")
            logger.info(f"Agent model changed to: {model_name}")

        except Exception as e:
            logger.error(f"Failed to change agent model: {e}")
            QMessageBox.warning(
                self,
                "Model Change Error",
                f"Failed to change to model {model_name}: {str(e)}"
            )

    def toggle_extended_reasoning(self, enable: bool):
        """
        Toggle extended reasoning mode.

        Args:
            enable: True to enable extended reasoning, False to disable
        """
        if self.agent:
            self.agent.extended_reasoning(enable)
            mode = "extended reasoning" if enable else "fast mode"
            self.add_system_message(f"Switched to {mode}")
            logger.info(f"Extended reasoning {'enabled' if enable else 'disabled'}")

    def closeEvent(self, event):
        """Handle widget close event."""
        # Cancel any running agent worker
        if self.agent_worker and self.agent_worker.isRunning():
            self.agent_worker.cancel()
            self.agent_worker.wait()

        # Close agent
        if self.agent:
            self.agent.close()

        super().closeEvent(event)


# Example usage and testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("LocalKnowledge Chat Interface")
    window.setGeometry(100, 100, 800, 600)

    # Create and set chat interface
    chat_interface = ChatInterface()
    window.setCentralWidget(chat_interface)

    # Add a welcome message
    chat_interface.add_system_message("Welcome to LocalKnowledge Chat! Ask me anything about medical and scientific literature.")

    window.show()
    sys.exit(app.exec())
