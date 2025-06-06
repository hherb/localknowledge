# UI Module

## Overview

The UI Module provides the graphical user interface for the Local Knowledge system. It is built using PySide6 (Qt for Python) and includes components for searching, viewing, and interacting with documents and their metadata. The UI is designed with a plugin architecture that allows for easy extension and customization of functionality.

## Plugin Architecture

The UI is built around a plugin architecture that allows for modular development and easy extension of functionality:

### Plugin System

The plugin system is implemented in `localknowledge.ui.plugins`:

- Plugins are discovered and loaded dynamically at runtime
- Each plugin provides specific functionality (e.g., PDF viewing, search, annotation)
- Plugins can be enabled or disabled through configuration
- Plugins can interact with each other through a shared context

### Plugin Interface

Each plugin implements a common interface:

```python
from localknowledge.ui.plugins import Plugin

class MyPlugin(Plugin):
    def __init__(self, context):
        super().__init__(context)
        self.name = "My Plugin"
        self.description = "A sample plugin"
        self.version = "1.0.0"

    def initialize(self):
        """Initialize the plugin."""
        # Create widgets, connect signals, etc.
        self.widget = MyPluginWidget()

    def get_widget(self):
        """Return the main widget for this plugin."""
        return self.widget

    def get_actions(self):
        """Return actions for menus and toolbars."""
        return [self.action1, self.action2]

    def shutdown(self):
        """Clean up resources when the plugin is disabled."""
        # Release resources, save state, etc.
```

### Plugin Manager

The `PluginManager` class in `localknowledge.ui.plugin_manager` manages the lifecycle of plugins:

- Discovers plugins in the plugin directory
- Loads and initializes plugins
- Provides access to loaded plugins
- Manages plugin dependencies
- Handles plugin configuration

The PluginManager is a QObject that emits signals when plugins are loaded or unloaded:

```python
from localknowledge.ui.plugin_manager import PluginManager

# Create a plugin manager
plugin_manager = PluginManager()

# Discover available plugins
plugins = plugin_manager.discover_plugins()

# Load a specific plugin
plugin = plugin_manager.load_plugin("MyPlugin")

# Get all active plugins
active_plugins = plugin_manager.get_active_plugins()

# Unload a plugin
plugin_manager.unload_plugin("MyPlugin")
```

### Plugin Communication

Plugins can communicate with each other through:

- Shared context object passed to each plugin
- Signals and slots for event-driven communication
- Direct method calls for synchronous operations

## Core Components

### Main Window

The `MainWindow` class in `localknowledge.ui.main` is the main application window:

- Provides the overall application layout
- Manages the configuration panel
- Handles user authentication
- Coordinates interactions between UI components

### Knowledge Browser

The `KnowledgeBrowser` class in `localknowledge.ui.knowledgebrowser` provides the main interface for browsing and searching documents:

- Search interface for keyword and semantic search
- Results display with document metadata
- Document viewer for PDFs and text
- Annotation and note-taking capabilities

### PDF Viewer

The `PDFViewer` class in `localknowledge.ui.pdfviewer` provides PDF viewing capabilities:

- PDF rendering
- Navigation (page turning, zooming)
- Text selection and copying
- Search within PDF

### Settings Dialog

The `SettingsDialog` class in `localknowledge.ui.settings` provides a dialog for configuring application settings:

- Database connection settings
- PDF storage settings
- UI preferences
- AI model settings

### Login Dialog

The `LoginDialog` class in `localknowledge.ui.login` provides a dialog for user authentication:

- Username and password input
- "Remember me" functionality
- Password reset option

## UI Layout

The main window is organized into several areas:

- **Toolbar**: Contains buttons for common actions
- **Configuration Panel**: Contains settings and filters (can be hidden)
- **Search Panel**: Contains search input and options
- **Results Panel**: Displays search results
- **Document Panel**: Displays the selected document
- **Status Bar**: Displays status information

## Usage Examples

### Starting the Application

```python
from localknowledge.ui.main import main

# Start the application
main()
```

### Creating a Custom Window

```python
from PySide6.QtWidgets import QApplication
from localknowledge.ui.main import MainWindow

# Create an application
app = QApplication([])

# Create a main window
window = MainWindow()

# Show the window
window.show()

# Run the application
app.exec()
```

### Using the Knowledge Browser

```python
from PySide6.QtWidgets import QApplication
from localknowledge.ui.knowledgebrowser import KnowledgeBrowser

# Create an application
app = QApplication([])

# Create a knowledge browser
browser = KnowledgeBrowser()

# Perform a search
browser.search("traumatic brain injury")

# Show the browser
browser.show()

# Run the application
app.exec()
```

### Using the PDF Viewer

```python
from PySide6.QtWidgets import QApplication
from localknowledge.ui.pdfviewer import PDFViewer

# Create an application
app = QApplication([])

# Create a PDF viewer
viewer = PDFViewer()

# Load a PDF
viewer.load_pdf("/path/to/document.pdf")

# Show the viewer
viewer.show()

# Run the application
app.exec()
```

## Customization

