"""
Context management system for sharing information across modules.

This module provides a thread-safe singleton context manager that can be used to share
information such as the current user across different modules. It includes a
subscription system for notifications when values change.
"""
import threading
import logging
import traceback
from typing import Dict, Any, Optional, List, Set, Callable
from PySide6.QtCore import QObject, Signal, QThread, QTimer, QCoreApplication

# Configure logging
logger = logging.getLogger(__name__)


class ContextSignals(QObject):
    """Qt signals for the context manager."""

    # Signal emitted when a context value changes
    # Parameters: key, value
    value_changed = Signal(str, object)


class ContextManager:
    """Thread-safe singleton context manager for sharing information across modules."""

    _instance = None
    _lock = threading.RLock()  # Reentrant lock for thread safety

    def __new__(cls):
        """Create a new instance if one doesn't exist."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ContextManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        """Initialize the context manager."""
        self._context = {}
        self._listeners = {}
        self._signals = ContextSignals()

        # Connect the value_changed signal to the _notify_listeners method
        self._signals.value_changed.connect(self._notify_listeners)

        # Track which thread created the context manager (usually the main thread)
        self._main_thread = threading.current_thread()

        # Debug info
        logger.debug(f"Context manager initialized in thread: {self._main_thread.name}")

    def set(self, key: str, value: Any):
        """
        Set a value in the context (thread-safe).

        Args:
            key: Context key
            value: Value to store
        """
        with self._lock:
            # Check if the value is actually changing
            old_value = self._context.get(key)
            if old_value == value:
                # No change, no need to notify
                return

            # Update the value
            self._context[key] = value

            # Emit the signal to notify listeners
            # This will be processed in the Qt event loop
            self._signals.value_changed.emit(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context (thread-safe).

        Args:
            key: Context key
            default: Default value to return if key doesn't exist

        Returns:
            Value from the context or default
        """
        with self._lock:
            return self._context.get(key, default)

    def register_listener(self, key: str, listener: callable):
        """
        Register a listener for a specific key (thread-safe).

        Args:
            key: Context key to listen for
            listener: Callback function to call when the key changes
        """
        with self._lock:
            if key not in self._listeners:
                self._listeners[key] = []

            if listener not in self._listeners[key]:
                self._listeners[key].append(listener)

                # Immediately notify the listener with the current value if it exists
                if key in self._context:
                    # Use a timer to ensure the notification happens in the Qt event loop
                    QTimer.singleShot(0, lambda: listener(self._context[key]))

    def unregister_listener(self, key: str, listener: callable):
        """
        Unregister a listener for a specific key (thread-safe).

        Args:
            key: Context key
            listener: Callback function to remove
        """
        with self._lock:
            if key in self._listeners and listener in self._listeners[key]:
                self._listeners[key].remove(listener)

    def _notify_listeners(self, key: str, value: Any):
        """
        Notify listeners of a value change.
        This method is called in the Qt event loop.

        Args:
            key: Context key that changed
            value: New value
        """
        # Get a copy of the listeners to avoid modification during iteration
        listeners = []
        with self._lock:
            if key in self._listeners:
                listeners = self._listeners[key].copy()

        # Notify each listener
        for listener in listeners:
            try:
                listener(value)
            except Exception as e:
                logger.error(f"Error in context listener for key '{key}': {e}")
                logger.error(traceback.format_exc())

    def clear(self):
        """Clear all context values (thread-safe)."""
        with self._lock:
            old_context = self._context.copy()
            self._context = {}

            # Notify listeners with None
            for key, value in old_context.items():
                self._signals.value_changed.emit(key, None)


# Create a singleton instance
context_manager = ContextManager()


# Convenience functions
def set_context(key: str, value: Any):
    """
    Set a value in the global context.

    Args:
        key: Context key
        value: Value to store
    """
    context_manager.set(key, value)


def get_context(key: str, default: Any = None) -> Any:
    """
    Get a value from the global context.

    Args:
        key: Context key
        default: Default value to return if key doesn't exist

    Returns:
        Value from the context or default
    """
    return context_manager.get(key, default)


def register_context_listener(key: str, listener: callable):
    """
    Register a listener for a specific key in the global context.

    Args:
        key: Context key to listen for
        listener: Callback function to call when the key changes
    """
    context_manager.register_listener(key, listener)


def unregister_context_listener(key: str, listener: callable):
    """
    Unregister a listener for a specific key in the global context.

    Args:
        key: Context key
        listener: Callback function to remove
    """
    context_manager.unregister_listener(key, listener)


# Specific convenience functions for common context values
def get_current_user():
    """
    Get the current user from the context.

    Returns:
        Dict or None: Current user information or None if not set
    """
    return get_context(CURRENT_USER)


def set_current_user(user_data):
    """
    Set the current user in the context.

    Args:
        user_data: User information dictionary
    """
    set_context(CURRENT_USER, user_data)


def get_current_project():
    """
    Get the current project ID from the context.

    Returns:
        int or None: Current project ID or None if not set
    """
    return get_context(CURRENT_PROJECT)


def set_current_project(project_id):
    """
    Set the current project ID in the context.

    Args:
        project_id: Project ID
    """
    set_context(CURRENT_PROJECT, project_id)


def get_project_name(project_id):
    """
    Get the name of a project from its ID.

    Args:
        project_id: Project ID

    Returns:
        str: Project name or a default string if not found
    """
    if project_id is None:
        return None

    try:
        from localknowledge.db.project import ProjectDatabaseManager
        project_db = ProjectDatabaseManager()
        project = project_db.get_project(project_id)
        project_db.close()

        if project:
            return project.get('title', f"Project {project_id}")
        else:
            return f"Project {project_id}"
    except Exception as e:
        logger.error(f"Error getting project name: {e}")
        return f"Project {project_id}"


def get_current_project_name():
    """
    Get the name of the current project.

    Returns:
        str or None: Current project name or None if no project is selected
    """
    project_id = get_current_project()
    if project_id is None:
        return None
    return get_project_name(project_id)


# Common context keys
CURRENT_USER = "current_user"
CURRENT_PROJECT = "current_project"
DB_CONNECTION_PARAMS = "db_connection_params"
