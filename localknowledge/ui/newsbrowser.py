"""
This module provides a PySide6 widget for browsing publication summaries
in an email client-like interface with read/unread status tracking.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import traceback

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QPointF, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QTabWidget, QLabel, QMessageBox,
    QTextBrowser, QTextEdit, QFrame, QComboBox, QCheckBox,
    QToolBar, QMainWindow, QStatusBar, QDialog, QDialogButtonBox,
    QSizePolicy, QScrollArea, QApplication
)

# Import our custom DocumentListWidget
from localknowledge.ui.document_list_widget import DocumentListWidget

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"
from PySide6.QtWebEngineWidgets import QWebEngineView
# Import our custom document display widget
from localknowledge.ui.document_display_widget import DocumentDisplayWidget

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.reading_tracker import ReadingTrackerManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.document import DocumentClient


# The SummaryItemDelegate and SummaryItem classes have been replaced by
# the DocumentItemDelegate and DocumentItem classes in document_list_widget.py


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
            register_context_listener, set_current_project,
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

        # Get user_id from context manager
        from localknowledge.context import get_current_user
        user = get_current_user()
        self.user_id = user.get('id', 1) if user else 1  # Default to user_id 1
        print(f"Using user_id={self.user_id}")

        self.pdf_base_dir = self._get_pdf_base_dir()
        self.read_summaries = set()  # Local cache of read summaries for performance

        # Get current project from context
        from localknowledge.context import get_current_project
        project = get_current_project()
        self.current_project_id = project.get('id') if project else None
        print(f"Using project_id={self.current_project_id}")

        # Register listeners for user and project changes
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)

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
        self.filter_combo.addItem("Suggested")
        self.filter_combo.addItem("Bookmarked")
        self.filter_combo.addItem("PubMed")
        self.filter_combo.addItem("MedRxiv")
        self.filter_combo.currentIndexChanged.connect(self._filter_summaries)
        toolbar.addWidget(self.filter_combo)

        # Add max results input
        toolbar.addWidget(QLabel("Max results:"))
        self.max_results_input = QLineEdit("25")
        self.max_results_input.setFixedWidth(50)
        self.max_results_input.setValidator(QIntValidator(1, 1000))
        self.max_results_input.editingFinished.connect(self._filter_summaries)
        toolbar.addWidget(self.max_results_input)

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

        # Left side - document list using our reusable widget
        self.summary_list = DocumentListWidget()
        self.summary_list.documentSelected.connect(self._on_document_selected)

        # Create status bar first - wrap in container to better control height
        status_container = QWidget()
        status_container.setFixedHeight(25)  # Fix container height to exactly one line
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)

        self.status_bar = QStatusBar()
        self.status_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(self.status_bar)

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

        # Create recommendation feedback buttons
        self.recommendation_group = QFrame()
        self.recommendation_group.setFrameShape(QFrame.StyledPanel)
        self.recommendation_group.setFrameShadow(QFrame.Raised)
        self.recommendation_group.setLineWidth(1)
        recommendation_layout = QHBoxLayout(self.recommendation_group)
        recommendation_layout.setContentsMargins(10, 5, 10, 5)

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

        # Add a stretch to push the notes button to the right
        recommendation_layout.addStretch(1)

        # Notes button
        self.notes_btn = QPushButton("Edit Notes")
        self.notes_btn.setToolTip("Edit notes for this document")
        self.notes_btn.clicked.connect(self._show_notes_dialog)
        recommendation_layout.addWidget(self.notes_btn)

        # Add widgets to main splitter
        self.main_splitter.addWidget(self.summary_list)

        # Create a container for the document display and recommendation widgets
        doc_container = QWidget()
        doc_layout = QVBoxLayout(doc_container)
        doc_layout.setContentsMargins(0, 0, 0, 0)
        doc_layout.setSpacing(5)

        # Add document display to the container
        doc_layout.addWidget(self.document_display)

        # Add recommendation group below the document display
        doc_layout.addWidget(self.recommendation_group)

        # Initially hide the recommendation group until a document with a recommendation is selected
        self.recommendation_group.setVisible(False)

        # Add the document container to the splitter
        self.main_splitter.addWidget(doc_container)

        # Set initial sizes for main splitter (40% for list, 60% for tabs)
        self.main_splitter.setSizes([400, 600])

        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)

        # Add status bar to main layout
        main_layout.addWidget(status_container)
        self.status_bar.showMessage("Ready")

    def _get_pdf_base_dir(self) -> Path:
        """
        Get the base directory for PDF files using the context manager.

        Returns:
        - Fully expanded path to the PDF storage directory
        """
        # Use the context manager to get the PDF base directory
        from localknowledge.context import get_pdf_base_dir as get_pdf_dir

        pdf_path = get_pdf_dir()

        # Print debug info about the PDF directory
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

            # Get max results from input
            try:
                max_results = int(self.max_results_input.text())
            except ValueError:
                max_results = 25  # Default if invalid input
                self.max_results_input.setText(str(max_results))

            # Get user_id from context manager
            from localknowledge.context import get_current_user
            user = get_current_user()
            self.user_id = user.get('id', 1) if user else 1  # Default to user_id 1
            print(f"Using user_id={self.user_id}")

            # Get current project from context
            from localknowledge.context import get_current_project
            project = get_current_project()
            self.current_project_id = project.get('id') if project else None

            print(f"Loading documents for user_id={self.user_id}, project_id={self.current_project_id}")

            # Get documents based on filter
            documents = []
            suggestions_map = {}  # Map of document_id to suggestion

            if filter_idx == 0:  # Suggested
                # Get reading suggestions for the current user using the suggestions manager
                try:
                    # Clear existing documents list
                    documents = []

                    # Get suggestions from the suggestions manager
                    print(f"Getting reading suggestions for user_id={self.user_id}")

                    # Get suggestions for this user
                    suggestions = self.suggestions_manager.get_reading_suggestions(
                        user_id=self.user_id,
                        include_read=False,  # Only show unread suggestions
                        min_strength=0,      # Include all strengths
                        limit=max_results
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

            elif filter_idx == 1:  # Bookmarked
                # Get bookmarked documents for the current user
                documents = self.db_manager.get_bookmarked_documents(
                    user_id=self.user_id,
                    project_id=self.current_project_id,
                    limit=max_results
                )

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 2:  # PubMed
                # Get recent documents from pubmed source
                documents = self.db_manager.get_recent_documents(limit=max_results, source_name='pubmed')
                print(f"Loaded {len(documents)} recent PubMed documents")

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            elif filter_idx == 3:  # MedRxiv
                # Get recent documents from medrxiv source
                documents = self.db_manager.get_recent_documents(limit=max_results, source_name='medrxiv')
                print(f"Loaded {len(documents)} recent MedRxiv documents")

                # Get suggestions for these documents
                if documents:
                    doc_ids = [doc['id'] for doc in documents]
                    self._load_suggestions_for_documents(doc_ids, suggestions_map)

            # Sort documents by publication date (newest first)
            documents.sort(key=lambda x: x.get('publication_date', ''), reverse=True)

            # Set documents in the list widget
            self.summary_list.set_documents(documents, self.read_summaries, suggestions_map)

            self.status_bar.showMessage(f"Loaded {len(documents)} documents")

        except Exception as e:
            self.status_bar.showMessage(f"Error: {str(e)}")
            print(f"Error loading documents: {str(e)}")
            traceback.print_exc()



    def _on_document_selected(self, document):
        """
        Handle document selection in the list.

        Args:
            document: Selected document dictionary
        """
        if not document:
            # Clear the document display
            self.document_display.clear()
            return

        # Store the current document
        self.current_document = document

        # Emit the signal with the selected document
        self.summarySelected.emit(self.current_document)

        # Mark as read when selected
        self._mark_current_as_read()

        # Get suggestion for this document if available
        document_id = self.current_document.get('id')
        self.current_suggestion = None
        if document_id:
            # First try to get suggestion for the current user
            self.current_suggestion = self.suggestions_manager.get_suggestion_by_document(document_id, self.user_id)

            # If no suggestion found for current user and current user is not user_id=1,
            # try to get suggestion for user_id=1 (for demo purposes)
            if not self.current_suggestion and self.user_id != 1:
                self.current_suggestion = self.suggestions_manager.get_suggestion_by_document(document_id, 1)
                if self.current_suggestion:
                    print(f"Using suggestion from user_id=1 for display")

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

        # Display the document in the document display widget
        self.document_display.display_document(self.current_document)

        # The document display widget gets user and project from context
        # No need to explicitly set them here

    def _display_summary(self):
        """Update the document display with the current document."""
        # This method is now handled by the document display widget
        if self.current_document:
            self.document_display.display_document(self.current_document)

    # PDF-related methods are now handled by the DocumentDisplayWidget

    def _mark_current_as_read(self):
        """Mark the currently selected document as read."""
        if not self.current_document:
            return

        document_id = self.current_document['id']
        if document_id not in self.read_summaries:
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

                # Get the current document item and update its read status
                current_item = self.summary_list.list_widget.currentItem()
                if current_item and hasattr(current_item, 'update_read_status'):
                    current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {self.current_document.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_read(self):
        """Mark the selected document as read."""
        if not self.current_document:
            return

        document_id = self.current_document['id']
        if document_id not in self.read_summaries:
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

                # Get the current document item and update its read status
                current_item = self.summary_list.list_widget.currentItem()
                if current_item and hasattr(current_item, 'update_read_status'):
                    current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {self.current_document.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_unread(self):
        """Mark the selected document as unread."""
        if not self.current_document:
            return

        document_id = self.current_document['id']
        if document_id in self.read_summaries:
            try:
                # Delete the reading record from the database
                query = """
                DELETE FROM reading_records
                WHERE document_id = %s AND user_id = %s
                """
                self.db_manager.execute(query, (document_id, self.user_id), commit=True)

                # Remove from local cache
                self.read_summaries.discard(document_id)

                # Get the current document item and update its read status
                current_item = self.summary_list.list_widget.currentItem()
                if current_item and hasattr(current_item, 'update_read_status'):
                    current_item.update_read_status(False)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as unread: {self.current_document.get('title', 'Unknown')}")
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

            # If no suggestion found for current user and current user is not user_id=1,
            # try to get suggestion for user_id=1 (for demo purposes)
            if not suggestion and self.user_id != 1:
                suggestion = self.suggestions_manager.get_suggestion_by_document(doc_id, 1)
                if suggestion:
                    print(f"Found suggestion for document_id={doc_id} from user_id=1: {suggestion.get('recommendation_strength', 0)}/5")

            if suggestion:
                print(f"Found suggestion for document_id={doc_id}: {suggestion.get('recommendation_strength', 0)}/5")
                suggestions_map[doc_id] = suggestion

        print(f"Loaded {len(suggestions_map)} suggestions for documents")

    def _filter_summaries(self):
        """Filter the summaries based on the selected filter."""
        self._load_summaries()  # Reload with the selected filter

    # Document display and PDF-related methods are now handled by the DocumentDisplayWidget

    def _on_document_rated(self, _, rating):
        """
        Handle document rating from the document display widget.

        Args:
            _: Document data dictionary (unused)
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

        # If we're currently viewing bookmarked documents, refresh the list
        if self.filter_combo.currentIndex() == 1:  # Bookmarked
            print(f"Refreshing bookmarked documents list after {action} action")
            self._load_summaries()
        else:
            print(f"Not refreshing list since we're not in bookmarked view")

    def close_database(self):
        """Close the database connections."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        if hasattr(self, 'reading_tracker'):
            self.reading_tracker.close()

        if hasattr(self, 'suggestions_manager'):
            self.suggestions_manager.close()

    def _rate_positive(self):
        """Rate the current document positively (thumbs up)."""
        # This method is now handled by the document display widget
        pass

    def _rate_negative(self):
        """Rate the current document negatively (thumbs down)."""
        # This method is now handled by the document display widget
        pass

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
                    current_item = self.summary_list.list_widget.currentItem()
                    if current_item and hasattr(current_item, 'update_read_status'):
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
        # This method is now handled by the document display widget
        pass


    def _check_bookmark_status(self):
        """Check if the current document is bookmarked."""
        # This method is now handled by the document display widget
        pass

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

        # Update context with the new project ID
        from localknowledge.context import set_current_project
        set_current_project(project_id)

        # Print debug info
        print(f"Setting current project to {project_id}")


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
