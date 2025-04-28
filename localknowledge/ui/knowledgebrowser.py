"""
This module provides a PySide6 widget for browsing and searching
the local publications database and viewing both PDF and markdown text.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import traceback
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QSize, QPointF, QObject, QRunnable, QThreadPool, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QTextDocument, QAbstractTextDocumentLayout, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QLabel, QMessageBox, QApplication,
    QScrollArea, QStatusBar, QStyledItemDelegate, QStyle,
    QComboBox, QToolButton, QDialog, QFrame, QCheckBox
)

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"
USER_ICON_PATH = "localknowledge/ui/icons/user.png"
BOOK_ICON_PATH = "localknowledge/ui/icons/book.png"
from PySide6.QtWebEngineWidgets import QWebEngineView
import pymupdf4llm

# Import our custom document display widget
from localknowledge.ui.document_display_widget import DocumentDisplayWidget

# Try to import remove_line_numbers
try:
    from localknowledge.medrxiv.remove_line_numbers import remove_sequential_line_numbers
    LINE_NUMBERS_REMOVAL_AVAILABLE = True
except ImportError:
    LINE_NUMBERS_REMOVAL_AVAILABLE = False
    # Define a fallback function if import fails
    def remove_sequential_line_numbers(text):
        return text  # Just return the original text

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.embeddings.embedding_manager import EmbeddingManager
from localknowledge.context import set_current_project

# Try to import rerankers
try:
    from localknowledge.ai.rerankers import get_reranker
    RERANKERS_AVAILABLE = True
except ImportError:
    RERANKERS_AVAILABLE = False
    # Define fallback function
    def get_reranker(model_name):
        return None


class PublicationItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering publication items with source icons and bold titles."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)
        # Load icons
        self.pubmed_icon = QIcon(PUBMED_ICON_PATH)
        self.medrxiv_icon = QIcon(MEDRXIV_ICON_PATH)

        # Load bookmark icons
        self.personal_bookmark_icon = QIcon(USER_ICON_PATH)
        self.project_bookmark_icon = QIcon(BOOK_ICON_PATH)

    def paint(self, painter, option, index):
        """Paint the item with custom formatting."""
        # Get the item data directly from the model
        item = index.model().itemFromIndex(index) if hasattr(index.model(), 'itemFromIndex') else None

        # If we can't get the item directly, try to get it from the list widget
        if not item or not isinstance(item, PublicationItem):
            # Try to get the list widget and the item from it
            list_widget = self.parent()
            if isinstance(list_widget, QListWidget):
                item = list_widget.item(index.row())

            # If we still don't have a valid item, fall back to default rendering
            if not item or not isinstance(item, PublicationItem):
                super().paint(painter, option, index)
                return

        # Get the item data
        item_data = index.data()
        if not item_data:
            super().paint(painter, option, index)
            return

        # Split the text into lines
        lines = item_data.split('\n')
        if len(lines) < 2:
            super().paint(painter, option, index)
            return

        # Extract title, authors, and date
        title = lines[0]
        authors = lines[1] if len(lines) > 1 else ''
        date = lines[2] if len(lines) > 2 else ''

        # Save painter state
        painter.save()

        # Draw selection background if selected
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Calculate icon and text positions
        rect = option.rect.adjusted(5, 5, -5, -5)  # Add some padding
        icon_size = QSize(16, 16)  # Size of the source icon

        # Draw source icon if available
        source_id = item.publication.get('source_id')
        icon_rect = QRect(rect.left(), rect.top() + (rect.height() - icon_size.height()) // 2,
                         icon_size.width(), icon_size.height())

        if source_id == 1:  # PubMed
            self.pubmed_icon.paint(painter, icon_rect)
        elif source_id == 2:  # medRxiv
            self.medrxiv_icon.paint(painter, icon_rect)

        # Draw bookmark icons if this is a bookmarked publication
        bookmark_type = item.publication.get('bookmark_type')
        if bookmark_type:
            # Calculate position for bookmark icons (to the right of the source icon)
            bookmark_icon_rect = QRect(icon_rect.right() + 4, icon_rect.top(),
                                      icon_size.width(), icon_size.height())

            # Draw personal bookmark icon (user emoji)
            if bookmark_type in ('personal', 'both'):
                self.personal_bookmark_icon.paint(painter, bookmark_icon_rect)

            # Draw project bookmark icon (book icon)
            if bookmark_type in ('project', 'both'):
                # If we already drew a personal bookmark icon, move this one to the right
                if bookmark_type == 'both':
                    bookmark_icon_rect = QRect(bookmark_icon_rect.right() + 4, bookmark_icon_rect.top(),
                                             icon_size.width(), icon_size.height())
                self.project_bookmark_icon.paint(painter, bookmark_icon_rect)

        # Calculate text position (after the icons)
        text_left = icon_rect.right() + 8

        # If we have bookmark icons, adjust the text position
        bookmark_type = item.publication.get('bookmark_type')
        if bookmark_type:
            # Add space for one or two bookmark icons
            if bookmark_type == 'both':
                text_left += (icon_size.width() + 4) * 2  # Space for two icons
            else:
                text_left += icon_size.width() + 4  # Space for one icon

        # Calculate text rectangles with adjusted left position
        title_height = painter.fontMetrics().height() + 2
        authors_height = painter.fontMetrics().height() + 2
        date_height = painter.fontMetrics().height()

        title_rect = QRect(text_left, rect.top(), rect.width() - (text_left - rect.left()), title_height)
        authors_rect = QRect(text_left, rect.top() + title_height, rect.width() - (text_left - rect.left()), authors_height)
        date_rect = QRect(text_left, rect.top() + title_height + authors_height, rect.width() - (text_left - rect.left()), date_height)

        # Draw title with bold font
        bold_font = painter.font()
        bold_font.setBold(True)
        painter.setFont(bold_font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        # Draw authors and date with normal font
        normal_font = painter.font()
        normal_font.setBold(False)
        painter.setFont(normal_font)
        painter.drawText(authors_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, authors)
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, date)

        # Restore painter state
        painter.restore()

    def sizeHint(self, option, index):
        """
        Get the size hint for the item.

        Args:
            option: Style options for the item
            index: Model index of the item

        Returns:
            QSize with the recommended size
        """
        size = super().sizeHint(option, index)
        # Make items a bit taller to accommodate icons
        return QSize(size.width(), max(size.height(), 60))


class PublicationItem(QListWidgetItem):
    """List widget item to display publication details and store publication data."""

    def __init__(self, publication: Dict[str, Any]):
        """
        Initialize a publication list item.

        Args:
            publication: Dictionary containing publication data
        """
        self.publication = publication

        # Create display text without HTML formatting
        title = publication.get('title', 'No Title')

        # Handle authors which is a list in the document structure
        authors = publication.get('authors', [])
        if authors:
            authors_str = ', '.join(authors)
        else:
            authors_str = 'Unknown Authors'

        # Handle date which is publication_date in the document structure
        date = publication.get('publication_date', '')
        if hasattr(date, 'strftime'):  # If it's a datetime object
            date = date.strftime('%Y-%m-%d')

        similarity = publication.get('similarity', '')

        # Add source tag if available
        source_name = publication.get('source_name', '')
        source_tag = f"[{source_name}] " if source_name else ""

        # Truncate the title if it's too long
        if len(title) > 80:
            title = title[:77] + "..."

        # Format display text without HTML tags
        if similarity:
            display_text = f"{source_tag}{title}\n{authors_str[:100]}{'...' if len(authors_str) > 100 else ''}\n{date} | Similarity: {similarity}"
        else:
            display_text = f"{source_tag}{title}\n{authors_str[:100]}{'...' if len(authors_str) > 100 else ''}\n{date}"

        # Initialize the item with display text
        super().__init__(display_text)

        # Make the item slightly taller for better readability
        self.setSizeHint(QSize(self.sizeHint().width(), self.sizeHint().height() + 10))

        # Set tooltip to show full title, authors, and bookmark status on hover
        tooltip = f"{publication.get('title', 'No Title')}\n{authors_str}"

        # Add bookmark information to tooltip if available
        bookmark_type = publication.get('bookmark_type')
        if bookmark_type:
            if bookmark_type == 'personal':
                tooltip += "\n\nPersonal bookmark"
            elif bookmark_type == 'project':
                tooltip += "\n\nProject bookmark"
            elif bookmark_type == 'both':
                tooltip += "\n\nPersonal and project bookmark"

        self.setToolTip(tooltip)


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

        self.db_manager = DocumentDatabaseManager()

        # Try to initialize the embedding manager, but make it optional
        self.embedding_manager = None
        try:
            # Just create the manager but don't test it yet
            self.embedding_manager = EmbeddingManager()
            print("Semantic search enabled")
        except Exception as e:
            print(f"Semantic search disabled: {e}")

        # Default search settings
        self.search_settings = {
            'similarity_threshold': 0.3,
            'max_results': 20,
            'use_reranker': False,
            'reranker_model': 'BAAI/bge-reranker-base',
            'hybrid_weight': 0.5,
            'embedding_model': 'snowflake-arctic-embed2:latest',
            'use_hyde': False,
            'hyde_model': 'gemma3:4b'
        }

        # Search sources
        self.search_sources = {
            'pubmed': True,
            'medrxiv': True
        }

        # Search strategies
        self.search_strategies = {
            'keyword': True,
            'semantic': True,
            'hybrid': True,
            'bm25': False
        }

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

        # Default user ID - in a real app, this would come from user authentication
        self.user_id = 1

        # Current project ID for project bookmarks
        self.current_project_id = None

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Create a status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")

        # Search area at top
        search_layout = QHBoxLayout()

        # Search input field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter research question or keywords (comma separated or use quotes)")
        self.search_input.returnPressed.connect(self._on_search)

        # Search mode selection
        self.search_mode = QComboBox()
        self.search_mode.addItem("Keyword Search", "keyword")
        self.search_mode.addItem("Semantic Search", "semantic")
        self.search_mode.addItem("Hybrid Search", "hybrid")
        self.search_mode.addItem("Bookmarked", "bookmarked")
        self.search_mode.setToolTip("Keyword search uses exact matching. Semantic search uses AI to find related content. Hybrid search combines both approaches.")

        # Disable semantic and hybrid search if embedding manager is not available
        if not self.embedding_manager:
            # Find the indices of the semantic and hybrid search options
            semantic_index = self.search_mode.findData("semantic")
            hybrid_index = self.search_mode.findData("hybrid")

            # Create a model for the combo box
            model = self.search_mode.model()

            # Disable semantic search
            if semantic_index >= 0:
                item = model.item(semantic_index)
                item.setEnabled(False)

            # Disable hybrid search
            if hybrid_index >= 0:
                item = model.item(hybrid_index)
                item.setEnabled(False)

        # When search mode changes, update the placeholder text and trigger search for bookmarks
        self.search_mode.currentIndexChanged.connect(self._on_search_mode_changed)

        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)

        # Settings button
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Search Settings")
        self.settings_button.clicked.connect(self._show_search_settings)

        search_layout.addWidget(self.search_mode)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.settings_button)

        # Splitter for results and document view
        self.splitter = QSplitter(Qt.Horizontal)

        # Left side - publication list
        self.publication_list = QListWidget()
        self.publication_list.currentItemChanged.connect(self._on_publication_selected)
        self.publication_list.setAlternatingRowColors(True)

        # Set custom delegate for rendering items with source icons and bold titles
        self.publication_item_delegate = PublicationItemDelegate(self.publication_list)
        self.publication_list.setItemDelegate(self.publication_item_delegate)

        # Set item height to accommodate icons
        self.publication_list.setIconSize(QSize(16, 16))

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

        # Right side - document display widget
        self.document_display = DocumentDisplayWidget(
            parent=self,
            status_bar=self.status_bar,
            db_manager=self.db_manager,
            pdf_base_dir=self.pdf_base_dir
        )

        # Connect signals from the document display widget
        self.document_display.documentRated.connect(self._on_document_rated)
        self.document_display.documentBookmarked.connect(self._on_document_bookmarked)

        # Add widgets to splitter
        self.splitter.addWidget(self.publication_list)
        self.splitter.addWidget(self.document_display)

        # Set initial sizes (40% for list, 60% for document)
        self.splitter.setSizes([400, 600])

        # Add layouts to main layout
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.splitter, 1)  # 1 means this will expand to fill available space
        main_layout.addWidget(self.status_bar)

        # Set window properties
        self.setWindowTitle("Knowledge Browser")
        self.resize(1200, 800)

    @Slot(int)
    def _on_search_mode_changed(self, _):
        """Handle search mode changes."""
        # Update placeholder text
        self._update_search_placeholder()

        # If bookmarked mode is selected, immediately show all bookmarks
        search_mode = self.search_mode.currentData()
        if search_mode == "bookmarked":
            print("Bookmarked mode selected - automatically showing all bookmarked items")
            QApplication.processEvents()  # Process any pending events before starting the search
            self._perform_bookmarked_search()

    def _update_search_placeholder(self):
        """Update the search input placeholder text based on the selected search mode."""
        search_mode = self.search_mode.currentData()

        if search_mode == "keyword":
            self.search_input.setPlaceholderText("Enter keywords (comma separated or use quotes)")
        elif search_mode == "semantic":
            self.search_input.setPlaceholderText("Enter a question or description of what you're looking for")
        elif search_mode == "hybrid":
            self.search_input.setPlaceholderText("Enter keywords or a question to search using both methods")
        elif search_mode == "bookmarked":
            self.search_input.setPlaceholderText("Filter bookmarked publications (leave empty to show all)")
        else:
            self.search_input.setPlaceholderText("Enter search terms")

    def _show_search_settings(self):
        """Show the search settings dialog."""
        # Import the settings widget
        from localknowledge.ui.knowledgebrowser_settings import KnowledgeBrowserSettings

        # Create a settings dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Knowledge Browser Settings")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)

        # Create layout
        layout = QVBoxLayout(dialog)

        # Create settings widget with current settings
        settings_widget = KnowledgeBrowserSettings(
            dialog,
            {
                'sources': self.search_sources,
                'search_strategies': self.search_strategies,
                'semantic_settings': self.search_settings,
                'hybrid_settings': {
                    'semantic_weight': self.search_settings.get('hybrid_weight', 0.5)
                }
            }
        )

        # Connect settings changed signal
        settings_widget.settingsChanged.connect(self._on_settings_changed)

        # Add settings widget to dialog
        layout.addWidget(settings_widget)

        # Show the dialog
        dialog.exec()

    @Slot(dict)
    def _on_settings_changed(self, settings):
        """Handle settings changes."""
        # Update search settings
        self.search_settings.update(settings['semantic_settings'])
        self.search_settings['hybrid_weight'] = settings['hybrid_settings']['semantic_weight']

        # Update search sources
        self.search_sources = settings['sources']

        # Update search strategies
        self.search_strategies = settings['search_strategies']

        print(f"Updated search settings: {self.search_settings}")

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
        # Get the current search mode
        search_mode = self.search_mode.currentData()
        search_text = self.search_input.text().strip()

        # For bookmarked search, we don't require search text
        if not search_text and search_mode != "bookmarked":
            return

        # Show a message that we're searching
        self.publication_list.clear()
        self.publication_list.addItem("Searching...")
        QApplication.processEvents()

        try:
            if search_mode == "keyword":
                # Keyword search - use the existing database search
                self._perform_keyword_search(search_text)
            elif search_mode == "semantic":
                # Semantic search - use the embedding manager
                self._perform_semantic_search(search_text)
            elif search_mode == "hybrid":
                # Hybrid search - combine keyword and semantic search
                self._perform_hybrid_search(search_text)
            elif search_mode == "bookmarked":
                # Bookmarked search - show bookmarked publications
                self._perform_bookmarked_search(search_text)
            else:
                # Unknown search mode
                raise ValueError(f"Unknown search mode: {search_mode}")

        except Exception as e:
            self.publication_list.clear()
            self.publication_list.addItem(f"Search Error: {str(e)}")
            QMessageBox.critical(self, "Search Error", f"An error occurred during search: {str(e)}")

    def _perform_keyword_search(self, search_text):
        """
        Perform a keyword-based search using the document database manager in a background thread.

        This method parses the search text to extract include and exclude terms, then creates a
        KeywordSearchWorker to perform the search in the background.

        Include terms are comma-separated.
        Exclude terms are prefixed with a minus sign (-).

        Example: "covid, vaccine, -children, -pediatric" will search for documents containing
        "covid" or "vaccine" but not containing "children" or "pediatric".
        """
        # Check if the search text is empty
        if not search_text.strip():
            self.publication_list.clear()
            self.publication_list.addItem("Please enter search terms.")
            return

        # Parse the search text to extract include and exclude terms
        include_terms = []
        exclude_terms = []

        # Split the search text by commas
        parts = search_text.split(',')

        # Process each part
        for part in parts:
            part = part.strip()
            if part.startswith('-'):
                # This is an exclude term
                term = part[1:].strip()
                if term:
                    exclude_terms.append(term)
            elif part:
                # This is an include term
                include_terms.append(part)

        # If no include terms, show an error
        if not include_terms:
            self.publication_list.clear()
            self.publication_list.addItem("Please enter at least one search term.")
            return

        # Join the include terms with commas for the query
        query = ', '.join(include_terms)

        # Get source filter based on settings
        source_name = None
        if self.search_sources.get('medrxiv', True) and not self.search_sources.get('pubmed', True):
            source_name = 'medrxiv'
        elif self.search_sources.get('pubmed', True) and not self.search_sources.get('medrxiv', True):
            source_name = 'pubmed'
        # If both are True or both are False, don't filter by source

        # Show a loading message
        self.publication_list.clear()
        self.publication_list.addItem("Searching...")
        QApplication.processEvents()  # Ensure the UI updates

        # Create a worker for the keyword search using the array operator pattern
        worker = KeywordSearchWorker(
            db_manager=self.db_manager,
            query=query,
            source_name=source_name,
            limit=self.search_settings.get('max_results', 20),
            exclude_terms=exclude_terms if exclude_terms else None
        )

        # Connect signals
        worker.signals.result.connect(self._handle_keyword_search_results)
        worker.signals.error.connect(self._handle_keyword_search_error)

        # Execute the worker
        self.threadpool.start(worker)

    def _handle_keyword_search_results(self, publications):
        """Handle the results from keyword search."""
        # Store the search query for reference
        self.last_search_query = "keyword"
        self.last_search_text = self.search_input.text().strip()

        # Display the results
        self._display_search_results(publications)

    def _handle_keyword_search_error(self, error_msg, traceback_str):
        """Handle errors from the keyword search worker."""
        self.publication_list.clear()
        self.publication_list.addItem(f"Search Error: {error_msg}")
        print(f"Keyword search error: {error_msg}\n{traceback_str}")



    def _perform_semantic_search(self, search_text):
        """Perform a semantic search using the embedding manager."""
        # Check if embedding manager is available
        if not self.embedding_manager:
            self.publication_list.clear()
            self.publication_list.addItem("Semantic search is not available. Please install Ollama and required models.")
            return

        # Get source filter based on settings
        source_id = None
        if self.search_sources.get('medrxiv', True) and not self.search_sources.get('pubmed', True):
            source_id = 'medrxiv'
        elif self.search_sources.get('pubmed', True) and not self.search_sources.get('medrxiv', True):
            source_id = 'pubmed'
        # If both are True or both are False, don't filter by source

        # Create a worker for the semantic search
        worker = SemanticSearchWorker(
            embedding_manager=self.embedding_manager,
            query=search_text,
            limit=self.search_settings['max_results'],
            threshold=self.search_settings['similarity_threshold'],
            source_id=source_id
        )

        # Connect signals
        worker.signals.result.connect(self._handle_semantic_search_results)
        worker.signals.error.connect(self._handle_semantic_search_error)

        # Execute the worker
        self.threadpool.start(worker)

    def _handle_semantic_search_results(self, results):
        """Handle the results from semantic search."""
        self.publication_list.clear()

        if not results:
            self.publication_list.addItem("No semantic search results found.")
            return

        # Check if there's an error in the results
        if len(results) == 1 and 'error' in results[0]:
            error_msg = results[0].get('text', 'Unknown error')
            self.publication_list.addItem(f"Error: {error_msg}")
            QMessageBox.warning(self, "Semantic Search Error", error_msg)
            return

        # For each result, try to find the corresponding publication in the database
        found_publications = []
        for result in results:
            document_id = result.get('document_id')
            similarity = result.get('similarity', 0)
            chunk_text = result.get('text', '')

            # Format similarity as percentage
            similarity_pct = f"{similarity * 100:.1f}%"

            try:
                # Get the document by ID if it's numeric
                if isinstance(document_id, int) or (isinstance(document_id, str) and document_id.isdigit()):
                    doc_id = document_id if isinstance(document_id, int) else int(document_id)
                    query = """
                    SELECT d.*, s.name as source_name, c.name as category_name
                    FROM document d
                    JOIN sources s ON d.source_id = s.id
                    LEFT JOIN categories c ON d.category_id = c.id
                    WHERE d.id = %s
                    """
                    result = self.db_manager.execute(query, (doc_id,))
                    if result:
                        publication = result[0]
                    else:
                        # Try to get by DOI if it's a string
                        if isinstance(document_id, str):
                            publication = self.db_manager.get_document_by_doi(document_id)
                        else:
                            publication = None
                else:
                    # Try to get by DOI
                    publication = self.db_manager.get_document_by_doi(document_id)

                if publication:
                    # Create a publication item with the similarity score added
                    publication['similarity'] = similarity_pct
                    publication['similarity_value'] = similarity  # Store raw value for sorting
                    publication['matched_text'] = chunk_text
                    found_publications.append(publication)
                else:
                    print(f"Could not find publication {document_id} in database")
            except Exception as e:
                print(f"Error retrieving publication {document_id}: {e}")

        # Store the search query for reference
        self.last_search_query = "semantic"
        self.last_search_text = self.search_input.text().strip()

        # If reranking is enabled and available, rerank the results
        if RERANKERS_AVAILABLE and self.search_settings.get('use_reranker', False) and found_publications:
            self.publication_list.clear()
            self.publication_list.addItem("Reranking results...")
            QApplication.processEvents()

            # Create a worker for reranking
            worker = RerankerWorker(
                query=self.last_search_text,
                documents=found_publications,
                reranker_model=self.search_settings.get('reranker_model', 'BAAI/bge-reranker-base')
            )

            # Connect signals
            worker.signals.result.connect(self._handle_reranking_results)
            worker.signals.error.connect(self._handle_reranking_error)

            # Execute the worker
            self.threadpool.start(worker)
        else:
            # Display the results without reranking
            self._display_search_results(found_publications)

    def _handle_reranking_results(self, reranked_docs):
        """Handle the results from reranking."""
        self._display_search_results(reranked_docs, reranked=True)

    def _handle_reranking_error(self, error_msg, traceback_str):
        """Handle errors from the reranking worker."""
        self.publication_list.clear()
        self.publication_list.addItem(f"Reranking Error: {error_msg}")
        print(f"Reranking error: {error_msg}\n{traceback_str}")

        # Fall back to displaying the original results
        if hasattr(self, 'last_search_results'):
            self._display_search_results(self.last_search_results)

    def _display_search_results(self, publications, reranked=False):
        """Display search results in the publication list."""
        self.publication_list.clear()

        if not publications:
            self.publication_list.addItem("No results found.")
            return

        # Add each publication to the list
        for pub in publications:
            item = PublicationItem(pub)
            self.publication_list.addItem(item)

        # Update status bar with result count based on search type
        search_type = getattr(self, 'last_search_query', 'search')

        if search_type == "keyword":
            self.status_bar.showMessage(f"Found {len(publications)} publications matching keyword search")
        elif search_type == "semantic":
            if reranked:
                self.status_bar.showMessage(f"Found {len(publications)} publications matching semantic search (reranked)")
            else:
                self.status_bar.showMessage(f"Found {len(publications)} publications matching semantic search")
        else:
            self.status_bar.showMessage(f"Found {len(publications)} publications")

        # Store the results for potential fallback
        self.last_search_results = publications

    def _perform_hybrid_search(self, search_text):
        """Perform a hybrid search combining keyword and semantic search."""
        # Check if embedding manager is available
        if not self.embedding_manager:
            self.publication_list.clear()
            self.publication_list.addItem("Hybrid search requires semantic search capabilities. Please install Ollama and required models.")
            return

        # Create a worker for the hybrid search
        worker = HybridSearchWorker(
            db_manager=self.db_manager,
            embedding_manager=self.embedding_manager,
            query=search_text,
            search_settings=self.search_settings
        )

        # Connect signals
        worker.signals.result.connect(self._handle_hybrid_search_results)
        worker.signals.error.connect(self._handle_hybrid_search_error)

        # Execute the worker
        self.threadpool.start(worker)

    def _handle_hybrid_search_results(self, result):
        """Handle the results from hybrid search."""
        self.publication_list.clear()

        combined_results = result.get('combined_results', [])
        keyword_count = result.get('keyword_count', 0)
        semantic_count = result.get('semantic_count', 0)
        reranked = result.get('reranked', False)

        if not combined_results:
            self.publication_list.addItem("No results found.")
            return

        # Store the search query for reference
        self.last_search_query = "hybrid"
        self.last_search_text = self.search_input.text().strip()

        # Add each publication to the list
        for pub in combined_results:
            item = PublicationItem(pub)
            self.publication_list.addItem(item)

        # Update status bar with result count
        status_msg = f"Found {len(combined_results)} publications from hybrid search "
        status_msg += f"(Keyword: {keyword_count}, Semantic: {semantic_count})"

        if reranked:
            status_msg += " (reranked)"

        self.status_bar.showMessage(status_msg)

        # Store the results for potential fallback
        self.last_search_results = combined_results

    def _handle_hybrid_search_error(self, error_msg, traceback_str):
        """Handle errors from the hybrid search worker."""
        self.publication_list.clear()
        self.publication_list.addItem(f"Search Error: {error_msg}")
        print(f"Hybrid search error: {error_msg}\n{traceback_str}")

    def _handle_semantic_search_error(self, error_msg, traceback_str):
        """Handle errors from the semantic search worker."""
        self.publication_list.clear()
        self.publication_list.addItem(f"Search Error: {error_msg}")
        print(f"Semantic search error: {error_msg}\n{traceback_str}")

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_publication_selected(self, current, _):
        """
        Handle publication selection in the list.

        Args:
            current: Currently selected item
            _previous: Previously selected item (unused)
        """
        if not current or not isinstance(current, PublicationItem):
            return

        # Get the publication data
        self.current_publication = current.publication

        # Emit the signal with the selected publication
        self.publicationSelected.emit(self.current_publication)

        # Update status bar with publication info
        title = self.current_publication.get('title', 'Unknown Title')
        if len(title) > 50:
            title = title[:47] + '...'

        # If this is a semantic or hybrid search result, show similarity in status bar
        if (hasattr(self, 'last_search_query') and
            self.last_search_query in ['semantic', 'hybrid'] and
            'similarity' in self.current_publication):

            similarity = self.current_publication.get('similarity', '')
            source = self.current_publication.get('search_source', '')
            status_msg = f"Publication: {title} | Similarity: {similarity}"

            # Add source information for hybrid search
            if self.last_search_query == 'hybrid':
                if source == 'both':
                    status_msg += " (found by both keyword and semantic search)"
                elif source == 'keyword':
                    status_msg += " (found by keyword search)"
                elif source == 'semantic':
                    status_msg += " (found by semantic search)"

            self.status_bar.showMessage(status_msg)
        else:
            self.status_bar.showMessage(f"Publication: {title}")

        # Display the publication in the document display widget
        self.document_display.display_document(self.current_publication)

    def _load_publication_content(self):
        """Load the selected publication's PDF and markdown content into the tabs."""
        if not self.current_publication:
            return

        # Get the local PDF path from the pdf_filename field
        local_pdf_path = self.current_publication.get('pdf_filename', '')

        # Try to load PDF
        pdf_found = False

        # First case: We have a local PDF path in the database
        if local_pdf_path:
            # Convert to string and ensure proper path handling
            if isinstance(self.pdf_base_dir, Path):
                full_pdf_path = self.pdf_base_dir / local_pdf_path
            else:
                # If pdf_base_dir is a string, create a path object
                full_pdf_path = Path(os.path.join(self.pdf_base_dir, local_pdf_path))

            if full_pdf_path.exists():
                # Load the PDF using our PDFViewer widget
                pdf_path = str(full_pdf_path)
                if self.pdf_viewer.load_pdf(pdf_path):
                    # Explicitly set the tab to PDF view
                    self.tab_widget.setCurrentIndex(0)
                    pdf_found = True
                else:
                    print(f"Error loading PDF: {pdf_path}")

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

                    # Load the PDF using our PDFViewer widget
                    if self.pdf_viewer.load_pdf(pdf_path):
                        self.tab_widget.setCurrentIndex(0)  # Show PDF tab
                    else:
                        print(f"Error loading PDF: {pdf_path}")
                        continue

                    # Update the database with the correct path
                    try:
                        # Update the document with the new PDF path
                        query = """
                        UPDATE document
                        SET pdf_filename = %s, updated_date = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """
                        self.db_manager.execute(query, (filename, self.current_publication['id']), commit=True)
                        print(f"Updated database with path: {filename}")
                    except Exception as e:
                        print(f"Failed to update database: {e}")

                    pdf_found = True

                    # No need to highlight search keywords here - handled by PDFViewer
                    break

        # Enable or disable the PDF tab based on whether a PDF was found
        pdf_tab_index = 0  # Assuming PDF tab is the first tab
        self.tab_widget.setTabEnabled(pdf_tab_index, pdf_found)

        # If we couldn't find the PDF, close the PDF viewer
        if not pdf_found:
            print("PDF not found by any method")
            self.pdf_viewer.close_pdf()
            # Switch to the text tab
            self.tab_widget.setCurrentIndex(1)  # Assuming text tab is the second tab

        # Check for existing markdown text
        full_text = self.current_publication.get('full_text', '')

        if full_text:
            # Display existing markdown text
            self._display_markdown(full_text)
        else:
            # Try to extract text if we have a PDF
            if pdf_found and local_pdf_path and Path(self.pdf_base_dir / local_pdf_path).exists():
                try:
                    self._extract_and_display_markdown(str(self.pdf_base_dir / local_pdf_path))
                except Exception as e:
                    self._display_markdown(f"Error extracting text from PDF: {str(e)}")
            else:
                # If no full text and no PDF, display the abstract
                self._display_formatted_abstract()

    def _display_formatted_abstract(self):
        """Format and display the abstract of the current publication."""
        if not self.current_publication:
            return

        # Get publication details
        title = self.current_publication.get('title', 'No Title')
        abstract = self.current_publication.get('abstract', '')

        # Handle authors which is a list in the document structure
        authors = self.current_publication.get('authors', [])
        if authors:
            authors_str = ', '.join(authors)
        else:
            authors_str = 'Unknown Authors'

        # Get publication date
        pub_date = self.current_publication.get('publication_date', '')
        if hasattr(pub_date, 'strftime'):  # If it's a datetime object
            pub_date = pub_date.strftime('%Y-%m-%d')

        # Get journal/source information
        journal = self.current_publication.get('journal', '')
        source_name = self.current_publication.get('source_name', '')
        doi = self.current_publication.get('doi', '')

        # Build the formatted markdown
        markdown_text = f"# {title}\n\n"
        markdown_text += f"**Authors:** {authors_str}\n\n"

        if journal:
            markdown_text += f"**Journal:** {journal}\n\n"

        if pub_date:
            markdown_text += f"**Publication Date:** {pub_date}\n\n"

        if source_name:
            markdown_text += f"**Source:** {source_name}\n\n"

        if doi:
            markdown_text += f"**DOI:** [{doi}](https://doi.org/{doi})\n\n"

        markdown_text += "## Abstract\n\n"

        if abstract:
            markdown_text += abstract
        else:
            markdown_text += "*No abstract available for this publication.*"

        # Display the formatted abstract
        self._display_markdown(markdown_text)

        # Switch to the markdown tab
        self.tab_widget.setCurrentIndex(1)

    def _show_pdf_not_found(self):
        """Show a placeholder when PDF is not available."""
        # Close the PDF in our viewer
        self.pdf_viewer.close_pdf()

        # Display the abstract instead of a "PDF not found" message
        self._display_formatted_abstract()

    def _on_search_completed(self, match_count):
        """Handle search completion from the PDF viewer.

        Args:
            match_count: Number of matches found
        """
        # This method is called when the PDF viewer completes a search
        # We can use it to update the UI or perform additional actions
        if match_count > 0:
            print(f"PDF search completed: {match_count} matches found")
        else:
            print("PDF search completed: No matches found")

    def _display_matched_text(self, text: str):
        """Display the matched text from semantic search with highlighting."""
        # Determine the source of the match
        source = "Semantic Search"
        if hasattr(self, 'last_search_query') and self.last_search_query == 'hybrid':
            search_source = self.current_publication.get('search_source', '')
            if search_source == 'both':
                source = "Hybrid Search (Keyword + Semantic)"
            elif search_source == 'semantic':
                source = "Hybrid Search (Semantic Match)"
            elif search_source == 'keyword':
                source = "Hybrid Search (Keyword Match)"
            else:
                source = "Hybrid Search"

        # Create a markdown version with the matched text highlighted
        markdown_text = f"# Matched Text from {source}\n\n```\n{text}\n```\n\n"

        # Display the markdown
        self._display_markdown(markdown_text)

        # Switch to the markdown tab
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

        # Save the markdown to the database if we have a DOI and current publication
        if doi and self.current_publication and 'id' in self.current_publication:
            try:
                # Update the document with the extracted text
                query = """
                UPDATE document
                SET full_text = %s, updated_date = CURRENT_TIMESTAMP
                WHERE id = %s
                """
                self.db_manager.execute(query, (markdown_text, self.current_publication['id']), commit=True)
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

    def _check_bookmark_status(self):
        """Check if the current publication is bookmarked."""
        # This method is now handled by the document display widget
        pass

    def _toggle_personal_bookmark(self, state):
        """Toggle personal bookmark for the current publication."""
        # This method is now handled by the document display widget
        pass

    def _toggle_project_bookmark(self, state):
        """Toggle project bookmark for the current publication."""
        # This method is now handled by the document display widget
        pass

    def _on_document_rated(self, document, rating):
        """
        Handle document rating from the document display widget.

        Args:
            document: Document data dictionary
            rating: Rating value (1 for positive, -1 for negative)
        """
        # The document display widget already handles the database update,
        # so we just need to update the UI if needed
        self.status_bar.showMessage(f"Document rated {'positively' if rating > 0 else 'negatively'}")

    def _on_document_bookmarked(self, document, bookmark_type, is_bookmarked):
        """
        Handle document bookmarking from the document display widget.

        Args:
            document: Document data dictionary
            bookmark_type: Type of bookmark ("personal" or "project")
            is_bookmarked: Whether the document was bookmarked or unbookmarked
        """
        # The document display widget already handles the database update,
        # so we just need to update the UI if needed
        action = "bookmarked" if is_bookmarked else "unbookmarked"
        self.status_bar.showMessage(f"Document {action} as {bookmark_type}")

    def set_current_project(self, project_id):
        """Set the current project ID for project bookmarks."""
        self.current_project_id = project_id

        # Update context with the new project ID
        set_current_project(project_id)

        # Print debug info
        print(f"Setting current project to {project_id}, checkbox enabled: {self.project_bookmark_cb.isEnabled()}")

        # If a publication is selected, check its bookmark status
        if self.current_publication:
            self._check_bookmark_status()
        else:
            # Even if no publication is selected, we should update the UI
            # to reflect the current project state
            self.project_bookmark_cb.setEnabled(project_id is not None)
            self.project_bookmark_cb.setChecked(False)

    def _perform_bookmarked_search(self, filter_text=None):
        """Perform a search for bookmarked publications."""
        # Show a loading message
        self.publication_list.clear()
        self.publication_list.addItem("Loading bookmarked publications...")
        QApplication.processEvents()  # Ensure the UI updates

        # Create a worker for the bookmarked search
        worker = BookmarkedSearchWorker(
            db_manager=self.db_manager,
            user_id=self.user_id,
            project_id=self.current_project_id,
            filter_text=filter_text,
            limit=self.search_settings.get('max_results', 100)  # Increased limit for bookmarks
        )

        # Connect signals
        worker.signals.result.connect(self._handle_bookmarked_search_results)
        worker.signals.error.connect(self._handle_bookmarked_search_error)

        # Execute the worker
        self.threadpool.start(worker)

    def _handle_bookmarked_search_results(self, publications):
        """Handle the results from bookmarked search."""
        # Store the search query for reference
        self.last_search_query = "bookmarked"
        self.last_search_text = self.search_input.text().strip()

        # Display the results
        self._display_search_results(publications)

    def _handle_bookmarked_search_error(self, error_msg, traceback_str):
        """Handle errors from the bookmarked search worker."""
        self.publication_list.clear()
        self.publication_list.addItem(f"Search Error: {error_msg}")
        print(f"Bookmarked search error: {error_msg}\n{traceback_str}")

    def close_database(self):
        """Close the database connections."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        if hasattr(self, 'embedding_manager') and self.embedding_manager:
            self.embedding_manager.close()

    # PDF-related methods are now handled by the PDFViewer widget



class WorkerSignals(QObject):
    """
    Defines signals available from a running worker thread.
    """
    finished = Signal()
    error = Signal(str, str)  # (error message, traceback)
    result = Signal(object)
    progress = Signal(int, int)  # current count, total count
    status = Signal(str)  # status message


class KeywordSearchWorker(QRunnable):
    """
    Worker thread for keyword search.
    """

    def __init__(self, db_manager, query, source_name=None, limit=20, offset=0, exclude_terms=None):
        """
        Initialize the worker.

        Args:
            db_manager: DocumentDatabaseManager instance
            query: Search query
            source_name: Filter by source name (optional)
            limit: Maximum number of results to return
            offset: Offset for pagination
            exclude_terms: Terms to exclude from search results (optional)
        """
        super().__init__()
        self.db_manager = db_manager
        self.query = query
        self.source_name = source_name
        self.limit = limit
        self.offset = offset
        self.exclude_terms = exclude_terms
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Perform the keyword search.
        """
        try:
            print(f"KeywordSearchWorker: Starting search with query: {self.query}")
            print(f"KeywordSearchWorker: Source filter: {self.source_name}")
            print(f"KeywordSearchWorker: Limit: {self.limit}")
            if self.exclude_terms:
                print(f"KeywordSearchWorker: Exclude terms: {self.exclude_terms}")

            # Perform the search using the document database manager with the array operator pattern
            publications = self.db_manager.search_documents(
                search_text=self.query,
                source_name=self.source_name,
                limit=self.limit,
                offset=self.offset,
                exclude_terms=self.exclude_terms
            )

            # Check if we got any results
            if publications:
                print(f"KeywordSearchWorker: Search completed, found {len(publications)} results")
                # Emit the result
                self.signals.result.emit(publications)
                print("KeywordSearchWorker: Results emitted")
            else:
                print("KeywordSearchWorker: Search completed, no results found")
                # Emit an empty result set
                self.signals.result.emit([])
                print("KeywordSearchWorker: Empty results emitted")

        except TimeoutError as e:
            # Handle timeout specifically
            print(f"KeywordSearchWorker: Search timed out: {e}")

            # Emit a timeout error
            self.signals.error.emit("Search timed out. Please try a more specific query.",
                                   "The search took too long to complete. This might be due to a complex query or database load.")
            print("KeywordSearchWorker: Timeout error emitted")

        except Exception as e:
            # Get the traceback
            import traceback
            trace = traceback.format_exc()

            print(f"KeywordSearchWorker: Error during search: {e}")
            print(trace)

            # Emit the error
            self.signals.error.emit(str(e), trace)
            print("KeywordSearchWorker: Error emitted")

        finally:
            # Always emit finished signal
            self.signals.finished.emit()
            print("KeywordSearchWorker: Finished signal emitted")