### Themes

The UI supports themes through Qt stylesheets:

```python
from PySide6.QtWidgets import QApplication
from localknowledge.ui.main import MainWindow
from localknowledge.ui.themes import load_theme

# Create an application
app = QApplication([])

# Load a theme
load_theme(app, "dark")

# Create a main window
window = MainWindow()

# Show the window
window.show()

# Run the application
app.exec()
```

### Custom Widgets

You can create custom widgets by subclassing Qt widgets:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class CustomWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Add widgets
        label = QLabel("Custom Widget")
        layout.addWidget(label)

        # Initialize state
        self.initialize()

    def initialize(self):
        """Initialize the widget state."""
        pass
```

## Configuration

### UI Configuration

UI configuration is stored in `localknowledge.ui.config`:

```python
# UI configuration
UI_CONFIG = {
    'theme': 'light',
    'font_size': 12,
    'show_config_panel': True,
    'remember_window_size': True,
    'default_search_type': 'keyword'
}
```

Environment variables can override these settings:

- `LK_UI_THEME`: UI theme (light, dark)
- `LK_UI_FONT_SIZE`: Font size
- `LK_UI_SHOW_CONFIG_PANEL`: Show configuration panel (true, false)

### User Preferences

User preferences are stored in the database and can be accessed through the `UserPreferences` class:

```python
from localknowledge.ui.preferences import UserPreferences

# Get user preferences
preferences = UserPreferences(user_id=1)

# Get a preference
theme = preferences.get('theme', default='light')

# Set a preference
preferences.set('theme', 'dark')

# Save preferences
preferences.save()
```

## Icons and Resources

The UI uses icons and resources from `localknowledge.ui.icons` and `localknowledge.ui.resources`:

```python
from PySide6.QtGui import QIcon
from localknowledge.ui.icons import get_icon

# Get an icon
icon = get_icon('search')

# Use the icon
button.setIcon(icon)
```

## Event Handling

The UI uses Qt's signal and slot mechanism for event handling:

```python
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Slot

# Create a button
button = QPushButton("Click Me")

# Connect a slot to the button's clicked signal
@Slot()
def on_button_clicked():
    print("Button clicked")

button.clicked.connect(on_button_clicked)
```

## Threading

For long-running operations, use Qt's threading capabilities:

```python
from PySide6.QtCore import QThread, Signal

class WorkerThread(QThread):
    # Define signals
    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None

    def set_data(self, data):
        """Set the data to process."""
        self.data = data

    def run(self):
        """Process the data."""
        try:
            # Perform long-running operation
            result = process_data(self.data)

            # Emit result signal
            self.result_ready.emit(result)
        except Exception as e:
            # Emit error signal
            self.error_occurred.emit(str(e))

# Create a worker thread
worker = WorkerThread()

# Connect signals
worker.result_ready.connect(on_result_ready)
worker.error_occurred.connect(on_error_occurred)

# Start the thread
worker.set_data(data)
worker.start()
```

## Performance Considerations

### UI Responsiveness

To maintain UI responsiveness:

- Use threading for long-running operations
- Use lazy loading for large data
- Use pagination for large result sets
- Use caching for frequently accessed data

### Memory Usage

To manage memory usage:

- Release resources when they are no longer needed
- Use weak references for parent-child relationships
- Use lazy loading for images and other resources

## Maintenance

### Adding a New Widget

To add a new widget:

1. Create a new file in `localknowledge.ui` for the widget
2. Implement the widget class
3. Add tests in `localknowledge.ui.tests`
4. Update documentation

Example:

```python
# In localknowledge/ui/custom_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class CustomWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Add widgets
        label = QLabel("Custom Widget")
        layout.addWidget(label)
```

### Updating the UI

To update the UI:

1. Identify the components to update
2. Make the changes
3. Test the changes
4. Update documentation

### Adding a New Theme

To add a new theme:

1. Create a new stylesheet in `localknowledge.ui.themes`
2. Add the theme to the theme registry
3. Test the theme
4. Update documentation

## Troubleshooting

### Common Issues

1. **UI Not Responding**: This may indicate a long-running operation in the main thread. Use threading for such operations.

2. **Widgets Not Displaying**: Check the layout hierarchy and ensure widgets are added to layouts.

3. **Signals Not Working**: Ensure signals are connected to slots and that the connection is maintained (not garbage collected).

### Debugging

For detailed debugging:

1. Enable Qt debugging:
   ```python
   from PySide6.QtCore import QLoggingCategory
   QLoggingCategory.setFilterRules("*.debug=true")
   ```

2. Use print statements or logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.ui').setLevel(logging.DEBUG)
   ```

3. Use Qt's debugging tools:
   ```python
   from PyQt5.QtWidgets import QApplication
   app = QApplication([])
   app.setApplicationName("LocalKnowledge")
   app.setOrganizationName("LocalKnowledge")
   app.setOrganizationDomain("localknowledge.org")
   ```

## Built-in Plugins

The Local Knowledge system comes with several built-in plugins:

### PDF Viewer Plugin

