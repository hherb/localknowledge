#!/usr/bin/env python3
"""
Plugin Finder Helper

This script helps the plugin manager discover plugin classes
by providing a consistent way to load and register plugins.
"""

import sys
import os
import importlib
from typing import Dict, List, Type, Any

# Get the parent directory to access rwb_main
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import PluginBase from the main application
from rwb_main import PluginBase

# Dictionary to store plugin classes
_plugin_classes: Dict[str, Type[PluginBase]] = {}

def register_plugin(cls: Type[PluginBase]) -> Type[PluginBase]:
    """
    Decorator to register a plugin class.
    
    Args:
        cls: Plugin class to register
        
    Returns:
        The same class, allowing this to be used as a decorator
    """
    if cls.__name__ not in _plugin_classes:
        _plugin_classes[cls.__name__] = cls
    return cls

def get_plugin_classes() -> Dict[str, Type[PluginBase]]:
    """
    Get all registered plugin classes.
    
    Returns:
        Dict of plugin class names to plugin classes
    """
    return _plugin_classes

# Import and register known plugins
def load_plugins():
    """Load all plugin modules to ensure their plugins are registered."""
    plugins_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(plugins_dir):
        if filename.endswith('.py') and not filename.startswith('__') and filename != 'plugin_finder.py':
            module_name = filename[:-3]
            try:
                # Import using the absolute path to avoid conflicts
                importlib.import_module(f"localknowledge.ui.plugins.{module_name}")
            except Exception as e:
                print(f"Error importing plugin {module_name}: {e}")

# Load plugins when this module is imported
load_plugins()
