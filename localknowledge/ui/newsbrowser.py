"""
This module provides a PySide6 widget for browsing publication summaries
in an email client-like interface with read/unread status tracking.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import traceback

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QSize, QPointF, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QLabel, QMessageBox, QApplication, QTextBrowser, QTextEdit,
    QFrame, QComboBox, QCheckBox, QToolBar, QMainWindow, QStatusBar,
    QDialog, QDialogButtonBox, QSizePolicy, QScrollArea
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
import fitz  # PyMuPDF for PDF search and highlighting

# Import markdown module if available
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.reading_tracker import ReadingTrackerManager


class SummaryItem(QListWidgetItem):
    """List widget item to display publication summary details with read/unread status."""

    def __init__(self, publication: Dict[str, Any], summary: Dict[str, Any], is_read: bool = False):
        """
        Initialize a summary list item.

        Args:
            publication: Dictionary containing publication details
            summary: Dictionary containing summary details
            is_read: Whether the summary has been read
        """
        self.publication = publication
        self.summary = summary
        self.is_read = is_read

        # Get display data
        title = publication.get('title', 'No Title')
        date = publication.get('date_posted', '')
        evaluation = "✓" if summary.get('evaluation', False) else "✗"

        # Format title with HTML - handle long titles
        if len(title) > 80:
            title = title[:77] + "..."

        # Set display text based on read status
        if not is_read:
            display_text = f"<b>{title}</b>\n{date} • Relevance: {evaluation}"
        else:
            display_text = f"{title}\n{date} • Relevance: {evaluation}"

        # Initialize the item with display text
        super().__init__(display_text)

        # Make the item slightly taller for better readability
        self.setSizeHint(QSize(self.sizeHint().width(), self.sizeHint().height() + 10))

        # Set tooltip to show full title on hover
        self.setToolTip(f"{publication.get('title', 'No Title')}")

        # Apply different styling based on read status
        self.update_read_status(is_read)

    def update_read_status(self, is_read: bool = True):
        """
        Update the read status of the item.

        Args:
            is_read: Whether the item has been read
        """
        self.is_read = is_read

        # Apply different background color based on read status
        if not is_read:
            # Unread items are bold and have a light blue background
            font = self.font()
            font.setBold(True)
            self.setFont(font)
            self.setBackground(QColor(240, 248, 255))  # Light blue
        else:
            # Read items have normal font and white background
            font = self.font()
            font.setBold(False)
            self.setFont(font)
            self.setBackground(QColor(255, 255, 255))  # White

        # Update the text to reflect read status - without using HTML tags
        title = self.publication.get('title', 'No Title')
        if len(title) > 80:
            title = title[:77] + "..."

        date = self.publication.get('date_posted', '')
        evaluation = "✓" if self.summary.get('evaluation', False) else "✗"

        # Don't use HTML tags in setText() since QListWidgetItem doesn't render HTML
        # The bold font is already set with setFont() above
        self.setText(f"{title}\n{date} • Relevance: {evaluation}")


class NewsBrowser(QWidget):
    """A PySide6 widget for browsing publication summaries like an email client."""

    # Signal emitted when a publication is selected
    summarySelected = Signal(dict, dict)

    def __init__(self, parent=None):
        """
        Initialize the news browser widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.db_manager = MedRxivDatabaseManager()
        # Initialize reading tracker for persistent read/unread status
        self.reading_tracker = ReadingTrackerManager()
        self.current_publication = None
        self.current_summary = None
        self.pdf_base_dir = self._get_pdf_base_dir()
        self.read_summaries = set()  # Local cache of read summaries for performance

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
        self.filter_combo.addItem("All Summaries")
        self.filter_combo.addItem("Unread Only")
        self.filter_combo.addItem("Relevant Only")
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

        # Add to interaction panel
        interaction_panel_layout.addWidget(rating_group)
        interaction_panel_layout.addStretch(1)
        interaction_panel_layout.addWidget(self.notes_btn)

        # Add elements to summary layout
        summary_layout.addWidget(self.summary_view)
        summary_layout.addWidget(interaction_panel)

        self.tab_widget.addTab(summary_container, "Summary")

        # PDF tab
        self.pdf_container = QWidget()
        pdf_layout = QVBoxLayout(self.pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)

        # Create PDF view
        self.pdf_view = QPdfView()
        self.pdf_document = QPdfDocument()
        self.pdf_view.setDocument(self.pdf_document)

        # Enable scrolling in the PDF view
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Show multiple pages for continuous scrolling
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)  # Fit to width by default

        # Create a scroll area to contain the PDF view for better scrolling
        pdf_scroll_area = QScrollArea()
        pdf_scroll_area.setWidget(self.pdf_view)
        pdf_scroll_area.setWidgetResizable(True)  # Allow the view to resize with the scroll area
        pdf_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pdf_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Add PDF navigation controls
        pdf_toolbar = QHBoxLayout()

        self.prev_page_btn = QPushButton("← Previous")
        self.prev_page_btn.clicked.connect(self._go_to_prev_page)
        self.prev_page_btn.setEnabled(False)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_page_btn = QPushButton("Next →")
        self.next_page_btn.clicked.connect(self._go_to_next_page)
        self.next_page_btn.setEnabled(False)

        # Add zoom controls
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self._zoom_in)

        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self._zoom_out)

        self.fit_width_btn = QPushButton("Fit Width")
        self.fit_width_btn.clicked.connect(self._fit_width)

        # Add PDF search controls
        self.pdf_search_input = QLineEdit()
        self.pdf_search_input.setPlaceholderText("Search in PDF...")
        self.pdf_search_input.returnPressed.connect(self._search_pdf)
        self.pdf_search_input.setFixedWidth(200)

        self.prev_match_btn = QPushButton("↑")
        self.prev_match_btn.setToolTip("Previous match")
        self.prev_match_btn.clicked.connect(self._find_prev_match)
        self.prev_match_btn.setEnabled(False)
        self.prev_match_btn.setFixedWidth(30)

        self.next_match_btn = QPushButton("↓")
        self.next_match_btn.setToolTip("Next match")
        self.next_match_btn.clicked.connect(self._find_next_match)
        self.next_match_btn.setEnabled(False)
        self.next_match_btn.setFixedWidth(30)

        # Add controls to toolbar
        pdf_toolbar.addWidget(self.prev_page_btn)
        pdf_toolbar.addWidget(self.page_label)
        pdf_toolbar.addWidget(self.next_page_btn)
        pdf_toolbar.addStretch()
        pdf_toolbar.addWidget(self.pdf_search_input)
        pdf_toolbar.addWidget(self.prev_match_btn)
        pdf_toolbar.addWidget(self.next_match_btn)
        pdf_toolbar.addStretch()
        pdf_toolbar.addWidget(self.zoom_out_btn)
        pdf_toolbar.addWidget(self.fit_width_btn)
        pdf_toolbar.addWidget(self.zoom_in_btn)

        # Add toolbar and PDF view to the layout
        pdf_layout.addLayout(pdf_toolbar)
        pdf_layout.addWidget(pdf_scroll_area)  # Use the scroll area instead of the PDF view directly

        # Add PDF container to tab
        self.tab_widget.addTab(self.pdf_container, "PDF")

        # Add widgets to main splitter
        self.main_splitter.addWidget(self.summary_list)
        self.main_splitter.addWidget(self.tab_widget)

        # Set initial sizes for main splitter (40% for list, 60% for tabs)
        self.main_splitter.setSizes([400, 600])

        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)

        # Create status bar - wrap in container to better control height
        status_container = QWidget()
        status_container.setFixedHeight(25)  # Fix container height to exactly one line
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)

        self.status_bar = QStatusBar()
        self.status_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(self.status_bar)

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
        """Load publication summaries from the database."""
        self.status_bar.showMessage("Loading summaries...")
        self.summary_list.clear()

        # Refresh the read status cache from the database
        self._refresh_read_status_cache()

        # Get all summaries with their publication data
        # This assumes we have a method to get this combined data
        try:
            # Get the current filter
            filter_idx = self.filter_combo.currentIndex()
            filter_text = self.filter_combo.currentText()

            if filter_idx == 0:  # All Summaries
                summaries = self._get_all_summaries()
            elif filter_idx == 1:  # Unread Only
                summaries = self._get_all_summaries()
                # Filter for unread using the read_summaries set
                summaries = [s for s in summaries if s['summary']['id'] not in self.read_summaries]
            elif filter_idx == 2:  # Relevant Only
                summaries = self._get_relevant_summaries()
            else:  # Filter by interest
                interest = filter_text.lower()
                summaries = self._get_summaries_by_interest(interest)

            for summary_data in summaries:
                publication = summary_data['publication']
                summary = summary_data['summary']

                # Check if this summary is in the read set (cached from database)
                is_read = summary['id'] in self.read_summaries

                # Create list item
                item = SummaryItem(publication, summary, is_read)
                self.summary_list.addItem(item)

            if not summaries:
                self.summary_list.addItem("No summaries found")

            self.status_bar.showMessage(f"Loaded {len(summaries)} summaries")

        except Exception as e:
            self.status_bar.showMessage(f"Error: {str(e)}")
            print(f"Error loading summaries: {str(e)}")
            traceback.print_exc()

    def _get_all_summaries(self):
        """
        Get all summaries with their publication data.

        Returns:
            List of dictionaries containing publication and summary data
        """
        # This is a custom query that joins the summaries and publications tables
        query = """
        SELECT
            s.id, s.summary, s.evaluation, s.reason, s.interests, s.created_at,
            p.doi, p.title, p.authors, p.date_posted, p.category, p.pdf_url, p.local_pdf_path
        FROM
            summaries s
        JOIN
            preprints p ON s.publication_id = p.doi
        ORDER BY
            s.created_at DESC
        """

        results = self.db_manager.execute(query)

        # Format the results into the expected structure
        formatted_results = []
        for row in results:
            formatted_results.append({
                'publication': {
                    'doi': row['doi'],
                    'title': row['title'],
                    'authors': row['authors'],
                    'date_posted': row['date_posted'],
                    'category': row['category'],
                    'pdf_url': row['pdf_url'],
                    'local_pdf_path': row['local_pdf_path']
                },
                'summary': {
                    'id': row['id'],
                    'summary': row['summary'],
                    'evaluation': row['evaluation'],
                    'reason': row['reason'],
                    'interests': row['interests'],
                    'created_at': row['created_at']
                }
            })

        return formatted_results

    def _get_relevant_summaries(self):
        """
        Get summaries that were evaluated as relevant.

        Returns:
            List of dictionaries containing publication and summary data
        """
        # This is a custom query that joins the summaries and publications tables
        query = """
        SELECT
            s.id, s.summary, s.evaluation, s.reason, s.interests, s.created_at,
            p.doi, p.title, p.authors, p.date_posted, p.category, p.pdf_url, p.local_pdf_path
        FROM
            summaries s
        JOIN
            preprints p ON s.publication_id = p.doi
        WHERE
            s.evaluation = true
        ORDER BY
            s.created_at DESC
        """

        results = self.db_manager.execute(query)

        # Format the results into the expected structure
        formatted_results = []
        for row in results:
            formatted_results.append({
                'publication': {
                    'doi': row['doi'],
                    'title': row['title'],
                    'authors': row['authors'],
                    'date_posted': row['date_posted'],
                    'category': row['category'],
                    'pdf_url': row['pdf_url'],
                    'local_pdf_path': row['local_pdf_path']
                },
                'summary': {
                    'id': row['id'],
                    'summary': row['summary'],
                    'evaluation': row['evaluation'],
                    'reason': row['reason'],
                    'interests': row['interests'],
                    'created_at': row['created_at']
                }
            })

        return formatted_results

    def _get_summaries_by_interest(self, interest):
        """
        Get summaries that match a specific interest.

        Args:
            interest: Interest string to match

        Returns:
            List of dictionaries containing publication and summary data
        """
        # This is a custom query that joins the summaries and publications tables
        query = """
        SELECT
            s.id, s.summary, s.evaluation, s.reason, s.interests, s.created_at,
            p.doi, p.title, p.authors, p.date_posted, p.category, p.pdf_url, p.local_pdf_path
        FROM
            summaries s
        JOIN
            preprints p ON s.publication_id = p.doi
        WHERE
            %s = ANY(s.interests)
        ORDER BY
            s.created_at DESC
        """

        results = self.db_manager.execute(query, (interest,))

        # Format the results into the expected structure
        formatted_results = []
        for row in results:
            formatted_results.append({
                'publication': {
                    'doi': row['doi'],
                    'title': row['title'],
                    'authors': row['authors'],
                    'date_posted': row['date_posted'],
                    'category': row['category'],
                    'pdf_url': row['pdf_url'],
                    'local_pdf_path': row['local_pdf_path']
                },
                'summary': {
                    'id': row['id'],
                    'summary': row['summary'],
                    'evaluation': row['evaluation'],
                    'reason': row['reason'],
                    'interests': row['interests'],
                    'created_at': row['created_at']
                }
            })

        return formatted_results

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_summary_selected(self, current, previous):
        """
        Handle summary selection in the list.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current or not isinstance(current, SummaryItem):
            # Clear the summary view
            self.summary_view.clear()
            self.pdf_document.close()
            return

        # Get the summary and publication data
        self.current_publication = current.publication
        self.current_summary = current.summary

        # Emit the signal with the selected publication and summary
        self.summarySelected.emit(self.current_publication, self.current_summary)

        # Mark as read when selected
        self._mark_current_as_read()

        # Load the reading record to get rating and notes
        self._load_reading_record()

        # Display the summary in the summary view
        self._display_summary()

        # Load the PDF if available
        self._load_pdf()

    def _display_summary(self):
        """Display the selected summary in the summary view."""
        if not self.current_summary or not self.current_publication:
            return

        # Get summary data
        title = self.current_publication.get('title', 'No Title')
        authors = self.current_publication.get('authors', 'Unknown Authors')
        date_posted = self.current_publication.get('date_posted', '')
        category = self.current_publication.get('category', '')
        doi = self.current_publication.get('doi', '')

        summary_text = self.current_summary.get('summary', 'No summary available')
        evaluation = self.current_summary.get('evaluation', False)
        reason = self.current_summary.get('reason', '')
        interests = self.current_summary.get('interests', [])
        created_at = self.current_summary.get('created_at', '')

        # Format evaluation as text
        evaluation_text = 'Relevant' if evaluation else 'Not Relevant'
        evaluation_color = 'green' if evaluation else 'red'

        # Format interests as a list
        interests_text = ', '.join(interests) if interests else 'None'

        # Format the summary as HTML
        html_content = f"""
        <div style="padding: 10px;">
            <h2>{title}</h2>
            <p><b>Authors:</b> {authors}</p>
            <p><b>Date Posted:</b> {date_posted}</p>
            <p><b>Category:</b> {category}</p>
            <p><b>DOI:</b> <a href="https://doi.org/{doi}">{doi}</a></p>
            <hr>
            <p><b>Evaluation:</b> <span style="color: {evaluation_color};">{evaluation_text}</span></p>
            <p><b>Reason:</b> {reason}</p>
            <p><b>Relevant Topics:</b> {interests_text}</p>
            <p><b>Summary Generated:</b> {created_at}</p>
            <hr>
            <h3>Summary</h3>
            <p>{summary_text}</p>
        </div>
        """

        # Set the HTML content
        self.summary_view.setHtml(html_content)

    def _load_pdf(self):
        """Load the selected publication's PDF into the PDF view."""
        if not self.current_publication:
            return

        # Get the local PDF path
        local_pdf_path = self.current_publication.get('local_pdf_path', '')

        # Try to load PDF
        pdf_found = False

        # First case: We have a local_pdf_path in the database
        if local_pdf_path:
            # Convert to string and ensure proper path handling
            if isinstance(self.pdf_base_dir, Path):
                full_pdf_path = self.pdf_base_dir / local_pdf_path
            else:
                # If pdf_base_dir is a string, create a path object
                full_pdf_path = Path(os.path.join(self.pdf_base_dir, local_pdf_path))

            if full_pdf_path.exists():
                # Load the PDF
                pdf_path = str(full_pdf_path)
                self.pdf_document.load(pdf_path)
                self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Ensure MultiPage mode is set
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
                # Update navigation controls
                self._update_pdf_navigation()

                # Store the current PDF path and initialize PyMuPDF document
                self.current_pdf_path = pdf_path
                try:
                    # Close previous document if it exists
                    if self.fitz_document:
                        self.fitz_document.close()
                    # Open with PyMuPDF for searching
                    self.fitz_document = fitz.open(pdf_path)
                except Exception as e:
                    print(f"Error opening PDF with PyMuPDF: {e}")
                    self.fitz_document = None

                pdf_found = True

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
                    self.pdf_document.load(pdf_path)
                    self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Ensure MultiPage mode is set
                    self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
                    # Update navigation controls
                    self._update_pdf_navigation()

                    # Store the current PDF path and initialize PyMuPDF document
                    self.current_pdf_path = pdf_path
                    try:
                        # Close previous document if it exists
                        if self.fitz_document:
                            self.fitz_document.close()
                        # Open with PyMuPDF for searching
                        self.fitz_document = fitz.open(pdf_path)
                    except Exception as e:
                        print(f"Error opening PDF with PyMuPDF: {e}")
                        self.fitz_document = None

                    # Update the database with the correct path
                    try:
                        self.db_manager.update_pdf_path(
                            doi,
                            filename,
                            self.current_publication.get('full_text', '')
                        )
                        print(f"Updated database with path: {filename}")
                    except Exception as e:
                        print(f"Failed to update database: {e}")

                    pdf_found = True
                    break

        # If we still couldn't find the PDF, show a message
        if not pdf_found:
            print("PDF not found by any method")
            # Display a message in the PDF view
            self.pdf_document.close()
            self._update_pdf_navigation()
            self.status_bar.showMessage("PDF not found")

    def _mark_current_as_read(self):
        """Mark the currently selected summary as read."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and not current_item.is_read:
            summary_id = current_item.summary['id']

            try:
                # Record in the database
                self.reading_tracker.mark_as_read(
                    source_type='medrxiv',
                    content_id=str(summary_id),
                    # We're not using user_id for now, can add if multi-user support is needed
                )

                # Update local cache
                self.read_summaries.add(summary_id)

                # Update the UI
                current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {current_item.publication.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_read(self):
        """Mark the selected summary as read."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and not current_item.is_read:
            summary_id = current_item.summary['id']

            try:
                # Record in the database
                self.reading_tracker.mark_as_read(
                    source_type='medrxiv',
                    content_id=str(summary_id),
                    # We're not using user_id for now, can add if multi-user support is needed
                )

                # Update local cache
                self.read_summaries.add(summary_id)

                # Update the UI
                current_item.update_read_status(True)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as read: {current_item.publication.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as read: {e}")
                traceback.print_exc()

    def _mark_as_unread(self):
        """Mark the selected summary as unread."""
        current_item = self.summary_list.currentItem()
        if current_item and isinstance(current_item, SummaryItem) and current_item.is_read:
            summary_id = current_item.summary['id']

            try:
                # Delete the reading record from the database
                self.reading_tracker.delete_reading_record(
                    source_type='medrxiv',
                    content_id=str(summary_id)
                )

                # Remove from local cache
                self.read_summaries.discard(summary_id)

                # Update the UI
                current_item.update_read_status(False)

                # Update the status bar
                self.status_bar.showMessage(f"Marked as unread: {current_item.publication.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error marking as unread: {e}")
                traceback.print_exc()

    def _refresh_read_status_cache(self):
        """
        Refresh the in-memory cache of read summaries from the database.
        This helps improve performance by avoiding database lookups for each item.
        """
        try:
            # Get recent read records for medrxiv articles
            read_records = self.reading_tracker.get_recent_reads(
                limit=1000,  # Fetch up to 1000 recent reads
                source_type='medrxiv'
            )

            # Clear and update the cache
            self.read_summaries.clear()
            for record in read_records:
                # Store the content_id (which corresponds to summary id) in our cache
                content_id = record.get('content_id')
                if content_id and content_id.isdigit():
                    self.read_summaries.add(int(content_id))

            print(f"Refreshed read status cache: {len(self.read_summaries)} read items")
        except Exception as e:
            print(f"Error refreshing read status cache: {e}")
            traceback.print_exc()

    def _filter_summaries(self):
        """Filter the summaries based on the selected filter."""
        self._load_summaries()  # Reload with the selected filter

    def _update_pdf_navigation(self):
        """Update PDF navigation controls based on current document state."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            total_pages = self.pdf_document.pageCount()
            current_page = self.pdf_view.pageNavigator().currentPage() + 1  # +1 because it's zero-based

            # Update the page label
            self.page_label.setText(f"Page {current_page} of {total_pages}")

            # Enable/disable navigation buttons
            self.prev_page_btn.setEnabled(current_page > 1)
            self.next_page_btn.setEnabled(current_page < total_pages)
        else:
            # Reset when no document is loaded
            self.page_label.setText("Page 1 of 1")
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)

    def _go_to_prev_page(self):
        """Navigate to the previous page in the PDF."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            navigator = self.pdf_view.pageNavigator()
            current_page = navigator.currentPage()
            if current_page > 0:  # It's zero-based
                navigator.jump(current_page - 1, QPointF())
                self._update_pdf_navigation()

    def _go_to_next_page(self):
        """Navigate to the next page in the PDF."""
        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            navigator = self.pdf_view.pageNavigator()
            current_page = navigator.currentPage()
            if current_page < self.pdf_document.pageCount() - 1:  # It's zero-based
                navigator.jump(current_page + 1, QPointF())
                self._update_pdf_navigation()

    def _zoom_in(self):
        """Zoom in on the PDF."""
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() * 1.25)

    def _zoom_out(self):
        """Zoom out of the PDF."""
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() / 1.25)

    def _fit_width(self):
        """Fit the PDF to the width of the view."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _search_pdf(self):
        """Search for text in the current PDF document using PyMuPDF."""
        if self.pdf_document.status() != QPdfDocument.Status.Ready or not self.fitz_document:
            QMessageBox.warning(self, "Search Error", "No PDF document is loaded.")
            return

        # Get search text
        search_text = self.pdf_search_input.text().strip()
        if not search_text:
            # Clear any existing highlights if search is empty
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)
            self.search_results = []
            return

        try:
            # Store the search text
            self.current_search_text = search_text

            # Reset search results
            self.search_results = []
            self.current_match_index = -1

            # Search in all pages
            for page_num in range(self.fitz_document.page_count):
                page = self.fitz_document[page_num]
                # Search for text on this page
                matches = page.search_for(search_text, quads=True)

                # Store results with page number
                for match in matches:
                    self.search_results.append((page_num, match))

            # Update match count
            search_match_count = len(self.search_results)

            if search_match_count > 0:
                # Enable navigation buttons
                self.prev_match_btn.setEnabled(True)
                self.next_match_btn.setEnabled(True)

                # Go to the first match
                self._find_next_match()

                # Show status message in the status bar
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage(f"Found {search_match_count} matches")
                else:
                    # If no status bar, show next to search box
                    self.pdf_search_input.setPlaceholderText(f"Found {search_match_count} matches")
            else:
                self.prev_match_btn.setEnabled(False)
                self.next_match_btn.setEnabled(False)
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage("No matches found")
                else:
                    self.pdf_search_input.setPlaceholderText("No matches found")

        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error searching PDF: {str(e)}")

    def _find_next_match(self):
        """Find and highlight the next match in the PDF."""
        if not self.search_results or self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        # Move to the next match
        self.current_match_index = (self.current_match_index + 1) % len(self.search_results)
        self._go_to_current_match()

    def _find_prev_match(self):
        """Find and highlight the previous match in the PDF."""
        if not self.search_results or self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        # Move to the previous match
        self.current_match_index = (self.current_match_index - 1) % len(self.search_results)
        self._go_to_current_match()

    def _go_to_current_match(self):
        """Navigate to and highlight the current match."""
        if not self.search_results or self.current_match_index < 0:
            return

        # Get the current match
        page_num, match = self.search_results[self.current_match_index]

        # Navigate to the page containing the match
        navigator = self.pdf_view.pageNavigator()
        navigator.jump(page_num, QPointF())

        # Update navigation controls
        self._update_pdf_navigation()

        # Create a temporary highlight annotation in PyMuPDF
        try:
            # Clear any previous highlights
            self._clear_highlights()

            # Add highlight to the current match
            page = self.fitz_document[page_num]

            # Try to create a more visible highlight
            try:
                # First attempt: Create a yellow text marker style highlight
                highlight = page.add_highlight_annot(match)
                highlight.set_colors({"stroke": (1, 1, 0)})  # Bright yellow
                highlight.set_opacity(0.7)  # More opaque
                highlight.update()

                # Add a red rectangle around the text for extra visibility
                rect = match.rect  # Get the rectangle of the match
                rect_annot = page.add_rect_annot(rect)
                rect_annot.set_colors({"stroke": (1, 0, 0)})  # Red border
                rect_annot.set_border(width=2)  # Thicker border
                rect_annot.update()
            except Exception as e:
                print(f"Error with advanced highlighting, falling back to basic: {e}")
                # Fallback: Simple red rectangle
                try:
                    rect = match.rect
                    rect_annot = page.add_rect_annot(rect)
                    rect_annot.set_colors({"stroke": (1, 0, 0)})  # Red border
                    rect_annot.set_border(width=2)  # Thicker border
                    rect_annot.update()
                except Exception as e2:
                    print(f"Error with fallback highlighting: {e2}")

            # Force a refresh of the PDF view
            # This is a workaround since we can't directly access the PySide6 PDF renderer
            # We'll reload the current page to show the highlight
            current_zoom = self.pdf_view.zoomFactor()
            self.pdf_view.setZoomFactor(current_zoom * 1.01)  # Slightly change zoom to force refresh
            QApplication.processEvents()
            self.pdf_view.setZoomFactor(current_zoom)  # Restore original zoom

        except Exception as e:
            print(f"Error highlighting match: {e}")

    def _clear_highlights(self):
        """Clear all highlight and rectangle annotations from the PDF."""
        if not self.fitz_document:
            return

        try:
            for page_num in range(self.fitz_document.page_count):
                page = self.fitz_document[page_num]
                for annot in page.annots():
                    # Type 8 is highlight annotation, type 4 is rectangle annotation
                    if annot.type[0] in [8, 4]:  # Clear both highlight and rectangle annotations
                        page.delete_annot(annot)
        except Exception as e:
            print(f"Error clearing highlights: {e}")

    def close_database(self):
        """Close the database connections."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        if hasattr(self, 'reading_tracker'):
            self.reading_tracker.close()

        # Close PyMuPDF document if it exists
        if hasattr(self, 'fitz_document') and self.fitz_document:
            self.fitz_document.close()
            self.fitz_document = None

    def _rate_positive(self):
        """Rate the current article positively (thumbs up)."""
        if not self.current_summary:
            return

        try:
            summary_id = self.current_summary['id']

            # Update the rating in the database
            self.reading_tracker.update_record_rating(
                source_type='medrxiv',
                content_id=str(summary_id),
                rating=1  # +1 for thumbs up
            )

            # Update the UI
            self.rating_label.setText("+1")
            self.status_bar.showMessage("Article rated positively")

        except Exception as e:
            print(f"Error rating article positively: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating rating")

    def _rate_negative(self):
        """Rate the current article negatively (thumbs down)."""
        if not self.current_summary:
            return

        try:
            summary_id = self.current_summary['id']

            # Update the rating in the database
            self.reading_tracker.update_record_rating(
                source_type='medrxiv',
                content_id=str(summary_id),
                rating=-1  # -1 for thumbs down
            )

            # Update the UI
            self.rating_label.setText("-1")
            self.status_bar.showMessage("Article rated negatively")

        except Exception as e:
            print(f"Error rating article negatively: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error updating rating")

    def _show_notes_dialog(self):
        """Show a dialog for editing notes for the current article."""
        if not self.current_summary:
            return

        try:
            summary_id = self.current_summary['id']

            # Get existing notes
            record = self.reading_tracker.get_reading_record(
                source_type='medrxiv',
                content_id=str(summary_id)
            )

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
                self.reading_tracker.update_record_notes(
                    source_type='medrxiv',
                    content_id=str(summary_id),
                    notes=notes
                )

                # Mark as read if not already
                if summary_id not in self.read_summaries:
                    self.read_summaries.add(summary_id)
                    current_item = self.summary_list.currentItem()
                    if current_item and isinstance(current_item, SummaryItem):
                        current_item.update_read_status(True)

                self.status_bar.showMessage("Notes saved")

        except Exception as e:
            print(f"Error handling notes: {e}")
            traceback.print_exc()
            self.status_bar.showMessage("Error saving notes")

    def _load_reading_record(self):
        """Load the current article's reading record including rating and notes."""
        if not self.current_summary:
            return

        try:
            summary_id = self.current_summary['id']

            # Get the reading record
            record = self.reading_tracker.get_reading_record(
                source_type='medrxiv',
                content_id=str(summary_id)
            )

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

        except Exception as e:
            print(f"Error loading reading record: {e}")
            traceback.print_exc()
            self.rating_label.setText("?")
            self.notes_btn.setText("Edit Notes")


class NewsBrowserWindow(QMainWindow):
    """A standalone window for the NewsBrowser widget."""

    def __init__(self, parent=None):
        """Initialize the main window for the news browser."""
        super().__init__(parent)

        # Set window properties
        self.setWindowTitle("Publication News Browser")
        self.resize(1200, 800)

        # Create the news browser widget
        self.news_browser = NewsBrowser()

        # Set as central widget
        self.setCentralWidget(self.news_browser)

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
