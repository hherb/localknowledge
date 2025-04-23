"""
Question-Answer Widget with split screen display.

This module provides a PySide6 widget with a question input box at the top,
and a split screen with identical widgets on the left and right.
Each side widget displays a list of titles on top and an abstract below.

The left side shows results from direct semantic search, while the right side
shows results from HyDE (Hypothetical Document Embeddings) search.
"""

from typing import Dict, List, Optional, Any
import logging

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QLabel, QTextEdit, QApplication, QFrame
)

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.embeddings.multiembeddings import EmbeddingManager
from localknowledge.ai.HyDE import generate_hyde_embedding

# Configure logging
logger = logging.getLogger(__name__)


class TitleListItem(QListWidgetItem):
    """List widget item to display document title with metadata."""

    def __init__(self, document: Dict[str, Any], similarity: float = None):
        """
        Initialize a title list item.

        Args:
            document: Document data dictionary
            similarity: Similarity score (optional)
        """
        # Create display text with title in bold
        display_text = document.get('title', 'Untitled')

        # Initialize the list item with the display text
        super().__init__(display_text)

        # Store the document data and similarity for later use
        self.document = document
        self.similarity = similarity

        # Set font for title (bold)
        font = self.font()
        font.setBold(True)
        self.setFont(font)

        # Set tooltip with more information
        authors = document.get('authors', [])
        if authors:
            if isinstance(authors, list):
                authors_str = ", ".join(authors)
            else:
                authors_str = str(authors)

            tooltip = f"{display_text}\n\nAuthors: {authors_str}"
            if similarity is not None:
                tooltip += f"\n\nSimilarity: {similarity:.2f}"

            self.setToolTip(tooltip)


