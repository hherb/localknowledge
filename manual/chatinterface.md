# Chat Interface Module

## Overview

The Chat Interface module (`localknowledge.ui.chatinterface`) provides a modern chat-style user interface for interacting with the LocalKnowledge AI agent. It features a clean, responsive design with message cards, file attachment support, and real-time streaming responses.

## Features

### User Interface Components

- **Dialog Area**: Scrollable area displaying conversation history with rounded message cards
- **Message Cards**: Distinct styling for user messages (blue, right-aligned) and AI responses (gray, left-aligned)
- **Text Input**: Multi-line text input field (3 lines) with placeholder text
- **File Attachment**: Paperclip button for attaching files via dialog or drag-and-drop
- **Control Buttons**: Send, Cancel, and Retry buttons with appropriate state management

### AI Integration

- **LocalKnowledge Agent**: Full integration with the pydantic-ai based agent
- **Streaming Responses**: Real-time display of AI responses as they are generated
- **Model Selection**: Support for changing AI models dynamically
- **Extended Reasoning**: Toggle between fast mode and extended reasoning mode
- **Context Management**: Automatic handling of conversation context

### File Support

- **Supported Formats**: Text files (.txt, .md, .py, .json), images (.png, .jpg, .jpeg), PDFs
- **Drag and Drop**: Files can be dragged directly onto the interface
- **Content Processing**: Text files are automatically read and included in the context
- **File Display**: Clear indication of attached files with file names

## Classes

### ChatInterface

Main widget class that provides the complete chat interface.

```python
from localknowledge.ui.chatinterface import ChatInterface

# Create chat interface
chat = ChatInterface()

# Add to your application
layout.addWidget(chat)
```

#### Key Methods

- `send_message()`: Send user message to AI agent
- `cancel_request()`: Cancel ongoing AI request
- `clear_chat()`: Clear all messages from chat area
- `add_system_message(message)`: Add system/status message
- `set_agent_model(model_name)`: Change AI model
- `toggle_extended_reasoning(enable)`: Toggle reasoning mode

#### Signals

- `message_sent(str)`: Emitted when user sends a message
- `response_received(str)`: Emitted when AI response is complete

### MessageCard

Individual message display widget with rounded corners and appropriate styling.

```python
from localknowledge.ui.chatinterface import MessageCard

# Create user message
user_card = MessageCard("Hello!", is_user=True)

# Create AI message
ai_card = MessageCard("Hi there!", is_user=False)
```

### ChatScrollArea

Custom scroll area optimized for chat messages with auto-scroll functionality.

### AgentWorker

Background thread worker for handling AI agent operations without blocking the UI.

## Usage Examples

### Basic Usage

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from localknowledge.ui.chatinterface import ChatInterface

app = QApplication(sys.argv)

window = QMainWindow()
chat_interface = ChatInterface()
window.setCentralWidget(chat_interface)

# Add welcome message
chat_interface.add_system_message("Welcome to LocalKnowledge Chat!")

window.show()
app.exec()
```

### Integration with Main Application

```python
from localknowledge.ui.chatinterface import ChatInterface

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Create chat interface
        self.chat = ChatInterface()
        
        # Connect signals
        self.chat.message_sent.connect(self.on_message_sent)
        self.chat.response_received.connect(self.on_response_received)
        
        # Add to layout
        self.setCentralWidget(self.chat)
    
    def on_message_sent(self, message):
        print(f"User sent: {message}")
    
    def on_response_received(self, response):
        print(f"AI responded: {response}")
```

### Model Management

```python
# Change AI model
chat_interface.set_agent_model("qwen3:8b")

# Toggle extended reasoning
chat_interface.toggle_extended_reasoning(True)