class SemanticSearchWorker(QRunnable):
    """
    Worker thread for performing semantic search.
    """

    def __init__(self, embedding_manager, query, limit=10, threshold=0.7, source_id=None):
        """
        Initialize the worker.

        Args:
            embedding_manager: EmbeddingManager instance
            query: Search query text
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (optional)
        """
        super().__init__()
        self.embedding_manager = embedding_manager
        self.query = query
        self.limit = limit
        self.threshold = threshold
        self.source_id = source_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Perform semantic search.
        """
        try:
            # Perform the search
            results = self.embedding_manager.search(
                query=self.query,
                limit=self.limit,
                threshold=self.threshold,
                source_id=self.source_id
            )

            # Emit the result
            self.signals.result.emit(results)

        except Exception as e:
            # Get the traceback
            import traceback
            trace = traceback.format_exc()

            # Emit the error
            self.signals.error.emit(str(e), trace)

        finally:
            # Always emit finished signal
            self.signals.finished.emit()


class RerankerWorker(QRunnable):
    """
    Worker thread for reranking search results.
    """

    def __init__(self, query, documents, reranker_model):
        """
        Initialize the worker.

        Args:
            query: The search query
            documents: List of document dictionaries to rerank
            reranker_model: Name of the reranker model to use
        """
        super().__init__()
        self.query = query
        self.documents = documents
        self.reranker_model = reranker_model
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Rerank the documents.
        """
        try:
            # Import the reranker module
            from localknowledge.ai.rerankers import get_reranker

            # Get the reranker
            reranker = get_reranker(self.reranker_model)

            if not reranker:
                raise ValueError(f"Reranker model '{self.reranker_model}' not found")

            # Rerank the documents
            reranked_docs = reranker.rerank(self.query, self.documents)

            # Emit the result
            self.signals.result.emit(reranked_docs)

        except Exception as e:
            # Get the traceback
            import traceback
            trace = traceback.format_exc()

            # Emit the error
            self.signals.error.emit(str(e), trace)

        finally:
            # Always emit finished signal
            self.signals.finished.emit()


