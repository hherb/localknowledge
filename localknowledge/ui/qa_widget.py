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
import traceback
import threading

from PySide6.QtCore import Qt, Signal, Slot, QSize, QEvent, QCoreApplication, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QLabel, QTextEdit, QApplication, QFrame, QComboBox, QCheckBox,
    QProgressBar, QSlider, QSpinBox
)

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.embeddings.multiembeddings import EmbeddingManager


# Import the connection pool
from localknowledge.db.connection_pool import get_cursor, initialize_pool, close_pool

# Simple thread-safe search function
def perform_semantic_search(embedding_manager, query, max_results=10, threshold=0.3, use_reranker=False, reranker_model='BAAI/bge-reranker-base'):
    """Perform a semantic search in a thread-safe way.

    Args:
        embedding_manager: The embedding manager to use
        query: The search query
        max_results: Maximum number of results to return
        threshold: Similarity threshold
        use_reranker: Whether to use reranking
        reranker_model: Reranker model to use

    Returns:
        List of search results
    """
    try:
        # Create embedding for the question
        question_embedding = embedding_manager.create_embedding(query)

        # Get the embedding source ID
        from localknowledge.db.embedding_source import get_embedding_source_by_name

        results = []
        with get_cursor() as cursor:
            # Get the embedding source ID
            embed_source_record = get_embedding_source_by_name(cursor, 'abstract')

            if not embed_source_record:
                logger.error("Embedding source 'abstract' not found")
                return []

            embed_source_id = embed_source_record['id']

            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(question_embedding)

            query_sql = """
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.id, d.title, d.abstract, d.source_id, d.authors
            FROM unified_multiembeddings e
            JOIN embedding_source s ON e.embed_source_id = s.id
            JOIN document d ON e.document_id = d.id
            WHERE e.embed_source_id = %s
            AND e.model_name = %s
            AND 1 - (e.embedding <=> vector(%s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
            """

            cursor.execute(
                query_sql,
                (embedding_str, embedding_str, embed_source_id, embedding_manager.model_name, embedding_str, threshold, max_results)
            )

            results = [dict(row) for row in cursor.fetchall()]

        # Apply reranking if requested
        if use_reranker and results:
            try:
                # Import in a safer way
                try:
                    from localknowledge.ai.rerankers import get_reranker
                    reranker = get_reranker(reranker_model)

                    if reranker:
                        # Limit the number of documents to rerank to avoid memory issues
                        max_rerank = min(len(results), 20)  # Only rerank up to 20 documents
                        to_rerank = results[:max_rerank]

                        # Rerank the limited set
                        reranked = reranker.rerank(query, to_rerank)

                        # Combine with any remaining results
                        if max_rerank < len(results):
                            results = reranked + results[max_rerank:]
                        else:
                            results = reranked
                except ImportError:
                    logging.warning("Rerankers module not available")
            except Exception as e:
                logging.error(f"Error during reranking: {e}")
                # Continue with original results if reranking fails

        return results
    except Exception as e:
        logging.error(f"Error in semantic search: {e}\n{traceback.format_exc()}")
        return []


