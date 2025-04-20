"""
PDF Viewer widget with search and highlighting capabilities.

This module provides a reusable PDF viewer widget with search functionality
and highlighting of search results.
"""

import os
from pathlib import Path
import sys
import traceback
import tempfile
import shutil

from PySide6.QtCore import Qt, Signal, Slot, QPointF, QSize, QObject, QEvent, QRect, QRectF
from PySide6.QtGui import QIcon, QAction, QKeySequence, QPainter, QColor, QPen, QBrush, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QApplication,
    QScrollArea, QSizePolicy, QMenu
)
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
import fitz  # PyMuPDF for PDF search and highlighting

# Import our custom PDF view implementation
from localknowledge.ui.custompdfview import CustomPdfView

# Print PySide6 version for debugging
import PySide6
print(f"PySide6 version: {PySide6.__version__}")


class PDFViewer(QWidget):
    """
    A reusable PDF viewer widget with search and highlighting capabilities.
    """

    # Signals
    pageChanged = Signal(int, int)  # current_page, total_pages
    searchCompleted = Signal(int)   # number of matches found

    def __init__(self, parent=None, status_bar=None):
        """
        Initialize the PDF viewer widget.

        Args:
            parent: Parent widget
            status_bar: Optional status bar for displaying messages
        """
        super().__init__(parent)

        # Store reference to status bar if provided
        self.status_bar = status_bar

        # Initialize PDF document and search variables
        self.pdf_document = QPdfDocument()
        self.current_pdf_path = None
        self.original_pdf_path = None  # Original PDF path before highlighting
        self.fitz_document = None  # PyMuPDF document object
        self.search_results = []   # Will store search result rectangles
        self.current_match_index = -1
        self.current_search_text = ""

        # Temporary file for highlighted PDF
        self.temp_dir = tempfile.mkdtemp(prefix="pdfviewer_")
        self.temp_pdf_path = None

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create PDF view
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)

        # Enable scrolling in the PDF view
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Show multiple pages for continuous scrolling
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)  # Fit to width by default

        # Set up text selection variables
        self.selection_start = None
        self.selection_end = None
        self.current_selection_page = -1
        self.selected_text = ""

        # Install event filter to handle mouse events for text selection
        self.pdf_view.viewport().installEventFilter(self)
        self.pdf_view.viewport().setMouseTracking(True)

        # Enable copy action with Ctrl+C
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self._copy_selected_text)
        self.addAction(self.copy_action)
        self.copy_action.setEnabled(False)

        # Create a scroll area to contain the PDF view for better scrolling
        self.pdf_scroll_area = QScrollArea()
        self.pdf_scroll_area.setWidget(self.pdf_view)
        self.pdf_scroll_area.setWidgetResizable(True)  # Allow the view to resize with the scroll area
        self.pdf_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pdf_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create toolbar with navigation and search controls
        toolbar = QHBoxLayout()

        # Page navigation
        self.prev_page_btn = QPushButton("←")
        self.prev_page_btn.setToolTip("Previous page")
        self.prev_page_btn.clicked.connect(self._go_to_prev_page)
        self.prev_page_btn.setFixedWidth(30)

        self.page_label = QLabel("Page 1 of 1")

        self.next_page_btn = QPushButton("→")
        self.next_page_btn.setToolTip("Next page")
        self.next_page_btn.clicked.connect(self._go_to_next_page)
        self.next_page_btn.setFixedWidth(30)

        # Search controls
        self.pdf_search_input = QLineEdit()
        self.pdf_search_input.setPlaceholderText("Search in PDF...")
        self.pdf_search_input.returnPressed.connect(self._search_pdf)
        self.pdf_search_input.setFixedWidth(200)

        self.prev_match_btn = QPushButton("↑")
        self.prev_match_btn.setToolTip("Previous match")
        self.prev_match_btn.clicked.connect(self._find_prev_match)
        self.prev_match_btn.setEnabled(False)
        self.prev_match_btn.setFixedWidth(30)

        self.next_match_btn = QPushButton("↓")
        self.next_match_btn.setToolTip("Next match")
        self.next_match_btn.clicked.connect(self._find_next_match)
        self.next_match_btn.setEnabled(False)
        self.next_match_btn.setFixedWidth(30)

        # Zoom controls
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom out")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        self.zoom_out_btn.setFixedWidth(30)

        self.fit_width_btn = QPushButton("Fit")
        self.fit_width_btn.setToolTip("Fit to width")
        self.fit_width_btn.clicked.connect(self._fit_width)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom in")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        self.zoom_in_btn.setFixedWidth(30)

        # Add controls to toolbar
        toolbar.addWidget(self.prev_page_btn)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_page_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.pdf_search_input)
        toolbar.addWidget(self.prev_match_btn)
        toolbar.addWidget(self.next_match_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.fit_width_btn)
        toolbar.addWidget(self.zoom_in_btn)

        # Add toolbar and PDF view to the main layout
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self.pdf_scroll_area)

        # Setup keyboard navigation for the PDF view
        self.pdf_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pdf_view.installEventFilter(self)

        # Connect signals
        self.pdf_view.pageNavigator().currentPageChanged.connect(self._update_pdf_navigation)

    def load_pdf(self, pdf_path):
        """
        Load a PDF file into the viewer.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            bool: True if the PDF was loaded successfully, False otherwise
        """
        if not pdf_path or not os.path.exists(pdf_path):
            print(f"PDF path does not exist: {pdf_path}")
            return False

        try:
            # Convert to string if it's a Path object
            if isinstance(pdf_path, Path):
                pdf_path = str(pdf_path)

            # Load the PDF into the Qt PDF document
            self.pdf_document.load(pdf_path)

            # Set view modes
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

            # Update navigation controls
            self._update_pdf_navigation()

            # Store the current PDF path
            self.current_pdf_path = pdf_path
            self.original_pdf_path = pdf_path

            # Initialize PyMuPDF document for searching
            try:
                # Close previous document if it exists
                if self.fitz_document:
                    self.fitz_document.close()

                # Open with PyMuPDF for searching
                self.fitz_document = fitz.open(pdf_path)

                # If there was a previous search, re-run it
                self._highlight_search_keywords()

            except Exception as e:
                print(f"Error opening PDF with PyMuPDF: {e}")
                traceback.print_exc()
                self.fitz_document = None

            return True

        except Exception as e:
            print(f"Error loading PDF: {e}")
            traceback.print_exc()
            return False

    def close_pdf(self):
        """Close the current PDF document and clean up resources."""
        # Close Qt PDF document
        self.pdf_document.close()

        # Close PyMuPDF document if it exists
        if self.fitz_document:
            self.fitz_document.close()
            self.fitz_document = None

        # Clear search results
        self.search_results = []
        self.current_match_index = -1
        self.current_search_text = ""
        self.current_pdf_path = None
        self.original_pdf_path = None

        # Clean up temporary files
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
                self.temp_pdf_path = None
            except Exception as e:
                print(f"Error removing temporary PDF: {e}")

        # Update UI
        self._update_pdf_navigation()

    def _update_pdf_navigation(self):
        """Update PDF navigation controls based on current document state."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            total_pages = self.pdf_document.pageCount()
            current_page = self.pdf_view.pageNavigator().currentPage() + 1  # +1 because it's zero-based

            # Update the page label
            self.page_label.setText(f"Page {current_page} of {total_pages}")

            # Enable/disable navigation buttons
            self.prev_page_btn.setEnabled(current_page > 1)
            self.next_page_btn.setEnabled(current_page < total_pages)

            # Emit signal with current page information
            self.pageChanged.emit(current_page, total_pages)
        else:
            # Reset when no document is loaded
            self.page_label.setText("Page 1 of 1")
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)

    def _go_to_prev_page(self):
        """Navigate to the previous page in the PDF."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            navigator = self.pdf_view.pageNavigator()
            current_page = navigator.currentPage()
            if current_page > 0:  # It's zero-based
                navigator.jump(current_page - 1, QPointF())
                self._update_pdf_navigation()

    def _go_to_next_page(self):
        """Navigate to the next page in the PDF."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            navigator = self.pdf_view.pageNavigator()
            current_page = navigator.currentPage()
            if current_page < self.pdf_document.pageCount() - 1:  # It's zero-based
                navigator.jump(current_page + 1, QPointF())
                self._update_pdf_navigation()

    def _zoom_in(self):
        """Zoom in on the PDF."""
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() * 1.25)

    def _zoom_out(self):
        """Zoom out of the PDF."""
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() / 1.25)

    def _fit_width(self):
        """Fit the PDF to the width of the view."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _search_pdf(self):
        """Search for text in the current PDF document."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            self._show_message("No PDF document is loaded.")
            return

        # Get search text
        search_text = self.pdf_search_input.text().strip()
        if not search_text:
            # Clear any existing highlights
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)
            self.search_results = []
            self._clear_highlights()
            return

        try:
            # Store the search text
            self.current_search_text = search_text
            print(f"Searching for: {search_text}")

            # Print available search methods for debugging
            print("\nChecking search methods:")
            if hasattr(self.pdf_view, 'search'):
                print("  - pdf_view.search() is available")
            if hasattr(self.pdf_view, 'searchForward'):
                print("  - pdf_view.searchForward() is available")
            if hasattr(self.pdf_view, 'searchBackward'):
                print("  - pdf_view.searchBackward() is available")

            # Try direct search method first
            search_success = False

            # Approach 1: Try the search method if available
            if hasattr(self.pdf_view, 'search'):
                try:
                    print("Attempting to use pdf_view.search()")
                    # Try with different parameter combinations
                    try:
                        # Try with just the search text
                        found = self.pdf_view.search(search_text)
                        search_success = found
                    except Exception as e1:
                        print(f"  - Basic search failed: {e1}")
                        try:
                            # Try with search flags parameter
                            found = self.pdf_view.search(search_text, 0)
                            search_success = found
                        except Exception as e2:
                            print(f"  - Search with flags failed: {e2}")
                except Exception as e:
                    print(f"Error using pdf_view.search(): {e}")

            # Approach 2: Use PyMuPDF for search and highlighting
            if not search_success and self.fitz_document:
                print("Falling back to PyMuPDF search")
                # Reset search results
                self.search_results = []
                self.current_match_index = -1

                # Search in all pages using PyMuPDF
                for page_num in range(self.fitz_document.page_count):
                    page = self.fitz_document[page_num]
                    # Search for text on this page
                    matches = page.search_for(search_text, quads=True)

                    # Store results with page number
                    for match in matches:
                        self.search_results.append((page_num, match))

                # Update match count
                search_match_count = len(self.search_results)

                if search_match_count > 0:
                    search_success = True
                    # Enable navigation buttons
                    self.prev_match_btn.setEnabled(True)
                    self.next_match_btn.setEnabled(True)

                    # Go to the first match
                    self._find_next_match()

                    # Show status message in the status bar or placeholder text
                    self._show_message(f"Found {search_match_count} matches")

                    # Emit signal with search results
                    self.searchCompleted.emit(search_match_count)

            # Handle case where no matches were found
            if not search_success:
                self.prev_match_btn.setEnabled(False)
                self.next_match_btn.setEnabled(False)
                self._show_message("No matches found")
                self.searchCompleted.emit(0)

        except Exception as e:
            print(f"Error searching PDF: {e}")
            traceback.print_exc()
            self._show_message(f"Error searching PDF: {str(e)}")

    def _find_next_match(self):
        """Find and highlight the next match in the PDF."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        print("Finding next match...")

        # Try to use native search if available
        if hasattr(self.pdf_view, 'searchForward') and self.current_search_text:
            try:
                print("Using native searchForward()")
                # Use the native search functionality to find the next match
                found = self.pdf_view.searchForward()
                if found:
                    self._show_message(f"Found next match for '{self.current_search_text}'")
                else:
                    # If we reach the end, try searching from the beginning
                    print("Reached end, searching from beginning")
                    # Clear current search and start a new one
                    if hasattr(self.pdf_view, 'search'):
                        found = self.pdf_view.search(self.current_search_text)
                        if found:
                            self._show_message(f"Found match for '{self.current_search_text}' (wrapped)")
                        else:
                            self._show_message(f"No more matches for '{self.current_search_text}'")
                    else:
                        self._show_message(f"No more matches for '{self.current_search_text}'")
                return
            except Exception as e:
                print(f"Error using searchForward: {e}")
                # Continue to fallback

        # Fallback to PyMuPDF search
        if not self.search_results:
            print("No search results available for PyMuPDF fallback")
            return

        print(f"Using PyMuPDF fallback with {len(self.search_results)} results")
        # Move to the next match
        self.current_match_index = (self.current_match_index + 1) % len(self.search_results)
        self._go_to_current_match()

    def _find_prev_match(self):
        """Find and highlight the previous match in the PDF."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        print("Finding previous match...")

        # Try to use native search if available
        if hasattr(self.pdf_view, 'searchBackward') and self.current_search_text:
            try:
                print("Using native searchBackward()")
                # Use the native search functionality to find the previous match
                found = self.pdf_view.searchBackward()
                if found:
                    self._show_message(f"Found previous match for '{self.current_search_text}'")
                else:
                    # If we reach the beginning, try searching from the end
                    print("Reached beginning, searching from end")
                    # This is tricky with the native API, we might need to search forward until we wrap around
                    self._show_message(f"No more matches for '{self.current_search_text}'")
                return
            except Exception as e:
                print(f"Error using searchBackward: {e}")
                # Continue to fallback

        # Fallback to PyMuPDF search
        if not self.search_results:
            print("No search results available for PyMuPDF fallback")
            return

        print(f"Using PyMuPDF fallback with {len(self.search_results)} results")
        # Move to the previous match
        self.current_match_index = (self.current_match_index - 1) % len(self.search_results)
        self._go_to_current_match()

    def _go_to_current_match(self):
        """Navigate to and highlight the current match."""
        if not self.search_results or self.current_match_index < 0 or not self.original_pdf_path:
            return

        # Get the current match
        page_num, match = self.search_results[self.current_match_index]

        # Create a temporary highlighted PDF
        try:
            # Remember current page and zoom
            current_page = self.pdf_view.pageNavigator().currentPage()
            current_zoom = self.pdf_view.zoomFactor()
            zoom_mode = self.pdf_view.zoomMode()

            # Create a unique temporary file for the highlighted PDF
            # Use a timestamp to ensure uniqueness
            import time
            timestamp = int(time.time() * 1000)
            temp_pdf_path = os.path.join(self.temp_dir, f"highlighted_{timestamp}_{os.path.basename(self.original_pdf_path)}")

            # If we already have a temporary PDF, close the current document
            if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
                try:
                    # Close the current document first
                    self.pdf_document.close()
                except Exception as e:
                    print(f"Error closing current document: {e}")

            # We'll create a new PDF with highlights rather than modifying a copy
            self.temp_pdf_path = temp_pdf_path

            # Open the original PDF with PyMuPDF for highlighting
            doc = fitz.open(self.original_pdf_path)

            # Add highlight to the current match
            page = doc[page_num]

            # Try to create a more visible highlight
            try:
                # First attempt: Create a yellow text marker style highlight
                highlight = page.add_highlight_annot(match)
                highlight.set_colors({"stroke": (1, 1, 0)})  # Bright yellow
                highlight.set_opacity(0.7)  # More opaque
                highlight.update()

                # Add a red rectangle around the text for extra visibility
                rect = match.rect  # Get the rectangle of the match
                rect_annot = page.add_rect_annot(rect)
                rect_annot.set_colors({"stroke": (1, 0, 0)})  # Red border
                rect_annot.set_border(width=2)  # Thicker border
                rect_annot.update()
            except Exception as e:
                print(f"Error with advanced highlighting, falling back to basic: {e}")
                # Fallback: Simple red rectangle
                try:
                    rect = match.rect
                    rect_annot = page.add_rect_annot(rect)
                    rect_annot.set_colors({"stroke": (1, 0, 0)})  # Red border
                    rect_annot.set_border(width=2)  # Thicker border
                    rect_annot.update()
                except Exception as e2:
                    print(f"Error with fallback highlighting: {e2}")

            # Save the highlighted PDF
            # We need to save to a new file, not overwrite the original
            doc.save(temp_pdf_path, garbage=3, deflate=True, clean=True)
            doc.close()

            # Load the highlighted PDF into the viewer
            self.pdf_document.load(temp_pdf_path)

            # Navigate to the page containing the match
            navigator = self.pdf_view.pageNavigator()
            navigator.jump(page_num, QPointF())

            # Restore zoom settings
            # Check if we're using a custom zoom factor
            if zoom_mode != QPdfView.ZoomMode.FitToWidth and zoom_mode != QPdfView.ZoomMode.FitInView:
                # This is a custom zoom, so set the zoom factor directly
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
                self.pdf_view.setZoomFactor(current_zoom)
            else:
                # This is a predefined zoom mode
                self.pdf_view.setZoomMode(zoom_mode)

            # Update navigation controls
            self._update_pdf_navigation()

            # Show current match position in status bar
            self._show_message(f"Match {self.current_match_index + 1} of {len(self.search_results)}")

        except Exception as e:
            print(f"Error highlighting match: {e}")
            traceback.print_exc()

            # If highlighting fails, just navigate to the page
            navigator = self.pdf_view.pageNavigator()
            navigator.jump(page_num, QPointF())
            self._update_pdf_navigation()

    def _clear_highlights(self):
        """Clear all highlights."""
        print("Clearing highlights...")

        # Try multiple approaches to clear highlights
        search_cleared = False

        # Approach 1: Use native search clearing if available
        if hasattr(self.pdf_view, 'search'):
            try:
                print("Using pdf_view.search('') to clear highlights")
                # Clear search by passing empty string
                self.pdf_view.search('')
                search_cleared = True
            except Exception as e:
                print(f"Error clearing search with pdf_view.search(''): {e}")

        # Approach 2: Try other methods if available
        if not search_cleared and hasattr(self.pdf_view, 'clearSearch'):
            try:
                print("Using pdf_view.clearSearch()")
                self.pdf_view.clearSearch()
                search_cleared = True
            except Exception as e:
                print(f"Error clearing search with clearSearch(): {e}")

        # Approach 3: Fallback to reloading the original PDF if using PyMuPDF highlighting
        if not search_cleared and self.original_pdf_path and os.path.exists(self.original_pdf_path):
            print("Falling back to reloading original PDF")
            try:
                # Remember current page and zoom
                current_page = self.pdf_view.pageNavigator().currentPage()
                current_zoom = self.pdf_view.zoomFactor()
                zoom_mode = self.pdf_view.zoomMode()

                # Load the original PDF without highlights
                self.pdf_document.load(self.original_pdf_path)

                # Navigate back to the same page
                navigator = self.pdf_view.pageNavigator()
                navigator.jump(current_page, QPointF())

                # Restore zoom settings
                # Check if we're using a custom zoom factor
                if zoom_mode != QPdfView.ZoomMode.FitToWidth and zoom_mode != QPdfView.ZoomMode.FitInView:
                    # This is a custom zoom, so set the zoom factor directly
                    self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
                    self.pdf_view.setZoomFactor(current_zoom)
                else:
                    # This is a predefined zoom mode
                    self.pdf_view.setZoomMode(zoom_mode)

                # Clean up temporary file if it exists
                if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
                    try:
                        os.remove(self.temp_pdf_path)
                        self.temp_pdf_path = None
                    except Exception as e:
                        print(f"Error removing temporary PDF: {e}")

                search_cleared = True

            except Exception as e:
                print(f"Error clearing highlights by reloading PDF: {e}")
                traceback.print_exc()

        if not search_cleared:
            print("Warning: Could not clear highlights using any method")

    def _highlight_search_keywords(self):
        """Highlight search keywords in the PDF if there's an active search."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        # Update navigation controls
        self._update_pdf_navigation()

        # If we have an active search, re-run it
        if self.current_search_text and self.current_search_text.strip():
            # Store the current text in a temporary variable
            temp_text = self.current_search_text

            # Set the search input text
            self.pdf_search_input.setText(temp_text)

            # Reset current match index if using PyMuPDF
            if not hasattr(self.pdf_view, 'search'):
                self.current_match_index = -1

            # Run the search again
            self._search_pdf()

    def _show_message(self, message):
        """Show a message in the status bar or as placeholder text."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage(message)
        else:
            # If no status bar, show next to search box
            self.pdf_search_input.setPlaceholderText(message)

    def eventFilter(self, watched, event):
        """
        Filter events for the PDF view to handle keyboard navigation and text selection.

        Args:
            watched: The object being watched
            event: The event that occurred

        Returns:
            True if the event was handled, False otherwise
        """
        # Handle text selection in the PDF view viewport
        if watched == self.pdf_view.viewport():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                # Start selection
                self.selection_start = event.position()
                self.selection_end = event.position()

                # Get current page
                try:
                    # Try to get the current page from the page navigator
                    if hasattr(self.pdf_view, 'pageNavigator'):
                        self.current_selection_page = self.pdf_view.pageNavigator().currentPage()
                    else:
                        # Fallback: estimate page based on scroll position
                        self.current_selection_page = self._estimate_current_page()
                except Exception as e:
                    print(f"Error determining page: {e}")
                    self.current_selection_page = 0

                # Clear previous selection
                self.selected_text = ""
                self.copy_action.setEnabled(False)
                self.pdf_view.viewport().update()
                return True

            elif event.type() == QEvent.MouseMove and self.selection_start is not None:
                # Update selection
                self.selection_end = event.position()
                self.pdf_view.viewport().update()  # Trigger repaint to show selection
                return True

            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.selection_start is not None:
                # Finalize selection
                self.selection_end = event.position()
                self._extract_selected_text()
                self.pdf_view.viewport().update()  # Trigger repaint to show selection
                return True

            elif event.type() == QEvent.ContextMenu and self.selected_text:
                # Show context menu for text selection
                menu = QMenu(self)
                copy_action = menu.addAction("Copy")
                copy_action.triggered.connect(self._copy_selected_text)
                menu.exec(event.globalPos())
                return True

            elif event.type() == QEvent.Paint:
                # Let the default paint event happen first
                result = super().eventFilter(watched, event)

                # Then paint our selection on top if needed
                if self.selection_start is not None and self.selection_end is not None:
                    painter = QPainter(watched)
                    painter.setRenderHint(QPainter.Antialiasing)

                    # Draw selection rectangle
                    selection_rect = QRectF(
                        self.selection_start.x(),
                        self.selection_start.y(),
                        self.selection_end.x() - self.selection_start.x(),
                        self.selection_end.y() - self.selection_start.y()
                    ).normalized()

                    # Use a semi-transparent blue for selection
                    selection_color = QColor(173, 216, 230, 100)  # Light blue with alpha
                    painter.setPen(QPen(selection_color.darker(120), 1))
                    painter.setBrush(QBrush(selection_color))
                    painter.drawRect(selection_rect)
                    painter.end()

                return result

        # Check if the PDF view has focus and a PDF is loaded
        if (watched == self.pdf_view and
            event.type() == QEvent.KeyPress and
            self.pdf_document.status() == QPdfDocument.Status.Ready):

            key = event.key()

            # Handle left/right arrow keys for navigation
            if key == Qt.Key.Key_Left or key == Qt.Key.Key_Up:
                self._go_to_prev_page()
                return True

            elif key == Qt.Key.Key_Right or key == Qt.Key.Key_Down:
                self._go_to_next_page()
                return True

            # Handle Page Up/Down keys
            elif key == Qt.Key.Key_PageUp:
                self._go_to_prev_page()
                return True

            elif key == Qt.Key.Key_PageDown:
                self._go_to_next_page()
                return True

            # Handle Home/End keys
            elif key == Qt.Key.Key_Home:
                # Go to first page
                self.pdf_view.pageNavigator().jump(0, QPointF())
                self._update_pdf_navigation()
                return True

            elif key == Qt.Key.Key_End:
                # Go to last page
                last_page = self.pdf_document.pageCount() - 1
                self.pdf_view.pageNavigator().jump(last_page, QPointF())
                self._update_pdf_navigation()
                return True

            # Handle Ctrl+C for copy
            elif key == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier and self.selected_text:
                self._copy_selected_text()
                return True

        # Let the parent class handle the event
        return super().eventFilter(watched, event)

    def _estimate_current_page(self):
        """Estimate the current page based on scroll position."""
        if not self.pdf_document or self.pdf_document.status() != QPdfDocument.Status.Ready:
            return 0

        # Get scroll position
        scroll_pos = self.pdf_view.verticalScrollBar().value()
        max_scroll = self.pdf_view.verticalScrollBar().maximum()

        # Estimate page based on scroll position
        page_count = self.pdf_document.pageCount()
        if page_count <= 1 or max_scroll == 0:
            return 0

        # Simple linear mapping from scroll position to page number
        estimated_page = int((scroll_pos / max_scroll) * (page_count - 1))
        return max(0, min(estimated_page, page_count - 1))

    def _extract_selected_text(self):
        """Extract text from the current selection using PyMuPDF."""
        if not self.fitz_document or self.current_selection_page < 0 or self.selection_start is None or self.selection_end is None:
            return

        try:
            # Get the page
            page = self.fitz_document[self.current_selection_page]

            # Convert selection coordinates to PDF coordinates
            # This is a simplified conversion - in a real implementation, you would need to
            # convert from screen coordinates to PDF coordinates more accurately
            pdf_width = page.rect.width
            pdf_height = page.rect.height

            view_width = self.pdf_view.viewport().width()
            view_height = self.pdf_view.viewport().height()

            # Calculate scale factors
            scale_x = pdf_width / view_width
            scale_y = pdf_height / view_height

            # Convert selection to PDF coordinates
            x0 = min(self.selection_start.x(), self.selection_end.x()) * scale_x
            y0 = min(self.selection_start.y(), self.selection_end.y()) * scale_y
            x1 = max(self.selection_start.x(), self.selection_end.x()) * scale_x
            y1 = max(self.selection_start.y(), self.selection_end.y()) * scale_y

            # Create a rectangle for text selection
            rect = fitz.Rect(x0, y0, x1, y1)

            # Extract text from the rectangle
            self.selected_text = page.get_text("text", clip=rect)

            # Enable copy action if text was selected
            self.copy_action.setEnabled(bool(self.selected_text))

            # Show selected text in status bar if available
            if hasattr(self, 'status_bar') and self.status_bar:
                truncated_text = self.selected_text[:50] + "..." if len(self.selected_text) > 50 else self.selected_text
                self.status_bar.showMessage(f"Selected: {truncated_text}")

        except Exception as e:
            print(f"Error extracting text: {e}")
            traceback.print_exc()
            self.selected_text = ""
            self.copy_action.setEnabled(False)

    def _copy_selected_text(self):
        """Copy selected text to clipboard."""
        if self.selected_text:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.selected_text)

            # Show confirmation in status bar if available
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.showMessage("Text copied to clipboard", 3000)


    def __del__(self):
        """Clean up resources when the widget is destroyed."""
        # Close any open PDF - but safely check if attributes exist first
        try:
            # Only call close_pdf if we have the necessary attributes
            if hasattr(self, 'pdf_document') and hasattr(self, 'pdf_view'):
                # Check if we have the page_label attribute before calling close_pdf
                if hasattr(self, 'page_label'):
                    self.close_pdf()
                else:
                    # Just close the document without updating navigation
                    if hasattr(self, 'fitz_document') and self.fitz_document:
                        self.fitz_document.close()
                    self.pdf_document.close()
        except Exception as e:
            print(f"Error closing PDF in __del__: {e}")

        # Remove temporary directory and all files in it
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                # First try to remove any files that might be in use
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except Exception:
                        pass  # Ignore errors for individual files

                # Then remove the directory
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up temporary directory: {e}")


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create the PDF viewer widget
    pdf_viewer = PDFViewer()
    pdf_viewer.resize(800, 600)
    pdf_viewer.show()

    # Load a PDF if provided as command line argument
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        pdf_viewer.load_pdf(sys.argv[1])

    sys.exit(app.exec())
