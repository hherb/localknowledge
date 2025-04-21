# UI Module

## Overview

The UI Module provides the graphical user interface for the Local Knowledge system. It is built using PyQt5 and includes components for searching, viewing, and interacting with documents and their metadata.

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
from PyQt5.QtWidgets import QApplication
from localknowledge.ui.main import MainWindow

# Create an application
app = QApplication([])

# Create a main window
window = MainWindow()

# Show the window
window.show()

# Run the application
app.exec_()
```

### Using the Knowledge Browser

```python
from PyQt5.QtWidgets import QApplication
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
app.exec_()
```

### Using the PDF Viewer

```python
from PyQt5.QtWidgets import QApplication
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
app.exec_()
```

## Customization

### Themes

The UI supports themes through Qt stylesheets:

```python
from PyQt5.QtWidgets import QApplication
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
app.exec_()
```

### Custom Widgets

You can create custom widgets by subclassing Qt widgets:

```python
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
from PyQt5.QtGui import QIcon
from localknowledge.ui.icons import get_icon

# Get an icon
icon = get_icon('search')

# Use the icon
button.setIcon(icon)
```

## Event Handling

The UI uses Qt's signal and slot mechanism for event handling:

```python
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import pyqtSlot

# Create a button
button = QPushButton("Click Me")

# Connect a slot to the button's clicked signal
@pyqtSlot()
def on_button_clicked():
    print("Button clicked")

button.clicked.connect(on_button_clicked)
```

## Threading

For long-running operations, use Qt's threading capabilities:

```python
from PyQt5.QtCore import QThread, pyqtSignal

class WorkerThread(QThread):
    # Define signals
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    
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
   from PyQt5.QtCore import QLoggingCategory
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
