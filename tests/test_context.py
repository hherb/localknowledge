"""
Unit tests for the context management system.
"""
import unittest
from localknowledge.context import (
    ContextManager, context_manager, set_context, get_context,
    register_context_listener, unregister_context_listener,
    CURRENT_USER, CURRENT_PROJECT
)


class TestContextManager(unittest.TestCase):
    """Test cases for the context management system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear the context before each test
        context_manager.clear()
        
    def test_singleton(self):
        """Test that ContextManager is a singleton."""
        cm1 = ContextManager()
        cm2 = ContextManager()
        self.assertIs(cm1, cm2)
        
    def test_set_get(self):
        """Test setting and getting values."""
        # Set a value
        set_context("test_key", "test_value")
        
        # Get the value
        value = get_context("test_key")
        self.assertEqual(value, "test_value")
        
        # Get a non-existent value
        value = get_context("non_existent")
        self.assertIsNone(value)
        
        # Get a non-existent value with default
        value = get_context("non_existent", "default")
        self.assertEqual(value, "default")
        
    def test_listeners(self):
        """Test listener registration and notification."""
        # Create a mock listener
        values = []
        
        def listener(value):
            values.append(value)
        
        # Register the listener
        register_context_listener("test_key", listener)
        
        # Set a value
        set_context("test_key", "test_value")
        
        # Check that the listener was called
        self.assertEqual(values, ["test_value"])
        
        # Set another value
        set_context("test_key", "another_value")
        
        # Check that the listener was called again
        self.assertEqual(values, ["test_value", "another_value"])
        
        # Unregister the listener
        unregister_context_listener("test_key", listener)
        
        # Set another value
        set_context("test_key", "third_value")
        
        # Check that the listener was not called
        self.assertEqual(values, ["test_value", "another_value"])
        
    def test_clear(self):
        """Test clearing the context."""
        # Set some values
        set_context("key1", "value1")
        set_context("key2", "value2")
        
        # Check that the values are set
        self.assertEqual(get_context("key1"), "value1")
        self.assertEqual(get_context("key2"), "value2")
        
        # Create a mock listener
        values = []
        
        def listener(value):
            values.append(value)
        
        # Register the listener
        register_context_listener("key1", listener)
        
        # Clear the context
        context_manager.clear()
        
        # Check that the values are cleared
        self.assertIsNone(get_context("key1"))
        self.assertIsNone(get_context("key2"))
        
        # Check that the listener was called with None
        self.assertEqual(values, [None])
        
    def test_multiple_listeners(self):
        """Test multiple listeners for the same key."""
        # Create mock listeners
        values1 = []
        values2 = []
        
        def listener1(value):
            values1.append(value)
            
        def listener2(value):
            values2.append(value)
        
        # Register the listeners
        register_context_listener("test_key", listener1)
        register_context_listener("test_key", listener2)
        
        # Set a value
        set_context("test_key", "test_value")
        
        # Check that both listeners were called
        self.assertEqual(values1, ["test_value"])
        self.assertEqual(values2, ["test_value"])
        
        # Unregister one listener
        unregister_context_listener("test_key", listener1)
        
        # Set another value
        set_context("test_key", "another_value")
        
        # Check that only the second listener was called
        self.assertEqual(values1, ["test_value"])
        self.assertEqual(values2, ["test_value", "another_value"])


if __name__ == "__main__":
    unittest.main()
