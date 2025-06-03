#!/usr/bin/env python3
"""
Test script to verify configuration sidebar fixes.

This script creates a minimal test environment to verify that the configuration
sidebar and splitter functionality works correctly.
"""

import sys
import os
from typing import Optional

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLabel, QPushButton, QTextEdit, QSizePolicy, QGroupBox,
        QCheckBox, QComboBox, QSpinBox, QFormLayout
    )
    from PySide6.QtCore import Qt
    
    # Import our fixed classes
    from localknowledge.ui.rwb_main import ConfigPanel, PluginBase
    
    class TestConfigWidget(QWidget):
        """Test configuration widget."""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setup_ui()
        
        def setup_ui(self):
            layout = QVBoxLayout(self)
            
            # Test group
            group = QGroupBox("Test Configuration")
            group_layout = QFormLayout(group)
            
            # Test controls
            combo = QComboBox()
            combo.addItems(["Option 1", "Option 2", "Option 3"])
            group_layout.addRow("Model:", combo)
            
            checkbox = QCheckBox("Enable feature")
            checkbox.setChecked(True)
            group_layout.addRow("Feature:", checkbox)
            
            spinbox = QSpinBox()
            spinbox.setRange(1, 100)
            spinbox.setValue(10)
            group_layout.addRow("Count:", spinbox)
            
            layout.addWidget(group)
            
            # Buttons
            button_layout = QHBoxLayout()
            apply_btn = QPushButton("Apply")
            reset_btn = QPushButton("Reset")
            button_layout.addWidget(apply_btn)
            button_layout.addWidget(reset_btn)
            layout.addLayout(button_layout)
            
            layout.addStretch()
    
    class TestPlugin(PluginBase):
        """Test plugin with configuration widget."""
        
        plugin_name = "Test Plugin"
        plugin_description = "Test plugin for configuration sidebar"
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.config_widget = None
            self.setup_ui()
        
        def setup_ui(self):
            layout = QVBoxLayout(self)
            
            label = QLabel("Test Plugin Content")
            label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
            layout.addWidget(label)
            
            text_area = QTextEdit()
            text_area.setPlainText(
                "This is a test plugin to verify that the configuration sidebar works correctly.\n\n"
                "The configuration panel should appear on the left when you click the settings button.\n\n"
                "Try:\n"
                "1. Clicking the settings button to toggle the config panel\n"
                "2. Dragging the splitter handle to resize the panels\n"
                "3. Switching between tabs to see config updates"
            )
            layout.addWidget(text_area)
        
        def get_config_widget(self) -> Optional[QWidget]:
            """Get the configuration widget."""
            if not self.config_widget:
                self.config_widget = TestConfigWidget()
            return self.config_widget
    
    class TestMainWindow(QMainWindow):
        """Test main window."""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Configuration Sidebar Test")
            self.setGeometry(100, 100, 1200, 800)
            self.setup_ui()
        
        def setup_ui(self):
            # Central widget
            central_widget = QWidget()
            central_layout = QVBoxLayout(central_widget)
            central_layout.setContentsMargins(0, 0, 0, 0)
            self.setCentralWidget(central_widget)
            
            # Create splitter (similar to the main app)
            self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
            self.main_splitter.setHandleWidth(12)
            self.main_splitter.setChildrenCollapsible(True)
            self.main_splitter.setOpaqueResize(True)
            
            # Style the splitter
            self.main_splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: #d0d0d0;
                    border: 1px solid #a0a0a0;
                    margin: 1px;
                    border-radius: 2px;
                }
                QSplitter::handle:hover {
                    background-color: #b0b0b0;
                    border: 1px solid #808080;
                }
                QSplitter::handle:pressed {
                    background-color: #909090;
                    border: 1px solid #606060;
                }
                QSplitter::handle:horizontal {
                    width: 12px;
                    min-width: 12px;
                    max-width: 12px;
                }
            """)
            
            # Create config panel
            self.config_panel = ConfigPanel()
            self.config_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Create test plugin
            self.test_plugin = TestPlugin()
            
            # Set config content
            config_widget = self.test_plugin.get_config_widget()
            if config_widget:
                self.config_panel.set_content(config_widget)
            
            # Add to splitter
            self.main_splitter.addWidget(self.config_panel)
            self.main_splitter.addWidget(self.test_plugin)
            
            # Set initial sizes (config: 350px, main: rest)
            self.main_splitter.setSizes([350, 850])
            
            # Add to layout
            central_layout.addWidget(self.main_splitter)
            
            # Add control buttons
            button_layout = QHBoxLayout()
            
            toggle_btn = QPushButton("Toggle Config Panel")
            toggle_btn.clicked.connect(self.toggle_config_panel)
            button_layout.addWidget(toggle_btn)
            
            clear_btn = QPushButton("Clear Config")
            clear_btn.clicked.connect(lambda: self.config_panel.set_content(None))
            button_layout.addWidget(clear_btn)
            
            restore_btn = QPushButton("Restore Config")
            restore_btn.clicked.connect(lambda: self.config_panel.set_content(self.test_plugin.get_config_widget()))
            button_layout.addWidget(restore_btn)
            
            button_layout.addStretch()
            central_layout.addLayout(button_layout)
            
            # Connect splitter signal
            self.main_splitter.splitterMoved.connect(self.on_splitter_moved)
        
        def toggle_config_panel(self):
            """Toggle config panel visibility."""
            sizes = self.main_splitter.sizes()
            total_width = sum(sizes)
            
            if sizes[0] > 50:  # Expanded
                self.main_splitter.setSizes([0, total_width])
            else:  # Collapsed
                self.main_splitter.setSizes([350, total_width - 350])
        
        def on_splitter_moved(self, pos, index):
            """Handle splitter movement."""
            sizes = self.main_splitter.sizes()
            print(f"Splitter moved: position={pos}, sizes={sizes}")
    
    def main():
        app = QApplication(sys.argv)
        
        window = TestMainWindow()
        window.show()
        
        print("Configuration Sidebar Test")
        print("=" * 50)
        print("Test the following:")
        print("1. Click 'Toggle Config Panel' to show/hide the config panel")
        print("2. Drag the splitter handle to resize panels")
        print("3. Click 'Clear Config' to remove config content")
        print("4. Click 'Restore Config' to restore config content")
        print("5. Check that the splitter handle is visible and responsive")
        
        return app.exec()

except ImportError as e:
    print(f"Import error: {e}")
    print("This test requires PySide6 and the localknowledge module.")
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
