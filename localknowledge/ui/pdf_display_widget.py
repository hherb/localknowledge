#!/usr/bin/env python3
"""
PDF Display Widget for displaying document PDFs.

This module provides a widget for displaying document PDFs with
navigation, search, and zoom capabilities.
"""

import logging
import os
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QPointF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy
)

# Import our custom PDFViewer widget
from localknowledge.ui.pdfviewer import PDFViewer

# Configure logging
logger = logging.getLogger(__name__)


class PDFDisplayWidget(QWidget):
    """
    Widget for displaying document PDFs.

    This widget displays a document's PDF with navigation, search, and zoom controls.
    If no PDF is available, it shows a message with options to fetch or upload a PDF.
    """

    # Signals
    pdfNotFound = Signal(dict)  # Document for which PDF was not found
    pdfFetchRequested = Signal(dict)  # Document for which to fetch PDF
    pdfUploadRequested = Signal(dict)  # Document for which to upload PDF

    def __init__(self, parent=None, status_bar=None, pdf_base_dir=None):
        """
        Initialize the PDF display widget.

        Args:
            parent: Parent widget
            status_bar: Optional status bar for displaying messages
            pdf_base_dir: Base directory for PDF files (default: None)
        """
        super().__init__(parent)

        # Store references
        self.status_bar = status_bar
        self.pdf_base_dir = Path(pdf_base_dir) if pdf_base_dir else None

        # Initialize variables
        self.current_document = None

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # PDF viewer
        self.pdf_viewer = PDFViewer(self, self.status_bar)

        # Search controls
        self.search_container = QWidget()
        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(5, 5, 5, 5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in PDF...")
        self.search_input.returnPressed.connect(self._on_search)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._on_search)

        self.match_label = QLabel("No matches")

        self.prev_match_btn = QPushButton("◀")
        self.prev_match_btn.setToolTip("Previous match")
        self.prev_match_btn.clicked.connect(self._on_prev_match)
        self.prev_match_btn.setEnabled(False)

        self.next_match_btn = QPushButton("▶")
        self.next_match_btn.setToolTip("Next match")
        self.next_match_btn.clicked.connect(self._on_next_match)
        self.next_match_btn.setEnabled(False)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.match_label)
        search_layout.addWidget(self.prev_match_btn)
        search_layout.addWidget(self.next_match_btn)


        # PDF not found message
        self.pdf_not_found_container = QWidget()
        pdf_not_found_layout = QVBoxLayout(self.pdf_not_found_container)
        pdf_not_found_layout.setAlignment(Qt.AlignCenter)

        self.pdf_not_found_label = QLabel("No PDF available for this document.")
        self.pdf_not_found_label.setAlignment(Qt.AlignCenter)
        pdf_not_found_layout.addWidget(self.pdf_not_found_label)

        # Buttons for fetching or uploading PDF
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setAlignment(Qt.AlignCenter)

        self.fetch_pdf_btn = QPushButton("Fetch PDF")
        self.fetch_pdf_btn.setToolTip("Fetch PDF from source")
        self.fetch_pdf_btn.clicked.connect(self._on_fetch_pdf)
        self.fetch_pdf_btn.setEnabled(False)  # Disabled until implemented

        self.upload_pdf_btn = QPushButton("Upload PDF")
        self.upload_pdf_btn.setToolTip("Upload a PDF file")
        self.upload_pdf_btn.clicked.connect(self._on_upload_pdf)
        self.upload_pdf_btn.setEnabled(False)  # Disabled until implemented

        buttons_layout.addWidget(self.fetch_pdf_btn)
        buttons_layout.addWidget(self.upload_pdf_btn)

        pdf_not_found_layout.addWidget(buttons_container)

        # Add widgets to main layout
        layout.addWidget(self.pdf_viewer)
        layout.addWidget(self.search_container)
        layout.addWidget(self.pdf_not_found_container)

        # Initially hide the PDF not found message and search container
        self.pdf_not_found_container.setVisible(False)
        self.search_container.setVisible(False)

        # Connect signals from the PDF viewer
        self.pdf_viewer.searchCompleted.connect(self._on_search_completed)

    def display_document(self, document: Dict[str, Any], suggestion: Optional[Dict[str, Any]] = None):
        """
        Display a document's PDF.

        Args:
            document: Document data dictionary
            suggestion: Optional suggestion data dictionary (not used in this widget)
        """
        if not document:
            self.clear()
            return

        # Store the current document
        self.current_document = document

        # Try to load the PDF
        pdf_found = self._load_pdf()

        # Show/hide widgets based on whether PDF was found
        self.pdf_viewer.setVisible(pdf_found)
        self.search_container.setVisible(pdf_found)
        self.pdf_not_found_container.setVisible(not pdf_found)

        # Reset search controls
        self.search_input.clear()
        self.match_label.setText("No matches")
        self.prev_match_btn.setEnabled(False)
        self.next_match_btn.setEnabled(False)

    def clear(self):
        """Clear the widget."""
        self.current_document = None
        self.pdf_viewer.close_pdf()
        self.pdf_not_found_container.setVisible(False)
        self.search_container.setVisible(False)

        # Reset search controls
        self.search_input.clear()
        self.match_label.setText("No matches")
        self.prev_match_btn.setEnabled(False)
        self.next_match_btn.setEnabled(False)

    def _load_pdf(self) -> bool:
        """
        Load the PDF for the current document.

        Returns:
            bool: True if PDF was loaded successfully, False otherwise
        """
        if not self.current_document:
            return False

        # Get the local PDF path from the pdf_filename field
        local_pdf_path = self.current_document.get('pdf_filename', '')

        # Try different methods to find and load the PDF
        pdf_found = False

        # Method 1: Try to load from pdf_filename field with pdf_base_dir
        if local_pdf_path and self.pdf_base_dir:
            full_path = self.pdf_base_dir / local_pdf_path
            if full_path.exists():
                if self.pdf_viewer.load_pdf(str(full_path)):
                    pdf_found = True
                    if self.status_bar:
                        self.status_bar.showMessage(f"Loaded PDF: {full_path}")

        # Method 2: Try to load from pdf_filename field as absolute path
        if not pdf_found and local_pdf_path:
            if os.path.exists(local_pdf_path):
                if self.pdf_viewer.load_pdf(local_pdf_path):
                    pdf_found = True
                    if self.status_bar:
                        self.status_bar.showMessage(f"Loaded PDF: {local_pdf_path}")

        # Method 3: Try to load from pdf_url field
        if not pdf_found and 'pdf_url' in self.current_document:
            pdf_url = self.current_document.get('pdf_url')
            if pdf_url:
                # This would require downloading the PDF first
                # For now, just show a message
                if self.status_bar:
                    self.status_bar.showMessage(f"PDF URL available but download not implemented: {pdf_url}")

        # If PDF not found, emit signal
        if not pdf_found:
            self.pdfNotFound.emit(self.current_document)
            if self.status_bar:
                self.status_bar.showMessage("PDF not found for this document")

        return pdf_found

    def _on_search(self):
        """Handle search button click."""
        search_text = self.search_input.text().strip()
        if not search_text:
            return

        # Perform search using the PDF viewer
        self.pdf_viewer.search_text(search_text)

    def _on_search_completed(self, match_count: int):
        """
        Handle search completion.

        Args:
            match_count: Number of matches found
        """
        if match_count > 0:
            self.match_label.setText(f"Match 1 of {match_count}")
            self.prev_match_btn.setEnabled(True)
            self.next_match_btn.setEnabled(True)
        else:
            self.match_label.setText("No matches")
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)

    def _on_prev_match(self):
        """Navigate to the previous search match."""
        self.pdf_viewer.go_to_prev_match()

        # Update match label
        current_match = self.pdf_viewer.current_match_index + 1
        total_matches = len(self.pdf_viewer.search_results)
        if total_matches > 0:
            self.match_label.setText(f"Match {current_match} of {total_matches}")

    def _on_next_match(self):
        """Navigate to the next search match."""
        self.pdf_viewer.go_to_next_match()

        # Update match label
        current_match = self.pdf_viewer.current_match_index + 1
        total_matches = len(self.pdf_viewer.search_results)
        if total_matches > 0:
            self.match_label.setText(f"Match {current_match} of {total_matches}")

    def _on_fetch_pdf(self):
        """Handle fetch PDF button click."""
        if not self.current_document:
            return

        # Emit signal to request PDF fetching
        self.pdfFetchRequested.emit(self.current_document)

        # Show message in status bar
        if self.status_bar:
            self.status_bar.showMessage("PDF fetch requested (not yet implemented)")

    def _on_upload_pdf(self):
        """Handle upload PDF button click."""
        if not self.current_document:
            return

        # Emit signal to request PDF upload
        self.pdfUploadRequested.emit(self.current_document)

        # Show message in status bar
        if self.status_bar:
            self.status_bar.showMessage("PDF upload requested (not yet implemented)")

    def set_pdf_base_dir(self, pdf_base_dir: str):
        """
        Set the base directory for PDF files.

        Args:
            pdf_base_dir: Base directory for PDF files
        """
        self.pdf_base_dir = Path(pdf_base_dir) if pdf_base_dir else None
