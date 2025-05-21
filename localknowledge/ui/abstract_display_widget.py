#!/usr/bin/env python3
"""
Abstract Display Widget for displaying document abstracts.

This module provides a widget for displaying document abstracts in a
nicely formatted way, including metadata like title, authors, etc.
"""

import logging
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QSizePolicy
)

# Configure logging
logger = logging.getLogger(__name__)


class AbstractDisplayWidget(QWidget):
    """
    Widget for displaying document abstracts.

    This widget displays a document's abstract along with metadata like
    title, authors, publication date, etc. in a nicely formatted way.
    """

    # Signals
    linkClicked = Signal(str)  # URL that was clicked

    def __init__(self, parent=None):
        """
        Initialize the abstract display widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize variables
        self.current_document = None
        self.current_suggestion = None

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Text browser for displaying the abstract
        self.abstract_view = QTextBrowser()
        self.abstract_view.setOpenExternalLinks(True)
        self.abstract_view.setReadOnly(True)
        self.abstract_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Connect signals
        self.abstract_view.anchorClicked.connect(self._on_link_clicked)

        # Add to layout
        layout.addWidget(self.abstract_view)

    def display_document(self, document: Dict[str, Any], suggestion: Optional[Dict[str, Any]] = None):
        """
        Display a document's abstract.

        Args:
            document: Document data dictionary
            suggestion: Optional suggestion data dictionary
        """
        if not document:
            self.clear()
            return

        # Store the current document and suggestion
        self.current_document = document
        self.current_suggestion = suggestion

        # Display the abstract
        self._display_abstract()

    def clear(self):
        """Clear the widget."""
        self.current_document = None
        self.current_suggestion = None
        self.abstract_view.clear()

    def _display_abstract(self):
        """Display the document abstract."""
        if not self.current_document:
            return

        # Get document data
        title = self.current_document.get('title', 'No Title')
        authors = self.current_document.get('authors', [])
        if isinstance(authors, list):
            authors_text = ', '.join(authors) if authors else 'Unknown Authors'
        else:
            authors_text = str(authors)

        publication_date = self.current_document.get('publication_date', '')
        source = self.current_document.get('source_name', '').capitalize()
        doi = self.current_document.get('doi', '')
        abstract = self.current_document.get('abstract', 'No abstract available')

        # Escape HTML special characters in the abstract to prevent issues with < and > characters
        if abstract:
            import html
            abstract = html.escape(abstract)

        keywords = self.current_document.get('keywords', [])
        journal = self.current_document.get('journal', '')
        url = self.current_document.get('url', '')

        # Debug log the abstract length
        logger.info(f"Abstract length for DOI {doi}: {len(abstract) if abstract else 0} characters")

        # Format keywords as a list
        keywords_text = ', '.join(keywords) if keywords else 'None'

        # Prepare recommendation section if available
        recommendation_html = ""
        if hasattr(self, 'current_suggestion') and self.current_suggestion:
            strength = self.current_suggestion.get('recommendation_strength', 0)
            evaluator_name = self.current_suggestion.get('evaluator_name', 'Unknown')
            confidence = self.current_suggestion.get('confidence_level', 0)
            comment = self.current_suggestion.get('comment', '')

            if strength > 0:
                # Use stars to indicate strength
                stars = "★" * min(strength, 5)  # Limit to 5 stars max

                # Set color based on strength
                if strength >= 4:
                    color = "#2ecc71"  # Green for high recommendations
                elif strength >= 2:
                    color = "#3498db"  # Blue for medium recommendations
                else:
                    color = "#95a5a6"  # Gray for low recommendations

                recommendation_html = f"""
                <div style="background-color: #f0f7ff; padding: 10px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid {color};">
                    <h3 style="color: {color}; margin-top: 0;">Recommendation ({stars}) - {strength}/5</h3>
                    <p><strong>By:</strong> {evaluator_name}</p>
                """

                if confidence:
                    recommendation_html += f"<p><strong>Confidence:</strong> {confidence:.2f}</p>"

                if comment:
                    recommendation_html += f"""
                    <p><strong>Comment:</strong></p>
                    <div style="padding-left: 10px; border-left: 2px solid #ddd; margin-left: 5px;">
                        {comment}
                    </div>
                    """

                recommendation_html += "</div>"

        # Format the document as HTML with improved styling
        html_content = f"""
        <div style="padding: 10px; font-family: Arial, sans-serif;">
            <h1 style="color: #2c3e50; margin-bottom: 10px;">{title}</h1>

            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                <p><strong>Authors:</strong> {authors_text}</p>
                <p><strong>Date:</strong> {publication_date}</p>
                <p><strong>Source:</strong> {source}</p>
                <p><strong>Journal:</strong> {journal}</p>
                <p><strong>DOI:</strong> <a href="https://doi.org/{doi}" style="color: #3498db;">{doi}</a></p>
                <p><strong>URL:</strong> <a href="{url}" style="color: #3498db;">{url}</a></p>
                <p><strong>Keywords:</strong> {keywords_text}</p>
            </div>

            {recommendation_html}

            <h2 style="color: #2c3e50; border-bottom: 1px solid #ddd; padding-bottom: 5px;">Abstract</h2>
            <div style="line-height: 1.6; text-align: justify; white-space: pre-wrap;">
                {abstract}
            </div>
        </div>
        """

        # Set the HTML content
        self.abstract_view.setHtml(html_content)

    def _on_link_clicked(self, url):
        """
        Handle link clicks in the abstract.

        Args:
            url: URL that was clicked
        """
        # Emit signal with the URL
        self.linkClicked.emit(url.toString())

        # Let the browser handle the URL (open in external browser)
        return True