The PDF Viewer plugin (`localknowledge.ui.plugins.pdfviewer`) provides PDF viewing capabilities:

- PDF rendering with pagination
- Zoom and rotation controls
- Text selection and copying
- Search functionality with result highlighting
- Scrolling with both mouse and keyboard

```python
from localknowledge.ui.plugins.pdfviewer import PDFViewerPlugin

# Create the plugin
plugin = PDFViewerPlugin(context)

# Initialize the plugin
plugin.initialize()

# Get the main widget
viewer = plugin.get_widget()

# Load a PDF
viewer.load_pdf("/path/to/document.pdf")
```

### Knowledge Browser Plugin

The Knowledge Browser plugin (`localknowledge.ui.plugins.knowledgebrowser`) provides search and browsing capabilities:

- Keyword and semantic search
- Result filtering and sorting
- Document preview
- Metadata display
- Integration with other plugins

```python
from localknowledge.ui.plugins.knowledgebrowser import KnowledgeBrowserPlugin

# Create the plugin
plugin = KnowledgeBrowserPlugin(context)

# Initialize the plugin
plugin.initialize()

# Get the main widget
browser = plugin.get_widget()

# Perform a search
browser.search("traumatic brain injury")
```

### Annotation Plugin

The Annotation plugin (`localknowledge.ui.plugins.annotation`) provides annotation capabilities:

- Text highlighting
- Note creation and editing
- Bookmark management
- Tag assignment
- Export and sharing of annotations

```python
from localknowledge.ui.plugins.annotation import AnnotationPlugin

# Create the plugin
plugin = AnnotationPlugin(context)

# Initialize the plugin
plugin.initialize()

# Get the main widget
annotation_panel = plugin.get_widget()

# Add an annotation
annotation_panel.add_annotation({
    "type": "highlight",
    "text": "Important passage",
    "page": 1,
    "rect": [100, 200, 300, 220],
    "color": "yellow"
})
```

### Settings Plugin

The Settings plugin (`localknowledge.ui.plugins.settings`) provides configuration capabilities:

- User preferences management
- Database connection settings
- Plugin configuration
- Theme selection
- Keyboard shortcut customization

```python
from localknowledge.ui.plugins.settings import SettingsPlugin

# Create the plugin
plugin = SettingsPlugin(context)

# Initialize the plugin
plugin.initialize()

# Get the main widget
settings_dialog = plugin.get_widget()

# Show the settings dialog
settings_dialog.show()
```

## Creating Custom Plugins

To create a custom plugin:

1. Create a new Python module in `localknowledge.ui.plugins` or a separate package
2. Implement the `Plugin` interface
3. Register the plugin with the plugin manager

Example custom plugin:

```python
from localknowledge.ui.plugins import Plugin
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Slot

class MyCustomPlugin(Plugin):
    def __init__(self, context):
        super().__init__(context)
        self.name = "My Custom Plugin"
        self.description = "A custom plugin example"
        self.version = "1.0.0"
        self.widget = None

    def initialize(self):
        """Initialize the plugin."""
        # Create the main widget
        self.widget = QWidget()
        layout = QVBoxLayout()
        self.widget.setLayout(layout)

        # Add widgets
        label = QLabel("My Custom Plugin")
        layout.addWidget(label)

        button = QPushButton("Click Me")
        button.clicked.connect(self.on_button_clicked)
        layout.addWidget(button)

        # Register for events from other plugins
        self.context.document_loaded.connect(self.on_document_loaded)

    def get_widget(self):
        """Return the main widget for this plugin."""
        return self.widget

    def get_actions(self):
        """Return actions for menus and toolbars."""
        return []

    @Slot()
    def on_button_clicked(self):
        """Handle button click."""
        print("Button clicked in custom plugin")

    @Slot(str)
    def on_document_loaded(self, document_path):
        """Handle document loaded event."""
        print(f"Document loaded: {document_path}")

    def shutdown(self):
        """Clean up resources when the plugin is disabled."""
        # Release resources, save state, etc.
        pass
```

## UI Components

### Toolbar

The toolbar provides quick access to common actions:

- Search button
- Settings button
- Login/logout button
- Help button

### Configuration Panel

The configuration panel provides access to settings and filters:

- Search type (keyword, semantic)
- Source filters (MedRxiv, PubMed)
- Date range filters
- Category filters

### Search Panel

The search panel provides search functionality:

- Search input field
- Search button
- Advanced search options
- Recent searches

### Results Panel

The results panel displays search results:

- List of documents
- Document metadata
- Sorting options
- Pagination

### Document Panel

The document panel displays the selected document:

- PDF viewer
- Text viewer
- Metadata display
- Annotation tools

### Status Bar

The status bar displays status information:

- Current search status
- Document count
- Selected document information
- Application status

## UI Design Principles

The UI follows these design principles:

- **Simplicity**: Keep the UI simple and focused
- **Consistency**: Use consistent patterns and terminology
- **Feedback**: Provide clear feedback for user actions
- **Efficiency**: Optimize for common tasks
- **Flexibility**: Allow customization for different needs
