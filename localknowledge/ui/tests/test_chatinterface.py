#!/usr/bin/env python3
"""
Unit tests for the ChatInterface widget.

This module contains tests for the chat interface functionality.
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from localknowledge.ui.chatinterface import ChatInterface, MessageCard, ChatScrollArea


class TestMessageCard(unittest.TestCase):
    """Test cases for MessageCard widget."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def test_user_message_card(self):
        """Test creating a user message card."""
        card = MessageCard("Hello, world!", is_user=True)
        
        self.assertEqual(card.message, "Hello, world!")
        self.assertTrue(card.is_user)
        self.assertEqual(card.message_label.text(), "Hello, world!")
    
    def test_ai_message_card(self):
        """Test creating an AI message card."""
        card = MessageCard("Hello, human!", is_user=False)
        
        self.assertEqual(card.message, "Hello, human!")
        self.assertFalse(card.is_user)
        self.assertEqual(card.message_label.text(), "Hello, human!")
    
    def test_update_message(self):
        """Test updating message content."""
        card = MessageCard("Initial message", is_user=True)
        card.update_message("Updated message")
        
        self.assertEqual(card.message, "Updated message")
        self.assertEqual(card.message_label.text(), "Updated message")


class TestChatScrollArea(unittest.TestCase):
    """Test cases for ChatScrollArea widget."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test case."""
        self.chat_area = ChatScrollArea()
    
    def test_add_message(self):
        """Test adding messages to chat area."""
        # Add user message
        user_card = self.chat_area.add_message("User message", is_user=True)
        self.assertIsInstance(user_card, MessageCard)
        self.assertTrue(user_card.is_user)
        
        # Add AI message
        ai_card = self.chat_area.add_message("AI response", is_user=False)
        self.assertIsInstance(ai_card, MessageCard)
        self.assertFalse(ai_card.is_user)
        
        # Check that messages were added (2 messages + 1 stretch item)
        self.assertEqual(self.chat_area.content_layout.count(), 3)
    
    def test_clear_messages(self):
        """Test clearing all messages."""
        # Add some messages
        self.chat_area.add_message("Message 1", is_user=True)
        self.chat_area.add_message("Message 2", is_user=False)
        
        # Clear messages
        self.chat_area.clear_messages()
        
        # Should only have the stretch item left
        self.assertEqual(self.chat_area.content_layout.count(), 1)


class TestChatInterface(unittest.TestCase):
    """Test cases for ChatInterface widget."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test case."""
        # Mock the agent to avoid requiring Ollama
        with patch('localknowledge.ui.chatinterface.LocalKnowledgeAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent
            self.chat_interface = ChatInterface()
    
    def test_initialization(self):
        """Test chat interface initialization."""
        self.assertIsNotNone(self.chat_interface.chat_area)
        self.assertIsNotNone(self.chat_interface.text_input)
        self.assertIsNotNone(self.chat_interface.send_button)
        self.assertIsNotNone(self.chat_interface.cancel_button)
        self.assertIsNotNone(self.chat_interface.retry_button)
        self.assertIsNotNone(self.chat_interface.attach_button)
    
    def test_ui_state_changes(self):
        """Test UI state changes during sending."""
        # Initial state
        self.assertTrue(self.chat_interface.send_button.isVisible())
        self.assertFalse(self.chat_interface.cancel_button.isVisible())
        self.assertFalse(self.chat_interface.retry_button.isVisible())
        
        # Sending state
        self.chat_interface.set_sending_state(True)
        self.assertFalse(self.chat_interface.send_button.isVisible())
        self.assertTrue(self.chat_interface.cancel_button.isVisible())
        self.assertFalse(self.chat_interface.retry_button.isVisible())
        self.assertFalse(self.chat_interface.text_input.isEnabled())
        
        # Back to normal state
        self.chat_interface.set_sending_state(False)
        self.assertTrue(self.chat_interface.send_button.isVisible())
        self.assertFalse(self.chat_interface.cancel_button.isVisible())
        self.assertTrue(self.chat_interface.text_input.isEnabled())
    
    def test_text_input_validation(self):
        """Test text input validation."""
        # Empty text should disable send button
        self.chat_interface.text_input.clear()
        self.chat_interface.on_text_changed()
        self.assertFalse(self.chat_interface.send_button.isEnabled())
        
        # Non-empty text should enable send button
        self.chat_interface.text_input.setPlainText("Hello")
        self.chat_interface.on_text_changed()
        self.assertTrue(self.chat_interface.send_button.isEnabled())
    
    def test_file_attachment(self):
        """Test file attachment functionality."""
        # Initially no files
        self.assertEqual(len(self.chat_interface.attached_files), 0)
        self.assertFalse(self.chat_interface.files_label.isVisible())
        
        # Add a file
        test_file = "/tmp/test.txt"
        self.chat_interface.attached_files.append(test_file)
        self.chat_interface.update_files_display()
        
        self.assertEqual(len(self.chat_interface.attached_files), 1)
        self.assertTrue(self.chat_interface.files_label.isVisible())
        self.assertIn("test.txt", self.chat_interface.files_label.text())
        
        # Clear files
        self.chat_interface.clear_attached_files()
        self.assertEqual(len(self.chat_interface.attached_files), 0)
        self.assertFalse(self.chat_interface.files_label.isVisible())
    
    def test_system_message(self):
        """Test adding system messages."""
        initial_count = self.chat_interface.chat_area.content_layout.count()
        
        self.chat_interface.add_system_message("System message")
        
        # Should have added one more widget
        self.assertEqual(
            self.chat_interface.chat_area.content_layout.count(),
            initial_count + 1
        )
    
    def test_clear_chat(self):
        """Test clearing chat functionality."""
        # Add some messages
        self.chat_interface.chat_area.add_message("User message", is_user=True)
        self.chat_interface.chat_area.add_message("AI response", is_user=False)
        
        # Clear chat
        self.chat_interface.clear_chat()
        
        # Should only have stretch item
        self.assertEqual(self.chat_interface.chat_area.content_layout.count(), 1)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestMessageCard))
    suite.addTests(loader.loadTestsFromTestCase(TestChatScrollArea))
    suite.addTests(loader.loadTestsFromTestCase(TestChatInterface))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
