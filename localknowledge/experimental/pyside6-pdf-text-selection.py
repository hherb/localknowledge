import sys
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QColorDialog, QHBoxLayout
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

class PdfHighlight:
    """Class to store highlight information with page context"""
    def __init__(self, page_index, rect_on_page, color):
        self.page_index = page_index  # The page number (zero-based)
        self.rect_on_page = rect_on_page  # Rect coordinates relative to page
        self.color = color  # Highlight color with alpha

class CustomPdfView(QPdfView):
    """
    CustomPdfView extends QPdfView to add text highlighting functionality.
    This implementation tracks highlights relative to pages, not viewport.
    """
    
    # Signal for when text is selected
    textSelected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        
        # Selection variables
        self.selection_start = QPointF()
        self.selection_end = QPointF()
        self.is_selecting = False
        self.current_selection = None  # Stores the current selection rectangle in viewport coordinates
        
        # Highlighting variables
        self.highlights = []  # List of PdfHighlight objects
        self.highlight_color = QColor(255, 255, 0, 100)  # Yellow with some transparency
        
        # Page tracking
        self.current_page = 0
        
        # Connect scroll signals to update highlights
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for starting selection"""
        if event.button() == Qt.LeftButton:
            # Start selection
            self.is_selecting = True
            self.selection_start = event.position()
            self.current_page = self.pageNavigator().currentPage()
            
            # Clear current selection
            self.current_selection = None
            self.viewport().update()
            
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for updating selection"""
        if self.is_selecting:
            self.selection_end = event.position()
            
            # Create a selection rectangle in viewport coordinates
            self.current_selection = QRectF(
                self.selection_start,
                self.selection_end
            ).normalized()
            
            # Update view
            self.viewport().update()
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for finalizing selection"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.selection_end = event.position()
            
            # Finalize the selection rectangle
            if self.selection_start != self.selection_end:
                self.current_selection = QRectF(
                    self.selection_start,
                    self.selection_end
                ).normalized()
                
                # For real text extraction, you would need to use OCR or a PDF library
                # that can extract text from a specific region
                self.textSelected.emit("")
            
            # Update view
            self.viewport().update()
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def viewportToPageCoordinates(self, viewport_rect, page_index):
        """
        Convert viewport coordinates to page coordinates.
        This is a simplified approach - in a real application, you'd need more
        sophisticated mapping based on the PDF rendering and scaling.
        """
        # Get page items and check if the specified page is visible
        page_items = self.findChildren(QWidget)
        page_item = None
        
        # Find the page widget for the specified page
        for item in page_items:
            # This is a simple approach to find page widgets
            # In a real app, you might need to use specific page item identification
            if hasattr(item, 'pageNumber') and item.pageNumber() == page_index:
                page_item = item
                break
        
        if not page_item:
            # If we can't find the page widget, make a rough estimate
            # This is very simplified and won't be accurate for many PDFs
            scroll_pos = self.verticalScrollBar().value()
            page_height = self.viewport().height()  # Estimate page height
            
            # Estimate page position based on index and current scroll
            page_top = (page_index * page_height) - scroll_pos
            
            # Create page coordinates rect relative to estimated page position
            page_rect = QRectF(
                viewport_rect.x(),
                viewport_rect.y() - page_top,
                viewport_rect.width(),
                viewport_rect.height()
            )
            
            return page_rect
        
        # If we found the page widget, use its geometry to make the conversion
        page_pos = page_item.mapFrom(self.viewport(), viewport_rect.topLeft().toPoint())
        page_rect = QRectF(
            page_pos.x(),
            page_pos.y(),
            viewport_rect.width(),
            viewport_rect.height()
        )
        
        return page_rect
    
    def pageToViewportCoordinates(self, page_rect, page_index):
        """
        Convert page coordinates to viewport coordinates.
        This is the inverse of viewportToPageCoordinates.
        """
        # Get page items and check if the specified page is visible
        page_items = self.findChildren(QWidget)
        page_item = None
        
        # Find the page widget for the specified page
        for item in page_items:
            if hasattr(item, 'pageNumber') and item.pageNumber() == page_index:
                page_item = item
                break
        
        if not page_item:
            # If we can't find the page widget, make a rough estimate
            scroll_pos = self.verticalScrollBar().value()
            page_height = self.viewport().height()  # Estimate page height
            
            # Estimate page position based on index and current scroll
            page_top = (page_index * page_height) - scroll_pos
            
            # Create viewport coordinates rect relative to estimated page position
            viewport_rect = QRectF(
                page_rect.x(),
                page_rect.y() + page_top,
                page_rect.width(),
                page_rect.height()
            )
            
            return viewport_rect
        
        # If we found the page widget, use its geometry to make the conversion
        viewport_pos = page_item.mapTo(self.viewport(), page_rect.topLeft().toPoint())
        viewport_rect = QRectF(
            viewport_pos.x(),
            viewport_pos.y(),
            page_rect.width(),
            page_rect.height()
        )
        
        return viewport_rect
    
    def highlightSelection(self):
        """Highlight the current selection rectangle"""
        if self.current_selection and not self.current_selection.isEmpty():
            # Convert viewport selection to page coordinates
            page_rect = self.viewportToPageCoordinates(
                self.current_selection,
                self.current_page
            )
            
            # Create a new highlight object with page coordinates
            highlight = PdfHighlight(
                self.current_page,
                page_rect,
                self.highlight_color
            )
            
            # Add to highlights list
            self.highlights.append(highlight)
            
            # Update view
            self.viewport().update()
    
    def clearHighlights(self):
        """Clear all highlighted areas"""
        self.highlights.clear()
        self.viewport().update()
    
    def setHighlightColor(self, color):
        """Set the color used for highlighting"""
        self.highlight_color = color
    
    def paintEvent(self, event):
        """Override paint event to draw selections and highlights"""
        # First do normal painting
        super().paintEvent(event)
        
        # Then draw our custom selections and highlights
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw current selection with semi-transparent blue
        if self.current_selection and not self.current_selection.isEmpty():
            selection_color = QColor(0, 120, 215, 50)  # Light blue with transparency
            painter.setPen(QPen(selection_color.darker(120), 1))
            painter.setBrush(QBrush(selection_color))
            painter.drawRect(self.current_selection)
        
        # Draw all highlights
        visible_pages = set()
        current_page = self.pageNavigator().currentPage()
        
        # In a simple approach, assume current and adjacent pages are visible
        visible_pages.add(current_page)
        visible_pages.add(current_page - 1)
        visible_pages.add(current_page + 1)
        
        for highlight in self.highlights:
            if highlight.page_index in visible_pages:
                # Convert page coordinates to viewport coordinates
                viewport_rect = self.pageToViewportCoordinates(
                    highlight.rect_on_page,
                    highlight.page_index
                )
                
                # Only draw if in visible area
                if viewport_rect.intersects(self.viewport().rect()):
                    painter.setPen(QPen(highlight.color.darker(120), 1))
                    painter.setBrush(QBrush(highlight.color))
                    painter.drawRect(viewport_rect)
        
        painter.end()
    
    def keyPressEvent(self, event):
        """Handle key press events for selection operations"""
        # Handle Ctrl+C to copy selected text (in a real app)
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            # In a real app, you would copy the selected text to clipboard
            print("Copy operation requested (not implemented)")
            event.accept()
        else:
            super().keyPressEvent(event)


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Viewer with Text Selection")
        self.resize(800, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create PDF view
        self.pdf_view = CustomPdfView()
        layout.addWidget(self.pdf_view)
        
        # Create document
        self.pdf_document = QPdfDocument()
        self.pdf_view.setDocument(self.pdf_document)
        
        # Connect signals
        self.pdf_view.textSelected.connect(self.onTextSelected)
        
        # Create buttons layout
        button_layout = QHBoxLayout()
        
        # Highlight button
        highlight_button = QPushButton("Highlight Selection")
        highlight_button.clicked.connect(self.pdf_view.highlightSelection)
        button_layout.addWidget(highlight_button)
        
        # Choose color button
        color_button = QPushButton("Choose Highlight Color")
        color_button.clicked.connect(self.chooseHighlightColor)
        button_layout.addWidget(color_button)
        
        # Clear highlights button
        clear_button = QPushButton("Clear Highlights")
        clear_button.clicked.connect(self.pdf_view.clearHighlights)
        button_layout.addWidget(clear_button)
        
        layout.addLayout(button_layout)
    
    def chooseHighlightColor(self):
        """Open color dialog to choose highlight color"""
        color = QColorDialog.getColor(self.pdf_view.highlight_color, self, "Choose Highlight Color")
        if color.isValid():
            # Add transparency
            color.setAlpha(100)
            self.pdf_view.setHighlightColor(color)
    
    def onTextSelected(self, text):
        """Handle selected text - could be used to extract or process the text"""
        # In a real app, you might want to do something with the selected text
        print("Selected text region (actual text extraction not implemented)")
    
    def loadFile(self, file_path):
        """Load PDF file"""
        self.pdf_document.load(file_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    
    # Load a PDF file if provided as argument
    if len(sys.argv) > 1:
        viewer.loadFile(sys.argv[1])
    
    viewer.show()
    sys.exit(app.exec())