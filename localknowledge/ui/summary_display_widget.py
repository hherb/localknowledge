#!/usr/bin/env python3
"""
Summary Display Widget for displaying document summaries.

This module provides a widget for displaying document summaries with
an option to generate summaries on-demand when not available.
"""

import logging
from typing import Dict, Any, Optional, Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QPushButton,
    QLabel, QSizePolicy, QProgressBar, QHBoxLayout
)

# Configure logging
logger = logging.getLogger(__name__)


class SummaryDisplayWidget(QWidget):
    """
    Widget for displaying document summaries.
    
    This widget displays a document's summary if available, or provides
    a button to generate a summary on-demand when not available.
    """
    
    # Signals
    summaryRequested = Signal(dict)  # Document for which a summary is requested
    
    def __init__(self, parent=None):
        """
        Initialize the summary display widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Initialize variables
        self.current_document = None
        self.summary_generator = None  # Function to generate summaries
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Text browser for displaying the summary
        self.summary_view = QTextBrowser()
        self.summary_view.setOpenExternalLinks(True)
        self.summary_view.setReadOnly(True)
        self.summary_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Generate summary button (initially hidden)
        self.generate_button_container = QWidget()
        generate_layout = QVBoxLayout(self.generate_button_container)
        generate_layout.setAlignment(Qt.AlignCenter)
        
        self.generate_label = QLabel("No summary available for this document.")
        self.generate_label.setAlignment(Qt.AlignCenter)
        generate_layout.addWidget(self.generate_label)
        
        self.generate_button = QPushButton("Generate Summary")
        self.generate_button.setToolTip("Generate a summary for this document")
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.generate_button.setEnabled(False)  # Disabled until implemented
        generate_layout.addWidget(self.generate_button, alignment=Qt.AlignCenter)
        
        # Progress bar for summary generation (initially hidden)
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_container)
        
        self.progress_label = QLabel("Generating summary...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        progress_layout.addWidget(self.progress_bar)
        
        # Add widgets to main layout
        layout.addWidget(self.summary_view)
        layout.addWidget(self.generate_button_container)
        layout.addWidget(self.progress_container)
        
        # Initially hide the summary view
        self.summary_view.setVisible(False)
    
    def set_summary_generator(self, generator: Callable[[Dict[str, Any]], str]):
        """
        Set the function to use for generating summaries.
        
        Args:
            generator: Function that takes a document and returns a summary
        """
        self.summary_generator = generator
        
        # Enable the generate button if we have a generator
        self.generate_button.setEnabled(self.summary_generator is not None)
    
    def display_document(self, document: Dict[str, Any]):
        """
        Display a document's summary.
        
        Args:
            document: Document data dictionary
        """
        if not document:
            self.clear()
            return
        
        # Store the current document
        self.current_document = document
        
        # Display the summary if available, or show the generate button
        if 'summary' in document and document['summary']:
            self._display_summary(document['summary'])
        else:
            self._show_generate_button()
    
    def clear(self):
        """Clear the widget."""
        self.current_document = None
        self.summary_view.clear()
        self.summary_view.setVisible(False)
        self.generate_button_container.setVisible(False)
        self.progress_container.setVisible(False)
    
    def _display_summary(self, summary: str):
        """
        Display a summary.
        
        Args:
            summary: Summary text
        """
        # Format the summary as HTML with improved styling
        html_content = f"""
        <div style="padding: 10px; font-family: Arial, sans-serif;">
            <h2 style="color: #2c3e50; border-bottom: 1px solid #ddd; padding-bottom: 5px;">Summary</h2>
            <div style="line-height: 1.6; text-align: justify;">
                {summary}
            </div>
        </div>
        """
        
        # Set the HTML content
        self.summary_view.setHtml(html_content)
        
        # Show the summary view and hide other widgets
        self.summary_view.setVisible(True)
        self.generate_button_container.setVisible(False)
        self.progress_container.setVisible(False)
    
    def _show_generate_button(self):
        """Show the generate summary button."""
        # Hide the summary view and progress container
        self.summary_view.setVisible(False)
        self.progress_container.setVisible(False)
        
        # Show the generate button container
        self.generate_button_container.setVisible(True)
    
    def _show_progress(self):
        """Show the progress indicator."""
        # Hide the summary view and generate button
        self.summary_view.setVisible(False)
        self.generate_button_container.setVisible(False)
        
        # Show the progress container
        self.progress_container.setVisible(True)
    
    def _on_generate_clicked(self):
        """Handle generate button click."""
        if not self.current_document:
            return
        
        # Show progress indicator
        self._show_progress()
        
        # Emit signal to request summary generation
        self.summaryRequested.emit(self.current_document)
        
        # If we have a generator function, use it directly
        # (This would be replaced with a proper async implementation)
        if self.summary_generator:
            try:
                summary = self.summary_generator(self.current_document)
                self._display_summary(summary)
            except Exception as e:
                logger.error(f"Error generating summary: {e}")
                self._show_generate_button()
    
    @Slot(str)
    def set_summary(self, summary: str):
        """
        Set the summary text (called when summary generation is complete).
        
        Args:
            summary: Generated summary text
        """
        if summary:
            self._display_summary(summary)
        else:
            self._show_generate_button()