# Add system notification
chat_interface.add_system_message("Switched to extended reasoning mode")
```

## Styling

The chat interface uses the centralized styling system from `localknowledge.ui.styles`:

- **Colors**: Consistent with application theme (primary blue, light backgrounds)
- **Fonts**: Standard application fonts with appropriate sizing
- **Borders**: Rounded corners for modern appearance
- **Spacing**: Consistent margins and padding throughout

### Message Card Styling

- **User Messages**: Blue background (`COLORS['primary']`), white text, right-aligned
- **AI Messages**: Light gray background (`COLORS['alt_background']`), dark text, left-aligned
- **System Messages**: Blue background (`COLORS['info']`), white italic text, centered

## Requirements

### Dependencies

- PySide6 (Qt for Python)
- LocalKnowledge AI agent (`localknowledge.ai.agent`)
- Ollama server (for AI functionality)

### AI Models

The interface works with any Ollama-compatible model, with special support for:

- `qwen3:8b` (default, supports extended reasoning)
- `llama3.2:3b`
- `gemma2:2b`
- `mistral:7b`

## Testing

### Unit Tests

Run the unit tests to verify functionality:

```bash
python localknowledge/ui/tests/test_chatinterface.py
```

### Manual Testing

Use the test application for interactive testing:

```bash
python test_chatinterface.py
```

## Configuration

### Agent Configuration

The chat interface initializes the AI agent with default settings:

- Web search: Enabled
- Local search: Enabled
- Extended reasoning: Disabled (fast mode)

### Customization

```python
# Custom agent configuration
chat = ChatInterface()

# Access the agent directly for advanced configuration
if chat.agent:
    chat.agent.enable_web_search = False
    chat.agent.enable_local_search = True
```

## Error Handling

The interface includes comprehensive error handling:

- **Agent Initialization**: Graceful fallback if agent fails to initialize
- **Network Errors**: Clear error messages for connection issues
- **File Errors**: Proper handling of file read/attachment errors
- **Cancellation**: Clean cancellation of ongoing requests

## Performance Considerations

- **Streaming**: Real-time response streaming for better user experience
- **Threading**: Background processing to keep UI responsive
- **Memory**: Efficient message storage and cleanup
- **File Handling**: Limited file content reading to prevent memory issues

## Plugin Integration

The chat interface is also available as a plugin for the main LocalKnowledge application.

### Chat Interface Plugin

The `ChatInterfacePlugin` class in `localknowledge.ui.plugins.chat_interface_plugin` provides:

- **Plugin Registration**: Automatic registration with the plugin system
- **Configuration Panel**: Rich configuration interface with model selection, reasoning mode, and search settings
- **Toolbar Actions**: Quick access to clear chat and toggle reasoning mode
- **State Management**: Automatic saving and restoring of plugin settings
- **Lifecycle Management**: Proper initialization and cleanup

### Loading the Plugin

In the main application:

1. **Via Menu**: Go to Plugins → Load Plugin → AI Chat
2. **Programmatically**:
   ```python
   window.load_plugin("ChatInterfacePlugin")
   ```

### Plugin Configuration

The configuration panel provides:

- **AI Model Selection**: Choose from available Ollama models
- **Extended Reasoning**: Toggle between fast mode and extended reasoning
- **Search Settings**: Enable/disable web search and local search
- **Chat Settings**: Auto-scroll and other interface options
- **Action Buttons**: Apply settings, reset to defaults, clear chat

### Plugin Features

- **Tab Integration**: Opens in a new tab in the main application
- **Configuration Panel**: Accessible via the configuration button
- **Toolbar Actions**: Additional actions added to the main toolbar
- **State Persistence**: Settings are saved and restored between sessions
- **Error Handling**: Graceful handling of initialization and runtime errors

## Testing

### Standalone Testing

```bash
# Test the chat interface widget directly
python test_chatinterface.py

# Test the plugin in isolation
python localknowledge/ui/plugins/chat_interface_plugin.py
```

### Plugin Testing

```bash
# Test the plugin in the main application
python test_chat_plugin.py
```

### Unit Tests

```bash
# Run unit tests for the chat interface
python localknowledge/ui/tests/test_chatinterface.py
```

## Future Enhancements

Planned improvements include:

- **Message History**: Persistent conversation history
- **Export/Import**: Save and load conversations
- **Rich Media**: Better support for images and documents
- **Voice Input**: Speech-to-text integration
- **Themes**: Multiple UI themes and customization options
- **Plugin Extensions**: Additional plugin-specific features and integrations
