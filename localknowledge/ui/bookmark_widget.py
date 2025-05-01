"""
Bookmark widget for displaying and managing bookmarks.

This module provides a widget for displaying and managing bookmarks
for a research project.
"""
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QSizePolicy, QMessageBox, QListWidget, QListWidgetItem,
    QLineEdit, QScrollArea, QSplitter
)
from PySide6.QtGui import QIcon, QPixmap, QColor

from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.ui.document_display_widget import DocumentDisplayWidget


class BookmarkItem(QFrame):
    """Widget for displaying a bookmarked document with delete button."""

    # Signals
    clicked = Signal(int)  # Signal emitted when the item is clicked with document_id
    deleteClicked = Signal(int)  # Signal emitted when the delete button is clicked with document_id

    def __init__(self, document_data: Dict[str, Any], parent=None):
        """
        Initialize the bookmark item.

        Args:
            document_data: Document data dictionary
            parent: Parent widget
        """
        super().__init__(parent)

        # Check if document_data is a dictionary
        if not isinstance(document_data, dict):
            print(f"Warning: document_data is not a dictionary: {type(document_data)}")
            # Create a minimal document data dictionary
            self.document_data = {'id': document_data if isinstance(document_data, int) else 0,
                                 'title': f"Unknown document ({type(document_data)})"}
        else:
            # Store the document data
            self.document_data = document_data

        # Set up the UI
        self.setup_ui()

        # Make the item clickable
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)

        # Set minimum size
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Set stylesheet
        self.setStyleSheet("""
            BookmarkItem {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
            BookmarkItem:hover {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
            }
        """)

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Document content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)

        # Document title
        title = self.document_data.get('title', 'No Title')
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.title_label.setWordWrap(True)
        content_layout.addWidget(self.title_label)

        # Document metadata
        metadata = []

        try:
            # Source
            source_name = self.document_data.get('source_name', '')
            if source_name:
                metadata.append(str(source_name))

            # Publication date
            pub_date = self.document_data.get('publication_date', '')
            if pub_date:
                # Convert date to string if it's a date object
                if hasattr(pub_date, 'strftime'):
                    pub_date = pub_date.strftime('%Y-%m-%d')
                metadata.append(str(pub_date))

            # Authors
            authors = self.document_data.get('authors', '')
            if authors:
                # Convert authors to string if it's a list
                if isinstance(authors, list):
                    # Make sure all list items are strings
                    authors = ", ".join(str(author) for author in authors)
                # Truncate author list if too long
                if isinstance(authors, str) and len(authors) > 50:
                    authors = authors[:47] + "..."
                metadata.append(str(authors))

            # Join metadata items, ensuring all are strings
            metadata_text = " | ".join(str(item) for item in metadata)
        except Exception as e:
            print(f"Error processing metadata: {e}")
            metadata_text = "Metadata unavailable"
        self.metadata_label = QLabel(metadata_text)
        self.metadata_label.setStyleSheet("color: #666; font-size: 10px;")
        content_layout.addWidget(self.metadata_label)

        # Add content layout to main layout
        layout.addLayout(content_layout, 1)  # 1 is stretch factor

        # Delete button
        self.delete_button = QPushButton()
        self.delete_button.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Remove bookmark")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #ddd;
                border-radius: 12px;
            }
        """)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_button)

    def mousePressEvent(self, event):
        """Handle mouse press event to emit clicked signal."""
        super().mousePressEvent(event)

        # Emit the document ID instead of the document data
        document_id = self.document_data.get('id')
        if document_id:
            self.clicked.emit(document_id)
        else:
            print("Warning: Document ID not found in document data")

    def _on_delete_clicked(self):
        """Handle delete button click."""
        # Emit the document ID instead of the document data
        document_id = self.document_data.get('id')
        if document_id:
            self.deleteClicked.emit(document_id)
        else:
            print("Warning: Document ID not found in document data")


class BookmarkWidget(QWidget):
    """Widget for displaying and managing bookmarks."""

    # Signal emitted when a bookmark is removed
    bookmarkRemoved = Signal(dict)  # Emits the document data dictionary

    def __init__(self, parent=None):
        """Initialize the bookmark widget."""
        super().__init__(parent)

        # Set up database manager
        self.db_manager = DocumentDatabaseManager()

        # Current project ID and user ID
        self.project_id = None
        self.user_id = None

        # Set up the UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status banner for non-intrusive feedback
        self.status_banner = QLabel()
        self.status_banner.setAlignment(Qt.AlignCenter)
        self.status_banner.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                border-radius: 4px;
                margin: 4px;
                font-weight: bold;
            }
        """)
        self.status_banner.setVisible(False)
        layout.addWidget(self.status_banner)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.main_splitter)

        # Left side - Bookmarks list
        left_widget = QWidget()
        left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        self.main_splitter.addWidget(left_widget)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)

        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search bookmarks...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        left_layout.addLayout(search_layout)

        # Bookmarks list
        bookmarks_layout = QVBoxLayout()
        bookmarks_layout.setSpacing(5)

        # Bookmarks list label
        bookmarks_label = QLabel("Project Bookmarks")
        bookmarks_label.setStyleSheet("font-weight: bold;")
        bookmarks_layout.addWidget(bookmarks_label)

        # Bookmarks list scroll area
        self.bookmarks_scroll = QScrollArea()
        self.bookmarks_scroll.setWidgetResizable(True)
        self.bookmarks_scroll.setFrameShape(QFrame.NoFrame)

        # Bookmarks list container
        self.bookmarks_container = QWidget()
        self.bookmarks_layout = QVBoxLayout(self.bookmarks_container)
        self.bookmarks_layout.setContentsMargins(0, 0, 0, 0)
        self.bookmarks_layout.setSpacing(5)
        self.bookmarks_layout.addStretch(1)  # Push items to the top

        # Set the container as the scroll area widget
        self.bookmarks_scroll.setWidget(self.bookmarks_container)

        # Add scroll area to bookmarks layout
        bookmarks_layout.addWidget(self.bookmarks_scroll)

        # Add bookmarks layout to left layout
        left_layout.addLayout(bookmarks_layout)

        # Right side - Document display
        right_widget = QWidget()
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.main_splitter.addWidget(right_widget)

        # Document display widget
        self.document_display = DocumentDisplayWidget()
        right_layout.addWidget(self.document_display)

        # Set splitter sizes (1:2 ratio)
        self.main_splitter.setSizes([1, 2])

    def load_project(self, project_id: int, user_id: int):
        """
        Load bookmarks for a project.

        Args:
            project_id: Project ID
            user_id: User ID
        """
        self.project_id = project_id
        self.user_id = user_id

        # Clear existing bookmarks
        self._clear_bookmarks()

        try:
            # Get bookmarks for this project
            bookmarks = self.db_manager.get_bookmarked_documents(user_id, project_id)

            if bookmarks:
                # Add bookmarks to the list
                for bookmark in bookmarks:
                    try:
                        self._add_bookmark_item(bookmark)
                    except Exception as e:
                        print(f"Error adding bookmark item: {e}")
                        # Continue with the next bookmark
                        continue
        except Exception as e:
            print(f"Error loading bookmarks: {e}")
            # Show a message to the user
            QMessageBox.warning(
                self,
                "Error",
                f"Could not load bookmarks for this project: {str(e)}"
            )

    def show_status_message(self, message: str, success: bool = True, duration_ms: int = 3000):
        """
        Show a status message in the banner.

        Args:
            message: Message to display
            success: Whether this is a success message (green) or error message (red)
            duration_ms: How long to display the message in milliseconds
        """
        # Set the message
        self.status_banner.setText(message)

        # Set the color based on success/error
        if success:
            self.status_banner.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    margin: 4px;
                    font-weight: bold;
                }
            """)
        else:
            self.status_banner.setStyleSheet("""
                QLabel {
                    background-color: #F44336;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    margin: 4px;
                    font-weight: bold;
                }
            """)

        # Show the banner
        self.status_banner.setVisible(True)

        # Hide after duration
        QTimer.singleShot(duration_ms, lambda: self.status_banner.setVisible(False))

    def _clear_bookmarks(self):
        """Clear all bookmarks from the list."""
        # Remove all widgets from the bookmarks layout except the stretch at the end
        while self.bookmarks_layout.count() > 1:
            item = self.bookmarks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_bookmark_item(self, document_data: Dict[str, Any]):
        """
        Add a bookmark item to the list.

        Args:
            document_data: Document data dictionary
        """
        # Create bookmark item
        item = BookmarkItem(document_data)
        item.deleteClicked.connect(self._on_delete_bookmark)
        item.clicked.connect(self._on_bookmark_selected)

        # Add to layout before the stretch
        self.bookmarks_layout.insertWidget(self.bookmarks_layout.count() - 1, item)

    def _on_bookmark_selected(self, document_id: int):
        """
        Handle bookmark selection.

        Args:
            document_id: Document ID
        """
        try:
            # Fetch the document from the database
            document = self.db_manager.get_document(document_id)

            if not document:
                print(f"Document not found with ID: {document_id}")
                self.show_status_message(f"Document not found with ID: {document_id}", success=False)
                return

            # Display the document directly in our document display widget

            # Set the title and abstract directly
            title = document.get('title', 'No Title')
            abstract = document.get('abstract', 'No abstract available')
            authors = document.get('authors', [])
            if isinstance(authors, list):
                authors_text = ', '.join(str(author) for author in authors)
            else:
                authors_text = str(authors)

            publication_date = document.get('publication_date', '')
            if hasattr(publication_date, 'strftime'):
                publication_date = publication_date.strftime('%Y-%m-%d')

            # Format the HTML
            html = f"""
            <h2>{title}</h2>
            <p><i>{authors_text}</i></p>
            <p><small>Published: {publication_date}</small></p>
            <hr>
            <p>{abstract}</p>
            """

            # Set the HTML in the abstract widget
            self.document_display.abstract_widget.abstract_view.setHtml(html)

            # Set the current document in the document display widget
            self.document_display.current_document = document
        except Exception as e:
            print(f"Error displaying document: {e}")
            # Show a message in the status banner
            self.show_status_message(f"Could not display the selected document: {str(e)}", success=False)

    def _on_delete_bookmark(self, document_id: int):
        """
        Handle delete bookmark button click.

        Args:
            document_id: Document ID
        """
        try:
            # Fetch the document from the database
            document = self.db_manager.get_document(document_id)
            if not document:
                print(f"Document not found with ID: {document_id}")
                self.show_status_message(f"Document not found with ID: {document_id}", success=False)
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                "Are you sure you want to remove this bookmark?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # Remove bookmark
                source_name = document.get('source_name')
                external_id = document.get('external_id')

                if not source_name or not external_id:
                    self.show_status_message("Could not identify document for bookmark removal", success=False)
                    return

                success = self.db_manager.remove_bookmark(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.user_id,
                    project_id=self.project_id
                )

                if success:
                    # Show success message in the status banner
                    self.show_status_message("Bookmark removed successfully", success=True)

                    # Reload bookmarks
                    self.load_project(self.project_id, self.user_id)

                    # Emit signal
                    self.bookmarkRemoved.emit(document)

                    # Clear document display
                    self.document_display.clear()
                else:
                    # Show error message in the status banner
                    self.show_status_message("Failed to remove bookmark", success=False)
        except Exception as e:
            print(f"Error deleting bookmark: {e}")
            self.show_status_message(f"Could not delete the bookmark: {str(e)}", success=False)

    def _on_search_changed(self, search_text: str):
        """
        Handle search text changed.

        Args:
            search_text: Search text
        """
        if not self.project_id or not self.user_id:
            return

        # Clear existing bookmarks
        self._clear_bookmarks()

        # Get bookmarks for this project
        bookmarks = self.db_manager.get_bookmarked_documents(self.user_id, self.project_id)

        if bookmarks:
            # Filter bookmarks by search text
            if search_text:
                search_text = search_text.lower()
                filtered_bookmarks = []

                for bookmark in bookmarks:
                    # Search in title, authors, abstract
                    title = bookmark.get('title', '').lower()
                    authors = bookmark.get('authors', '').lower()
                    abstract = bookmark.get('abstract', '').lower()

                    if (search_text in title or
                        search_text in authors or
                        search_text in abstract):
                        filtered_bookmarks.append(bookmark)

                bookmarks = filtered_bookmarks

            # Add bookmarks to the list
            for bookmark in bookmarks:
                self._add_bookmark_item(bookmark)


# For testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the bookmark widget
    bookmark_widget = BookmarkWidget()
    layout.addWidget(bookmark_widget)

    # Set a test project ID and user ID
    bookmark_widget.load_project(1, 1)  # Assuming project ID 1 and user ID 1 exist

    # Show the window
    window.setGeometry(100, 100, 800, 600)
    window.show()

    sys.exit(app.exec())
