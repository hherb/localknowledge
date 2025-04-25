"""
Context management system for sharing information across modules.

This module provides a singleton context manager that can be used to share
information such as the current user across different modules.
"""
from typing import Dict, Any, Optional


class ContextManager:
    """Singleton context manager for sharing information across modules."""
    
    _instance = None
    
    def __new__(cls):
        """Create a new instance if one doesn't exist."""
        if cls._instance is None:
            cls._instance = super(ContextManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the context manager."""
        self._context = {}
        self._listeners = {}
    
    def set(self, key: str, value: Any):
        """
        Set a value in the context.
        
        Args:
            key: Context key
            value: Value to store
        """
        self._context[key] = value
        
        # Notify listeners
        if key in self._listeners:
            for listener in self._listeners[key]:
                listener(value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context.
        
        Args:
            key: Context key
            default: Default value to return if key doesn't exist
            
        Returns:
            Value from the context or default
        """
        return self._context.get(key, default)
    
    def register_listener(self, key: str, listener: callable):
        """
        Register a listener for a specific key.
        
        Args:
            key: Context key to listen for
            listener: Callback function to call when the key changes
        """
        if key not in self._listeners:
            self._listeners[key] = []
        
        if listener not in self._listeners[key]:
            self._listeners[key].append(listener)
    
    def unregister_listener(self, key: str, listener: callable):
        """
        Unregister a listener for a specific key.
        
        Args:
            key: Context key
            listener: Callback function to remove
        """
        if key in self._listeners and listener in self._listeners[key]:
            self._listeners[key].remove(listener)
    
    def clear(self):
        """Clear all context values."""
        old_context = self._context.copy()
        self._context = {}
        
        # Notify listeners with None
        for key, listeners in self._listeners.items():
            if key in old_context:
                for listener in listeners:
                    listener(None)


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


# Common context keys
CURRENT_USER = "current_user"
CURRENT_PROJECT = "current_project"
