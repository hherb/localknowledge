"""
This module provides a PySide6 widget for browsing publication summaries
in an email client-like interface with read/unread status tracking.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import traceback

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QSize, QPointF, QObject, QRunnable, QThreadPool, QRect
from PySide6.QtGui import QColor, QFont, QIcon, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QLabel, QMessageBox, QApplication, QTextBrowser, QTextEdit,
    QFrame, QComboBox, QCheckBox, QToolBar, QMainWindow, QStatusBar,
    QDialog, QDialogButtonBox, QSizePolicy, QScrollArea, QStyledItemDelegate, QStyle
)

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"
from PySide6.QtWebEngineWidgets import QWebEngineView
# Import our custom PDFViewer widget
from localknowledge.ui.pdfviewer import PDFViewer

# Import markdown module if available
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.reading_tracker import ReadingTrackerManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.document import DocumentClient


class SummaryItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering summary items with source icons."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)
        # Load icons
        self.pubmed_icon = QIcon(PUBMED_ICON_PATH)
        self.medrxiv_icon = QIcon(MEDRXIV_ICON_PATH)

    def paint(self, painter, option, index):
        """
        Paint the item with custom rendering.

        Args:
            painter: QPainter to use for drawing
            option: Style options for the item
            index: Model index of the item
        """
        # Get the item data directly from the model
        item = index.model().itemFromIndex(index) if hasattr(index.model(), 'itemFromIndex') else None

        # If we can't get the item directly, try to get it from the list widget
        if not item or not isinstance(item, SummaryItem):
            # Try to get the list widget and the item from it
            list_widget = self.parent()
            if isinstance(list_widget, QListWidget):
                item = list_widget.item(index.row())

            # If we still don't have a valid item, fall back to default rendering
            if not item or not isinstance(item, SummaryItem):
                super().paint(painter, option, index)
                return

        # Save painter state
        painter.save()

        # Draw selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Calculate icon and text positions
        rect = option.rect
        icon_size = QSize(16, 16)  # Size of the source icon

        # Draw source icon if available
        source_id = item.document.get('source_id')
        icon_rect = QRect(rect.left() + 4, rect.top() + (rect.height() - icon_size.height()) // 2,
                         icon_size.width(), icon_size.height())

        if source_id == 1:  # PubMed
            self.pubmed_icon.paint(painter, icon_rect)
        elif source_id == 2:  # medRxiv
            self.medrxiv_icon.paint(painter, icon_rect)

        # Calculate text position (after the icon)
        text_left = icon_rect.right() + 8

        # Get the document data
        title = item.document.get('title', 'No Title')
        date = item.document.get('publication_date', '')
        source = item.document.get('source_name', '').capitalize()

        # Add suggestion strength indicator if available
        suggestion_indicator = ""
        if item.suggestion:
            strength = item.suggestion.get('recommendation_strength', 0)
            # Use stars to indicate strength (★)
            stars = "★" * strength
            suggestion_indicator = f" • Recommended: {stars}"

        # Format title - handle long titles
        if len(title) > 80:
            title = title[:77] + "..."

        # Draw the title text
        title_rect = QRect(text_left, rect.top() + 4, rect.width() - text_left - 4, rect.height() // 2)

        # Use bold font for the title if unread
        font = painter.font()
        if not item.is_read:
            font.setBold(True)
            painter.setFont(font)

        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop, title)

        # Reset font for metadata
        font.setBold(False)
        painter.setFont(font)

        # Draw the metadata text
        meta_text = f"{date} • Source: {source}{suggestion_indicator}"
        meta_rect = QRect(text_left, rect.top() + rect.height() // 2, rect.width() - text_left - 4, rect.height() // 2)
        painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignTop, meta_text)

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
        # Make items a bit taller to accommodate icons and two lines of text
        return QSize(size.width(), max(size.height(), 44))


class SummaryItem(QListWidgetItem):
    """List widget item to display document details with read/unread status and suggestion info."""

    def __init__(self, document: Dict[str, Any], is_read: bool = False, suggestion: Optional[Dict[str, Any]] = None):
        """
        Initialize a document list item.

        Args:
            document: Dictionary containing document details
            is_read: Whether the document has been read
            suggestion: Optional dictionary with suggestion details
        """
        self.document = document
        self.is_read = is_read
        self.suggestion = suggestion

        # Get display data
        title = document.get('title', 'No Title')
        date = document.get('publication_date', '')
        source = document.get('source_name', '').capitalize()

        # Add suggestion strength indicator if available
        suggestion_indicator = ""
        if suggestion:
            strength = suggestion.get('recommendation_strength', 0)
            # Use stars to indicate strength (★)
            stars = "★" * strength
            suggestion_indicator = f" • Recommended: {stars}"

        # Format title with HTML - handle long titles
        if len(title) > 80:
            title = title[:77] + "..."

        # Set display text based on read status
        if not is_read:
            display_text = f"<b>{title}</b>\n{date} • Source: {source}{suggestion_indicator}"
        else:
            display_text = f"{title}\n{date} • Source: {source}{suggestion_indicator}"

        # Initialize the item with display text
        super().__init__(display_text)

        # Make the item slightly taller for better readability
        self.setSizeHint(QSize(self.sizeHint().width(), self.sizeHint().height() + 10))

        # Set tooltip to show full title and suggestion details on hover
        tooltip = f"{document.get('title', 'No Title')}"
        if suggestion:
            evaluator = suggestion.get('evaluator_name', 'Unknown')
            comment = suggestion.get('comment', '')
            if comment:
                tooltip += f"\n\nRecommended by: {evaluator}\nComment: {comment}"
            else:
                tooltip += f"\n\nRecommended by: {evaluator}"
        self.setToolTip(tooltip)

        # Apply different styling based on read status and suggestion strength
        self.update_read_status(is_read)

    def update_read_status(self, is_read: bool = True):
        """
        Update the read status of the item.

        Args:
            is_read: Whether the item has been read
        """
        self.is_read = is_read

        # Get suggestion strength if available
        suggestion_strength = 0
        suggestion_indicator = ""
        if self.suggestion:
            suggestion_strength = self.suggestion.get('recommendation_strength', 0)
            # Use stars to indicate strength (★)
            stars = "★" * suggestion_strength
            suggestion_indicator = f" • Recommended: {stars}"

        # Apply different background color based on read status and suggestion strength
        if not is_read:
            # Unread items are bold
            font = self.font()
            font.setBold(True)
            self.setFont(font)

            # Apply background color based on suggestion strength
            if suggestion_strength >= 4:
                # Strong recommendations get a light green background
                self.setBackground(QColor(230, 255, 230))  # Light green
            elif suggestion_strength >= 2:
                # Medium recommendations get a light yellow background
                self.setBackground(QColor(255, 255, 230))  # Light yellow
            else:
                # No or weak recommendations get a light blue background
                self.setBackground(QColor(240, 248, 255))  # Light blue
        else:
            # Read items have normal font and white background
            font = self.font()
            font.setBold(False)
            self.setFont(font)
            self.setBackground(QColor(255, 255, 255))  # White

        # Update the text to reflect read status - without using HTML tags
        title = self.document.get('title', 'No Title')
        if len(title) > 80:
            title = title[:77] + "..."

        date = self.document.get('publication_date', '')
        source = self.document.get('source_name', '').capitalize()

        # Don't use HTML tags in setText() since QListWidgetItem doesn't render HTML
        # The bold font is already set with setFont() above
        self.setText(f"{title}\n{date} • Source: {source}{suggestion_indicator}")


class NewsBrowser(QWidget):
    """A PySide6 widget for browsing publication summaries like an email client."""

    # Signal emitted when a document is selected
    summarySelected = Signal(dict)

    def __init__(self, parent=None):
        """
        Initialize the news browser widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Import context management
        from localknowledge.context import (
            register_context_listener, get_current_user, get_current_project,
            CURRENT_USER, CURRENT_PROJECT
        )

        self.db_manager = DocumentDatabaseManager()
        self.doc_client = DocumentClient()
        # Initialize reading tracker for persistent read/unread status
        self.reading_tracker = ReadingTrackerManager()
        # Initialize reading suggestions manager
        self.suggestions_manager = ReadingSuggestionsManager()
        self.current_document = None
        self.current_suggestion = None

        # Get current user from context
        current_user = get_current_user()
        self.user_id = current_user['id'] if current_user else 1
        print(f"Current user: {current_user}, user_id: {self.user_id}")

        self.pdf_base_dir = self._get_pdf_base_dir()
        self.read_summaries = set()  # Local cache of read summaries for performance

        # Get current project from context
        self.current_project_id = get_current_project()

        # Register listeners for user and project changes
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)

        # For PDF search
        self.current_pdf_path = None
        self.search_results = []  # Will store search result rectangles
        self.current_match_index = -1
        self.current_search_text = ""
        self.fitz_document = None  # PyMuPDF document object

        # Initialize thread pool for background tasks
        self.threadpool = QThreadPool()
        print(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

        self._init_ui()

        # Load initial summaries
        self._load_summaries()

    def _init_ui(self):
        """Initialize the user interface."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create toolbar
        toolbar = QToolBar()

        # Add filter combo box
        self.filter_label = QLabel("Filter by: ")
        toolbar.addWidget(self.filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Documents")
        self.filter_combo.addItem("Unread Only")
        self.filter_combo.addItem("Reading Suggestions")  # New option for reading suggestions
        self.filter_combo.addItem("Recommended")
        self.filter_combo.addItem("Bookmarked")  # New option for bookmarked documents
        self.filter_combo.addItem("MedRxiv Only")
        self.filter_combo.addItem("PubMed Only")
        self.filter_combo.addItem("Emergency Medicine")
        self.filter_combo.addItem("Rural Medicine")
        self.filter_combo.addItem("AI in Medicine")
        self.filter_combo.addItem("Machine Learning")
        self.filter_combo.currentIndexChanged.connect(self._filter_summaries)
        toolbar.addWidget(self.filter_combo)

        toolbar.addSeparator()

        # Mark as read/unread buttons
        self.mark_read_btn = QPushButton("Mark as Read")
        self.mark_read_btn.clicked.connect(self._mark_as_read)
        toolbar.addWidget(self.mark_read_btn)

        self.mark_unread_btn = QPushButton("Mark as Unread")
        self.mark_unread_btn.clicked.connect(self._mark_as_unread)
        toolbar.addWidget(self.mark_unread_btn)

        toolbar.addSeparator()

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_summaries)
        toolbar.addWidget(self.refresh_btn)

        # Add toolbar to main layout
        main_layout.addWidget(toolbar)

        # Main splitter - vertical
        #self.main_splitter = QSplitter(Qt.Vertical)

        # Main horizontal splitter for list and tabbed view
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left side - summary list
        self.summary_list = QListWidget()
        self.summary_list.currentItemChanged.connect(self._on_summary_selected)
        self.summary_list.setAlternatingRowColors(True)

        # Set custom delegate for rendering items with source icons
        self.item_delegate = SummaryItemDelegate(self.summary_list)
        self.summary_list.setItemDelegate(self.item_delegate)

        # Set item height to accommodate icons and tags
        self.summary_list.setIconSize(QSize(16, 16))

        self.summary_list.setStyleSheet("""
            QListWidget {
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px 0;
            }
            QListWidget::item:alternate {
                background-color: #f9f9f9;
            }
            QListWidget::item:selected {
                background-color: #d0e3ff;
                color: black;
            }
        """)

        # Right side - tabbed interface
        self.tab_widget = QTabWidget()

        # Summary tab with rating and notes controls
        summary_container = QWidget()
        summary_layout = QVBoxLayout(summary_container)

        self.summary_view = QTextBrowser()
        self.summary_view.setOpenExternalLinks(True)

        # User interaction panel (ratings and notes)
        interaction_panel = QFrame()
        interaction_panel.setFrameShape(QFrame.StyledPanel)
        interaction_panel.setFrameShadow(QFrame.Raised)
        interaction_panel.setLineWidth(1)
        interaction_panel_layout = QHBoxLayout(interaction_panel)

        # Rating controls
        rating_group = QWidget()
        rating_layout = QHBoxLayout(rating_group)
        rating_layout.setContentsMargins(0, 0, 0, 0)

        rating_label = QLabel("Rating:")
        self.thumbs_up_btn = QPushButton("👍")
        self.thumbs_up_btn.setToolTip("Thumbs Up (+1)")
        self.thumbs_up_btn.clicked.connect(self._rate_positive)

        self.thumbs_down_btn = QPushButton("👎")
        self.thumbs_down_btn.setToolTip("Thumbs Down (-1)")
        self.thumbs_down_btn.clicked.connect(self._rate_negative)

        self.rating_label = QLabel("0")  # Shows current rating

        rating_layout.addWidget(rating_label)
        rating_layout.addWidget(self.thumbs_up_btn)
        rating_layout.addWidget(self.thumbs_down_btn)
        rating_layout.addWidget(self.rating_label)

        # Notes button
        self.notes_btn = QPushButton("Edit Notes")
        self.notes_btn.clicked.connect(self._show_notes_dialog)

        # Create recommendation feedback buttons
        self.recommendation_group = QWidget()
        recommendation_layout = QHBoxLayout(self.recommendation_group)
        recommendation_layout.setContentsMargins(0, 0, 0, 0)

        recommendation_label = QLabel("Recommendation:")
        self.agree_btn = QPushButton("👍 Agree")
        self.agree_btn.setToolTip("Agree with this recommendation")
        self.agree_btn.clicked.connect(self._agree_with_recommendation)
        self.agree_btn.setEnabled(False)  # Disabled by default

        self.disagree_btn = QPushButton("👎 Disagree")
        self.disagree_btn.setToolTip("Disagree with this recommendation")
        self.disagree_btn.clicked.connect(self._disagree_with_recommendation)
        self.disagree_btn.setEnabled(False)  # Disabled by default

        recommendation_layout.addWidget(recommendation_label)
        recommendation_layout.addWidget(self.agree_btn)
        recommendation_layout.addWidget(self.disagree_btn)

        # Bookmark controls
        bookmark_group = QWidget()
        bookmark_layout = QHBoxLayout(bookmark_group)
        bookmark_layout.setContentsMargins(0, 0, 0, 0)

        bookmark_label = QLabel("Bookmark:")
        self.personal_bookmark_cb = QCheckBox("Personal")
        self.personal_bookmark_cb.setToolTip("Add to personal bookmarks")
        self.personal_bookmark_cb.stateChanged.connect(self._toggle_personal_bookmark)

        self.project_bookmark_cb = QCheckBox("Project")
        self.project_bookmark_cb.setToolTip("Add to project bookmarks")
        self.project_bookmark_cb.stateChanged.connect(self._toggle_project_bookmark)

        bookmark_layout.addWidget(bookmark_label)
        bookmark_layout.addWidget(self.personal_bookmark_cb)
        bookmark_layout.addWidget(self.project_bookmark_cb)

        # Add to interaction panel
        interaction_panel_layout.addWidget(rating_group)
        interaction_panel_layout.addWidget(self.recommendation_group)
        interaction_panel_layout.addWidget(bookmark_group)
        interaction_panel_layout.addStretch(1)
        interaction_panel_layout.addWidget(self.notes_btn)

        # Add elements to summary layout
        summary_layout.addWidget(self.summary_view)
        summary_layout.addWidget(interaction_panel)

        self.tab_widget.addTab(summary_container, "Summary")

        # Create status bar first - wrap in container to better control height
        status_container = QWidget()
        status_container.setFixedHeight(25)  # Fix container height to exactly one line
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)

        self.status_bar = QStatusBar()
        self.status_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(self.status_bar)

        # PDF tab
        self.pdf_container = QWidget()
        pdf_layout = QVBoxLayout(self.pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)

        # Create PDF viewer widget with status bar for search results
        self.pdf_viewer = PDFViewer(self, self.status_bar)

        # Add the PDF viewer to the layout
        pdf_layout.addWidget(self.pdf_viewer)

        # Connect signals from the PDF viewer
        self.pdf_viewer.searchCompleted.connect(self._on_search_completed)

        # Add PDF container to tab
        self.tab_widget.addTab(self.pdf_container, "PDF")

        # Add widgets to main splitter
        self.main_splitter.addWidget(self.summary_list)
        self.main_splitter.addWidget(self.tab_widget)

        # Set initial sizes for main splitter (40% for list, 60% for tabs)
        self.main_splitter.setSizes([400, 600])

        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)

        # Add status bar to main layout
        main_layout.addWidget(status_container)
        self.status_bar.showMessage("Ready")

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
            pdf_base_dir = os.path.join(home_dir, "knowledgebase", "pdf")
        else:
            # Expand the tilde if it exists in the path
            pdf_base_dir = os.path.expanduser(pdf_base_dir)

        # Print debug info about the PDF directory
        pdf_path = Path(pdf_base_dir)
        if not pdf_path.exists():
            print(f"Directory {pdf_path} does not exist")

        return pdf_path

    def _load_summaries(self):
        """Load documents from the database."""
        self.status_bar.showMessage("Loading documents...")
        self.summary_list.clear()

        # Refresh the read status cache from the database
        self._refresh_read_status_cache()

        try:
            # Get the current filter
            filter_idx = self.filter_combo.currentIndex()
            filter_text = self.filter_combo.currentText()

            # Get documents based on filter
            documents = []
            suggestions_map = {}  # Map of document_id to suggestion

            if filter_idx == 0:  # All Documents
                # Get documents from all sources using search with empty query
                documents = self.db_manager.search_documents("", limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 1:  # Unread Only
                # Get all documents and filter for unread
                all_docs = self.db_manager.search_documents("", limit=100)
                # Filter for unread using the read_documents set
                documents = [doc for doc in all_docs if doc['id'] not in self.read_summaries]

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 2:  # Reading Suggestions
                # Get reading suggestions for the current user using the suggestions manager
                try:
                    # Clear existing documents list
                    documents = []

                    # Get suggestions from the suggestions manager
                    print(f"Getting reading suggestions for user_id={self.user_id}")

                    # Check if there are any suggestions for this user
                    check_query = "SELECT COUNT(*) FROM reading_suggestions WHERE user_id = %s"
                    count_result = self.db_manager.execute(check_query, (self.user_id,))
                    suggestion_count = count_result[0]['count'] if count_result else 0
                    print(f"Found {suggestion_count} suggestions in the database for user_id={self.user_id}")

                    # If no suggestions for current user, try user_id=2 (for testing/demo purposes)
                    if suggestion_count == 0 and self.user_id != 2:
                        print(f"No suggestions found for user_id={self.user_id}, trying user_id=2 for demo purposes")
                        suggestions = self.suggestions_manager.get_reading_suggestions(
                            user_id=2,  # Use user_id=2 for demo purposes
                            include_read=False,
                            min_strength=0,
                            limit=100
                        )
                    else:
                        suggestions = self.suggestions_manager.get_reading_suggestions(
                            user_id=self.user_id,
                            include_read=False,  # Only show unread suggestions
                            min_strength=0,      # Include all strengths
                            limit=100
                        )

                    # Debug: Print the first suggestion to see its structure
                    if suggestions and len(suggestions) > 0:
                        print(f"First suggestion keys: {suggestions[0].keys()}")
                    else:
                        print("No reading suggestions found")

                    if suggestions:
                        for row in suggestions:
                            # The reading_suggestions query joins with the document table,
                            # so we should have both document_id from reading_suggestions and id from document

                            # First, ensure we have a document ID
                            document_id = None
                            if 'document_id' in row:
                                document_id = row['document_id']
                            elif 'id' in row:
                                document_id = row['id']

                            if document_id is not None:
                                # Create document dictionary from the suggestion data
                                # Filter out suggestion-specific fields to get just the document data
                                doc = {k: v for k, v in row.items() if k not in [
                                    'id', 'user_id', 'evaluator_id', 'recommendation_strength',
                                    'confidence_level', 'comment', 'user_agreement',
                                    'created_at', 'updated_at', 'evaluator_name'
                                ]}

                                # Ensure the document has an id field
                                doc['id'] = document_id

                                documents.append(doc)

                                # Store suggestion info in the suggestions map
                                suggestions_map[document_id] = {
                                    'id': row.get('id'),
                                    'recommendation_strength': row.get('recommendation_strength', 0),
                                    'confidence_level': row.get('confidence_level', 0),
                                    'comment': row.get('comment', ''),
                                    'user_agreement': row.get('user_agreement'),
                                    'evaluator_name': row.get('evaluator_name', 'Unknown')
                                }
                            else:
                                print(f"Warning: Suggestion without document ID: {row}")

                    print(f"Found {len(documents)} reading suggestions")
                except Exception as e:
                    print(f"Error getting reading suggestions: {e}")
                    traceback.print_exc()

            elif filter_idx == 3:  # Recommended
                # Get reading suggestions for the current user
                print(f"Getting recommended documents for user_id={self.user_id}")

                # Check if there are any suggestions for this user
                check_query = "SELECT COUNT(*) FROM reading_suggestions WHERE user_id = %s AND recommendation_strength >= 1"
                count_result = self.db_manager.execute(check_query, (self.user_id,))
                suggestion_count = count_result[0]['count'] if count_result else 0
                print(f"Found {suggestion_count} recommendations in the database for user_id={self.user_id}")

                # If no suggestions for current user, try user_id=2 (for testing/demo purposes)
                if suggestion_count == 0 and self.user_id != 2:
                    print(f"No recommendations found for user_id={self.user_id}, trying user_id=2 for demo purposes")
                    suggestions = self.suggestions_manager.get_reading_suggestions(
                        user_id=2,  # Use user_id=2 for demo purposes
                        include_read=False,
                        min_strength=1,
                        limit=100
                    )
                else:
                    suggestions = self.suggestions_manager.get_reading_suggestions(
                        user_id=self.user_id,
                        include_read=False,
                        min_strength=1,
                        limit=100
                    )

                # Debug: Print the first suggestion to see its structure
                if suggestions and len(suggestions) > 0:
                    print(f"First recommendation keys: {suggestions[0].keys()}")
                else:
                    print("No recommendations found")

                # Extract documents from suggestions
                if suggestions:
                    documents = []
                    for suggestion in suggestions:
                        # The reading_suggestions query joins with the document table,
                        # so we should have both document_id from reading_suggestions and id from document

                        # First, ensure we have a document ID
                        document_id = None
                        if 'document_id' in suggestion:
                            document_id = suggestion['document_id']
                        elif 'id' in suggestion:
                            document_id = suggestion['id']

                        if document_id is not None:
                            # Create document dictionary from the suggestion data
                            # Filter out suggestion-specific fields to get just the document data
                            doc = {k: v for k, v in suggestion.items() if k not in [
                                'id', 'user_id', 'evaluator_id', 'recommendation_strength',
                                'confidence_level', 'comment', 'user_agreement',
                                'created_at', 'updated_at', 'evaluator_name'
                            ]}

                            # Ensure the document has an id field
                            doc['id'] = document_id

                            documents.append(doc)

                            # Store suggestion info in the suggestions map
                            suggestions_map[document_id] = {
                                'id': suggestion.get('id'),
                                'recommendation_strength': suggestion.get('recommendation_strength', 0),
                                'confidence_level': suggestion.get('confidence_level', 0),
                                'comment': suggestion.get('comment', ''),
                                'user_agreement': suggestion.get('user_agreement'),
                                'evaluator_name': suggestion.get('evaluator_name', 'Unknown')
                            }
                        else:
                            print(f"Warning: Recommendation without document ID: {suggestion}")

            elif filter_idx == 4:  # Bookmarked
                # Get bookmarked documents for the current user
                documents = self.db_manager.get_bookmarked_documents(
                    user_id=self.user_id,
                    project_id=self.current_project_id,
                    limit=100
                )

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 5:  # MedRxiv Only
                # Get documents from medrxiv source
                source_id = self.db_manager.get_source_id('medrxiv')
                if source_id:
                    documents = self.db_manager.search_documents("", limit=100, source_id=source_id)

                    # Get suggestions for these documents
                    if documents:
                        doc_ids = [doc['id'] for doc in documents]
                        self._load_suggestions_for_documents(doc_ids, suggestions_map)
                else:
                    documents = []

            elif filter_idx == 6:  # PubMed Only
                # Get documents from pubmed source
                source_id = self.db_manager.get_source_id('pubmed')
                if source_id:
                    documents = self.db_manager.search_documents("", limit=100, source_id=source_id)

                    # Get suggestions for these documents
                    if documents:
                        doc_ids = [doc['id'] for doc in documents]
                        self._load_suggestions_for_documents(doc_ids, suggestions_map)
                else:
                    documents = []
            elif filter_idx == 7:  # Emergency Medicine
                documents = self.db_manager.search_documents("emergency medicine", limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 8:  # Rural Medicine
                documents = self.db_manager.search_documents("rural medicine", limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 9:  # AI in Medicine
                documents = self.db_manager.search_documents("artificial intelligence medicine", limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 10:  # Machine Learning
                documents = self.db_manager.search_documents("machine learning", limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            else:  # Filter by keyword search
                # Use the filter text as a search query
                documents = self.db_manager.search_documents(filter_text, limit=100)

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            # Add documents to the list
            for document in documents:
                # Check if this document is in the read set (cached from database)
                is_read = document['id'] in self.read_summaries

                # Get suggestion for this document if available
                suggestion = suggestions_map.get(document['id'])

                # Create list item with suggestion info
                item = SummaryItem(document, is_read, suggestion)
                self.summary_list.addItem(item)

            if not documents:
                self.summary_list.addItem("No documents found")

            self.status_bar.showMessage(f"Loaded {len(documents)} documents")

        except Exception as e:
            self.status_bar.showMessage(f"Error: {str(e)}")
            print(f"Error loading documents: {str(e)}")
            traceback.print_exc()



    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_summary_selected(self, current, _):
        """
        Handle document selection in the list.

        Args:
            current: Currently selected item
            _: Previously selected item (unused)
        """
        if not current or not isinstance(current, SummaryItem):
            # Clear the summary view
            self.summary_view.clear()
            if hasattr(self, 'pdf_viewer'):
                self.pdf_viewer.close_pdf()
            return

        # Get the document data
        self.current_document = current.document

        # Emit the signal with the selected document
        self.summarySelected.emit(self.current_document)

        # Mark as read when selected
        self._mark_current_as_read()

        # Load the reading record to get rating and notes
        self._load_reading_record()

        # Display the document in the summary view
        self._display_summary()

        # Load the PDF if available
        self._load_pdf()

    def _display_summary(self):
        """Display the selected document in the summary view."""
        if not self.current_document:
            return

        # Get document data
        title = self.current_document.get('title', 'No Title')
        authors = self.current_document.get('authors', [])
        authors_text = ', '.join(authors) if authors else 'Unknown Authors'
        publication_date = self.current_document.get('publication_date', '')
        source = self.current_document.get('source_name', '').capitalize()
        doi = self.current_document.get('doi', '')
        abstract = self.current_document.get('abstract', 'No abstract available')
        keywords = self.current_document.get('keywords', [])
        journal = self.current_document.get('journal', '')
        url = self.current_document.get('url', '')

        # Format keywords as a list
        keywords_text = ', '.join(keywords) if keywords else 'None'

        # Get suggestion for this document if available
        document_id = self.current_document.get('id')
        self.current_suggestion = None
        if document_id:
            # First try to get suggestion for the current user
            self.current_suggestion = self.suggestions_manager.get_suggestion_by_document(document_id, self.user_id)

            # If no suggestion found for current user and current user is not user_id=2,
            # try to get suggestion for user_id=2 (for demo purposes)
            if not self.current_suggestion and self.user_id != 2:
                self.current_suggestion = self.suggestions_manager.get_suggestion_by_document(document_id, 2)
                if self.current_suggestion:
                    print(f"Using suggestion from user_id=2 for display")

        # Add suggestion information if available
        suggestion_html = ""
        if self.current_suggestion:
            strength = self.current_suggestion.get('recommendation_strength', 0)
            evaluator = self.current_suggestion.get('evaluator_name', 'Unknown')
            comment = self.current_suggestion.get('comment', '')
            confidence = self.current_suggestion.get('confidence_level', 0)
            user_agreement = self.current_suggestion.get('user_agreement')

            # Format stars for strength
            stars = "★" * strength + "☆" * (5 - strength)

            # Format user agreement
            agreement_text = ""
            if user_agreement is True:
                agreement_text = "<span style='color: green;'>You agreed with this recommendation</span>"
            elif user_agreement is False:
                agreement_text = "<span style='color: red;'>You disagreed with this recommendation</span>"

            suggestion_html = f"""
            <div style="background-color: #f8f8f8; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                <h3>Recommendation</h3>
                <p><b>Strength:</b> {stars} ({strength}/5)</p>
                <p><b>Recommended by:</b> {evaluator}</p>
                <p><b>Confidence:</b> {confidence:.2f if confidence else 'N/A'}</p>
                {f"<p><b>Comment:</b> {comment}</p>" if comment else ""}
                <p>{agreement_text}</p>
            </div>
            """

        # Format the document as HTML
        html_content = f"""
        <div style="padding: 10px;">
            <h2>{title}</h2>
            {suggestion_html}
            <p><b>Authors:</b> {authors_text}</p>
            <p><b>Date:</b> {publication_date}</p>
            <p><b>Source:</b> {source}</p>
            <p><b>Journal:</b> {journal}</p>
            <p><b>DOI:</b> <a href="https://doi.org/{doi}">{doi}</a></p>
            <p><b>URL:</b> <a href="{url}">{url}</a></p>
            <hr>
            <p><b>Keywords:</b> {keywords_text}</p>
            <hr>
            <h3>Abstract</h3>
            <p>{abstract}</p>
        </div>
        """

        # Set the HTML content
        self.summary_view.setHtml(html_content)

    def _load_pdf(self):
        """Load the selected document's PDF into the PDF view."""
        if not self.current_document:
            return

        # Get the local PDF path
        local_pdf_path = self.current_document.get('local_file_path', '')
        pdf_filename = self.current_document.get('pdf_filename', '')

        # Try to load PDF
        pdf_found = False

        # First case: We have a local_file_path in the document
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
                    # Store the current PDF path
                    self.current_pdf_path = pdf_path
                    pdf_found = True
                else:
                    print(f"Error loading PDF: {pdf_path}")

        # Second case: We have a pdf_filename in the document
        if not pdf_found and pdf_filename:
            # Convert to string and ensure proper path handling
            if isinstance(self.pdf_base_dir, Path):
                full_pdf_path = self.pdf_base_dir / pdf_filename
            else:
                # If pdf_base_dir is a string, create a path object
                full_pdf_path = Path(os.path.join(self.pdf_base_dir, pdf_filename))

            if full_pdf_path.exists():
                # Load the PDF using our PDFViewer widget
                pdf_path = str(full_pdf_path)
                if self.pdf_viewer.load_pdf(pdf_path):
                    # Store the current PDF path
                    self.current_pdf_path = pdf_path
                    pdf_found = True
                else:
                    print(f"Error loading PDF: {pdf_path}")

        # Third case: No path in database, but we have DOI - try to find by filename pattern
        if not pdf_found and 'doi' in self.current_document and self.current_document['doi']:
            doi = self.current_document['doi']
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
                        # Store the current PDF path
                        self.current_pdf_path = pdf_path
                    else:
                        print(f"Error loading PDF: {pdf_path}")
                        continue

                    # Update the database with the correct path
                    try:
                        # Get source_id and document_id for the update
                        source_name = self.current_document.get('source_name', '')
                        external_id = self.current_document.get('external_id', '')

                        if source_name and external_id:
                            # Update the document with the correct PDF path
                            self.db_manager.update_document_pdf_path(
                                source_name,
                                external_id,
                                filename
                            )
                            print(f"Updated database with path: {filename}")
                    except Exception as e:
                        print(f"Failed to update database: {e}")

                    pdf_found = True
                    break

        # If we still couldn't find the PDF, show a message
        if not pdf_found:
            print("PDF not found by any method")
            # Close the PDF in our viewer
            self.pdf_viewer.close_pdf()
            self.status_bar.showMessage("PDF not found")

    def _on_search_completed(self, match_count):
        """Handle search completion from the PDF viewer.

        Args:
            match_count: Number of matches found
        """
        # This method is called when the PDF viewer completes a search
        # We can use it to update the UI or perform additional actions
        if match_count > 0:
            self.status_bar.showMessage(f"Found {match_count} matches")
        else:
            self.status_bar.showMessage("No matches found")

    def _mark_current_as_read(self):
        """Mark the currently selected document as read."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and not current_item.is_read:
            document_id = current_item.document['id']

            try:
                # Record in the database
                # First check if a record already exists
                check_query = """
                SELECT id FROM reading_records
                WHERE document_id = %s AND user_id = %s
                """
                existing = self.db_manager.execute(check_query, (document_id, self.user_id))

                if existing:
                    # Update existing record
                    update_query = """
                    UPDATE reading_records
                    SET read_timestamp = NOW()
                    WHERE document_id = %s AND user_id = %s
                    """
                    self.db_manager.execute(update_query, (document_id, self.user_id), commit=True)
                else:
                    # Insert new record
                    insert_query = """
                    INSERT INTO reading_records (document_id, user_id, read_timestamp)
                    VALUES (%s, %s, NOW())
                    """
                    self.db_manager.execute(insert_query, (document_id, self.user_id), commit=True)

                # Update local cache
                self.read_summaries.add(document_id)

                # Update the UI
                current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {current_item.document.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_read(self):
        """Mark the selected document as read."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and not current_item.is_read:
            document_id = current_item.document['id']

            try:
                # Record in the database
                # First check if a record already exists
                check_query = """
                SELECT id FROM reading_records
                WHERE document_id = %s AND user_id = %s
                """
                existing = self.db_manager.execute(check_query, (document_id, self.user_id))

                if existing:
                    # Update existing record
                    update_query = """
                    UPDATE reading_records
                    SET read_timestamp = NOW()
                    WHERE document_id = %s AND user_id = %s
                    """
                    self.db_manager.execute(update_query, (document_id, self.user_id), commit=True)
                else:
                    # Insert new record
                    insert_query = """
                    INSERT INTO reading_records (document_id, user_id, read_timestamp)
                    VALUES (%s, %s, NOW())
                    """
                    self.db_manager.execute(insert_query, (document_id, self.user_id), commit=True)

                # Update local cache
                self.read_summaries.add(document_id)

                # Update the UI
                current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {current_item.document.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_unread(self):
        """Mark the selected document as unread."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and current_item.is_read:
            document_id = current_item.document['id']

            try:
                # Delete the reading record from the database
                query = """
                DELETE FROM reading_records
                WHERE document_id = %s AND user_id = %s
                """
                self.db_manager.execute(query, (document_id, self.user_id), commit=True)

                # Remove from local cache
                self.read_summaries.discard(document_id)

                # Update the UI
                current_item.update_read_status(False)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as unread: {current_item.document.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as unread: {e}")
                traceback.print_exc()

    def _refresh_read_status_cache(self):
        """
        Refresh the in-memory cache of read documents from the database.
        This helps improve performance by avoiding database lookups for each item.
        """
        try:
            # Get recent read records directly from the database for the current user
            query = """
            SELECT document_id FROM reading_records
            WHERE user_id = %s
            ORDER BY read_timestamp DESC
            LIMIT 1000
            """
            read_records = self.db_manager.execute(query, (self.user_id,))

            # Clear and update the cache
            self.read_summaries.clear()
            for record in read_records:
                # Get the document ID from the reading record
                document_id = record.get('document_id')
                if document_id:
                    self.read_summaries.add(document_id)

            print(f"Refreshed read status cache: {len(self.read_summaries)} read items")
        except Exception as e:
            print(f"Error refreshing read status cache: {e}")
            traceback.print_exc()

    def _load_suggestions_for_documents(self, doc_ids: List[int], suggestions_map: Dict[int, Dict[str, Any]]):
        """
        Load suggestions for a list of documents.

        Args:
            doc_ids: List of document IDs
            suggestions_map: Dictionary to store suggestions, keyed by document ID
        """
        if not doc_ids:
            print("No document IDs provided to _load_suggestions_for_documents")
            return

        print(f"Loading suggestions for {len(doc_ids)} documents")

        # Get suggestions for these documents
        for doc_id in doc_ids:
            # First try to get suggestion for the current user
            suggestion = self.suggestions_manager.get_suggestion_by_document(doc_id, self.user_id)

            # If no suggestion found for current user and current user is not user_id=2,
            # try to get suggestion for user_id=2 (for demo purposes)
            if not suggestion and self.user_id != 2:
                suggestion = self.suggestions_manager.get_suggestion_by_document(doc_id, 2)
                if suggestion:
                    print(f"Found suggestion for document_id={doc_id} from user_id=2: {suggestion.get('recommendation_strength', 0)}/5")

            if suggestion:
                print(f"Found suggestion for document_id={doc_id}: {suggestion.get('recommendation_strength', 0)}/5")
                suggestions_map[doc_id] = suggestion

        print(f"Loaded {len(suggestions_map)} suggestions for documents")

    def _filter_summaries(self):
        """Filter the summaries based on the selected filter."""
        self._load_summaries()  # Reload with the selected filter

    # PDF-related methods are now handled by the PDFViewer widget

    def close_database(self):
        """Close the database connections."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        if hasattr(self, 'reading_tracker'):
            self.reading_tracker.close()

        if hasattr(self, 'suggestions_manager'):
            self.suggestions_manager.close()

        # Close PDF viewer
        if hasattr(self, 'pdf_viewer'):
            self.pdf_viewer.close_pdf()

    def _rate_positive(self):
        """Rate the current document positively (thumbs up)."""
        if not self.current_document:
            return

        try:
            document_id = self.current_document['id']

            # Update the rating in the database
            # First check if a record already exists
            check_query = """
            SELECT id FROM reading_records
            WHERE document_id = %s AND user_id = %s
            """
            existing = self.db_manager.execute(check_query, (document_id, self.user_id))

            if existing:
                # Update existing record
                update_query = """
                UPDATE reading_records
                SET rating = %s
                WHERE document_id = %s AND user_id = %s
                """
                self.db_manager.execute(update_query, (1, document_id, self.user_id), commit=True)
            else:
                # Insert new record
                insert_query = """
                INSERT INTO reading_records (document_id, user_id, read_timestamp, rating)
                VALUES (%s, %s, NOW(), %s)
                """
                self.db_manager.execute(insert_query, (document_id, self.user_id, 1), commit=True)

            # Update the UI
            self.rating_label.setText("+1")
            self.status_bar.showMessage("Document rated positively")

        except Exception as e:
            print(f"Error rating document positively: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating rating")

    def _rate_negative(self):
        """Rate the current document negatively (thumbs down)."""
        if not self.current_document:
            return

        try:
            document_id = self.current_document['id']

            # Update the rating in the database
            # First check if a record already exists
            check_query = """
            SELECT id FROM reading_records
            WHERE document_id = %s AND user_id = %s
            """
            existing = self.db_manager.execute(check_query, (document_id, self.user_id))

            if existing:
                # Update existing record
                update_query = """
                UPDATE reading_records
                SET rating = %s
                WHERE document_id = %s AND user_id = %s
                """
                self.db_manager.execute(update_query, (-1, document_id, self.user_id), commit=True)
            else:
                # Insert new record
                insert_query = """
                INSERT INTO reading_records (document_id, user_id, read_timestamp, rating)
                VALUES (%s, %s, NOW(), %s)
                """
                self.db_manager.execute(insert_query, (document_id, self.user_id, -1), commit=True)

            # Update the UI
            self.rating_label.setText("-1")
            self.status_bar.showMessage("Document rated negatively")

        except Exception as e:
            print(f"Error rating document negatively: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating rating")

    def _show_notes_dialog(self):
        """Show a dialog for editing notes for the current document."""
        if not self.current_document:
            return

        try:
            document_id = self.current_document['id']

            # Get existing notes directly from the database
            query = """
            SELECT notes FROM reading_records
            WHERE document_id = %s AND user_id = %s
            """
            record = self.db_manager.execute(query, (document_id, self.user_id))
            record = record[0] if record else None

            existing_notes = record.get('notes', '') if record else ''

            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Edit Notes")
            dialog.setMinimumSize(500, 300)

            layout = QVBoxLayout(dialog)

            # Notes editor
            notes_edit = QTextEdit(existing_notes)
            layout.addWidget(QLabel("Notes:"))
            layout.addWidget(notes_edit)

            # Tag editor (for future use)
            # tag_edit = QLineEdit()
            # layout.addWidget(QLabel("Tags (comma separated):"))
            # layout.addWidget(tag_edit)

            # Buttons
            button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            # Show dialog
            if dialog.exec() == QDialog.Accepted:
                notes = notes_edit.toPlainText()

                # Save notes to database
                # First check if a record already exists
                check_query = """
                SELECT id FROM reading_records
                WHERE document_id = %s AND user_id = %s
                """
                existing = self.db_manager.execute(check_query, (document_id, self.user_id))

                if existing:
                    # Update existing record
                    update_query = """
                    UPDATE reading_records
                    SET notes = %s
                    WHERE document_id = %s AND user_id = %s
                    """
                    self.db_manager.execute(update_query, (notes, document_id, self.user_id), commit=True)
                else:
                    # Insert new record
                    insert_query = """
                    INSERT INTO reading_records (document_id, user_id, read_timestamp, notes)
                    VALUES (%s, %s, NOW(), %s)
                    """
                    self.db_manager.execute(insert_query, (document_id, self.user_id, notes), commit=True)

                # Mark as read if not already
                if document_id not in self.read_summaries:
                    self.read_summaries.add(document_id)
                    current_item = self.summary_list.currentItem()
                    if current_item and isinstance(current_item, SummaryItem):
                        current_item.update_read_status(True)

                self.status_bar.showMessage("Notes saved")

        except Exception as e:
            print(f"Error handling notes: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error saving notes")

    def _agree_with_recommendation(self):
        """Agree with the current recommendation."""
        if not self.current_document or not self.current_suggestion:
            return

        try:
            suggestion_id = self.current_suggestion.get('id')
            if suggestion_id:
                # Update the user agreement in the database
                self.suggestions_manager.update_user_agreement(suggestion_id, True)

                # Update the current suggestion
                self.current_suggestion['user_agreement'] = True

                # Update the display
                self._display_summary()

                # Update the status bar
                self.status_bar.showMessage("You agreed with this recommendation")

                # Disable the agree button and enable the disagree button
                self.agree_btn.setEnabled(False)
                self.disagree_btn.setEnabled(True)
        except Exception as e:
            print(f"Error agreeing with recommendation: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating recommendation feedback")

    def _disagree_with_recommendation(self):
        """Disagree with the current recommendation."""
        if not self.current_document or not self.current_suggestion:
            return

        try:
            suggestion_id = self.current_suggestion.get('id')
            if suggestion_id:
                # Update the user agreement in the database
                self.suggestions_manager.update_user_agreement(suggestion_id, False)

                # Update the current suggestion
                self.current_suggestion['user_agreement'] = False

                # Update the display
                self._display_summary()

                # Update the status bar
                self.status_bar.showMessage("You disagreed with this recommendation")

                # Enable the agree button and disable the disagree button
                self.agree_btn.setEnabled(True)
                self.disagree_btn.setEnabled(False)
        except Exception as e:
            print(f"Error disagreeing with recommendation: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating recommendation feedback")

    def _load_reading_record(self):
        """Load the current document's reading record including rating and notes."""
        if not self.current_document:
            return

        try:
            document_id = self.current_document['id']

            # Get the reading record directly from the database
            query = """
            SELECT rating, notes FROM reading_records
            WHERE document_id = %s AND user_id = %s
            """
            record = self.db_manager.execute(query, (document_id, self.user_id))
            record = record[0] if record else None

            if record:
                # Update rating display
                rating = record.get('rating')
                if rating is not None:
                    self.rating_label.setText(f"{rating:+d}")  # Format as +1 or -1
                else:
                    self.rating_label.setText("0")

                # We don't need to display notes here since they're shown in the dialog
                # But we could indicate if notes exist
                has_notes = bool(record.get('notes'))
                self.notes_btn.setText("Edit Notes" if not has_notes else "Edit Notes ✓")
            else:
                # Reset UI for no record
                self.rating_label.setText("0")
                self.notes_btn.setText("Edit Notes")

            # Update recommendation buttons based on current suggestion
            if self.current_suggestion:
                user_agreement = self.current_suggestion.get('user_agreement')
                if user_agreement is True:
                    # User agreed with this recommendation
                    self.agree_btn.setEnabled(False)
                    self.disagree_btn.setEnabled(True)
                elif user_agreement is False:
                    # User disagreed with this recommendation
                    self.agree_btn.setEnabled(True)
                    self.disagree_btn.setEnabled(False)
                else:
                    # User hasn't provided feedback yet
                    self.agree_btn.setEnabled(True)
                    self.disagree_btn.setEnabled(True)

                # Show the recommendation buttons
                self.recommendation_group.setVisible(True)
            else:
                # No recommendation, hide the buttons
                self.recommendation_group.setVisible(False)

            # Check bookmark status
            self._check_bookmark_status()

        except Exception as e:
            print(f"Error loading reading record: {e}")
            traceback.print_exc()
            self.rating_label.setText("?")
            self.notes_btn.setText("Edit Notes")
            self.recommendation_group.setVisible(False)


    def _check_bookmark_status(self):
        """Check if the current document is bookmarked."""
        if not self.current_document:
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            return

        try:
            # Always ensure the project checkbox is enabled/disabled based on current project
            # This needs to be done regardless of the current document
            # IMPORTANT: Make sure the project checkbox is always enabled if a project is selected
            project_enabled = self.current_project_id is not None
            self.project_bookmark_cb.setEnabled(project_enabled)

            # Check personal bookmark
            personal_bookmark = self.db_manager.is_bookmarked(
                source_name,
                external_id,
                self.user_id
            )

            # Check project bookmark if a project is selected
            project_bookmark = None
            if self.current_project_id:
                project_bookmark = self.db_manager.is_bookmarked(
                    source_name,
                    external_id,
                    self.user_id,
                    self.current_project_id
                )

            # Update checkboxes without triggering signals
            self.personal_bookmark_cb.blockSignals(True)
            self.project_bookmark_cb.blockSignals(True)

            # Set checkbox states
            is_personal = personal_bookmark == 'personal' or personal_bookmark == 'both'
            self.personal_bookmark_cb.setChecked(is_personal)

            # Set project checkbox state
            if self.current_project_id:
                is_project = project_bookmark == 'project' or project_bookmark == 'both'
                self.project_bookmark_cb.setChecked(is_project)
            else:
                self.project_bookmark_cb.setChecked(False)

            # Unblock signals
            self.personal_bookmark_cb.blockSignals(False)
            self.project_bookmark_cb.blockSignals(False)

            # Make sure the project checkbox is still enabled if a project is selected
            # This is needed because sometimes the checkbox gets disabled during state changes
            if project_enabled:
                self.project_bookmark_cb.setEnabled(True)

            # Debug output
            print(f"Bookmark status for {source_name}/{external_id}: Personal={is_personal}, Project={self.project_bookmark_cb.isChecked()}, Project enabled={self.project_bookmark_cb.isEnabled()}")

        except Exception as e:
            print(f"Error checking bookmark status: {e}")
            traceback.print_exc()

    def _toggle_personal_bookmark(self, state):
        """Toggle personal bookmark for the current document."""
        if not self.current_document:
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            return

        try:
            # Check if there's also a project bookmark
            project_bookmark = False
            if self.current_project_id:
                project_bookmark_type = self.db_manager.is_bookmarked(
                    source_name,
                    external_id,
                    self.user_id,
                    self.current_project_id
                )
                project_bookmark = project_bookmark_type is not None

            if state:  # Checked
                # Add personal bookmark
                bookmark_type = 'both' if project_bookmark else 'personal'
                self.db_manager.add_bookmark(
                    source_name,
                    external_id,
                    self.user_id,
                    bookmark_type,
                    self.current_project_id if project_bookmark else None
                )
                self.status_bar.showMessage("Added to personal bookmarks")
            else:  # Unchecked
                if project_bookmark:
                    # Change to project-only bookmark
                    self.db_manager.add_bookmark(
                        source_name,
                        external_id,
                        self.user_id,
                        'project',
                        self.current_project_id
                    )
                else:
                    # Remove personal bookmark
                    self.db_manager.remove_bookmark(
                        source_name,
                        external_id,
                        self.user_id
                    )
                self.status_bar.showMessage("Removed from personal bookmarks")

        except Exception as e:
            print(f"Error toggling personal bookmark: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating bookmark")

    def _toggle_project_bookmark(self, state):
        """Toggle project bookmark for the current document."""
        if not self.current_document or not self.current_project_id:
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            return

        try:
            # Check if there's also a personal bookmark
            personal_bookmark_type = self.db_manager.is_bookmarked(
                source_name,
                external_id,
                self.user_id
            )
            personal_bookmark = personal_bookmark_type is not None and personal_bookmark_type != 'project'

            if state:  # Checked
                # Add project bookmark
                bookmark_type = 'both' if personal_bookmark else 'project'
                self.db_manager.add_bookmark(
                    source_name,
                    external_id,
                    self.user_id,
                    bookmark_type,
                    self.current_project_id
                )
                self.status_bar.showMessage("Added to project bookmarks")
            else:  # Unchecked
                if personal_bookmark:
                    # Change to personal-only bookmark
                    self.db_manager.add_bookmark(
                        source_name,
                        external_id,
                        self.user_id,
                        'personal'
                    )
                else:
                    # Remove project bookmark
                    self.db_manager.remove_bookmark(
                        source_name,
                        external_id,
                        self.user_id,
                        self.current_project_id
                    )
                self.status_bar.showMessage("Removed from project bookmarks")

        except Exception as e:
            print(f"Error toggling project bookmark: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating bookmark")

    def _on_user_changed(self, user_data):
        """
        Handle user change from context system.

        Args:
            user_data: User information dictionary
        """
        if user_data:
            self.user_id = user_data.get('id', 1)
        else:
            self.user_id = 1

        # Refresh read status cache and reload summaries
        self._refresh_read_status_cache()
        self._load_summaries()

        # Update bookmark status if a document is selected
        if self.current_document:
            self._check_bookmark_status()

    def _on_project_changed(self, project_id):
        """
        Handle project change from context system.

        Args:
            project_id: Project ID
        """
        # Only update if the project has actually changed
        if project_id != self.current_project_id:
            self.set_current_project(project_id)

    def set_current_project(self, project_id):
        """Set the current project ID for project bookmarks."""
        self.current_project_id = project_id

        # Update project bookmark checkbox state - ALWAYS ensure it's enabled if project_id is not None
        project_enabled = project_id is not None
        self.project_bookmark_cb.setEnabled(project_enabled)

        # Print debug info
        print(f"Setting current project to {project_id}, checkbox enabled: {self.project_bookmark_cb.isEnabled()}")

        # If a document is selected, check its bookmark status
        if self.current_document:
            self._check_bookmark_status()
        else:
            # Even if no document is selected, we should update the UI
            # to reflect the current project state
            self.project_bookmark_cb.setEnabled(project_enabled)
            self.project_bookmark_cb.setChecked(False)

        # Make sure the project checkbox is still enabled if a project is selected
        if project_enabled:
            self.project_bookmark_cb.setEnabled(True)


class NewsBrowserWindow(QMainWindow):
    """A standalone window for the NewsBrowser widget."""

    def __init__(self, parent=None):
        """Initialize the main window for the news browser."""
        super().__init__(parent)

        # Import context management
        from localknowledge.context import (
            register_context_listener, CURRENT_USER, CURRENT_PROJECT
        )

        # Set window properties
        self.setWindowTitle("Publication News Browser")
        self.resize(1200, 800)

        # Create the news browser widget
        self.news_browser = NewsBrowser()

        # Set as central widget
        self.setCentralWidget(self.news_browser)

        # Register listeners for project and user changes
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)
        register_context_listener(CURRENT_USER, self._on_user_changed)

        # Update window title
        self._update_window_title()

    def get_current_project(self):
        """Get the current project ID."""
        return self.news_browser.current_project_id

    def _on_project_changed(self, _):
        """
        Handle project change from context system.

        Args:
            _: Project ID (unused)
        """
        # Update window title when project changes
        self._update_window_title()

    def _on_user_changed(self, _):
        """
        Handle user change from context system.

        Args:
            _: User information dictionary (unused)
        """
        # Update window title when user changes
        self._update_window_title()

    def _update_window_title(self):
        """Update the window title with current project and user information."""
        from localknowledge.context import get_current_user, get_current_project_name

        title = "Publication News Browser"

        # Add project name if available
        project_name = get_current_project_name()
        if project_name:
            title += f" - Project: {project_name}"

        # Add user name if available
        user = get_current_user()
        if user:
            user_name = f"{user.get('firstname', '')} {user.get('surname', '')}"
            title += f" - User: {user_name}"

        self.setWindowTitle(title)

    def closeEvent(self, event):
        """Handle window close event."""
        # Ensure database connections are closed
        self.news_browser.close_database()
        super().closeEvent(event)


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # For standalone usage, use the window wrapper
    browser_window = NewsBrowserWindow()
    browser_window.show()

    sys.exit(app.exec())
