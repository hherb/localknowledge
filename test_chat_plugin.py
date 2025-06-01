#!/usr/bin/env python3
"""
Test script for the Chat Interface Plugin in the main application.

This script demonstrates how to load and use the chat interface plugin
within the LocalKnowledge main application framework.
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Import the main application
from localknowledge.ui.rwb_main import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main function to test the chat plugin in the main application."""
    # Create application
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("LocalKnowledge Chat Plugin Test")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("LocalKnowledge")
    
    try:
        # Create main window
        window = MainWindow()
        
        # Show the window
        window.show()
        
        # Load the chat interface plugin automatically
        logger.info("Loading Chat Interface Plugin...")
        window.load_plugin("ChatInterfacePlugin")
        
        # Show status message
        window.statusBar().showMessage("Chat Interface Plugin loaded successfully! Use the configuration panel to adjust settings.")
        
        logger.info("Chat Interface Plugin test application started")
        logger.info("Instructions:")
        logger.info("1. The chat interface should be loaded in a new tab")
        logger.info("2. Click the configuration button to access chat settings")
        logger.info("3. Try sending messages to test the AI functionality")
        logger.info("4. Make sure Ollama is running with qwen3:8b model for full functionality")
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
