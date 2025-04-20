"""
This module provides a PySide6 widget for browsing and searching
the local publications database and viewing both PDF and markdown text.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import traceback

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QSize, QPointF, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QLabel, QMessageBox, QApplication,
    QScrollArea
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
# Import PdfMultiPageView for better PDF viewing
try:
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    QML_AVAILABLE = True
except ImportError:
    QML_AVAILABLE = False

import pymupdf4llm
import fitz  # PyMuPDF for PDF search and highlighting

# Import optional dependencies
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# Try to import remove_line_numbers
try:
    from localknowledge.medrxiv.remove_line_numbers import remove_sequential_line_numbers
    LINE_NUMBERS_REMOVAL_AVAILABLE = True
except ImportError:
    LINE_NUMBERS_REMOVAL_AVAILABLE = False
    # Define a fallback function if import fails
    def remove_sequential_line_numbers(text):
        return text  # Just return the original text

from localknowledge.db.medrxiv import MedRxivDatabaseManager


class PublicationItem(QListWidgetItem):
    """List widget item to display publication details and store publication data."""

    def __init__(self, publication: Dict[str, Any]):
        """
        Initialize a publication list item.

        Args:
            publication: Dictionary containing publication data
        """
        self.publication = publication

        # Create display text with HTML formatting
        title = publication.get('title', 'No Title')
        authors = publication.get('authors', 'Unknown Authors')
        date = publication.get('date_posted', '')

        # Truncate the title if it's too long
        if len(title) > 80:
            title = title[:77] + "..."

        # Format with HTML for bold titles
        display_text = f"<b>{title}</b>\n{authors[:100]}{'...' if len(authors) > 100 else ''}\n{date}"

        # Initialize the item with display text
        super().__init__(display_text)

        # Make the item slightly taller for better readability
        self.setSizeHint(QSize(self.sizeHint().width(), self.sizeHint().height() + 10))

        # Set tooltip to show full title and authors on hover
        self.setToolTip(f"{publication.get('title', 'No Title')}\n{publication.get('authors', 'Unknown Authors')}")


class KnowledgeBrowser(QWidget):
    """A PySide6 widget for browsing and searching publication knowledge."""

    # Signal emitted when a publication is selected
    publicationSelected = Signal(dict)

    def __init__(self, parent=None):
        """
        Initialize the knowledge browser widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.db_manager = MedRxivDatabaseManager()
        self.current_publication = None
        self.pdf_base_dir = self._get_pdf_base_dir()

        # Initialize PDF search
        self.pdf_search = None
        self.current_search_text = ""
        self.search_match_count = 0
        self.current_match_index = -1

        # For PyMuPDF search
        self.current_pdf_path = None
        self.search_results = []  # Will store search result rectangles
        self.fitz_document = None  # PyMuPDF document object

        # Initialize thread pool for background tasks
        self.threadpool = QThreadPool()
        print(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Search area at top
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter research question or keywords (comma separated or use quotes)")
        self.search_input.returnPressed.connect(self._on_search)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Splitter for results and document view
        self.splitter = QSplitter(Qt.Horizontal)

        # Left side - publication list
        self.publication_list = QListWidget()
        self.publication_list.currentItemChanged.connect(self._on_publication_selected)
        self.publication_list.setAlternatingRowColors(True)
        self.publication_list.setStyleSheet("""
            QListWidget {
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px 0;
            }
            QListWidget::item:alternate {
                background-color: #f0f5ff;
            }
        """)

        # Right side - tabbed view
        self.tab_widget = QTabWidget()

        # PDF tab
        self.pdf_view = QPdfView()
        self.pdf_document = QPdfDocument()
        self.pdf_view.setDocument(self.pdf_document)

        # Enable scrolling in the PDF view
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Show multiple pages for continuous scrolling
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)  # Fit to width by default

        # Create a scroll area to contain the PDF view for better scrolling
        pdf_scroll_area = QScrollArea()
        pdf_scroll_area.setWidget(self.pdf_view)
        pdf_scroll_area.setWidgetResizable(True)  # Allow the view to resize with the scroll area
        pdf_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pdf_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create a container widget for the PDF view with navigation controls
        pdf_container = QWidget()
        pdf_layout = QVBoxLayout(pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)

        # Add PDF navigation controls
        pdf_toolbar = QHBoxLayout()

        self.prev_page_btn = QPushButton("← Previous")
        self.prev_page_btn.clicked.connect(self._go_to_prev_page)
        self.prev_page_btn.setEnabled(False)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_page_btn = QPushButton("Next →")
        self.next_page_btn.clicked.connect(self._go_to_next_page)
        self.next_page_btn.setEnabled(False)

        # Add PDF search controls
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

        # Add zoom controls
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self._zoom_in)

        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self._zoom_out)

        self.fit_width_btn = QPushButton("Fit Width")
        self.fit_width_btn.clicked.connect(self._fit_width)

        # Add controls to toolbar
        pdf_toolbar.addWidget(self.prev_page_btn)
        pdf_toolbar.addWidget(self.page_label)
        pdf_toolbar.addWidget(self.next_page_btn)
        pdf_toolbar.addStretch()
        pdf_toolbar.addWidget(self.pdf_search_input)
        pdf_toolbar.addWidget(self.prev_match_btn)
        pdf_toolbar.addWidget(self.next_match_btn)
        pdf_toolbar.addStretch()
        pdf_toolbar.addWidget(self.zoom_out_btn)
        pdf_toolbar.addWidget(self.fit_width_btn)
        pdf_toolbar.addWidget(self.zoom_in_btn)

        # Add toolbar and PDF view to the layout
        pdf_layout.addLayout(pdf_toolbar)
        pdf_layout.addWidget(pdf_scroll_area)  # Use the scroll area instead of the PDF view directly

        # Setup keyboard navigation for the PDF view
        self.pdf_view.setFocusPolicy(Qt.StrongFocus)
        self.pdf_view.installEventFilter(self)

        # Add the container to the tab
        self.tab_widget.addTab(pdf_container, "PDF")

        # Markdown tab
        self.markdown_view = QWebEngineView()
        self.tab_widget.addTab(self.markdown_view, "Extracted Text")

        # Add widgets to splitter
        self.splitter.addWidget(self.publication_list)
        self.splitter.addWidget(self.tab_widget)

        # Set initial sizes (40% for list, 60% for document)
        self.splitter.setSizes([400, 600])

        # Add layouts to main layout
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.splitter, 1)  # 1 means this will expand to fill available space

        # Set window properties
        self.setWindowTitle("Knowledge Browser")
        self.resize(1200, 800)

    def _get_pdf_base_dir(self) -> Path:
        """
        Get the base directory for PDF files, ensuring proper path expansion.

        Returns:
        - Fully expanded path to the PDF storage directory
        """
        # Get PDF directory from environment variable or use default
        pdf_base_dir = os.environ.get('PDF_BASE_DIR')

        if not pdf_base_dir:
            home_dir = os.path.expanduser("~")
            pdf_base_dir = os.path.join(home_dir, "knowledgebase", "pdf")  # Changed from "pdfs" to "pdf"
        else:
            # Expand the tilde if it exists in the path
            pdf_base_dir = os.path.expanduser(pdf_base_dir)

        # Print debug info about the PDF directory
        pdf_path = Path(pdf_base_dir)
        if not pdf_path.exists():
            print(f"Directory {pdf_path} does not exist")

        return pdf_path  # Return Path object instead of string

    @Slot()
    def _on_search(self):
        """Handle search button click or Enter key in search input."""
        search_text = self.search_input.text().strip()
        if not search_text:
            return

        try:
            # Process search terms to build the query
            # If the search text is in quotes, search for the exact phrase
            # Otherwise, split by commas and search for each term
            search_terms = []

            # Extract quoted terms first
            quoted_terms = []
            remaining_text = search_text

            quote_start = remaining_text.find('"')
            while quote_start != -1:
                quote_end = remaining_text.find('"', quote_start + 1)
                if quote_end != -1:
                    quoted_term = remaining_text[quote_start + 1:quote_end].strip()
                    if quoted_term:
                        quoted_terms.append(quoted_term)
                    remaining_text = remaining_text[:quote_start] + " " + remaining_text[quote_end + 1:]
                else:
                    # Unmatched quote, break
                    break
                quote_start = remaining_text.find('"')

            # Add quoted terms
            search_terms.extend(quoted_terms)

            # Process remaining comma-separated terms
            comma_terms = [term.strip() for term in remaining_text.split(",") if term.strip()]
            search_terms.extend(comma_terms)

            # Remove duplicates and empty terms
            search_terms = [term for term in search_terms if term]

            if not search_terms:
                QMessageBox.warning(self, "Search Error", "Please enter valid search terms.")
                return

            # Convert the search terms into an appropriate query based on the database
            # This assumes your database supports a full-text search with & operator for AND
            query = " & ".join(search_terms)

            # Show a message that we're searching
            self.publication_list.clear()
            self.publication_list.addItem("Searching...")
            QApplication.processEvents()

            # Perform the search
            publications = self.db_manager.search_preprints(query, fields=['abstract'])

            self.publication_list.clear()

            if not publications:
                self.publication_list.addItem("No results found.")
                return

            # Add search results to the list
            for pub in publications:
                item = PublicationItem(pub)
                self.publication_list.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"An error occurred during search: {str(e)}")

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_publication_selected(self, current, previous):
        """
        Handle publication selection in the list.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current or not isinstance(current, PublicationItem):
            return

        # Get the publication data
        self.current_publication = current.publication

        # Emit the signal with the selected publication
        self.publicationSelected.emit(self.current_publication)

        # Load the PDF if available
        self._load_publication_content()

    def _load_publication_content(self):
        """Load the selected publication's PDF and markdown content into the tabs."""
        if not self.current_publication:
            return

        # Get the local PDF path
        local_pdf_path = self.current_publication.get('local_pdf_path', '')

        # Try to load PDF
        pdf_found = False

        # First case: We have a local_pdf_path in the database
        if local_pdf_path:
            # Convert to string and ensure proper path handling
            if isinstance(self.pdf_base_dir, Path):
                full_pdf_path = self.pdf_base_dir / local_pdf_path
            else:
                # If pdf_base_dir is a string, create a path object
                full_pdf_path = Path(os.path.join(self.pdf_base_dir, local_pdf_path))


            if full_pdf_path.exists():
                # Load the PDF
                pdf_path = str(full_pdf_path)
                self.pdf_document.load(pdf_path)
                self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Ensure MultiPage mode is set
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
                # Update navigation controls
                self._update_pdf_navigation()

                # Store the current PDF path and initialize PyMuPDF document
                self.current_pdf_path = pdf_path
                try:
                    # Close previous document if it exists
                    if self.fitz_document:
                        self.fitz_document.close()
                    # Open with PyMuPDF for searching
                    self.fitz_document = fitz.open(pdf_path)
                except Exception as e:
                    print(f"Error opening PDF with PyMuPDF: {e}")
                    self.fitz_document = None

                # Apply keyword highlighting from search terms
                self._highlight_search_keywords()
                # Explicitly set the tab to PDF view
                self.tab_widget.setCurrentIndex(0)
                pdf_found = True

        # Second case: No path in database, but we have DOI - try to find by filename pattern
        if not pdf_found and 'doi' in self.current_publication:
            doi = self.current_publication['doi']
            print(f"Trying to find PDF by DOI: {doi}")

            # Format variations to try
            potential_filenames = [
                f"{doi.replace('/', '_')}.pdf",  # 10.1101_2021.04.27.21252790.pdf
                f"{doi.replace('/', '-')}.pdf",  # 10.1101-2021.04.27.21252790.pdf
                f"{doi}.pdf"                     # 10.1101/2021.04.27.21252790.pdf (unlikely)
            ]

            for filename in potential_filenames:
                possible_path = self.pdf_base_dir / filename
                print(f"Trying: {possible_path}")

                if possible_path.exists():
                    print(f"Found PDF at: {possible_path}")
                    pdf_path = str(possible_path)
                    self.pdf_document.load(pdf_path)
                    self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Ensure MultiPage mode is set
                    self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
                    # Update navigation controls
                    self._update_pdf_navigation()
                    self.tab_widget.setCurrentIndex(0)  # Show PDF tab

                    # Store the current PDF path and initialize PyMuPDF document
                    self.current_pdf_path = pdf_path
                    try:
                        # Close previous document if it exists
                        if self.fitz_document:
                            self.fitz_document.close()
                        # Open with PyMuPDF for searching
                        self.fitz_document = fitz.open(pdf_path)
                    except Exception as e:
                        print(f"Error opening PDF with PyMuPDF: {e}")
                        self.fitz_document = None

                    # Update the database with the correct path
                    try:
                        self.db_manager.update_pdf_path(
                            doi,
                            filename,
                            self.current_publication.get('full_text', '')
                        )
                        print(f"Updated database with path: {filename}")
                    except Exception as e:
                        print(f"Failed to update database: {e}")

                    pdf_found = True

                    # Apply keyword highlighting from search terms
                    self._highlight_search_keywords()
                    break

        # If we still couldn't find the PDF, show the not found message
        if not pdf_found:
            print("PDF not found by any method")
            self._show_pdf_not_found()

        # Check for existing markdown text
        full_text = self.current_publication.get('full_text', '')

        if full_text:
            # Display existing markdown text
            self._display_markdown(full_text)
        else:
            # Try to extract text if we have a PDF
            if local_pdf_path and Path(self.pdf_base_dir / local_pdf_path).exists():
                try:
                    self._extract_and_display_markdown(str(self.pdf_base_dir / local_pdf_path))
                except Exception as e:
                    self._display_markdown(f"Error extracting text from PDF: {str(e)}")
            else:
                self._display_markdown("No text available for this publication.")

    def _show_pdf_not_found(self):
        """Show a placeholder when PDF is not available."""
        # Clear the PDF view
        self.pdf_document.close()

        # Close PyMuPDF document if it exists
        if self.fitz_document:
            self.fitz_document.close()
            self.fitz_document = None

        # Clear search results
        self.search_results = []
        self.current_match_index = -1

        # Create a message in the markdown view about the missing PDF
        self._display_markdown("# PDF Not Available\n\nThe PDF for this publication is not available locally.")

        # Switch to markdown tab
        self.tab_widget.setCurrentIndex(1)

    def _display_markdown(self, markdown_text: str):
        """
        Display markdown text in the markdown view.

        Args:
            markdown_text: Markdown text to display
        """
        # Convert markdown to HTML
        if MARKDOWN_AVAILABLE:
            html_content = markdown.markdown(markdown_text)
        else:
            # If markdown module is not available, just wrap in pre tags
            html_content = f"<pre>{markdown_text}</pre>"

        # Add some styling
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    line-height: 1.6;
                    color: #333;
                    background-color: #fff;
                }}
                h1, h2, h3 {{ color: #205493; }}
                pre {{
                    background-color: #f5f5f5;
                    padding: 10px;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                }}
                th {{
                    background-color: #f2f2f2;
                    text-align: left;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        self.markdown_view.setHtml(html)

    def _extract_and_display_markdown(self, pdf_path: str):
        """
        Extract markdown text from a PDF in the background and display it.

        Args:
            pdf_path: Path to the PDF file
        """
        # Display a loading message with animated indicator while extraction happens
        loading_message = """
        # Converting PDF to Text...

        <div style="text-align: center; margin: 30px 0;">
            <div style="font-size: 20px; color: #666;">
                Extracting and processing text from PDF.
                <br><br>
                <img src="data:image/gif;base64,R0lGODlhIAAgAPUAAP///wAAAPr6+sTExOjo6PDw8NDQ0H5+fpqamvb29ubm5vz8/JKSkoaGhuLi4ri4uKCgoOzs7K6urtzc3NLS0vT09M7OzsfHx+Dg4Orq6uXl5fLy8tdXV8zMzLi4uLq6uvX19e3t7c/Pz+7u7vj4+Pv7+9HR0djY2MXFxbOzs/Pz89fX17GxsfT09ODg4OXl5ePj4+np6dra2sDAwMTExNbW1sLCwr+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/vywAAAAAIAAgAEAI/wAHCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqTJkyhTqlzJsqXLlzBjypy50YCAAQUC6NzJM4CAnjpFCh1KtClGAQEEECBAQEABp1CjSp1KtarVq1izat3KVeuCAgEGDFjA4IABAwTCih0btoCAAwYWOI0oIK3du3jz6t3LF++AAwUEGOgbIK1IAYADCx5MuLDhw4gPGzggQC+BAwMWNCBQALLlywYGEMCcubPnz6BDix5NurTp06hTq17NurXr17Bjy55Nu7bt20IDCBAwPKCBAQECDAQQsCA38+YBCkyfTt164gHYt2vv3l1A9wLgwZP/Tl5A+QDo06svL6B9AO/gw4sfT768+fPo06tfz769+/fw48ufT7++/fv48+vfz7+///8ABijggAQWaOCBCCao4IIMNujggxBGKOGEFFZo4YUYZqjhhhx26OGHIIYo4ogklmjiQ0EAADs=" alt="Loading..." />
                <br><br>
                This may take a moment depending on the PDF size and complexity.
            </div>
        </div>
        """
        self._display_markdown(loading_message)

        # Switch to the markdown tab to show loading indicator
        self.tab_widget.setCurrentIndex(1)

        # Get the DOI and local path for updating the database later
        doi = self.current_publication.get('doi', None) if self.current_publication else None
        local_pdf_path = self.current_publication.get('local_pdf_path', '') if self.current_publication else ''

        # Create a worker for the extraction
        worker = PDFExtractionWorker(pdf_path, doi, local_pdf_path)

        # Connect signals
        worker.signals.result.connect(self._handle_extraction_result)
        worker.signals.error.connect(self._handle_extraction_error)

        # Execute the worker
        self.threadpool.start(worker)

    def _handle_extraction_result(self, result):
        """
        Handle the result of PDF text extraction.

        Args:
            result: Dictionary containing extraction results and metadata
        """
        markdown_text = result.get("markdown_text", "")
        doi = result.get("doi")
        local_pdf_path = result.get("local_pdf_path")

        # Save the markdown to the database if we have a DOI
        if doi:
            try:
                self.db_manager.update_pdf_path(
                    doi,
                    local_pdf_path,
                    markdown_text
                )
            except Exception as e:
                print(f"Failed to update database with extracted text: {e}")

        # Display the markdown
        self._display_markdown(markdown_text)

    def _handle_extraction_error(self, error_msg, traceback_str):
        """
        Handle errors from the PDF extraction worker.

        Args:
            error_msg: Error message
            traceback_str: Traceback as string
        """
        error_text = f"# Error Extracting Text\n\n```\n{error_msg}\n\n{traceback_str}\n```"
        self._display_markdown(error_text)

    def close_database(self):
        """Close the database connection."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

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
        """Search for text in the current PDF document using PyMuPDF."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready or not self.fitz_document:
            QMessageBox.warning(self, "Search Error", "No PDF document is loaded.")
            return

        # Get search text
        search_text = self.pdf_search_input.text().strip()
        if not search_text:
            # Clear any existing highlights if search is empty
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)
            self.search_results = []
            return

        try:
            # Store the search text
            self.current_search_text = search_text

            # Reset search results
            self.search_results = []
            self.current_match_index = -1

            # Search in all pages
            for page_num in range(self.fitz_document.page_count):
                page = self.fitz_document[page_num]
                # Search for text on this page
                matches = page.search_for(search_text, quads=True)

                # Store results with page number
                for match in matches:
                    self.search_results.append((page_num, match))

            # Update match count
            self.search_match_count = len(self.search_results)

            if self.search_match_count > 0:
                # Enable navigation buttons
                self.prev_match_btn.setEnabled(True)
                self.next_match_btn.setEnabled(True)

                # Go to the first match
                self._find_next_match()

                # Show status message in the status bar
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage(f"Found {self.search_match_count} matches")
                else:
                    # If no status bar, show next to search box
                    self.pdf_search_input.setPlaceholderText(f"Found {self.search_match_count} matches")
            else:
                self.prev_match_btn.setEnabled(False)
                self.next_match_btn.setEnabled(False)
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage("No matches found")
                else:
                    self.pdf_search_input.setPlaceholderText("No matches found")

        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error searching PDF: {str(e)}")

    def _search_finished(self):
        """Handle PDF search completion."""
        # Update match count
        self.search_match_count = self.pdf_search.matchCount()

        if self.search_match_count == 0:
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)
            QMessageBox.information(self, "Search Results", "No matches found.")

    def _find_next_match(self):
        """Find and highlight the next match in the PDF."""
        if not self.search_results or self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        # Move to the next match
        self.current_match_index = (self.current_match_index + 1) % len(self.search_results)
        self._go_to_current_match()

    def _find_prev_match(self):
        """Find and highlight the previous match in the PDF."""
        if not self.search_results or self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        # Move to the previous match
        self.current_match_index = (self.current_match_index - 1) % len(self.search_results)
        self._go_to_current_match()

    def _go_to_current_match(self):
        """Navigate to and highlight the current match."""
        if not self.search_results or self.current_match_index < 0:
            return

        # Get the current match
        page_num, match = self.search_results[self.current_match_index]

        # Navigate to the page containing the match
        navigator = self.pdf_view.pageNavigator()
        navigator.jump(page_num, QPointF())

        # Update navigation controls
        self._update_pdf_navigation()

        # Create a temporary highlight annotation in PyMuPDF
        try:
            # Clear any previous highlights
            self._clear_highlights()

            # Add highlight to the current match
            page = self.fitz_document[page_num]

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

            # Force a refresh of the PDF view
            # This is a workaround since we can't directly access the PySide6 PDF renderer
            # We'll reload the current page to show the highlight
            current_zoom = self.pdf_view.zoomFactor()
            self.pdf_view.setZoomFactor(current_zoom * 1.01)  # Slightly change zoom to force refresh
            QApplication.processEvents()
            self.pdf_view.setZoomFactor(current_zoom)  # Restore original zoom

        except Exception as e:
            print(f"Error highlighting match: {e}")

    def _clear_highlights(self):
        """Clear all highlight and rectangle annotations from the PDF."""
        if not self.fitz_document:
            return

        try:
            for page_num in range(self.fitz_document.page_count):
                page = self.fitz_document[page_num]
                for annot in page.annots():
                    # Type 8 is highlight annotation, type 4 is rectangle annotation
                    if annot.type[0] in [8, 4]:  # Clear both highlight and rectangle annotations
                        page.delete_annot(annot)
        except Exception as e:
            print(f"Error clearing highlights: {e}")

    def _highlight_search_keywords(self):
        """
        Highlight search keywords in the PDF if there's an active search.
        """
        if self.pdf_document.status() != QPdfDocument.Status.Ready or not self.fitz_document:
            return

        # Update navigation controls
        self._update_pdf_navigation()

        # If we have an active search, re-run it
        if self.current_search_text and self.current_search_text.strip():
            # Store the current text in a temporary variable
            temp_text = self.current_search_text

            # Clear the search input and results
            self.pdf_search_input.setText(temp_text)
            self.search_results = []
            self.current_match_index = -1

            # Run the search again
            self._search_pdf()

    def eventFilter(self, watched, event):
        """
        Filter events to handle keyboard navigation in the PDF view.

        Args:
            watched: The object that triggered the event
            event: The event

        Returns:
            True if the event was handled, False otherwise
        """
        # Check if the PDF view has focus and a PDF is loaded
        if (watched == self.pdf_view and
            event.type() == event.Type.KeyPress and
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

        # Let the parent class handle the event
        return super().eventFilter(watched, event)


class WorkerSignals(QObject):
    """
    Defines signals available from a running worker thread.
    """
    finished = Signal()
    error = Signal(str, str)  # (error message, traceback)
    result = Signal(object)


class PDFExtractionWorker(QRunnable):
    """
    Worker thread for extracting text from PDF files.
    """

    def __init__(self, pdf_path, doi=None, local_pdf_path=None):
        """
        Initialize the worker.

        Args:
            pdf_path: Path to the PDF file to extract text from
            doi: DOI of the publication (for database update)
            local_pdf_path: Local path of the PDF (for database update)
        """
        super().__init__()
        self.pdf_path = pdf_path
        self.doi = doi
        self.local_pdf_path = local_pdf_path
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Extract text from the PDF file.
        """
        try:
            # Extract markdown from PDF
            markdown_text = pymupdf4llm.to_markdown(self.pdf_path)

            # Clean line numbers if needed
            if LINE_NUMBERS_REMOVAL_AVAILABLE:
                markdown_text = remove_sequential_line_numbers(markdown_text)

            # Emit the result
            self.signals.result.emit({
                "markdown_text": markdown_text,
                "doi": self.doi,
                "local_pdf_path": self.local_pdf_path
            })

        except Exception as e:
            # Get the traceback
            import traceback
            trace = traceback.format_exc()

            # Emit the error
            self.signals.error.emit(str(e), trace)

        finally:
            # Always emit finished signal
            self.signals.finished.emit()


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = KnowledgeBrowser()
    browser.show()
    sys.exit(app.exec())
