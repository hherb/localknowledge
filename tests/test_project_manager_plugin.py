#!/usr/bin/env python3
"""
Test script for the ProjectManagerPlugin.

This script tests the ProjectManagerPlugin class in a standalone application.
"""

import sys
import os

# Add the parent directory to the path so we can import localknowledge
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow
from localknowledge.ui.plugins.project_manager import ProjectManagerPlugin
from localknowledge.context import set_current_user


class TestWindow(QMainWindow):
    """Test window for the ProjectManagerPlugin."""

    def __init__(self):
        """Initialize the test window."""
        super().__init__()

        self.setWindowTitle("Project Manager Plugin Test")
        self.resize(1200, 800)

        # Create the plugin
        self.plugin = ProjectManagerPlugin()

        # Set as central widget
        self.setCentralWidget(self.plugin)

        # Set up test data
        self.setup_test_data()

    def setup_test_data(self):
        """Set up test data for the plugin."""
        # Set the current user ID (using hherb or a default)
        from localknowledge.db.user import UserDatabaseManager
        user_db = UserDatabaseManager()

        try:
            # Try to get the user 'hherb' first
            result = user_db.execute("SELECT id FROM users WHERE username = %s", ("hherb",))
            if result and len(result) > 0:
                self.user_id = result[0]['id']
            else:
                # Use a default user ID
                self.user_id = 1
        except Exception as e:
            print(f"Error getting user: {e}")
            # Use a default user ID as fallback
            self.user_id = 1

        # Set the current user in the context
        # Create a user dictionary as expected by the context system
        user_data = user_db.get_user(self.user_id)
        if user_data:
            set_current_user(user_data)
        else:
            # Fallback to just the ID if we can't get the user data
            set_current_user({'id': self.user_id})

        print(f"Test setup complete. User ID: {self.user_id}")


def main():
    """Main function to run the test."""
    app = QApplication(sys.argv)

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