class BookmarkedSearchWorker(QRunnable):
    """
    Worker thread for searching bookmarked publications.
    """

    def __init__(self, db_manager, user_id, project_id=None, filter_text=None, limit=20, offset=0):
        """
        Initialize the worker.

        Args:
            db_manager: Database manager instance
            user_id: User ID
            project_id: Project ID (optional)
            filter_text: Text to filter results (optional)
            limit: Maximum number of results to return
            offset: Offset for pagination
        """
        super().__init__()
        self.db_manager = db_manager
        self.user_id = user_id
        self.project_id = project_id
        self.filter_text = filter_text
        self.limit = limit
        self.offset = offset
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Perform the bookmarked search.
        """
        try:
            print(f"BookmarkedSearchWorker: Starting search for user {self.user_id}")
            if self.project_id:
                print(f"BookmarkedSearchWorker: Project filter: {self.project_id}")
            if self.filter_text:
                print(f"BookmarkedSearchWorker: Text filter: {self.filter_text}")

            # Get all personal bookmarks
            print(f"BookmarkedSearchWorker: Getting personal bookmarks for user {self.user_id}")
            personal_bookmarks = self.db_manager.get_bookmarked_documents(
                user_id=self.user_id,
                project_id=None,
                limit=self.limit,
                offset=self.offset
            )
            print(f"BookmarkedSearchWorker: Found {len(personal_bookmarks)} personal bookmarks")

            # Mark these as personal bookmarks
            for pub in personal_bookmarks:
                pub['bookmark_type'] = pub.get('bookmark_type', 'personal')

            # Get project bookmarks if a project is selected
            project_bookmarks = []
            if self.project_id:
                print(f"BookmarkedSearchWorker: Getting project bookmarks for project {self.project_id}")
                project_bookmarks = self.db_manager.get_bookmarked_documents(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    limit=self.limit,
                    offset=self.offset
                )
                print(f"BookmarkedSearchWorker: Found {len(project_bookmarks)} project bookmarks")

                # Mark these as project bookmarks
                for pub in project_bookmarks:
                    pub['bookmark_type'] = pub.get('bookmark_type', 'project')

            # Combine and deduplicate results
            # We'll use a dictionary to deduplicate by document ID
            combined_publications = {}

            # Add personal bookmarks
            for pub in personal_bookmarks:
                combined_publications[pub['id']] = pub

            # Add project bookmarks, updating bookmark_type to 'both' if already exists
            for pub in project_bookmarks:
                if pub['id'] in combined_publications:
                    # This document is bookmarked both personally and in the project
                    combined_publications[pub['id']]['bookmark_type'] = 'both'
                else:
                    combined_publications[pub['id']] = pub

            # Convert back to list
            publications = list(combined_publications.values())

            # If filter text is provided, filter the results
            if self.filter_text and publications:
                filtered_publications = []
                filter_terms = [term.strip().lower() for term in self.filter_text.split(',')]

                for pub in publications:
                    # Check if any filter term is in the title, abstract, or authors
                    title = pub.get('title', '').lower()
                    abstract = pub.get('abstract', '').lower()
                    authors = ' '.join(pub.get('authors', [])).lower()

                    if any(term in title or term in abstract or term in authors for term in filter_terms):
                        filtered_publications.append(pub)

                publications = filtered_publications

            # Check if we got any results
            if publications:
                print(f"BookmarkedSearchWorker: Search completed, found {len(publications)} results")
                # Emit the result
                self.signals.result.emit(publications)
            else:
                print("BookmarkedSearchWorker: Search completed, no results found")
                # Emit an empty result set
                self.signals.result.emit([])

        except Exception as e:
            # Get the traceback
            import traceback
            trace = traceback.format_exc()

            print(f"BookmarkedSearchWorker: Error during search: {e}")
            print(trace)

            # Emit the error
            self.signals.error.emit(str(e), trace)

        finally:
            # Always emit finished signal
            self.signals.finished.emit()


class HybridSearchWorker(QRunnable):
    """
    Worker thread for performing hybrid search (keyword + semantic).
    """

    def __init__(self, db_manager, embedding_manager, query, search_settings):
        """
        Initialize the worker.

        Args:
            db_manager: Database manager instance
            embedding_manager: Embedding manager instance
            query: Search query text
            search_settings: Dictionary of search settings
        """
        super().__init__()
        self.db_manager = db_manager
        self.embedding_manager = embedding_manager
        self.query = query
        self.search_settings = search_settings
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Perform hybrid search by combining keyword and semantic search results.
        """
        try:
            # Process search terms for keyword search
            search_terms = []
            remaining_text = self.query

            # Extract quoted terms first
            quoted_terms = []
            quote_start = remaining_text.find('"')
            while quote_start != -1:
                quote_end = remaining_text.find('"', quote_start + 1)
                if quote_end != -1:
                    quoted_term = remaining_text[quote_start + 1:quote_end].strip()
                    if quoted_term:
                        quoted_terms.append(quoted_term)
                    remaining_text = remaining_text[:quote_start] + " " + remaining_text[quote_end + 1:]
                else:
                    break
                quote_start = remaining_text.find('"')

            # Add quoted terms
            search_terms.extend(quoted_terms)

            # Process remaining comma-separated terms
            comma_terms = [term.strip() for term in remaining_text.split(",") if term.strip()]
            search_terms.extend(comma_terms)

            # Remove duplicates and empty terms
            search_terms = [term for term in search_terms if term]

            # Step 1: Perform keyword search
            keyword_results = []
            if search_terms:
                # Convert the search terms into an appropriate query
                query = " & ".join(search_terms)

                # Get source filter based on settings
                source_name = None
                if self.search_settings.get('sources', {}).get('medrxiv', True) and not self.search_settings.get('sources', {}).get('pubmed', True):
                    source_name = 'medrxiv'
                elif self.search_settings.get('sources', {}).get('pubmed', True) and not self.search_settings.get('sources', {}).get('medrxiv', True):
                    source_name = 'pubmed'
                # If both are True or both are False, don't filter by source

                # Perform the search using the document database manager
                keyword_results = self.db_manager.search_documents(
                    search_text=query,
                    source_name=source_name,
                    limit=self.search_settings.get('max_results', 20),
                    offset=0
                )

                # Add source information to each result
                for pub in keyword_results:
                    pub['search_source'] = 'keyword'

            # Step 2: Perform semantic search
            semantic_results = []
            if self.embedding_manager:
                try:
                    # Get source filter based on settings
                    source_id = None
                    if self.search_settings.get('sources', {}).get('medrxiv', True) and not self.search_settings.get('sources', {}).get('pubmed', True):
                        source_id = 'medrxiv'
                    elif self.search_settings.get('sources', {}).get('pubmed', True) and not self.search_settings.get('sources', {}).get('medrxiv', True):
                        source_id = 'pubmed'
                    # If both are True or both are False, don't filter by source

                    # Get raw semantic search results
                    raw_results = self.embedding_manager.search(
                        query=self.query,
                        limit=self.search_settings.get('max_results', 20),
                        threshold=self.search_settings.get('similarity_threshold', 0.3),
                        source_id=source_id
                    )

                    # Process semantic results
                    for result in raw_results:
                        document_id = result.get('document_id')
                        similarity = result.get('similarity', 0)
                        chunk_text = result.get('text', '')

                        # Format similarity as percentage
                        similarity_pct = f"{similarity * 100:.1f}%"

                        try:
                            # Get the document by ID if it's numeric
                            if isinstance(document_id, int) or (isinstance(document_id, str) and document_id.isdigit()):
                                doc_id = document_id if isinstance(document_id, int) else int(document_id)
                                query = """
                                SELECT d.*, s.name as source_name, c.name as category_name
                                FROM document d
                                JOIN sources s ON d.source_id = s.id
                                LEFT JOIN categories c ON d.category_id = c.id
                                WHERE d.id = %s
                                """
                                result = self.db_manager.execute(query, (doc_id,))
                                if result:
                                    publication = result[0]
                                else:
                                    # Try to get by DOI if it's a string
                                    if isinstance(document_id, str):
                                        publication = self.db_manager.get_document_by_doi(document_id)
                                    else:
                                        publication = None
                            else:
                                # Try to get by DOI
                                publication = self.db_manager.get_document_by_doi(document_id)

                            if publication:
                                # Add semantic search metadata
                                publication['similarity'] = similarity_pct
                                publication['similarity_value'] = similarity
                                publication['matched_text'] = chunk_text
                                publication['search_source'] = 'semantic'
                                semantic_results.append(publication)
                        except Exception as e:
                            print(f"Error retrieving publication {document_id}: {e}")
                except Exception as e:
                    print(f"Semantic search error: {e}")

            # Step 3: Combine and deduplicate results
            combined_results = self._combine_results(keyword_results, semantic_results)

            # Step 4: Rerank if enabled
            if (RERANKERS_AVAILABLE and
                self.search_settings.get('use_reranker', False) and
                combined_results):
                try:
                    # Import the reranker module
                    from localknowledge.ai.rerankers import get_reranker

                    # Get the reranker
                    reranker = get_reranker(self.search_settings.get('reranker_model', 'BAAI/bge-reranker-base'))

                    if reranker:
                        # Rerank the documents
                        combined_results = reranker.rerank(self.query, combined_results)

                        # Mark as reranked
                        for result in combined_results:
                            result['reranked'] = True
                except Exception as e:
                    print(f"Reranking error: {e}")

            # Emit the result
            self.signals.result.emit({
                'combined_results': combined_results,
                'keyword_count': len(keyword_results),
                'semantic_count': len(semantic_results),
                'reranked': self.search_settings.get('use_reranker', False) and RERANKERS_AVAILABLE
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

    def _combine_results(self, keyword_results, semantic_results):
        """
        Combine and deduplicate results from keyword and semantic searches.

        Args:
            keyword_results: List of publications from keyword search
            semantic_results: List of publications from semantic search

        Returns:
            Combined and deduplicated list of publications
        """
        # Create a dictionary to track unique DOIs
        unique_results = {}

        # Process keyword results first
        for pub in keyword_results:
            doi = pub.get('doi')
            if doi:
                unique_results[doi] = pub

        # Process semantic results, merging with keyword results if they exist
        for pub in semantic_results:
            doi = pub.get('doi')
            if doi:
                if doi in unique_results:
                    # Merge the results - keep keyword result but add semantic metadata
                    existing_pub = unique_results[doi]
                    existing_pub['similarity'] = pub.get('similarity')
                    existing_pub['similarity_value'] = pub.get('similarity_value', 0)
                    existing_pub['matched_text'] = pub.get('matched_text')
                    existing_pub['search_source'] = 'both'
                else:
                    unique_results[doi] = pub

        # Convert back to list
        combined_results = list(unique_results.values())

        # Get the hybrid weight parameter
        hybrid_weight = self.search_settings.get('hybrid_weight', 0.5)

        # Sort by a weighted combination of factors
        def sort_key(pub):
            # Base score starts at 0
            score = 0

            # Add semantic similarity score (weighted by hybrid_weight)
            if 'similarity_value' in pub:
                score += pub.get('similarity_value', 0) * hybrid_weight

            # Add keyword match score (weighted by 1-hybrid_weight)
            if pub.get('search_source') in ['keyword', 'both']:
                # Give keyword matches a boost weighted by (1-hybrid_weight)
                score += (1 - hybrid_weight)

            # Use date as a secondary sort key
            date_str = pub.get('date', '')

            return (score, date_str)

        # Sort by the combined score (higher is better)
        combined_results.sort(key=sort_key, reverse=True)

        return combined_results


class PDFExtractionWorker(QRunnable):
    """
    Worker thread for extracting text from PDF files.
    """

    def __init__(self, pdf_path, doi=None, _=None):
        """
        Initialize the worker.

        Args:
            pdf_path: Path to the PDF file to extract text from
            doi: DOI of the publication (for database update)
            _: Unused parameter, kept for backward compatibility
        """
        super().__init__()
        self.pdf_path = pdf_path
        self.doi = doi
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
                "doi": self.doi
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
