#!/usr/bin/env python3
"""
Test script for the DocumentListWidget.

This script creates a simple application to test the DocumentListWidget
with sample data.
"""

import sys
import os
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

# Add parent directory to path to allow importing localknowledge modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from localknowledge.ui.document_list_widget import DocumentListWidget


class TestWindow(QMainWindow):
    """Test window for the DocumentListWidget."""
    
    def __init__(self):
        """Initialize the test window."""
        super().__init__()
        self.setWindowTitle("Document List Widget Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Add label
        label = QLabel("Document List Widget Test")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # Create document list widget
        self.document_list = DocumentListWidget()
        layout.addWidget(self.document_list)
        
        # Connect signals
        self.document_list.documentSelected.connect(self.on_document_selected)
        self.document_list.documentActivated.connect(self.on_document_activated)
        
        # Add sample data
        self.add_sample_data()
    
    def add_sample_data(self):
        """Add sample data to the document list."""
        # Sample documents
        documents = [
            {
                'id': 1,
                'source_id': 1,  # PubMed
                'source_name': 'pubmed',
                'external_id': '12345678',
                'title': 'Sample PubMed Article with a Very Long Title That Should Be Displayed Properly',
                'abstract': 'This is a sample abstract for testing purposes.',
                'authors': ['Smith, John', 'Doe, Jane', 'Johnson, Robert'],
                'publication_date': datetime(2023, 5, 15),
                'bookmark_type': 'personal'
            },
            {
                'id': 2,
                'source_id': 2,  # medRxiv
                'source_name': 'medrxiv',
                'external_id': '10.1101/2023.01.01.12345',
                'title': 'Sample medRxiv Preprint',
                'abstract': 'This is a sample abstract for a medRxiv preprint.',
                'authors': ['Brown, Michael', 'Wilson, Sarah'],
                'publication_date': datetime(2023, 6, 20),
                'bookmark_type': 'project'
            },
            {
                'id': 3,
                'source_id': 1,  # PubMed
                'source_name': 'pubmed',
                'external_id': '87654321',
                'title': 'Another PubMed Article',
                'abstract': 'This is another sample abstract.',
                'authors': ['Garcia, Maria', 'Lee, David', 'Wang, Li'],
                'publication_date': datetime(2023, 7, 10),
                'bookmark_type': 'both'
            },
            {
                'id': 4,
                'source_id': 2,  # medRxiv
                'source_name': 'medrxiv',
                'external_id': '10.1101/2023.02.02.54321',
                'title': 'Another medRxiv Preprint with Recommendation',
                'abstract': 'This is another sample abstract for a medRxiv preprint.',
                'authors': ['Taylor, James', 'Anderson, Emily'],
                'publication_date': datetime(2023, 8, 5)
            }
        ]
        
        # Sample read IDs
        read_ids = [1, 3]
        
        # Sample suggestions
        suggestions = {
            4: {
                'recommendation_strength': 3,
                'reason': 'This article matches your interests in machine learning.'
            }
        }
        
        # Set documents in the list
        self.document_list.set_documents(documents, read_ids, suggestions)
    
    def on_document_selected(self, document):
        """
        Handle document selection.
        
        Args:
            document: Selected document
        """
        print(f"Selected document: {document['title']}")
    
    def on_document_activated(self, document):
        """
        Handle document activation (double-click).
        
        Args:
            document: Activated document
        """
        print(f"Activated document: {document['title']}")
        print(f"Abstract: {document['abstract']}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