def perform_hyde_search(embedding_manager, query, max_results=10, threshold=0.3, use_reranker=False, reranker_model='BAAI/bge-reranker-base', hyde_model='gemma3:4b'):
    """Perform a HyDE search in a thread-safe way.

    Args:
        embedding_manager: The embedding manager to use
        query: The search query
        max_results: Maximum number of results to return
        threshold: Similarity threshold
        use_reranker: Whether to use reranking
        reranker_model: Reranker model to use
        hyde_model: Model to use for generating hypothetical abstracts

    Returns:
        Dictionary with results and abstract
    """
    try:
        # First get the hypothetical abstract
        from localknowledge.ai.HyDE import generate_hypothetical_abstract
        hypothetical_abstract = generate_hypothetical_abstract(
            question=query,
            model=hyde_model
        )

        # Create embedding of the hypothetical abstract
        if not hypothetical_abstract:
            return {
                'results': [],
                'abstract': "Failed to generate hypothetical abstract."
            }

        # Create a direct embedding of the hypothetical abstract
        try:
            hyde_embedding = embedding_manager.create_embedding(hypothetical_abstract)
        except Exception as e:
            logging.error(f"Error creating HyDE embedding: {e}")
            return {
                'results': [],
                'abstract': hypothetical_abstract
            }

        # Get the embedding source ID
        from localknowledge.db.embedding_source import get_embedding_source_by_name

        results = []
        with get_cursor() as cursor:
            # Get the embedding source ID
            embed_source_record = get_embedding_source_by_name(cursor, 'abstract')

            if not embed_source_record:
                logger.error("Embedding source 'abstract' not found")
                return {
                    'results': [],
                    'abstract': hypothetical_abstract
                }

            embed_source_id = embed_source_record['id']

            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(hyde_embedding)

            query_sql = """
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.id, d.title, d.abstract, d.source_id, d.authors
            FROM unified_multiembeddings e
            JOIN embedding_source s ON e.embed_source_id = s.id
            JOIN document d ON e.document_id = d.id
            WHERE e.embed_source_id = %s
            AND e.model_name = %s
            AND 1 - (e.embedding <=> vector(%s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
            """

            cursor.execute(
                query_sql,
                (embedding_str, embedding_str, embed_source_id, embedding_manager.model_name, embedding_str, threshold, max_results)
            )

            results = [dict(row) for row in cursor.fetchall()]

        # Apply reranking if requested
        if use_reranker and results:
            try:
                # Import in a safer way
                try:
                    from localknowledge.ai.rerankers import get_reranker
                    reranker = get_reranker(reranker_model)

                    if reranker:
                        # Limit the number of documents to rerank to avoid memory issues
                        max_rerank = min(len(results), 20)  # Only rerank up to 20 documents
                        to_rerank = results[:max_rerank]

                        # Rerank the limited set
                        reranked = reranker.rerank(query, to_rerank)

                        # Combine with any remaining results
                        if max_rerank < len(results):
                            results = reranked + results[max_rerank:]
                        else:
                            results = reranked
                except ImportError:
                    logging.warning("Rerankers module not available")
            except Exception as e:
                logging.error(f"Error during reranking: {e}")
                # Continue with original results if reranking fails

        return {
            'results': results,
            'abstract': hypothetical_abstract
        }
    except Exception as e:
        logging.error(f"Error in HyDE search: {e}\n{traceback.format_exc()}")
        return {
            'results': [],
            'abstract': None
        }


def perform_keyword_search(query, max_results=10):
    """Perform a keyword search in a thread-safe way.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        List of search results
    """
    try:
        # Use wildcard search
        search_term = f"%{query}%"

        with get_cursor() as cursor:
            # Only search documents that have abstract embeddings
            query_sql = """
            SELECT d.id, d.title, d.abstract, d.source_id, d.authors FROM document d
            JOIN unified_multiembeddings e ON d.id = e.document_id
            JOIN embedding_source s ON e.embed_source_id = s.id
            WHERE (d.title ILIKE %s OR d.abstract ILIKE %s)
            AND s.name = 'abstract'
            GROUP BY d.id
            LIMIT %s
            """

            cursor.execute(query_sql, (search_term, search_term, max_results))
            results = [dict(row) for row in cursor.fetchall()]

        return results
    except Exception as e:
        logging.error(f"Error in keyword search: {e}\n{traceback.format_exc()}")
        return []


def perform_synthetic_qa(query):
    """Perform a synthetic Q&A operation.

    Args:
        query: The search query

    Returns:
        List with a single synthetic result
    """
    try:
        # For now, just return a placeholder result
        # In a real implementation, this would call an LLM to generate answers
        synthetic_result = {
            'title': f"Synthetic answer to: {query}",
            'abstract': "This is a placeholder for a synthetic answer that would be generated by an LLM. " +
                       "In a real implementation, this would contain an answer generated based on the question.",
            'authors': ['AI Assistant'],
            'similarity': 1.0,
            'source_id': None,  # No specific source for synthetic answers
            'synthetic': True
        }

        return [synthetic_result]
    except Exception as e:
        logging.error(f"Error in synthetic Q&A: {e}\n{traceback.format_exc()}")
        return []

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
        # Get the document title
        title = document.get('title', 'Untitled')

        # Get the source information
        source_id = document.get('source_id')
        source_tag = ''

        # Add source tag based on source_id
        if source_id == 1:
            source_tag = '[pubmed] '
        elif source_id == 2:
            source_tag = '[medrxiv] '

        # Create display text with source tag and title
        display_text = f"{source_tag}{title}"

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

            tooltip = f"{title}\n\nSource: {'PubMed' if source_id == 1 else 'medRxiv' if source_id == 2 else 'Unknown'}\nAuthors: {authors_str}"
            if similarity is not None:
                tooltip += f"\n\nSimilarity: {similarity:.2f}"

            self.setToolTip(tooltip)


