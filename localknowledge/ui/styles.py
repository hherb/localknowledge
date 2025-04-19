"""
Centralized styling module for the LocalKnowledge UI.

This module defines consistent styles for UI components across the application.
Use these styles for any new UI components to maintain a consistent look and feel.
"""

from PySide6.QtGui import QColor, QFont
from typing import Dict, Any

# Colors
COLORS = {
    "primary": "#2962ff",  # Main app color - deep blue
    "secondary": "#00b0ff",  # Secondary color - lighter blue
    "background": "#ffffff",  # White
    "alt_background": "#f9f9f9",  # Light grey for alternating items
    "text": "#202020",  # Nearly black
    "light_text": "#757575",  # Medium grey
    "accent": "#d0e3ff",  # Light blue accent
    "success": "#4caf50",  # Green
    "error": "#f44336",  # Red
    "warning": "#ff9800",  # Orange
    "info": "#2196f3",  # Blue
    "unread": "#e3f2fd",  # Light blue for unread items
    "read": "#ffffff",  # White for read items
    "selected": "#d0e3ff",  # Light blue for selection
    "hover": "#f5f5f5",  # Very light grey for hover states
}

# Font sizes
FONT_SIZES = {
    "small": 9,
    "normal": 10,
    "medium": 12,
    "large": 14,
    "x_large": 16,
    "xx_large": 20,
}

# Font weights
FONT_WEIGHTS = {
    "normal": QFont.Weight.Normal,
    "bold": QFont.Weight.Bold,
}

# Widget styles as CSS strings
STYLE_SHEETS = {
    # List widget with alternating row colors and nice item padding
    "LIST_WIDGET": """
        QListWidget {
            padding: 5px;
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 8px;
            margin: 2px 0;
        }
        QListWidget::item:alternate {
            background-color: #f9f9f9;
        }
        QListWidget::item:selected {
            background-color: #d0e3ff;
            color: black;
            border-radius: 2px;
        }
        QListWidget::item:hover {
            background-color: #f5f5f5;
            border-radius: 2px;
        }
    """,
    
    # Button styles
    "BUTTON_PRIMARY": """
        QPushButton {
            background-color: #2962ff;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1e50f7;
        }
        QPushButton:pressed {
            background-color: #0039cb;
        }
        QPushButton:disabled {
            background-color: #bdbdbd;
        }
    """,
    
    "BUTTON_SECONDARY": """
        QPushButton {
            background-color: white;
            color: #2962ff;
            border: 1px solid #2962ff;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #f5f5f5;
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
        QPushButton:disabled {
            color: #bdbdbd;
            border-color: #bdbdbd;
        }
    """,
    
    "TOOLBAR_BUTTON": """
        QPushButton {
            background-color: transparent;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QPushButton:hover {
            background-color: #f5f5f5;
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
    """,
    
    # Text display
    "TEXT_VIEW": """
        QTextBrowser {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 10px;
        }
    """,
    
    # Combo box (dropdown)
    "COMBO_BOX": """
        QComboBox {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 4px;
            min-width: 6em;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #e0e0e0;
        }
        QComboBox::down-arrow {
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #e0e0e0;
            selection-background-color: #d0e3ff;
        }
    """,
    
    # Tab widget
    "TAB_WIDGET": """
        QTabWidget::pane {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            top: -1px;
        }
        QTabBar::tab {
            background-color: #f5f5f5;
            border: 1px solid #e0e0e0;
            border-bottom-color: #e0e0e0;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 6px 12px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom-color: white;
        }
        QTabBar::tab:!selected {
            margin-top: 2px;
        }
    """,
    
    # Line edit (text input)
    "LINE_EDIT": """
        QLineEdit {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 4px;
        }
        QLineEdit:focus {
            border: 1px solid #2962ff;
        }
    """,
    
    # Text edit (multi-line input)
    "TEXT_EDIT": """
        QTextEdit {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 4px;
        }
        QTextEdit:focus {
            border: 1px solid #2962ff;
        }
    """,
    
    # Toolbar
    "TOOLBAR": """
        QToolBar {
            background-color: white;
            border-bottom: 1px solid #e0e0e0;
            spacing: 6px;
            padding: 4px;
        }
    """,
    
    # Status bar
    "STATUS_BAR": """
        QStatusBar {
            background-color: #f5f5f5;
            border-top: 1px solid #e0e0e0;
        }
        QStatusBar::item {
            border: none;
        }
    """,
    
    # Frame for panels
    "PANEL_FRAME": """
        QFrame {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }
    """,
    
    # Dialog
    "DIALOG": """
        QDialog {
            background-color: white;
        }
    """,
    
    # Main window
    "MAIN_WINDOW": """
        QMainWindow {
            background-color: #f9f9f9;
        }
        QMainWindow::separator {
            background-color: #e0e0e0;
            width: 1px;
            height: 1px;
        }
    """,
}

# Function to get styled QColor objects
def get_color(color_name: str) -> QColor:
    """
    Get a QColor object for a named color from the COLORS dictionary.
    
    Args:
        color_name: Name of the color to retrieve
        
    Returns:
        QColor object for the specified color
    """
    if color_name in COLORS:
        return QColor(COLORS[color_name])
    return QColor("black")  # Default

# Function to get a font with specified properties
def get_font(size_name: str = "normal", weight_name: str = "normal") -> QFont:
    """
    Get a QFont with the specified size and weight.
    
    Args:
        size_name: Name of the font size (small, normal, medium, large, etc.)
        weight_name: Name of the font weight (normal, bold)
        
    Returns:
        QFont object with the specified properties
    """
    font = QFont()
    
    # Set size
    if size_name in FONT_SIZES:
        font.setPointSize(FONT_SIZES[size_name])
    else:
        font.setPointSize(FONT_SIZES["normal"])
    
    # Set weight
    if weight_name in FONT_WEIGHTS:
        font.setWeight(FONT_WEIGHTS[weight_name])
    
    return font
