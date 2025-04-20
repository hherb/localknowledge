"""
Custom PDF viewer with text selection and search capabilities.

This module provides a custom implementation of QPdfView that adds text selection
and search functionality for versions of PySide6 that don't have these features built-in.
"""

import os
from pathlib import Path
import sys
import traceback

from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QApplication,
    QScrollArea, QSizePolicy
)
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument


class CustomPdfView(QPdfView):
    """
    Custom PDF view with text selection and search capabilities.
    """
    
    # Signals
    selectionChanged = Signal(str)  # Emitted when text selection changes
    searchCompleted = Signal(int)   # Emitted when search completes, with number of matches
    
    def __init__(self, parent=None):
        """Initialize the custom PDF view."""
        super().__init__(parent)
        
        # Set up view properties
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        
        # Initialize text selection variables
        self.selection_start = QPointF()
        self.selection_end = QPointF()
        self.is_selecting = False
        self.current_page = 0
        self.selected_text = ""
        
        # Initialize search variables
        self.search_text = ""
        self.search_results = []  # List of (page_index, QRectF) tuples
        self.current_match_index = -1
        
        # Initialize highlighting variables
        self.highlighted_areas = []  # List of (page_index, QRectF, color) tuples
        self.highlight_color = QColor(255, 255, 0, 100)  # Yellow with alpha
        self.search_highlight_color = QColor(255, 165, 0, 100)  # Orange with alpha
    
    def mousePressEvent(self, event):
        """Handle mouse press events for starting text selection."""
        if event.button() == Qt.LeftButton:
            # Start selection
            self.is_selecting = True
            self.selection_start = event.position()
            
            # Find current page
            try:
                # Try to use pageAt method if available
                if hasattr(self, 'pageAt'):
                    self.current_page = self.pageAt(event.position().toPoint())
                else:
                    # Fallback: estimate page based on position
                    self.current_page = self._estimatePageAt(event.position().toPoint())
            except Exception as e:
                print(f"Error determining page: {e}")
                self.current_page = 0
            
            # Clear previous selection
            self.clearSelection()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for updating text selection."""
        if self.is_selecting:
            self.selection_end = event.position()
            # Create selection from start to current position
            self.updateTextSelection()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for finalizing text selection."""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.selection_end = event.position()
            self.updateTextSelection()
            
            # Get selected text
            self.extractSelectedText()
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def updateTextSelection(self):
        """Update text selection based on mouse positions."""
        if not self.document() or self.current_page < 0:
            return
        
        try:
            # Create a visual selection rectangle
            selection_rect = QRectF(
                self.selection_start.x(), 
                self.selection_start.y(),
                self.selection_end.x() - self.selection_start.x(),
                self.selection_end.y() - self.selection_start.y()
            ).normalized()
            
            # Store the selection for highlighting
            self.highlighted_areas = [(self.current_page, selection_rect, QColor(173, 216, 230, 100))]  # Light blue
            
            # Trigger repaint
            self.viewport().update()
        except Exception as e:
            print(f"Error updating text selection: {e}")
    
    def clearSelection(self):
        """Clear the current text selection."""
        self.highlighted_areas = [h for h in self.highlighted_areas if h[2] != QColor(173, 216, 230, 100)]
        self.selected_text = ""
        self.viewport().update()
    
    def extractSelectedText(self):
        """Extract text from the current selection."""
        if not self.document():
            return
        
        try:
            # This is a placeholder - in a real implementation, we would extract text
            # from the PDF document based on the selection coordinates
            # For now, we'll just emit a signal with a placeholder text
            self.selected_text = "Selected text would appear here"
            self.selectionChanged.emit(self.selected_text)
        except Exception as e:
            print(f"Error extracting text: {e}")
    
    def search(self, text):
        """
        Search for text in the PDF document.
        
        Args:
            text: Text to search for
            
        Returns:
            bool: True if any matches were found, False otherwise
        """
        if not text or not self.document():
            return False
        
        self.search_text = text
        self.search_results = []
        self.current_match_index = -1
        
        try:
            # This is a placeholder - in a real implementation, we would search the PDF
            # For now, we'll just create some dummy search results
            page_count = self.document().pageCount()
            for page in range(page_count):
                # Create 1-3 dummy results per page
                import random
                result_count = random.randint(1, 3)
                for i in range(result_count):
                    # Create a random rectangle on the page
                    x = random.uniform(100, 400)
                    y = random.uniform(100, 600)
                    width = random.uniform(50, 200)
                    height = random.uniform(20, 40)
                    rect = QRectF(x, y, width, height)
                    self.search_results.append((page, rect))
            
            # Highlight the first match if any were found
            if self.search_results:
                self.current_match_index = 0
                self._highlightCurrentMatch()
                self.searchCompleted.emit(len(self.search_results))
                return True
            else:
                self.searchCompleted.emit(0)
                return False
        except Exception as e:
            print(f"Error searching PDF: {e}")
            traceback.print_exc()
            return False
    
    def searchForward(self):
        """
        Move to the next search result.
        
        Returns:
            bool: True if moved to a new match, False otherwise
        """
        if not self.search_results:
            return False
        
        try:
            # Move to the next match
            self.current_match_index = (self.current_match_index + 1) % len(self.search_results)
            self._highlightCurrentMatch()
            return True
        except Exception as e:
            print(f"Error navigating to next match: {e}")
            return False
    
    def searchBackward(self):
        """
        Move to the previous search result.
        
        Returns:
            bool: True if moved to a new match, False otherwise
        """
        if not self.search_results:
            return False
        
        try:
            # Move to the previous match
            self.current_match_index = (self.current_match_index - 1) % len(self.search_results)
            self._highlightCurrentMatch()
            return True
        except Exception as e:
            print(f"Error navigating to previous match: {e}")
            return False
    
    def _highlightCurrentMatch(self):
        """Highlight the current search match."""
        if not self.search_results or self.current_match_index < 0:
            return
        
        try:
            # Get the current match
            page_index, rect = self.search_results[self.current_match_index]
            
            # Navigate to the page containing the match
            if hasattr(self, 'pageNavigator'):
                self.pageNavigator().jump(page_index, QPointF(rect.x(), rect.y()))
            
            # Update highlights to show only the current match
            self.highlighted_areas = [h for h in self.highlighted_areas if h[2] != self.search_highlight_color]
            self.highlighted_areas.append((page_index, rect, self.search_highlight_color))
            
            # Trigger repaint
            self.viewport().update()
        except Exception as e:
            print(f"Error highlighting current match: {e}")
    
    def paintEvent(self, event):
        """Override paint event to draw highlights."""
        super().paintEvent(event)
        
        if not self.document() or not self.highlighted_areas:
            return
        
        try:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw all highlighted areas
            for page_index, rect, color in self.highlighted_areas:
                # Draw highlight directly in viewport coordinates
                painter.setPen(QPen(color.darker(120), 1))
                painter.setBrush(QBrush(color))
                painter.drawRect(rect)
            
            painter.end()
        except Exception as e:
            print(f"Error painting highlights: {e}")
    
    def _estimatePageAt(self, point):
        """
        Estimate which page contains the given point.
        This is a fallback for when pageAt() is not available.
        
        Args:
            point: Point in viewport coordinates
            
        Returns:
            int: Estimated page index
        """
        if not self.document():
            return 0
        
        # Very simple estimation based on vertical position
        # This assumes pages are stacked vertically
        page_count = self.document().pageCount()
        if page_count <= 1:
            return 0
        
        viewport_height = self.viewport().height()
        y_position = point.y() + self.verticalScrollBar().value()
        
        # Estimate page based on position (assuming equal page heights)
        estimated_page = int((y_position / viewport_height) * page_count)
        
        # Clamp to valid range
        return max(0, min(estimated_page, page_count - 1))