class DocumentDisplayWidget(QWidget):
    """Widget to display a list of titles and the selected document's abstract."""

    # Signal emitted when a document is selected
    documentSelected = Signal(dict)

    # Signal emitted when search method is changed
    searchMethodChanged = Signal(str, bool)  # method, use_reranker

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

        # Add search method selection and controls
        controls_layout = QVBoxLayout()

        # Top row: Search method and reranker
        search_method_layout = QHBoxLayout()

        # Search method combo box
        self.search_method_combo = QComboBox()
        self.search_method_combo.addItem("Semantic", "semantic")
        self.search_method_combo.addItem("Keyword", "keyword")
        self.search_method_combo.addItem("HyDE", "hyde")
        self.search_method_combo.addItem("Synthetic Q&A", "synthetic")
        self.search_method_combo.currentIndexChanged.connect(self._on_search_method_changed)

        # Reranker checkbox
        self.reranker_checkbox = QCheckBox("Use Reranker")
        self.reranker_checkbox.toggled.connect(self._on_reranker_toggled)

        # Add to top row layout
        search_method_layout.addWidget(QLabel("Search Method:"))
        search_method_layout.addWidget(self.search_method_combo, 1)  # 1 is stretch factor
        search_method_layout.addWidget(self.reranker_checkbox)

        controls_layout.addLayout(search_method_layout)

        # Middle row: Similarity threshold slider
        similarity_layout = QHBoxLayout()

        # Similarity threshold label
        similarity_label = QLabel("Similarity:")
        similarity_layout.addWidget(similarity_label)

        # Similarity threshold slider
        self.similarity_slider = QSlider(Qt.Horizontal)
        self.similarity_slider.setRange(0, 100)  # 0-100 for 0.0-1.0
        self.similarity_slider.setValue(30)  # Default 0.3
        self.similarity_slider.setTickPosition(QSlider.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        self.similarity_slider.valueChanged.connect(self._on_similarity_changed)
        similarity_layout.addWidget(self.similarity_slider, 1)  # 1 is stretch factor

        # Similarity value label
        self.similarity_value_label = QLabel("0.30")
        self.similarity_value_label.setMinimumWidth(40)
        similarity_layout.addWidget(self.similarity_value_label)

        controls_layout.addLayout(similarity_layout)

        # Bottom row: Max results
        max_results_layout = QHBoxLayout()

        # Max results label
        max_results_layout.addWidget(QLabel("Max Results:"))

        # Max results spinner
        self.max_results_spinner = QSpinBox()
        self.max_results_spinner.setRange(1, 100)
        self.max_results_spinner.setValue(10)  # Default 10
        self.max_results_spinner.valueChanged.connect(self._on_max_results_changed)
        max_results_layout.addWidget(self.max_results_spinner)

        # Add spacer to push controls to the left
        max_results_layout.addStretch(1)

        controls_layout.addLayout(max_results_layout)

        main_layout.addLayout(controls_layout)

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
    def _on_search_method_changed(self, _):
        """
        Handle change of search method.

        Args:
            _: Index of the selected item in the combo box (unused)
        """
        # Get the selected search method
        method = self.search_method_combo.currentData()

        # Update reranker checkbox visibility based on method
        # Only semantic and HyDE searches can use reranking
        self.reranker_checkbox.setVisible(method in ["semantic", "hyde"])

        # Update similarity slider visibility
        # Only semantic and HyDE searches use similarity threshold
        self.similarity_slider.setEnabled(method in ["semantic", "hyde"])
        self.similarity_value_label.setEnabled(method in ["semantic", "hyde"])

        # Emit signal with the selected method and reranker state
        self.searchMethodChanged.emit(method, self.reranker_checkbox.isChecked())

    def _on_reranker_toggled(self, checked):
        """
        Handle toggling of the reranker checkbox.

        Args:
            checked: Whether the checkbox is checked
        """
        # Emit signal with the current method and new reranker state
        method = self.search_method_combo.currentData()
        self.searchMethodChanged.emit(method, checked)

    def _on_similarity_changed(self, value):
        """
        Handle change of similarity threshold slider.

        Args:
            value: New slider value (0-100)
        """
        # Convert to float (0.0-1.0)
        similarity = value / 100.0

        # Update the label
        self.similarity_value_label.setText(f"{similarity:.2f}")

    def _on_max_results_changed(self, _):
        """
        Handle change of max results spinner.

        Args:
            _: New spinner value (unused)
        """
        # No need to update any settings here - the value will be read directly from the spinner
        pass

    def _on_title_selected(self, current, _):
        """
        Handle selection of a title in the list.

        Args:
            current: Currently selected item
            _: Previously selected item (unused)
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

    # Signal emitted when the widget is closed
    closed = Signal()

    def __init__(self, parent=None):
        """
        Initialize the QA widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize connection pool
        initialize_pool(min_connections=2, max_connections=10)
        logger.info("Database connection pool initialized")

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
            'use_reranker': False,
            'reranker_model': 'BAAI/bge-reranker-base',
            'left_search_method': 'semantic',
            'right_search_method': 'hyde',
            'left_use_reranker': False,
            'right_use_reranker': False
        }

        # Initialize thread pool for background tasks
        self.threadpool = QThreadPool()
        logger.info(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

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

        # Left panel - Direct Semantic Search by default
        self.left_panel = DocumentDisplayWidget(title="Left Panel")
        self.left_panel.search_method_combo.setCurrentText("Semantic")
        self.left_panel.reranker_checkbox.setChecked(self.search_settings['left_use_reranker'])
        self.left_panel.searchMethodChanged.connect(self._on_left_search_method_changed)

        # Right panel - HyDE Search by default
        self.right_panel = DocumentDisplayWidget(title="Right Panel")
        self.right_panel.search_method_combo.setCurrentText("HyDE")
        self.right_panel.reranker_checkbox.setChecked(self.search_settings['right_use_reranker'])
        self.right_panel.searchMethodChanged.connect(self._on_right_search_method_changed)

        # Add panels to main splitter
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)

        # Set initial sizes (1:1 ratio)
        self.main_splitter.setSizes([400, 400])

        # Add main splitter to layout
        main_layout.addWidget(self.main_splitter, 1)  # 1 is the stretch factor

        # Status bar and progress indicators
        status_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label, 1)  # 1 is stretch factor

        # Left panel progress bar
        self.left_progress = QProgressBar()
        self.left_progress.setRange(0, 100)
        self.left_progress.setValue(0)
        self.left_progress.setVisible(False)
        self.left_progress.setMaximumWidth(150)
        status_layout.addWidget(self.left_progress)

        # Right panel progress bar
        self.right_progress = QProgressBar()
        self.right_progress.setRange(0, 100)
        self.right_progress.setValue(0)
        self.right_progress.setVisible(False)
        self.right_progress.setMaximumWidth(150)
        status_layout.addWidget(self.right_progress)

        main_layout.addLayout(status_layout)

        # Add a label to show the hypothetical abstract
        self.hyde_abstract_label = QLabel("HyDE Abstract:")
        self.hyde_abstract_view = QTextEdit()
        self.hyde_abstract_view.setReadOnly(True)
        self.hyde_abstract_view.setMaximumHeight(100)
        self.hyde_abstract_view.setVisible(False)  # Hidden by default

        # Add to main layout
        main_layout.addWidget(self.hyde_abstract_label)
        main_layout.addWidget(self.hyde_abstract_view)

    @Slot(str, bool)
    def _on_left_search_method_changed(self, method, use_reranker):
        """Handle change of search method in the left panel.

        Args:
            method: The selected search method
            use_reranker: Whether to use reranking
        """
        logger.info(f"Left panel search method changed to {method}, reranker: {use_reranker}")
        self.search_settings['left_search_method'] = method
        self.search_settings['left_use_reranker'] = use_reranker

        # Update the panel title based on the method
        if method == "semantic":
            self.left_panel.title_text = "Semantic Search"
        elif method == "keyword":
            self.left_panel.title_text = "Keyword Search"
        elif method == "hyde":
            self.left_panel.title_text = "HyDE Search"
        elif method == "synthetic":
            self.left_panel.title_text = "Synthetic Q&A"

        # Update the left panel's similarity slider and max results spinner
        # based on the panel's settings
        if hasattr(self.left_panel, 'similarity_slider') and hasattr(self.left_panel, 'max_results_spinner'):
            self.left_panel.similarity_slider.setValue(int(self.search_settings['similarity_threshold'] * 100))
            self.left_panel.max_results_spinner.setValue(self.search_settings['max_results'])

    @Slot(str, bool)
    def _on_right_search_method_changed(self, method, use_reranker):
        """Handle change of search method in the right panel.

        Args:
            method: The selected search method
            use_reranker: Whether to use reranking
        """
        logger.info(f"Right panel search method changed to {method}, reranker: {use_reranker}")
        self.search_settings['right_search_method'] = method
        self.search_settings['right_use_reranker'] = use_reranker

        # Update the panel title based on the method
        if method == "semantic":
            self.right_panel.title_text = "Semantic Search"
        elif method == "keyword":
            self.right_panel.title_text = "Keyword Search"
        elif method == "hyde":
            self.right_panel.title_text = "HyDE Search"
        elif method == "synthetic":
            self.right_panel.title_text = "Synthetic Q&A"

        # Update the right panel's similarity slider and max results spinner
        # based on the panel's settings
        if hasattr(self.right_panel, 'similarity_slider') and hasattr(self.right_panel, 'max_results_spinner'):
            self.right_panel.similarity_slider.setValue(int(self.search_settings['similarity_threshold'] * 100))
            self.right_panel.max_results_spinner.setValue(self.search_settings['max_results'])

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

        # Perform search without try/except to see the full error traceback
        if self.embedding_manager:
            # Perform search based on selected methods
            self._perform_search(question)
        else:
            # Keyword search fallback for both panels
            self._perform_keyword_search(question, self.left_panel)
            self._perform_keyword_search(question, self.right_panel)
            self.status_label.setText("Semantic search is not available. Using keyword search only.")

    def _perform_semantic_search(self, question: str, use_reranker: bool = False):
        """
        Perform a semantic search using the embedding manager.

        Args:
            question: Question to search for
            use_reranker: Whether to use reranking

        Returns:
            List of search results
        """
        logger.info(f"Performing semantic search for question: {question}, reranker: {use_reranker}")

        # Check if embedding manager is available
        if not self.embedding_manager:
            logger.debug("Semantic search is not available")
            return []

        # Create embedding for the question
        question_embedding = self.embedding_manager.create_embedding(question)

        # Use the embeddings_db to search with the embedding
        from localknowledge.db.embeddings import get_embeddings_db
        embeddings_db = get_embeddings_db()

        results = embeddings_db.search_similar(
            embedding=question_embedding,
            embed_source='abstract',  # Use 'abstract' as the embedding source
            model_name=self.embedding_manager.model_name,
            limit=self.search_settings['max_results'],
            threshold=self.search_settings['similarity_threshold']
        )

        # Apply reranking if requested
        if use_reranker and results:
            results = self._apply_reranking(question, results)

        return results

    def _perform_hyde_search(self, question: str, use_reranker: bool = False):
        """
        Perform a HyDE (Hypothetical Document Embeddings) search.

        Args:
            question: Question to search for
            use_reranker: Whether to use reranking

        Returns:
            List of search results
        """
        logger.info(f"Performing HyDE search for question: {question}, reranker: {use_reranker}")

        # Check if embedding manager is available
        if not self.embedding_manager:
            logger.debug("Semantic search is not available")
            return []

        # First get the hypothetical abstract to display
        from localknowledge.ai.HyDE import generate_hypothetical_abstract
        hypothetical_abstract = generate_hypothetical_abstract(
            question=question,
            model=self.search_settings['hyde_model']
        )

        # Display the hypothetical abstract
        if hypothetical_abstract:
            self.hyde_abstract_view.setText(hypothetical_abstract)
            self.hyde_abstract_view.setVisible(True)

        # Create a direct embedding of the hypothetical abstract
        hyde_embedding = None
        if hypothetical_abstract and self.embedding_manager:
            try:
                # Use the embedding manager's create_embedding method
                hyde_embedding = self.embedding_manager.create_embedding(hypothetical_abstract)
            except Exception as e:
                logger.error(f"Error creating HyDE embedding: {e}")
                return []

        # Search with the HyDE embedding
        results = []
        if hyde_embedding:
            try:
                # Log what we're doing
                logger.info(f"Searching with HyDE embedding from abstract: {hypothetical_abstract[:50]}...")

                # Use the embeddings database manager
                from localknowledge.db.embeddings import get_embeddings_db
                embeddings_db = get_embeddings_db()

                # Search using the embedding directly
                results = embeddings_db.search_similar(
                    embedding=hyde_embedding,
                    embed_source='abstract',  # Use 'abstract' as the embedding source
                    model_name=self.embedding_manager.model_name,
                    limit=self.search_settings['max_results'],
                    threshold=self.search_settings['similarity_threshold']
                )

                # Apply reranking if requested
                if use_reranker and results:
                    results = self._apply_reranking(question, results)

            except Exception as e:
                logger.error(f"Error in HyDE search: {e}")
                return []

        return results

    def _perform_synthetic_qa_search(self, question: str, panel=None):
        """
        Perform a synthetic Q&A search using an LLM to generate answers.

        Args:
            question: Question to search for
            panel: Panel to display results in (optional)

        Returns:
            List of synthetic answers as search results
        """
        logger.info(f"Performing synthetic Q&A for question: {question}")

        # For now, just return a placeholder result
        # In a real implementation, this would call an LLM to generate answers
        synthetic_result = {
            'title': f"Synthetic answer to: {question}",
            'abstract': "This is a placeholder for a synthetic answer that would be generated by an LLM. " +
                       "In a real implementation, this would contain an answer generated based on the question.",
            'authors': ['AI Assistant'],
            'similarity': 1.0,
            'synthetic': True
        }

        # If panel is provided, update its status
        if panel:
            panel.title_text = "Synthetic Q&A"

        return [synthetic_result]

    def _apply_reranking(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply reranking to the search results.

        Args:
            query: The search query
            documents: List of documents to rerank

        Returns:
            Reranked list of documents
        """
        logger.info(f"Applying reranking to {len(documents)} documents")

        try:
            # Try to import rerankers
            try:
                from localknowledge.ai.rerankers import get_reranker
                reranker = get_reranker(self.search_settings['reranker_model'])

                if not reranker:
                    logger.warning(f"Reranker model '{self.search_settings['reranker_model']}' not found")
                    return documents

                # Rerank the documents
                reranked_docs = reranker.rerank(query, documents)
                logger.info(f"Reranked {len(documents)} documents")

                return reranked_docs
            except ImportError:
                logger.warning("Rerankers module not available")
                return documents
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            return documents


    def _perform_search(self, question: str):
        """
        Perform search based on the selected methods for each panel.

        Args:
            question: Question to search for
        """
        # Get the selected search methods
        left_method = self.search_settings['left_search_method']
        right_method = self.search_settings['right_search_method']

        # Show progress bars
        self.left_progress.setValue(0)
        self.left_progress.setVisible(True)
        self.right_progress.setValue(0)
        self.right_progress.setVisible(True)

        # Get panel-specific settings
        left_max_results = self.left_panel.max_results_spinner.value() if hasattr(self.left_panel, 'max_results_spinner') else self.search_settings['max_results']
        left_threshold = self.left_panel.similarity_slider.value() / 100.0 if hasattr(self.left_panel, 'similarity_slider') else self.search_settings['similarity_threshold']
        left_use_reranker = self.search_settings['left_use_reranker']

        right_max_results = self.right_panel.max_results_spinner.value() if hasattr(self.right_panel, 'max_results_spinner') else self.search_settings['max_results']
        right_threshold = self.right_panel.similarity_slider.value() / 100.0 if hasattr(self.right_panel, 'similarity_slider') else self.search_settings['similarity_threshold']
        right_use_reranker = self.search_settings['right_use_reranker']

        # Update status
        self.status_label.setText(f"Searching with {left_method} and {right_method}...")

        # Create a simple function to update progress
        def update_left_progress(value):
            self.left_progress.setValue(value)
            QApplication.processEvents()  # Process UI events to keep the UI responsive

        def update_right_progress(value):
            self.right_progress.setValue(value)
            QApplication.processEvents()  # Process UI events to keep the UI responsive

        # Perform left panel search in a separate thread
        left_thread = threading.Thread(target=self._perform_panel_search, args=(
            question, left_method, left_max_results, left_threshold, left_use_reranker, self.left_panel, update_left_progress
        ))
        left_thread.daemon = True  # Make thread a daemon so it exits when the main thread exits
        left_thread.start()

        # Perform right panel search in a separate thread
        right_thread = threading.Thread(target=self._perform_panel_search, args=(
            question, right_method, right_max_results, right_threshold, right_use_reranker, self.right_panel, update_right_progress
        ))
        right_thread.daemon = True  # Make thread a daemon so it exits when the main thread exits
        right_thread.start()

    def _perform_panel_search(self, question, method, max_results, threshold, use_reranker, panel, progress_callback):
        """
        Perform search for a single panel.

        Args:
            question: The search query
            method: The search method to use
            max_results: Maximum number of results to return
            threshold: Similarity threshold
            use_reranker: Whether to use reranking
            panel: The panel to display results in
            progress_callback: Function to call with progress updates
        """
        try:
            # Update progress
            progress_callback(10)

            # Perform search based on method
            results = None
            if method == "semantic":
                progress_callback(20)
                results = perform_semantic_search(
                    embedding_manager=self.embedding_manager,
                    query=question,
                    max_results=max_results,
                    threshold=threshold,
                    use_reranker=use_reranker,
                    reranker_model=self.search_settings['reranker_model']
                )
                progress_callback(90)
            elif method == "hyde":
                progress_callback(20)
                hyde_result = perform_hyde_search(
                    embedding_manager=self.embedding_manager,
                    query=question,
                    max_results=max_results,
                    threshold=threshold,
                    use_reranker=use_reranker,
                    reranker_model=self.search_settings['reranker_model'],
                    hyde_model=self.search_settings['hyde_model']
                )
                progress_callback(90)

                # Handle HyDE result which includes the abstract
                if hyde_result and 'abstract' in hyde_result:
                    # Display the hypothetical abstract in the main thread
                    if hyde_result['abstract']:
                        # We need to update the UI in the main thread
                        # Create a custom event
                        event = QEvent(QEvent.Type.User)
                        # Store data as a property of the event
                        event.data = lambda: {
                            'type': 'update_hyde_abstract',
                            'abstract': hyde_result['abstract']
                        }
                        QApplication.instance().postEvent(self, event)

                    # Use the actual results
                    results = hyde_result.get('results', [])
            elif method == "keyword":
                progress_callback(20)
                results = perform_keyword_search(
                    query=question,
                    max_results=max_results
                )
                progress_callback(90)
            elif method == "synthetic":
                progress_callback(50)
                results = perform_synthetic_qa(question)
                progress_callback(90)
            else:
                # Default to semantic search
                progress_callback(20)
                results = perform_semantic_search(
                    embedding_manager=self.embedding_manager,
                    query=question,
                    max_results=max_results,
                    threshold=threshold
                )
                progress_callback(90)

            # Make sure results is a list
            if results is None:
                results = []

            # Update the UI in the main thread
            # Create a custom event
            event = QEvent(QEvent.Type.User)
            # Store data as a property of the event
            event.data = lambda: {
                'type': 'update_results',
                'panel': panel,
                'results': results,
                'method': method
            }
            QApplication.instance().postEvent(self, event)

            # Update progress
            progress_callback(100)

            # Hide progress bar in the main thread
            # Create a custom event
            event = QEvent(QEvent.Type.User)
            # Store data as a property of the event
            event.data = lambda: {
                'type': 'hide_progress',
                'panel': panel
            }
            QApplication.instance().postEvent(self, event)
        except Exception as e:
            logger.error(f"Error in panel search: {e}\n{traceback.format_exc()}")

            # Update the UI in the main thread with the error
            # Create a custom event
            event = QEvent(QEvent.Type.User)
            # Store data as a property of the event
            event.data = lambda: {
                'type': 'search_error',
                'panel': panel,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            QApplication.instance().postEvent(self, event)

            # Hide progress bar in the main thread
            # Create a custom event
            event = QEvent(QEvent.Type.User)
            # Store data as a property of the event
            event.data = lambda: {
                'type': 'hide_progress',
                'panel': panel
            }
            QApplication.instance().postEvent(self, event)

    def event(self, event):
        """
        Handle custom events from worker threads.

        Args:
            event: The event to handle

        Returns:
            True if the event was handled, False otherwise
        """
        if event.type() == QEvent.Type.User:
            # Get the event data
            data = event.data()

            # Handle different event types
            if isinstance(data, dict):
                event_type = data.get('type')

                if event_type == 'update_results':
                    # Get the parameters
                    panel = data.get('panel')
                    results = data.get('results', [])
                    method = data.get('method', 'unknown')

                    # Display results in the panel
                    if panel and hasattr(panel, 'set_documents'):
                        panel.set_documents(results)

                    # Update the panel title
                    if panel and hasattr(panel, 'title_text'):
                        panel.title_text = f"{method.capitalize()} Search ({len(results)} results)"

                    # Update the status label
                    self._update_status_label()

                    return True

                elif event_type == 'update_hyde_abstract':
                    # Get the abstract
                    abstract = data.get('abstract')

                    # Display the abstract
                    if abstract:
                        self.hyde_abstract_view.setText(abstract)
                        self.hyde_abstract_view.setVisible(True)

                    return True

                elif event_type == 'hide_progress':
                    # Get the panel
                    panel = data.get('panel')

                    # Hide the progress bar
                    if panel == self.left_panel:
                        self.left_progress.setVisible(False)
                    elif panel == self.right_panel:
                        self.right_progress.setVisible(False)

                    return True

                elif event_type == 'search_error':
                    # Get the parameters
                    panel = data.get('panel')
                    error = data.get('error', 'Unknown error')

                    # Log the error
                    logger.error(f"Search error: {error}\n{data.get('traceback', '')}")

                    # Update the panel
                    if panel and hasattr(panel, 'clear'):
                        panel.clear()

                    if panel and hasattr(panel, 'title_text'):
                        panel.title_text = f"Error: {str(error)[:50]}"

                    # Update the status label
                    self._update_status_label()

                    return True

        # Let the base class handle other events
        return super().event(event)

    def _handle_search_results(self, results, panel, method):
        """
        Handle search results from a worker.

        Args:
            results: The search results
            panel: The panel to display results in
            method: The search method used
        """
        try:
            # Handle HyDE results which include the abstract
            if isinstance(results, dict) and 'results' in results and 'abstract' in results:
                # Display the hypothetical abstract
                if results['abstract']:
                    self.hyde_abstract_view.setText(results['abstract'])
                    self.hyde_abstract_view.setVisible(True)

                # Use the actual results
                results = results['results']

            # Make sure results is a list
            if results is None:
                results = []

            # Make a copy of the results to avoid thread issues
            results_copy = list(results)

            # Display results in the panel
            panel.set_documents(results_copy)

            # Update the panel title
            title = f"{method.capitalize()} Search ({len(results_copy)} results)"
            if hasattr(panel, 'title_text'):
                panel.title_text = title

            # Update the status label with counts
            self._update_status_label()
        except Exception as e:
            logger.error(f"Error handling search results: {e}\n{traceback.format_exc()}")
            # Try to recover
            try:
                panel.clear()
                if hasattr(panel, 'title_text'):
                    panel.title_text = f"Error: {str(e)[:50]}"
            except:
                pass

    def _handle_search_error(self, error, traceback_text, panel):
        """
        Handle search error from a worker.

        Args:
            error: The error message
            traceback_text: The error traceback
            panel: The panel where the error occurred
        """
        try:
            logger.error(f"Search error: {error}\n{traceback_text}")

            # Safely clear the panel
            try:
                panel.clear()
            except Exception as e:
                logger.error(f"Error clearing panel: {e}")

            # Safely update the title
            try:
                if hasattr(panel, 'title_text'):
                    panel.title_text = f"Error: {str(error)[:50]}"
            except Exception as e:
                logger.error(f"Error updating panel title: {e}")

            # Safely update the status label
            try:
                self._update_status_label()
            except Exception as e:
                logger.error(f"Error updating status label: {e}")

        except Exception as e:
            # Last resort error handling
            logger.critical(f"Critical error in error handler: {e}\n{traceback.format_exc()}")
            # Try to show something to the user
            try:
                self.status_label.setText(f"Critical error: {str(e)[:50]}")
            except:
                pass

    def _update_status_label(self):
        """
        Update the status label with current result counts and abstract count.
        """
        try:
            # Get the total count of abstract embeddings
            try:
                abstract_count = self._get_abstract_embedding_count()
            except Exception as e:
                logger.error(f"Error getting abstract count: {e}")
                abstract_count = 0

            # Get result counts safely
            try:
                left_count = self.left_panel.title_list.count() if hasattr(self.left_panel, 'title_list') else 0
            except Exception as e:
                logger.error(f"Error getting left panel count: {e}")
                left_count = 0

            try:
                right_count = self.right_panel.title_list.count() if hasattr(self.right_panel, 'title_list') else 0
            except Exception as e:
                logger.error(f"Error getting right panel count: {e}")
                right_count = 0

            # Get method names
            left_method = self.search_settings.get('left_search_method', 'unknown')
            right_method = self.search_settings.get('right_search_method', 'unknown')

            # Update status
            self.status_label.setText(
                f"Found {left_count} {left_method} results and {right_count} {right_method} results "
                f"from {abstract_count:,} abstract embeddings"
            )
        except Exception as e:
            # Last resort error handling
            logger.error(f"Error updating status label: {e}\n{traceback.format_exc()}")
            try:
                self.status_label.setText("Error updating status")
            except:
                pass

    def _perform_keyword_search(self, question: str, panel=None):
        """
        Perform a keyword search using the document database.

        Args:
            question: Question to search for
            panel: Panel to display results in (optional)

        Returns:
            List of search results
        """
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
        ) or []

        # If panel is provided, update its status
        if panel:
            panel.title_text = f"Keyword Search ({len(results)} results)"

        return results

    def _get_abstract_embedding_count(self) -> int:
        """
        Get the total count of abstract embeddings in the database.

        Returns:
            Number of abstract embeddings
        """
        try:
            with get_cursor() as cursor:
                # Get the embedding source ID for 'abstract'
                from localknowledge.db.embedding_source import get_embedding_source_by_name
                embed_source_record = get_embedding_source_by_name(cursor, 'abstract')

                if not embed_source_record:
                    logger.warning("Embedding source 'abstract' not found")
                    return 0

                embed_source_id = embed_source_record['id']

                # Count embeddings for this source
                query = """
                SELECT COUNT(*) as count
                FROM unified_multiembeddings
                WHERE embed_source_id = %s
                """

                cursor.execute(query, (embed_source_id,))
                result = cursor.fetchone()

                if result and 'count' in result:
                    return result['count']
                return 0
        except Exception as e:
            logger.error(f"Error getting abstract embedding count: {e}\n{traceback.format_exc()}")
            return 0

    # This method is no longer used as we now display results directly in _perform_search
    # Keeping it as a reference for now
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

        # Get the total count of abstract embeddings
        abstract_count = self._get_abstract_embedding_count()

        self.status_label.setText(
            f"Found {left_count} results and {right_count} results "
            f"from {abstract_count:,} abstract embeddings"
        )


    def closeEvent(self, event):
        """
        Handle the widget close event.

        Args:
            event: The close event
        """
        # Close the connection pool
        close_pool()
        logger.info("Database connection pool closed")

        # Close database connections
        if hasattr(self, 'doc_db') and self.doc_db:
            self.doc_db.close()

        # Emit the closed signal
        self.closed.emit()

        # Accept the close event
        event.accept()


# Example standalone usage
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    widget = QAWidget()
    widget.resize(1000, 800)
    widget.show()

    sys.exit(app.exec())