class DocumentDisplayWidget(QWidget):
    """Widget to display a list of titles and the selected document's abstract."""

    # Signal emitted when a document is selected
    documentSelected = Signal(dict)

    def __init__(self, title=None, parent=None):
        """
        Initialize the document display widget.

        Args:
            title: Optional title for the widget
            parent: Parent widget
        """
        super().__init__(parent)

        # Store the title
        self.title_text = title

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Add title label if provided
        if self.title_text:
            title_label = QLabel(self.title_text)
            title_label.setAlignment(Qt.AlignCenter)
            font = title_label.font()
            font.setBold(True)
            title_label.setFont(font)
            main_layout.addWidget(title_label)

        # Create a splitter for the title list and abstract view
        self.splitter = QSplitter(Qt.Vertical)

        # Title list
        self.title_list = QListWidget()
        self.title_list.setMinimumHeight(100)
        self.title_list.currentItemChanged.connect(self._on_title_selected)

        # Abstract view
        self.abstract_view = QTextEdit()
        self.abstract_view.setReadOnly(True)

        # Add widgets to splitter
        self.splitter.addWidget(self.title_list)
        self.splitter.addWidget(self.abstract_view)

        # Set initial sizes (1:1 ratio)
        self.splitter.setSizes([200, 200])

        # Add splitter to main layout
        main_layout.addWidget(self.splitter)

    def clear(self):
        """Clear the title list and abstract view."""
        self.title_list.clear()
        self.abstract_view.clear()

    def add_document(self, document: Dict[str, Any], similarity: float = None):
        """
        Add a document to the title list.

        Args:
            document: Document data dictionary
            similarity: Similarity score (optional)
        """
        item = TitleListItem(document, similarity)
        self.title_list.addItem(item)

    def set_documents(self, documents: List[Dict[str, Any]]):
        """
        Set the list of documents to display.

        Args:
            documents: List of document data dictionaries
        """
        self.clear()
        for doc in documents:
            similarity = doc.pop('similarity', None) if isinstance(doc, dict) else None
            self.add_document(doc, similarity)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_title_selected(self, current, previous):
        """
        Handle selection of a title in the list.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if current is None:
            self.abstract_view.clear()
            return

        # Get the document data from the selected item
        document = current.document

        # Display the abstract
        abstract = document.get('abstract', 'No abstract available.')
        self.abstract_view.setText(abstract)

        # Emit signal with the selected document
        self.documentSelected.emit(document)


class QAWidget(QWidget):
    """
    Widget with a question input box and split screen display of search results.

    The left panel shows results from direct semantic search, while the right panel
    shows results from HyDE (Hypothetical Document Embeddings) search.
    """

    def __init__(self, parent=None):
        """
        Initialize the QA widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize database managers
        self.doc_db = DocumentDatabaseManager()

        # Try to initialize the embedding manager, but make it optional
        self.embedding_manager = None
        try:
            # Create the embedding manager
            self.embedding_manager = EmbeddingManager()
            logger.info("Semantic search enabled")
        except Exception as e:
            logger.warning(f"Semantic search disabled: {e}")

        # Default search settings
        self.search_settings = {
            'similarity_threshold': 0.3,
            'max_results': 10,
            'hyde_model': 'gemma3:4b',  # Model for generating hypothetical abstracts
        }

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Search bar at the top
        search_layout = QHBoxLayout()

        # Question input
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Enter your question...")
        self.question_input.returnPressed.connect(self._on_search)

        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)

        # Add to search layout
        search_layout.addWidget(self.question_input, 1)  # 1 is the stretch factor
        search_layout.addWidget(self.search_button)

        # Add search layout to main layout
        main_layout.addLayout(search_layout)

        # Create horizontal splitter for left and right panels
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Direct Semantic Search
        self.left_panel = DocumentDisplayWidget(title="Direct Semantic Search")

        # Right panel - HyDE Search
        self.right_panel = DocumentDisplayWidget(title="HyDE Search")

        # Add panels to main splitter
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)

        # Set initial sizes (1:1 ratio)
        self.main_splitter.setSizes([400, 400])

        # Add main splitter to layout
        main_layout.addWidget(self.main_splitter, 1)  # 1 is the stretch factor

        # Status bar
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        # Add a label to show the hypothetical abstract
        self.hyde_abstract_label = QLabel("HyDE Abstract:")
        self.hyde_abstract_view = QTextEdit()
        self.hyde_abstract_view.setReadOnly(True)
        self.hyde_abstract_view.setMaximumHeight(100)
        self.hyde_abstract_view.setVisible(False)  # Hidden by default

        # Add to main layout
        main_layout.addWidget(self.hyde_abstract_label)
        main_layout.addWidget(self.hyde_abstract_view)

    @Slot()
    def _on_search(self):
        """Handle search button click or Enter key in question input."""
        # Get the question text
        question = self.question_input.text().strip()

        if not question:
            self.status_label.setText("Please enter a question")
            return

        # Clear previous results
        self.left_panel.clear()
        self.right_panel.clear()
        self.hyde_abstract_view.clear()
        self.hyde_abstract_view.setVisible(False)

        # Update status
        self.status_label.setText("Searching...")
        QApplication.processEvents()  # Update the UI

        try:
            # Check if embedding manager is available
            if self.embedding_manager:
                # Perform both direct semantic search and HyDE search
                self._perform_dual_search(question)
            else:
                # Keyword search fallback
                self._perform_keyword_search(question)
                self.status_label.setText("Semantic search is not available. Using keyword search only.")
        except Exception as e:
            logger.error(f"Error during search: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _perform_dual_search(self, question: str):
        """
        Perform both direct semantic search and HyDE search.

        Args:
            question: Question to search for
        """
        # Check if embedding manager is available
        if not self.embedding_manager:
            self.status_label.setText("Semantic search is not available")
            return

        try:
            # 1. Direct semantic search for left panel
            direct_results = self.embedding_manager.search(
                query=question,
                limit=self.search_settings['max_results'],
                threshold=self.search_settings['similarity_threshold']
            )

            # 2. HyDE search for right panel
            # Generate HyDE embedding
            hyde_embedding = generate_hyde_embedding(
                question=question,
                generation_model=self.search_settings['hyde_model'],
                embedding_model=self.embedding_manager.model_name
            )

            # Get the hypothetical abstract to display
            from localknowledge.ai.HyDE import generate_hypothetical_abstract
            hypothetical_abstract = generate_hypothetical_abstract(
                question=question,
                model=self.search_settings['hyde_model']
            )

            # Display the hypothetical abstract
            if hypothetical_abstract:
                self.hyde_abstract_view.setText(hypothetical_abstract)
                self.hyde_abstract_view.setVisible(True)

            # Search with the HyDE embedding
            hyde_results = []
            if hyde_embedding:
                # Use the embedding manager's database to search
                hyde_results = self.embedding_manager.db.search_similar(
                    self.embedding_manager.model_name,
                    hyde_embedding,
                    limit=self.search_settings['max_results'],
                    threshold=self.search_settings['similarity_threshold']
                )

            # Update status
            direct_count = len(direct_results)
            hyde_count = len(hyde_results)
            self.status_label.setText(f"Found {direct_count} direct results and {hyde_count} HyDE results")

            # Display results in respective panels
            self.left_panel.set_documents(direct_results)
            self.right_panel.set_documents(hyde_results)

        except Exception as e:
            logger.error(f"Error in dual search: {e}")
            self.status_label.setText(f"Search error: {str(e)}")

    def _perform_keyword_search(self, question: str):
        """
        Perform a keyword search using the document database.

        Args:
            question: Question to search for
        """
        try:
            # Simple keyword search in title and abstract
            query = """
            SELECT * FROM document
            WHERE title ILIKE %s OR abstract ILIKE %s
            LIMIT %s
            """

            # Use wildcard search
            search_term = f"%{question}%"

            # Execute query
            results = self.doc_db.execute(
                query,
                (search_term, search_term, self.search_settings['max_results'])
            )

            # Update status
            self.status_label.setText(f"Found {len(results)} results")

            # Split results between left and right panels
            if results:
                # Split results
                mid_point = len(results) // 2
                left_results = results[:mid_point]
                right_results = results[mid_point:]

                # Display results
                self._display_results(left_results, right_results)
            else:
                self.status_label.setText("No results found")
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            self.status_label.setText(f"Search error: {str(e)}")

    def _display_results(self, left_results: List[Dict[str, Any]], right_results: List[Dict[str, Any]]):
        """
        Display search results in the left and right panels.

        Args:
            left_results: Results for the left panel
            right_results: Results for the right panel
        """
        # Display left results
        self.left_panel.set_documents(left_results)

        # Display right results
        self.right_panel.set_documents(right_results)

        # Update status with result counts
        left_count = len(left_results)
        right_count = len(right_results)
        self.status_label.setText(f"Found {left_count} direct results and {right_count} HyDE results")


# Example standalone usage
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    widget = QAWidget()
    widget.resize(1000, 800)
    widget.show()

    sys.exit(app.exec())
