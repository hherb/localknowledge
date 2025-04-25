# Context Management System

The context management system provides a way to share information across different modules in the application. It is implemented as a singleton that can be accessed from anywhere in the codebase.

## Overview

The context management system is designed to:

1. Store and retrieve values by key
2. Notify listeners when values change
3. Provide a centralized way to access shared information

## Usage

### Basic Usage

```python
from localknowledge.context import set_context, get_context

# Store a value
set_context("key", "value")

# Retrieve a value
value = get_context("key")  # Returns "value"

# Retrieve a non-existent value
value = get_context("non_existent")  # Returns None

# Retrieve a non-existent value with a default
value = get_context("non_existent", "default")  # Returns "default"
```

### Listening for Changes

You can register listeners to be notified when values change:

```python
from localknowledge.context import register_context_listener, unregister_context_listener

# Define a listener function
def on_value_changed(value):
    print(f"Value changed to: {value}")

# Register the listener
register_context_listener("key", on_value_changed)

# Set a value (will trigger the listener)
set_context("key", "new_value")  # Prints "Value changed to: new_value"

# Unregister the listener
unregister_context_listener("key", on_value_changed)

# Set another value (will not trigger the listener)
set_context("key", "another_value")  # No output
```

### Common Context Keys

The context management system defines some common keys for use throughout the application:

- `CURRENT_USER`: The currently logged-in user
- `CURRENT_PROJECT`: The currently selected project

## Implementation Details

The context management system is implemented as a singleton class `ContextManager` in `localknowledge/context.py`. The singleton instance is created when the module is imported and can be accessed directly as `context_manager`.

For convenience, the module also provides functions that delegate to the singleton instance:

- `set_context(key, value)`: Set a value in the context
- `get_context(key, default=None)`: Get a value from the context
- `register_context_listener(key, listener)`: Register a listener for a key
- `unregister_context_listener(key, listener)`: Unregister a listener for a key

## Example: User Authentication

The context management system is used to share the current user across different modules:

```python
from localknowledge.context import set_context, get_context, CURRENT_USER

# When a user logs in
def on_login_successful(user_data):
    set_context(CURRENT_USER, user_data)

# In another module
def get_current_user():
    return get_context(CURRENT_USER)
```

## Example: Project Selection

The context management system is used to share the currently selected project:

```python
from localknowledge.context import set_context, get_context, CURRENT_PROJECT

# When a project is selected
def on_project_selected(project_id):
    set_context(CURRENT_PROJECT, project_id)

# In another module
def get_current_project():
    return get_context(CURRENT_PROJECT)
```

## Best Practices

1. Use the predefined context keys when possible
2. Register listeners in the `__init__` method of classes that need to respond to context changes
3. Unregister listeners when objects are destroyed to prevent memory leaks
4. Use the context system for sharing global state, not for passing data between closely related objects
