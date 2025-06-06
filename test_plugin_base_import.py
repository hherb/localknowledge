#!/usr/bin/env python3
"""
Test script to verify that PluginBase can be imported correctly
from the new plugin_base module.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_plugin_base_import():
    """Test that PluginBase can be imported from the new module."""
    try:
        # Import PluginBase from the new location
        from localknowledge.ui.plugin_base import PluginBase
        print("✓ Successfully imported PluginBase from localknowledge.ui.plugin_base")
        
        # Test that it's a class
        assert isinstance(PluginBase, type), "PluginBase should be a class"
        print("✓ PluginBase is a class")
        
        # Test that it has the expected attributes
        assert hasattr(PluginBase, 'plugin_name'), "PluginBase should have plugin_name attribute"
        assert hasattr(PluginBase, 'plugin_description'), "PluginBase should have plugin_description attribute"
        assert hasattr(PluginBase, 'initialize'), "PluginBase should have initialize method"
        assert hasattr(PluginBase, 'get_main_widget'), "PluginBase should have get_main_widget method"
        assert hasattr(PluginBase, 'get_config_widget'), "PluginBase should have get_config_widget method"
        print("✓ PluginBase has all expected attributes and methods")
        
        # Test that we can create an instance (this requires PySide6 to be available)
        try:
            instance = PluginBase()
            print("✓ Successfully created PluginBase instance")
            
            # Test some methods
            assert instance.initialize() == True, "initialize() should return True"
            assert instance.get_title() == "Base Plugin", "get_title() should return plugin_name"
            assert instance.get_actions() == [], "get_actions() should return empty list"
            print("✓ PluginBase methods work correctly")
            
        except ImportError as e:
            print(f"⚠ Could not create PluginBase instance (PySide6 not available): {e}")
        
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import PluginBase: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_plugin_finder_import():
    """Test that plugin_finder can import PluginBase from the new location."""
    try:
        # This will test the import in plugin_finder.py
        from localknowledge.ui.plugins.plugin_finder import PluginBase
        print("✓ plugin_finder.py can import PluginBase from new location")
        return True
    except ImportError as e:
        print(f"✗ plugin_finder.py failed to import PluginBase: {e}")
        return False

if __name__ == "__main__":
    print("Testing PluginBase refactoring...")
    print("=" * 50)
    
    success = True
    
    # Test direct import
    success &= test_plugin_base_import()
    print()
    
    # Test plugin_finder import
    success &= test_plugin_finder_import()
    print()
    
    if success:
        print("🎉 All tests passed! PluginBase refactoring is successful.")
    else:
        print("❌ Some tests failed. Please check the imports.")
    
    print("=" * 50)
