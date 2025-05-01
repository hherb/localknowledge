#!/usr/bin/env python3
"""
Document Display Widget for displaying document content in a tabbed interface.

This module provides a reusable widget for displaying document content with
a tabbed interface that can show different aspects of a document (abstract, summary, PDF, etc.).
It includes controls for rating and bookmarking documents.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QCheckBox, QFrame,
    QSplitter, QStatusBar, QSizePolicy
)

# Import context management
from localknowledge.context import (
    register_context_listener, unregister_context_listener,
    get_current_user, get_current_project,
    CURRENT_USER, CURRENT_PROJECT
)

# Import our custom widgets
from localknowledge.ui.abstract_display_widget import AbstractDisplayWidget
from localknowledge.ui.summary_display_widget import SummaryDisplayWidget
from localknowledge.ui.pdf_display_widget import PDFDisplayWidget

# Configure logging
logger = logging.getLogger(__name__)

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"
USER_ICON_PATH = "localknowledge/ui/icons/user.png"
BOOK_ICON_PATH = "localknowledge/ui/icons/book.png"


class DocumentDisplayWidget(QWidget):
    """
    Widget for displaying document content in a tabbed interface.

    This widget provides a tabbed interface for displaying different aspects of a document,
    such as abstract, PDF, etc. It also includes controls for rating and bookmarking documents.
    """

    # Signals
    documentRated = Signal(dict, int)  # document, rating
    documentBookmarked = Signal(dict, str, bool)  # document, bookmark_type, is_bookmarked

    def __init__(self, parent=None, status_bar=None, db_manager=None, pdf_base_dir=None):
        """
        Initialize the document display widget.

        Args:
            parent: Parent widget
            status_bar: Optional status bar for displaying messages
            db_manager: Optional database manager for database operations
            pdf_base_dir: Optional base directory for PDF files
        """
        super().__init__(parent)

        # Store references
        self.status_bar = status_bar
        self.db_manager = db_manager
        self.pdf_base_dir = pdf_base_dir

        # Initialize variables
        self.current_document = None
        self.current_user_id = None
        self.current_project_id = None

        # Set up UI
        self.setup_ui()

        # Connect to context management system
        self._connect_to_context()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Abstract tab - using our AbstractDisplayWidget
        self.abstract_widget = AbstractDisplayWidget()
        self.tab_widget.addTab(self.abstract_widget, "Abstract")

        # Summary tab - using our SummaryDisplayWidget
        self.summary_widget = SummaryDisplayWidget()
        self.summary_widget.summaryRequested.connect(self._on_summary_requested)
        self.tab_widget.addTab(self.summary_widget, "Summary")

        # PDF tab - using our PDFDisplayWidget
        self.pdf_widget = PDFDisplayWidget(
            parent=self,
            status_bar=self.status_bar,
            pdf_base_dir=self.pdf_base_dir
        )
        self.pdf_widget.pdfNotFound.connect(self._on_pdf_not_found)
        self.pdf_widget.pdfFetchRequested.connect(self._on_pdf_fetch_requested)
        self.pdf_widget.pdfUploadRequested.connect(self._on_pdf_upload_requested)
        self.tab_widget.addTab(self.pdf_widget, "PDF")

        # User interaction panel (ratings and bookmarks)
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

        # Add controls to interaction panel
        interaction_panel_layout.addWidget(rating_group)
        interaction_panel_layout.addStretch(1)
        interaction_panel_layout.addWidget(bookmark_group)

        # Add widgets to main layout - tab widget first, then interaction panel
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(interaction_panel)

    def _connect_to_context(self):
        """Connect to the context management system."""
        # Get current values
        user = get_current_user()
        if user:
            self.current_user_id = user.get('id')

        self.current_project_id = get_current_project()

        # Update project bookmark checkbox enabled state
        self.project_bookmark_cb.setEnabled(self.current_project_id is not None)

        # Register listeners for context changes
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)

    def _disconnect_from_context(self):
        """Disconnect from the context management system."""
        unregister_context_listener(CURRENT_USER, self._on_user_changed)
        unregister_context_listener(CURRENT_PROJECT, self._on_project_changed)

    def _on_user_changed(self, user):
        """
        Handle user change in context.

        Args:
            user: New user data
        """
        self.current_user_id = user.get('id') if user else None

        # Update bookmark status if a document is loaded
        if self.current_document:
            self._check_bookmark_status()

    def _on_project_changed(self, project_id):
        """
        Handle project change in context.

        Args:
            project_id: New project ID
        """
        self.current_project_id = project_id

        # Update project bookmark checkbox enabled state
        self.project_bookmark_cb.setEnabled(project_id is not None)

        # Update bookmark status if a document is loaded
        if self.current_document:
            self._check_bookmark_status()

    def display_document(self, document: Dict[str, Any], suggestion: Optional[Dict[str, Any]] = None):
        """
        Display a document in the widget.

        Args:
            document: Document data dictionary
            suggestion: Optional suggestion data dictionary
        """
        if not document:
            self.clear()
            return

        # Store the current document
        self.current_document = document

        # Get current user and project from context manager
        from localknowledge.context import get_current_user, get_current_project
        user = get_current_user()
        project = get_current_project()

        self.current_user_id = user.get('id', 1) if user else 1
        # Handle project being either an integer (project ID) or a dictionary with an 'id' key
        if isinstance(project, dict) and 'id' in project:
            self.current_project_id = project['id']
        else:
            self.current_project_id = project  # project is already the ID or None

        logger.info(f"Displaying document with user_id={self.current_user_id}, project_id={self.current_project_id}")

        # If no suggestion was provided, try to get it from the document
        if not suggestion and document.get('id'):
            # Try to get suggestion from the database
            from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
            suggestions_manager = ReadingSuggestionsManager()
            suggestion = suggestions_manager.get_suggestion_by_document(document.get('id'), self.current_user_id)

            # If no suggestion found for current user, try user_id=1 as fallback
            if not suggestion and self.current_user_id != 1:
                suggestion = suggestions_manager.get_suggestion_by_document(document.get('id'), 1)

        # Display the document in each tab
        self.abstract_widget.display_document(document, suggestion)
        self.summary_widget.display_document(document)
        self.pdf_widget.display_document(document)

        # Check bookmark status
        self._check_bookmark_status()

        # Check rating
        self._check_rating()

        # Update status bar if available
        if self.status_bar:
            title = document.get('title', 'No Title')
            self.status_bar.showMessage(f"Document: {title}")

    def clear(self):
        """Clear the widget."""
        self.current_document = None
        self.abstract_widget.clear()
        self.summary_widget.clear()
        self.pdf_widget.clear()
        self.rating_label.setText("0")
        self.personal_bookmark_cb.setChecked(False)
        self.project_bookmark_cb.setChecked(False)

    def _on_summary_requested(self, document: Dict[str, Any]):
        """
        Handle request to generate a summary for a document.

        Args:
            document: Document for which to generate a summary
        """
        if not document:
            return

        # For now, just show a message in the status bar
        if self.status_bar:
            self.status_bar.showMessage("Summary generation is not yet implemented")

        # In the future, this would call a summary generation service
        # and update the summary widget when complete

    def set_summary_generator(self, generator: Callable[[Dict[str, Any]], str]):
        """
        Set the function to use for generating summaries.

        Args:
            generator: Function that takes a document and returns a summary
        """
        self.summary_widget.set_summary_generator(generator)

    def set_pdf_base_dir(self, pdf_base_dir: str):
        """
        Set the base directory for PDF files.

        Args:
            pdf_base_dir: Base directory for PDF files
        """
        self.pdf_base_dir = pdf_base_dir
        self.pdf_widget.set_pdf_base_dir(pdf_base_dir)

    def _on_pdf_not_found(self, document: Dict[str, Any]):
        """
        Handle PDF not found event.

        Args:
            document: Document for which PDF was not found
        """
        # Switch to the abstract tab
        self.tab_widget.setCurrentWidget(self.abstract_widget)

        # Show message in status bar
        if self.status_bar:
            self.status_bar.showMessage("PDF not found for this document")

    def _on_pdf_fetch_requested(self, document: Dict[str, Any]):
        """
        Handle request to fetch PDF for a document.

        Args:
            document: Document for which to fetch PDF
        """
        # For now, just show a message in the status bar
        if self.status_bar:
            self.status_bar.showMessage("PDF fetch is not yet implemented")

    def _on_pdf_upload_requested(self, document: Dict[str, Any]):
        """
        Handle request to upload PDF for a document.

        Args:
            document: Document for which to upload PDF
        """
        # For now, just show a message in the status bar
        if self.status_bar:
            self.status_bar.showMessage("PDF upload is not yet implemented")

    def _check_bookmark_status(self):
        """Check if the current document is bookmarked."""
        if not self.current_document or not self.db_manager or not self.current_user_id:
            # Reset checkboxes
            self.personal_bookmark_cb.setChecked(False)
            self.project_bookmark_cb.setChecked(False)
            logger.info("Reset bookmark checkboxes: missing document, db_manager, or user_id")
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            logger.error(f"Cannot check bookmark status: missing source_name or external_id in document: {self.current_document}")
            return

        try:
            # Get current user and project from context manager
            from localknowledge.context import get_current_user, get_current_project
            user = get_current_user()
            project = get_current_project()

            self.current_user_id = user.get('id', 1) if user else 1
            # Handle project being either an integer (project ID) or a dictionary with an 'id' key
            if isinstance(project, dict) and 'id' in project:
                self.current_project_id = project['id']
            else:
                self.current_project_id = project  # project is already the ID or None

            # Log the document we're checking
            logger.info(f"Checking bookmark status for document: source={source_name}, id={external_id}, " +
                       f"user={self.current_user_id}, project={self.current_project_id}")

            # Check personal bookmark
            personal_bookmark_type = self.db_manager.is_bookmarked(
                source_name=source_name,
                external_id=external_id,
                user_id=self.current_user_id,
                project_id=None
            )
            # Convert to boolean - is_bookmarked returns bookmark type or None
            is_personal_bookmarked = personal_bookmark_type is not None
            logger.info(f"Personal bookmark check result: {personal_bookmark_type}")

            # Check project bookmark if a project is selected
            is_project_bookmarked = False
            if self.current_project_id:
                project_bookmark_type = self.db_manager.is_bookmarked(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.current_user_id,
                    project_id=self.current_project_id
                )
                is_project_bookmarked = project_bookmark_type is not None
                logger.info(f"Project bookmark check result: {project_bookmark_type}")

            # Update checkboxes without triggering signals
            self.personal_bookmark_cb.blockSignals(True)
            self.project_bookmark_cb.blockSignals(True)

            # Convert to boolean values for setChecked
            self.personal_bookmark_cb.setChecked(bool(is_personal_bookmarked))
            self.project_bookmark_cb.setChecked(bool(is_project_bookmarked))
            logger.info(f"Setting checkbox states: personal={bool(is_personal_bookmarked)}, project={bool(is_project_bookmarked)}")

            self.personal_bookmark_cb.blockSignals(False)
            self.project_bookmark_cb.blockSignals(False)

        except Exception as e:
            logger.error(f"Error checking bookmark status: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error checking bookmark status: {e}")

    def _check_rating(self):
        """Check the user's rating for the current document."""
        if not self.current_document or not self.db_manager or not self.current_user_id:
            self.rating_label.setText("0")
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            return

        try:
            # Get the user's rating for this document
            rating = self.db_manager.get_user_rating(
                source_name=source_name,
                external_id=external_id,
                user_id=self.current_user_id
            )

            # Update rating label
            self.rating_label.setText(str(rating) if rating is not None else "0")

        except Exception as e:
            logger.error(f"Error checking rating: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error checking rating: {e}")

    def _rate_positive(self):
        """Rate the current document positively."""
        self._rate_document(1)

    def _rate_negative(self):
        """Rate the current document negatively."""
        self._rate_document(-1)

    def _rate_document(self, rating: int):
        """
        Rate the current document.

        Args:
            rating: Rating value (1 for positive, -1 for negative)
        """
        if not self.current_document or not self.db_manager or not self.current_user_id:
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            return

        try:
            # Set the user's rating for this document
            self.db_manager.set_user_rating(
                source_name=source_name,
                external_id=external_id,
                user_id=self.current_user_id,
                rating=rating
            )

            # Update rating label
            self.rating_label.setText(str(rating))

            # Emit signal
            self.documentRated.emit(self.current_document, rating)

            # Show success message
            if self.status_bar:
                self.status_bar.showMessage(f"Document rated {'positively' if rating > 0 else 'negatively'}")

        except Exception as e:
            logger.error(f"Error rating document: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error rating document: {e}")

    def _toggle_personal_bookmark(self, state):
        """
        Toggle personal bookmark for the current document.

        Args:
            state: Checkbox state (Qt.Checked or Qt.Unchecked)
        """
        # When checkbox is checked (Qt.Checked), we want to add a bookmark
        # When checkbox is unchecked (Qt.Unchecked), we want to remove a bookmark
        logger.info(f"Personal bookmark checkbox state changed to: {state}")

        # Get the actual checkbox state
        is_checked = self.personal_bookmark_cb.isChecked()
        logger.info(f"Personal bookmark isChecked(): {is_checked}")

        self._toggle_bookmark("personal", is_checked)

    def _toggle_project_bookmark(self, state):
        """
        Toggle project bookmark for the current document.

        Args:
            state: Checkbox state (Qt.Checked or Qt.Unchecked)
        """
        # When checkbox is checked (Qt.Checked), we want to add a bookmark
        # When checkbox is unchecked (Qt.Unchecked), we want to remove a bookmark
        logger.info(f"Project bookmark checkbox state changed to: {state}")

        # Get the actual checkbox state
        is_checked = self.project_bookmark_cb.isChecked()
        logger.info(f"Project bookmark isChecked(): {is_checked}")

        self._toggle_bookmark("project", is_checked)

    def _toggle_bookmark(self, bookmark_type: str, is_bookmarked: bool):
        """
        Toggle bookmark for the current document.

        Args:
            bookmark_type: Type of bookmark ("personal" or "project")
            is_bookmarked: Whether to bookmark or unbookmark
        """
        if not self.current_document or not self.db_manager or not self.current_user_id:
            logger.error("Cannot toggle bookmark: missing document, db_manager, or user_id")
            return

        source_name = self.current_document.get('source_name')
        external_id = self.current_document.get('external_id')

        if not source_name or not external_id:
            logger.error(f"Cannot toggle bookmark: missing source_name or external_id in document: {self.current_document}")
            return

        try:
            # Determine project ID based on bookmark type
            project_id = None
            if bookmark_type == "project" or (bookmark_type == "personal" and self.project_bookmark_cb.isChecked()):
                project_id = self.current_project_id
                if not project_id:
                    # Can't bookmark to a project if none is selected
                    logger.error("Cannot toggle project bookmark: no project selected")
                    return

            # Determine the actual bookmark type to use
            actual_bookmark_type = bookmark_type

            # If toggling personal bookmark and project is also checked, use "both"
            if bookmark_type == "personal" and self.project_bookmark_cb.isChecked() and is_bookmarked:
                actual_bookmark_type = "both"
                logger.info("Both personal and project checkboxes are checked, using 'both' bookmark type")

            # If toggling project bookmark and personal is also checked, use "both"
            if bookmark_type == "project" and self.personal_bookmark_cb.isChecked() and is_bookmarked:
                actual_bookmark_type = "both"
                logger.info("Both personal and project checkboxes are checked, using 'both' bookmark type")

            # Log the action being performed
            logger.info(f"Toggle bookmark: type={actual_bookmark_type}, is_bookmarked={is_bookmarked}, " +
                       f"source={source_name}, id={external_id}, user={self.current_user_id}, project={project_id}")

            # Set or remove bookmark
            if is_bookmarked:
                # Adding a bookmark
                logger.info(f"Adding bookmark of type {actual_bookmark_type} with project_id={project_id}")
                result = self.db_manager.add_bookmark(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.current_user_id,
                    bookmark_type=actual_bookmark_type,
                    project_id=project_id
                )
                status_msg = f"Added to {'both personal and project' if actual_bookmark_type == 'both' else ('project' if project_id and actual_bookmark_type == 'project' else 'personal')} bookmarks"
                logger.info(f"Add bookmark result: {result}")

                # Verify the bookmark was added
                check_result = self.db_manager.is_bookmarked(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.current_user_id,
                    project_id=project_id
                )
                logger.info(f"Verification after adding: is_bookmarked={check_result}")
            else:
                # Removing a bookmark
                logger.info(f"Removing bookmark with project_id={project_id}")
                result = self.db_manager.remove_bookmark(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.current_user_id,
                    project_id=project_id
                )
                status_msg = f"Removed from {'project' if project_id else 'personal'} bookmarks"
                logger.info(f"Remove bookmark result: {result}")

                # Verify the bookmark was removed
                check_result = self.db_manager.is_bookmarked(
                    source_name=source_name,
                    external_id=external_id,
                    user_id=self.current_user_id,
                    project_id=project_id
                )
                logger.info(f"Verification after removing: is_bookmarked={check_result}")

            # Emit signal
            self.documentBookmarked.emit(self.current_document, actual_bookmark_type, is_bookmarked)

            # Show success message
            if self.status_bar:
                self.status_bar.showMessage(status_msg)

        except Exception as e:
            logger.error(f"Error toggling bookmark: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error toggling bookmark: {e}")

    def closeEvent(self, event):
        """
        Handle widget close event.

        Args:
            event: Close event
        """
        # Disconnect from context management system
        self._disconnect_from_context()

        # Accept the event
        event.accept()
