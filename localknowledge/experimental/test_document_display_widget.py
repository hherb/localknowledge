#!/usr/bin/env python3
"""
Test script for the DocumentDisplayWidget.

This script demonstrates the usage of the DocumentDisplayWidget by creating
a simple application that displays a sample document.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QPushButton, QStatusBar, QSplitter, QHBoxLayout
)
from PySide6.QtCore import Qt

# Import our custom widgets
from localknowledge.ui.document_display_widget import DocumentDisplayWidget
from localknowledge.context import set_current_user, set_current_project


class MockDBManager:
    """Mock database manager for testing."""

    def __init__(self):
        """Initialize the mock database manager."""
        self.bookmarks = {}
        self.ratings = {}

    def is_bookmarked(self, source_name, external_id, user_id, project_id=None):
        """
        Check if a document is bookmarked.

        Args:
            source_name: Source name
            external_id: External ID
            user_id: User ID
            project_id: Project ID (optional)

        Returns:
            bool: True if bookmarked, False otherwise
        """
        key = (source_name, external_id, user_id, project_id)
        return key in self.bookmarks

    def add_bookmark(self, source_name, external_id, user_id, project_id=None):
        """
        Add a bookmark.

        Args:
            source_name: Source name
            external_id: External ID
            user_id: User ID
            project_id: Project ID (optional)
        """
        key = (source_name, external_id, user_id, project_id)
        self.bookmarks[key] = True
        print(f"Added bookmark: {key}")

    def remove_bookmark(self, source_name, external_id, user_id, project_id=None):
        """
        Remove a bookmark.

        Args:
            source_name: Source name
            external_id: External ID
            user_id: User ID
            project_id: Project ID (optional)
        """
        key = (source_name, external_id, user_id, project_id)
        if key in self.bookmarks:
            del self.bookmarks[key]
            print(f"Removed bookmark: {key}")

    def get_user_rating(self, source_name, external_id, user_id):
        """
        Get a user's rating for a document.

        Args:
            source_name: Source name
            external_id: External ID
            user_id: User ID

        Returns:
            int: Rating value or None if not rated
        """
        key = (source_name, external_id, user_id)
        return self.ratings.get(key)

    def set_user_rating(self, source_name, external_id, user_id, rating):
        """
        Set a user's rating for a document.

        Args:
            source_name: Source name
            external_id: External ID
            user_id: User ID
            rating: Rating value
        """
        key = (source_name, external_id, user_id)
        self.ratings[key] = rating
        print(f"Set rating: {key} = {rating}")


class TestWindow(QMainWindow):
    """Test window for the DocumentDisplayWidget."""

    def __init__(self):
        """Initialize the test window."""
        super().__init__()

        # Set up window
        self.setWindowTitle("Document Display Widget Test")
        self.setGeometry(100, 100, 800, 600)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Create mock database manager
        self.db_manager = MockDBManager()

        # Create a temporary directory for test PDFs
        self.temp_dir = tempfile.mkdtemp(prefix="test_pdf_")

        # Set up central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Control buttons
        control_layout = QHBoxLayout()

        # Button to set user
        self.set_user_btn = QPushButton("Set User")
        self.set_user_btn.clicked.connect(self.set_user)
        control_layout.addWidget(self.set_user_btn)

        # Button to set project
        self.set_project_btn = QPushButton("Set Project")
        self.set_project_btn.clicked.connect(self.set_project)
        control_layout.addWidget(self.set_project_btn)

        # Button to clear project
        self.clear_project_btn = QPushButton("Clear Project")
        self.clear_project_btn.clicked.connect(self.clear_project)
        control_layout.addWidget(self.clear_project_btn)

        # Button to load document
        self.load_doc_btn = QPushButton("Load Document")
        self.load_doc_btn.clicked.connect(self.load_document)
        control_layout.addWidget(self.load_doc_btn)

        # Button to load document with summary
        self.load_with_summary_btn = QPushButton("Load With Summary")
        self.load_with_summary_btn.clicked.connect(self.load_document_with_summary)
        control_layout.addWidget(self.load_with_summary_btn)

        # Button to load document with PDF
        self.load_with_pdf_btn = QPushButton("Load With PDF")
        self.load_with_pdf_btn.clicked.connect(self.load_document_with_pdf)
        control_layout.addWidget(self.load_with_pdf_btn)

        # Button to clear document
        self.clear_doc_btn = QPushButton("Clear Document")
        self.clear_doc_btn.clicked.connect(self.clear_document)
        control_layout.addWidget(self.clear_doc_btn)

        # Add control layout to main layout
        main_layout.addLayout(control_layout)

        # Create document display widget
        self.document_display = DocumentDisplayWidget(
            parent=self,
            status_bar=self.status_bar,
            db_manager=self.db_manager,
            pdf_base_dir=self.temp_dir
        )

        # Set a mock summary generator
        self.document_display.set_summary_generator(self.mock_summary_generator)

        # Connect signals
        self.document_display.documentRated.connect(self.on_document_rated)
        self.document_display.documentBookmarked.connect(self.on_document_bookmarked)

        # Add document display to main layout
        main_layout.addWidget(self.document_display)

        # Set initial user
        self.set_user()

    def set_user(self):
        """Set a test user in the context."""
        user = {
            'id': 1,
            'firstname': 'Test',
            'surname': 'User'
        }
        set_current_user(user)
        self.status_bar.showMessage("Set user: Test User (ID: 1)")

    def set_project(self):
        """Set a test project in the context."""
        set_current_project(1)
        self.status_bar.showMessage("Set project: Test Project (ID: 1)")

    def clear_project(self):
        """Clear the project in the context."""
        set_current_project(None)
        self.status_bar.showMessage("Cleared project")

    def mock_summary_generator(self, document: Dict[str, Any]) -> str:
        """
        Generate a mock summary for a document.

        Args:
            document: Document to summarize

        Returns:
            str: Generated summary
        """
        title = document.get('title', 'Unknown Title')
        abstract = document.get('abstract', 'No abstract available')

        # Create a simple summary by taking the first sentence of the abstract
        # and adding some template text
        first_sentence = abstract.split('.')[0] + '.' if '.' in abstract else abstract

        summary = f"""
        <p>This is a mock summary of the document titled "{title}".</p>

        <p>The main point of this document appears to be: {first_sentence}</p>

        <p>This summary was generated by a mock generator for demonstration purposes.
        In a real application, this would be generated by a more sophisticated
        summarization algorithm or service.</p>
        """

        return summary

    def load_document(self):
        """Load a test document."""
        document = {
            'id': 1,
            'title': 'Test Document',
            'authors': ['John Doe', 'Jane Smith'],
            'publication_date': '2023-01-01',
            'source_name': 'pubmed',
            'external_id': '12345678',
            'doi': '10.1234/test.12345',
            'abstract': 'This is a test abstract for the document display widget. '
                       'It demonstrates how the widget displays document content '
                       'in a tabbed interface with controls for rating and bookmarking. '
                       'The abstract provides an overview of the document contents. '
                       'It can be quite lengthy and contain multiple paragraphs of text.',
            'keywords': ['test', 'document', 'display', 'widget'],
            'journal': 'Test Journal',
            'url': 'https://example.com/test'
        }
        self.document_display.display_document(document)
        self.status_bar.showMessage("Loaded test document")

    def load_document_with_summary(self):
        """Load a test document with a pre-generated summary."""
        document = {
            'id': 2,
            'title': 'Test Document with Summary',
            'authors': ['Alice Johnson', 'Bob Williams'],
            'publication_date': '2023-02-15',
            'source_name': 'medrxiv',
            'external_id': '87654321',
            'doi': '10.5678/test.54321',
            'abstract': 'This document already has a pre-generated summary. '
                       'The abstract is different from the summary and provides more details. '
                       'It contains technical information that might be difficult to understand '
                       'for non-experts in the field.',
            'summary': '<p>This is a pre-generated summary of the document.</p>'
                      '<p>It provides a concise overview of the main points without '
                      'requiring the user to read the entire abstract.</p>'
                      '<p>Summaries are useful for quickly understanding the content '
                      'of a document and deciding whether to read it in full.</p>',
            'keywords': ['summary', 'test', 'pre-generated'],
            'journal': 'Test Journal of Summaries',
            'url': 'https://example.com/test-with-summary'
        }
        self.document_display.display_document(document)
        self.status_bar.showMessage("Loaded test document with summary")

    def load_document_with_pdf(self):
        """Load a test document with a PDF file."""
        # Create a simple text file as a mock PDF
        pdf_filename = "test_document.pdf"
        pdf_path = os.path.join(self.temp_dir, pdf_filename)

        # Create a mock PDF file (just a text file for testing)
        with open(pdf_path, 'w') as f:
            f.write("This is a mock PDF file for testing purposes.\n")
            f.write("In a real application, this would be a real PDF file.\n")

        document = {
            'id': 3,
            'title': 'Test Document with PDF',
            'authors': ['John Smith', 'Jane Doe'],
            'publication_date': '2023-03-20',
            'source_name': 'pubmed',
            'external_id': '98765432',
            'doi': '10.9876/test.98765',
            'abstract': 'This document has a PDF file associated with it. '
                       'The PDF contains the full text of the document, '
                       'including figures, tables, and references.',
            'pdf_filename': pdf_filename,  # Just the filename, not the full path
            'keywords': ['pdf', 'test', 'document'],
            'journal': 'Test Journal of PDFs',
            'url': 'https://example.com/test-with-pdf'
        }

        self.document_display.display_document(document)
        self.status_bar.showMessage("Loaded test document with PDF")

    def clear_document(self):
        """Clear the document display."""
        self.document_display.clear()
        self.status_bar.showMessage("Cleared document display")

    def on_document_rated(self, document, rating):
        """
        Handle document rating.

        Args:
            document: Document data dictionary
            rating: Rating value
        """
        self.status_bar.showMessage(f"Document rated: {rating}")

    def on_document_bookmarked(self, document, bookmark_type, is_bookmarked):
        """
        Handle document bookmarking.

        Args:
            document: Document data dictionary
            bookmark_type: Type of bookmark
            is_bookmarked: Whether the document was bookmarked or unbookmarked
        """
        action = "bookmarked" if is_bookmarked else "unbookmarked"
        self.status_bar.showMessage(f"Document {action} as {bookmark_type}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
