import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QToolBar, QSplitter, 
                               QTabWidget, QStatusBar, QLabel, QPushButton,
                               QTextEdit, QCheckBox, QSpinBox, QFormLayout)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QAction


class ConfigurationPanel(QWidget):
    """Left sidebar configuration panel"""
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Configuration title
        title = QLabel("Configuration")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # Sample configuration options
        form_layout = QFormLayout()
        
        # Sample checkbox
        self.enable_feature = QCheckBox()
        form_layout.addRow("Enable Feature:", self.enable_feature)
        
        # Sample spinbox
        self.timeout_value = QSpinBox()
        self.timeout_value.setRange(1, 300)
        self.timeout_value.setValue(30)
        form_layout.addRow("Timeout (sec):", self.timeout_value)
        
        # Sample text area
        self.notes_area = QTextEdit()
        self.notes_area.setMaximumHeight(100)
        self.notes_area.setPlaceholderText("Configuration notes...")
        form_layout.addRow("Notes:", self.notes_area)
        
        layout.addLayout(form_layout)
        layout.addStretch()  # Push everything to the top
        
        self.setLayout(layout)
        self.setMinimumWidth(200)


class MainTabWidget(QTabWidget):
    """Main tabbed widget where plugins can add tabs"""
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        # Add some sample tabs to demonstrate functionality
        self.add_sample_tabs()
    
    def add_sample_tabs(self):
        """Add sample tabs to demonstrate the interface"""
        # Tab 1
        tab1 = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_layout.addWidget(QLabel("This is Tab 1 content"))
        tab1_layout.addWidget(QTextEdit("Plugin content would go here..."))
        tab1.setLayout(tab1_layout)
        self.addTab(tab1, "Data View")
        
        # Tab 2
        tab2 = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_layout.addWidget(QLabel("This is Tab 2 content"))
        tab2_layout.addWidget(QPushButton("Sample Plugin Button"))
        tab2.setLayout(tab2_layout)
        self.addTab(tab2, "Analysis")
        
        # Tab 3
        tab3 = QWidget()
        tab3_layout = QVBoxLayout()
        tab3_layout.addWidget(QLabel("This is Tab 3 content"))
        tab3_layout.addStretch()
        tab3.setLayout(tab3_layout)
        self.addTab(tab3, "Settings")
    
    def add_plugin_tab(self, widget, title):
        """Method for plugins to add their own tabs"""
        return self.addTab(widget, title)


def create_cogwheel_icon(size=24):
    """Create a simple cogwheel icon programmatically"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Set pen for drawing
    pen = QPen(Qt.black, 2)
    painter.setPen(pen)
    
    # Draw outer circle
    center = size // 2
    outer_radius = size // 2 - 2
    inner_radius = size // 4
    
    # Draw gear teeth (simplified)
    for i in range(8):
        angle = i * 45
        painter.save()
        painter.translate(center, center)
        painter.rotate(angle)
        painter.drawLine(0, -outer_radius, 0, -outer_radius + 3)
        painter.restore()
    
    # Draw circles
    painter.drawEllipse(center - outer_radius + 3, center - outer_radius + 3, 
                       (outer_radius - 3) * 2, (outer_radius - 3) * 2)
    painter.drawEllipse(center - inner_radius, center - inner_radius, 
                       inner_radius * 2, inner_radius * 2)
    
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_panel_visible = True
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Plugin Application")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create configuration panel
        self.config_panel = ConfigurationPanel()
        
        # Create main tab widget
        self.main_tabs = MainTabWidget()
        
        # Add widgets to splitter
        self.splitter.addWidget(self.config_panel)
        self.splitter.addWidget(self.main_tabs)
        
        # Set splitter proportions (config panel smaller)
        self.splitter.setSizes([250, 750])
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
        
        # Create status bar
        self.create_status_bar()
    
    def create_toolbar(self):
        """Create the top toolbar with cogwheel icon"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        
        # Create cogwheel action
        cogwheel_icon = create_cogwheel_icon()
        self.toggle_config_action = QAction(cogwheel_icon, "Toggle Configuration Panel", self)
        self.toggle_config_action.triggered.connect(self.toggle_config_panel)
        
        toolbar.addAction(self.toggle_config_action)
        
        # Add separator and stretch to push other items to the right if needed
        toolbar.addSeparator()
        
        # Add toolbar to main window
        self.addToolBar(toolbar)
    
    def create_status_bar(self):
        """Create the bottom status bar"""
        status_bar = QStatusBar()
        status_bar.showMessage("Ready")
        
        # Add some permanent widgets to status bar
        self.status_label = QLabel("Status: Ready")
        status_bar.addPermanentWidget(self.status_label)
        
        self.setStatusBar(status_bar)
    
    def toggle_config_panel(self):
        """Toggle visibility of the configuration panel"""
        if self.config_panel_visible:
            self.config_panel.hide()
            self.config_panel_visible = False
            self.statusBar().showMessage("Configuration panel hidden")
        else:
            self.config_panel.show()
            self.config_panel_visible = True
            self.statusBar().showMessage("Configuration panel shown")
    
    def add_plugin_tab(self, widget, title):
        """Public method for plugins to add tabs"""
        return self.main_tabs.add_plugin_tab(widget, title)
    
    def update_status(self, message):
        """Update status bar message"""
        self.statusBar().showMessage(message)
        self.status_label.setText(f"Status: {message}")


def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Plugin Application")
    app.setApplicationVersion("1.0")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Example of how a plugin might add a tab
    # plugin_widget = QWidget()
    # plugin_layout = QVBoxLayout()
    # plugin_layout.addWidget(QLabel("This is a plugin tab"))
    # plugin_widget.setLayout(plugin_layout)
    # window.add_plugin_tab(plugin_widget, "Plugin Tab")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()