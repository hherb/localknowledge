#!/usr/bin/env python3
"""
Plugin Manager Module

This module contains the PluginManager class that manages the lifecycle of plugins
in the RWB (Researcher's Workbench) system.

The PluginManager is responsible for:
- Discovering available plugins in plugin directories
- Loading and initializing plugins
- Managing active plugin instances
- Providing access to loaded plugins
- Handling plugin unloading and cleanup

Features:
- Automatic plugin discovery via plugin_finder modules
- Signal-based notifications for plugin loading/unloading events
- Support for multiple plugin directories
- Error handling and logging for plugin operations
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Type

from PySide6.QtCore import QObject, Signal

# Import PluginBase from the plugin base module
from localknowledge.ui.plugin_base import PluginBase

# Configure logging
logger = logging.getLogger(__name__)


class PluginManager(QObject):
    """
    Manages loading and unloading of plugins.
    
    The PluginManager class provides a centralized way to manage plugins in the RWB system.
    It handles plugin discovery, loading, initialization, and cleanup.
    
    Signals:
        plugin_loaded (str): Emitted when a plugin is successfully loaded
        plugin_unloaded (str): Emitted when a plugin is successfully unloaded
    
    Attributes:
        plugin_dirs (List[str]): List of directories to search for plugins
        plugins (Dict[str, Type[PluginBase]]): Available plugin classes
        active_plugins (Dict[str, PluginBase]): Currently active plugin instances
    """

    plugin_loaded = Signal(str)
    plugin_unloaded = Signal(str)

    def __init__(self, plugin_dirs: List[str] = None):
        """
        Initialize the plugin manager.

        Args:
            plugin_dirs: List of directories to search for plugins.
                        If None, uses default plugin directory relative to this module.
        """
        super().__init__()

        if plugin_dirs is None:
            # Default plugin directories
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.plugin_dirs = [
                os.path.join(base_dir, "plugins"),
            ]
        else:
            self.plugin_dirs = plugin_dirs

        self.plugins: Dict[str, Type[PluginBase]] = {}
        self.active_plugins: Dict[str, PluginBase] = {}

    def discover_plugins(self) -> Dict[str, Type[PluginBase]]:
        """
        Discover available plugins in the plugin directories.
        
        This method searches through all configured plugin directories for
        plugin_finder.py modules and loads the plugins they register.

        Returns:
            Dict[str, Type[PluginBase]]: Dictionary mapping plugin names to plugin classes
        """

        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                os.makedirs(plugin_dir, exist_ok=True)
                continue

            sys.path.insert(0, plugin_dir)

            # Check if finder module exists, if not, skip this directory
            finder_path = os.path.join(plugin_dir, "plugin_finder.py")
            if not os.path.exists(finder_path):
                continue

            try:
                # Import the plugin_finder module
                logger.info("Loading plugin finder module...")
                # Try absolute import first
                try:
                    from localknowledge.ui.plugins.plugin_finder import get_plugin_classes
                except ImportError:
                    # Fall back to direct import
                    sys.path.insert(0, os.path.dirname(plugin_dir))
                    from plugins.plugin_finder import get_plugin_classes

                # Get registered plugin classes
                registered_plugins = get_plugin_classes()
                self.plugins.update(registered_plugins)
            except Exception as e:
                logger.error(f"Error loading plugins via plugin_finder: {e}")

        logger.info(f"Discovered plugins: {list(self.plugins.keys())}")
        return self.plugins

    def load_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Load a plugin by name.
        
        This method instantiates a plugin class and initializes it. If the plugin
        is already loaded, returns the existing instance.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Optional[PluginBase]: Plugin instance or None if loading failed
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin '{plugin_name}' not found")
            return None

        if plugin_name in self.active_plugins:
            return self.active_plugins[plugin_name]

        try:
            plugin_class = self.plugins[plugin_name]
            plugin = plugin_class()

            if plugin.initialize():
                self.active_plugins[plugin_name] = plugin
                self.plugin_loaded.emit(plugin_name)
                return plugin
            else:
                logger.error(f"Plugin '{plugin_name}' failed to initialize")
                return None

        except Exception as e:
            logger.error(f"Error initializing plugin '{plugin_name}': {e}")
            return None

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin by name.
        
        This method calls the plugin's cleanup method and removes it from
        the active plugins list.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            bool: True if unloaded successfully, False otherwise
        """
        if plugin_name not in self.active_plugins:
            return False

        plugin = self.active_plugins[plugin_name]

        if plugin.close_plugin():
            del self.active_plugins[plugin_name]
            self.plugin_unloaded.emit(plugin_name)
            return True

        return False

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Get an active plugin instance by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Optional[PluginBase]: Plugin instance or None if not loaded
        """
        return self.active_plugins.get(plugin_name)

    def get_available_plugins(self) -> Dict[str, Type[PluginBase]]:
        """
        Get all available plugins.
        
        Returns a dictionary of all discovered plugin classes, whether
        they are currently loaded or not.

        Returns:
            Dict[str, Type[PluginBase]]: Dictionary of available plugin classes
        """
        return self.plugins

    def get_active_plugins(self) -> Dict[str, PluginBase]:
        """
        Get all active plugins.
        
        Returns a dictionary of all currently loaded and active plugin instances.

        Returns:
            Dict[str, PluginBase]: Dictionary of active plugin instances
        """
        return self.active_plugins
