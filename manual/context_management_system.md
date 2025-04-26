# Context Management System

The Context Management System provides a thread-safe, centralized way to share information across different modules and components in the application. It includes a notification system that allows components to be notified when values change.

## Overview

The context management system is designed to:

1. Provide thread-safe access to global state
2. Notify components when values change
3. Centralize access to commonly used information
4. Eliminate the need for direct component-to-component communication

## Key Features

- **Thread Safety**: All operations are protected by locks to ensure thread safety
- **Change Notifications**: Components can register to be notified when values change
- **Qt Integration**: Uses Qt's signal/slot mechanism for thread-safe notifications
- **Convenience Functions**: Provides specialized functions for common operations

## Basic Usage

### Setting and Getting Values

```python
from localknowledge.context import set_context, get_context

# Store a value
set_context("key", "value")

# Retrieve a value
value = get_context("key")  # Returns "value"

# Retrieve a non-existent value with default
value = get_context("non_existent", "default")  # Returns "default"
```

### Listening for Changes

```python
from localknowledge.context import register_context_listener, unregister_context_listener

# Define a callback function
def on_value_changed(new_value):
    print(f"Value changed to: {new_value}")

# Register the listener
register_context_listener("key", on_value_changed)

# Set a value (will trigger the listener)
set_context("key", "new value")  # Prints "Value changed to: new value"

# Unregister when no longer needed
unregister_context_listener("key", on_value_changed)
```

## Common Context Keys

The system defines several common context keys:

- `CURRENT_USER`: The currently logged-in user
- `CURRENT_PROJECT`: The currently selected project
- `DB_CONNECTION_PARAMS`: Database connection parameters

## Convenience Functions

### User Management

```python
from localknowledge.context import get_current_user, set_current_user

# Get the current user
user = get_current_user()

# Set the current user
set_current_user(user_data)
```

### Project Management

```python
from localknowledge.context import get_current_project, set_current_project, get_current_project_name

# Get the current project ID
project_id = get_current_project()

# Set the current project
set_current_project(project_id)

# Get the name of the current project
project_name = get_current_project_name()
```

## Best Practices

1. **Always use the context system** for sharing information between components
2. **Register listeners** when a component needs to react to changes
3. **Unregister listeners** when a component is being destroyed
4. **Use convenience functions** for common operations
5. **Keep context values immutable** when possible
6. **Use descriptive key names** to avoid conflicts

## Example: Window Title Updates

```python
from localknowledge.context import register_context_listener, get_current_user, get_current_project_name, CURRENT_USER, CURRENT_PROJECT

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Register listeners for user and project changes
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)
        
        # Initial update
        self._update_window_title()
    
    def _on_user_changed(self, _):
        """Handle user change."""
        self._update_window_title()
    
    def _on_project_changed(self, _):
        """Handle project change."""
        self._update_window_title()
    
    def _update_window_title(self):
        """Update window title with current user and project."""
        title = "My Application"
        
        # Add user name if available
        user = get_current_user()
        if user:
            user_name = f"{user.get('firstname', '')} {user.get('surname', '')}"
            title += f" - {user_name}"
        
        # Add project name if available
        project_name = get_current_project_name()
        if project_name:
            title += f" - Project: {project_name}"
        
        self.setWindowTitle(title)
```

## Example: Bookmark Management

```python
from localknowledge.context import register_context_listener, get_current_project, CURRENT_PROJECT

class BookmarkManager:
    def __init__(self):
        self.current_project_id = get_current_project()
        
        # Register for project changes
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)
    
    def _on_project_changed(self, project_id):
        """Handle project change."""
        self.current_project_id = project_id
        self._update_bookmark_ui()
    
    def _update_bookmark_ui(self):
        """Update UI based on current project."""
        # Enable/disable project bookmark controls
        project_enabled = self.current_project_id is not None
        self.project_bookmark_cb.setEnabled(project_enabled)
        
        # Update bookmark status if a document is selected
        if self.current_document:
            self._check_bookmark_status()
```

## Implementation Details

The context management system is implemented as a singleton with thread-safe access. It uses Qt's signal/slot mechanism to ensure that notifications are delivered in a thread-safe manner, even when components are in different threads.

The system also includes a caching mechanism to avoid unnecessary database queries for frequently accessed information, such as project names.
