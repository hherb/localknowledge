#!/usr/bin/env python3
"""
Document List Widget for displaying document items.

This module provides a reusable widget for displaying document items with
consistent formatting across different parts of the application.
Each item displays the title in bold on the first line, and a second line with
source icon, optional recommendation/bookmark indicators, publication date, and authors.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QIcon, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QStyle, QLabel
)

from localknowledge.ui.styles import STYLE_SHEETS, get_font, get_color

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"
USER_ICON_PATH = "localknowledge/ui/icons/user.png"
BOOK_ICON_PATH = "localknowledge/ui/icons/book.png"

# Configure logging
logger = logging.getLogger(__name__)


class DocumentItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering document items with source icons and metadata."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)
        # Load icons
        self.pubmed_icon = QIcon(PUBMED_ICON_PATH)
        self.medrxiv_icon = QIcon(MEDRXIV_ICON_PATH)
        self.personal_bookmark_icon = QIcon(USER_ICON_PATH)
        self.project_bookmark_icon = QIcon(BOOK_ICON_PATH)

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
        if not item or not isinstance(item, DocumentItem):
            # Try to get the list widget and the item from it
            list_widget = self.parent()
            if isinstance(list_widget, QListWidget):
                item = list_widget.item(index.row())

            # If we still don't have a valid item, fall back to default rendering
            if not item or not isinstance(item, DocumentItem):
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
        rect = option.rect.adjusted(5, 5, -5, -5)  # Add some padding
        icon_size = QSize(16, 16)  # Size of the source icon

        # Calculate title and metadata positions
        title_rect = QRect(rect.left(), rect.top(), rect.width(), rect.height() // 2)
        metadata_rect = QRect(rect.left(), rect.top() + rect.height() // 2, rect.width(), rect.height() // 2)

        # Draw title with bold font
        title_font = painter.font()
        title_font.setBold(True)
        painter.setFont(title_font)

        document = item.document
        title = document.get('title', 'No Title')
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, title)

        # Reset font for metadata
        metadata_font = painter.font()
        metadata_font.setBold(False)
        painter.setFont(metadata_font)

        # Draw source icon
        source_id = document.get('source_id')
        icon_rect = QRect(metadata_rect.left(), metadata_rect.top() + (metadata_rect.height() - icon_size.height()) // 2,
                         icon_size.width(), icon_size.height())

        if source_id == 1:  # PubMed
            self.pubmed_icon.paint(painter, icon_rect)
        elif source_id == 2:  # medRxiv
            self.medrxiv_icon.paint(painter, icon_rect)

        # Move to the right of the source icon
        current_x = icon_rect.right() + 4

        # Draw recommendation info if available
        if hasattr(item, 'suggestion') and item.suggestion:
            strength = item.suggestion.get('recommendation_strength', 0)
            evaluator_name = item.suggestion.get('evaluator_name', 'Unknown')

            if strength > 0:
                # Use stars to indicate strength (★)
                stars = "★" * min(strength, 5)  # Limit to 5 stars max

                # Format the recommendation text with evaluator name
                rec_text = f"Recommended ({stars}) by {evaluator_name}"

                # Set color based on strength
                if strength >= 4:
                    painter.setPen(QColor(0, 128, 0))  # Dark green for high recommendations
                elif strength >= 2:
                    painter.setPen(QColor(0, 0, 128))  # Dark blue for medium recommendations

                # Draw the recommendation text
                rec_width = painter.fontMetrics().horizontalAdvance(rec_text)
                rec_rect = QRect(current_x, metadata_rect.top(), rec_width, metadata_rect.height())
                painter.drawText(rec_rect, Qt.AlignLeft | Qt.AlignVCenter, rec_text)

                # Reset pen color
                if option.state & QStyle.State_Selected:
                    painter.setPen(option.palette.highlightedText().color())
                else:
                    painter.setPen(option.palette.text().color())

                current_x = rec_rect.right() + 8

        # Draw bookmark icons if this is a bookmarked document
        bookmark_type = document.get('bookmark_type')
        if bookmark_type:
            # Draw personal bookmark icon (user emoji)
            if bookmark_type in ('personal', 'both'):
                bookmark_icon_rect = QRect(current_x, icon_rect.top(),
                                          icon_size.width(), icon_size.height())
                self.personal_bookmark_icon.paint(painter, bookmark_icon_rect)
                current_x = bookmark_icon_rect.right() + 4

            # Draw project bookmark icon (book emoji)
            if bookmark_type in ('project', 'both'):
                bookmark_icon_rect = QRect(current_x, icon_rect.top(),
                                          icon_size.width(), icon_size.height())
                self.project_bookmark_icon.paint(painter, bookmark_icon_rect)
                current_x = bookmark_icon_rect.right() + 4

        # Draw publication date
        date = document.get('publication_date', '')
        date_str = ""
        if date:
            if isinstance(date, datetime):
                date_str = date.strftime("%Y-%m-%d")
            elif isinstance(date, str):
                date_str = date
            else:
                # Try to get just the year
                try:
                    date_str = str(date.year)
                except:
                    date_str = str(date)

        if date_str:
            date_width = painter.fontMetrics().horizontalAdvance(date_str)
            date_rect = QRect(current_x, metadata_rect.top(), date_width, metadata_rect.height())
            painter.drawText(date_rect, Qt.AlignLeft | Qt.AlignVCenter, date_str)
            current_x = date_rect.right() + 8

        # Draw authors (trimmed to max 25 chars)
        authors = document.get('authors', [])
        if authors:
            if isinstance(authors, list):
                authors_str = ", ".join(authors)
            else:
                authors_str = str(authors)

            if len(authors_str) > 25:
                authors_str = authors_str[:25] + "..."

            if authors_str:
                authors_rect = QRect(current_x, metadata_rect.top(),
                                    metadata_rect.right() - current_x, metadata_rect.height())
                painter.drawText(authors_rect, Qt.AlignLeft | Qt.AlignVCenter, authors_str)

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
        # Make items a bit taller to accommodate two lines of text
        return QSize(size.width(), max(size.height(), 44))


class DocumentItem(QListWidgetItem):
    """List widget item to display document details with metadata."""

    def __init__(self, document: Dict[str, Any], is_read: bool = False,
                 suggestion: Optional[Dict[str, Any]] = None):
        """
        Initialize a document list item.

        Args:
            document: Dictionary containing document details
            is_read: Whether the document has been read
            suggestion: Optional dictionary with suggestion details
        """
        super().__init__()
        self.document = document
        self.is_read = is_read
        self.suggestion = suggestion

        # Set a reasonable size hint
        self.setSizeHint(QSize(300, 44))

        # Set font based on read status
        font = QFont()
        if not is_read:
            font.setBold(True)
        self.setFont(font)

        # Set tooltip with full title, authors, and recommendation info
        title = document.get('title', 'No Title')
        authors = document.get('authors', [])
        if isinstance(authors, list):
            authors_str = ", ".join(authors)
        else:
            authors_str = str(authors)

        tooltip = f"{title}\n{authors_str}"

        # Add recommendation info to tooltip if available
        if suggestion:
            strength = suggestion.get('recommendation_strength', 0)
            evaluator_name = suggestion.get('evaluator_name', 'Unknown')
            confidence = suggestion.get('confidence_level', 0)
            comment = suggestion.get('comment', '')

            if strength > 0:
                stars = "★" * min(strength, 5)  # Limit to 5 stars max
                tooltip += f"\n\nRecommendation: {stars} ({strength}/5)"
                tooltip += f"\nBy: {evaluator_name}"

                if confidence:
                    tooltip += f"\nConfidence: {confidence:.2f}"

                if comment:
                    # Truncate long comments in tooltip
                    if len(comment) > 200:
                        comment = comment[:197] + "..."
                    tooltip += f"\n\nComment: {comment}"

        self.setToolTip(tooltip)

    def update_read_status(self, is_read: bool):
        """
        Update the read status of the item.

        Args:
            is_read: Whether the document has been read
        """
        self.is_read = is_read
        font = self.font()
        font.setBold(not is_read)
        self.setFont(font)


class DocumentListWidget(QWidget):
    """Widget for displaying a list of documents with consistent formatting."""

    # Signal emitted when a document is selected
    documentSelected = Signal(dict)

    # Signal emitted when a document is double-clicked
    documentActivated = Signal(dict)

    def __init__(self, parent=None):
        """Initialize the document list widget."""
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)

        # Set custom delegate for rendering items
        self.item_delegate = DocumentItemDelegate(self.list_widget)
        self.list_widget.setItemDelegate(self.item_delegate)

        # Set item height to accommodate icons and two lines of text
        self.list_widget.setIconSize(QSize(16, 16))

        # Apply stylesheet
        self.list_widget.setStyleSheet(STYLE_SHEETS["LIST_WIDGET"])

        # Connect signals
        self.list_widget.currentItemChanged.connect(self._on_document_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_document_activated)

        # Add list widget to layout
        layout.addWidget(self.list_widget)

    def add_document(self, document: Dict[str, Any], is_read: bool = False,
                    suggestion: Optional[Dict[str, Any]] = None) -> Optional[DocumentItem]:
        """
        Add a document to the list.

        Args:
            document: Dictionary containing document details
            is_read: Whether the document has been read
            suggestion: Optional dictionary with suggestion details

        Returns:
            The created DocumentItem or None if creation failed
        """
        try:
            item = DocumentItem(document, is_read, suggestion)
            self.list_widget.addItem(item)
            return item
        except Exception as e:
            logger.error(f"Failed to add document: {str(e)}")
            return None

    def clear(self):
        """Clear all items from the list."""
        self.list_widget.clear()

    def get_current_document(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently selected document.

        Returns:
            Dictionary containing document details or None if no document is selected
        """
        current_item = self.list_widget.currentItem()
        if current_item and isinstance(current_item, DocumentItem):
            return current_item.document
        return None

    def set_documents(self, documents: List[Dict[str, Any]],
                     read_ids: Optional[List[int]] = None,
                     suggestions: Optional[Dict[int, Dict[str, Any]]] = None):
        """
        Set the list of documents to display.

        Args:
            documents: List of document dictionaries
            read_ids: Optional list of IDs of documents that have been read
            suggestions: Optional dictionary mapping document IDs to suggestion details
        """
        print("\n=== Debug: DocumentListWidget.set_documents ===")
        print(f"Received {len(documents)} documents")
        print(f"Read IDs: {read_ids}")
        print(f"Suggestions map contains {len(suggestions) if suggestions else 0} items")

        self.clear()

        if not documents:
            print("No documents to display")
            no_docs_item = QListWidgetItem("No documents found")
            no_docs_item.setFlags(no_docs_item.flags() & ~Qt.ItemIsEnabled)
            self.list_widget.addItem(no_docs_item)
            print("=== End Debug ===\n")
            return

        read_ids = read_ids or set()
        suggestions = suggestions or {}

        for idx, document in enumerate(documents):
            doc_id = document.get('id')
            print(f"\nProcessing document {idx + 1}:")
            print(f"ID: {doc_id}")
            print(f"Title: {document.get('title', 'No Title')}")

            # Check if this document is in the read set
            is_read = doc_id in read_ids
            print(f"Is read: {is_read}")

            # Get suggestion for this document if available
            suggestion = suggestions.get(doc_id)
            print(f"Has suggestion: {bool(suggestion)}")
            if suggestion:
                print(f"Suggestion strength: {suggestion.get('recommendation_strength')}")

            # Add the document to the list
            item = self.add_document(document, is_read, suggestion)
            if item:
                print("Document item added successfully")
            else:
                print("Failed to add document item")

        print(f"\nFinal list widget item count: {self.list_widget.count()}")
        print("=== End Debug ===\n")

    def _on_document_selected(self, current, previous):
        """
        Handle document selection in the list.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if current and isinstance(current, DocumentItem):
            self.documentSelected.emit(current.document)

    def _on_document_activated(self, item):
        """
        Handle document activation (double-click) in the list.

        Args:
            item: Activated item
        """
        if item and isinstance(item, DocumentItem):
            self.documentActivated.emit(item.document)
