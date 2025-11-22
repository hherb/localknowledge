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
import re

from PySide6.QtCore import Qt, Signal, Slot, QSize, QEvent, QCoreApplication, QThreadPool, QRect, QTimer
from PySide6.QtGui import QFont, QIcon, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QLabel, QTextEdit, QApplication, QFrame, QComboBox, QCheckBox,
    QProgressBar, QSlider, QSpinBox, QStyledItemDelegate, QStyle,
    QStackedWidget
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


def perform_fulltext_search(query, max_results=10):
    """Perform a fulltext search using PostgreSQL's fulltext search capabilities.

    Uses LLM keyword extraction to identify keywords and synonyms, then constructs
    a PostgreSQL fulltext query that finds documents containing at least one term
    from each keyword group.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        List of search results with rank and similarity scores
    """
    try:
        # Import the keyword extractor
        from localknowledge.textprocessing.llm_keyword_extractor import extract_keywords

        # Extract keywords and synonyms using the LLM
        keywords_text = extract_keywords(query)
        logging.info(f"Extracted keywords: {keywords_text}")

        # Parse the keywords and synonyms
        # Format is: (keywordA, synonymA1, synonymA2...), (keywordB, synonymB1...)
        keyword_groups = []

        # Handle the case where the LLM might not return the expected format
        if not keywords_text or '(' not in keywords_text:
            # Fall back to simple keyword extraction
            simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', query.lower()).split() if word and len(word) > 2)
            if not simple_keywords:
                return []

            # Add :* to each term for prefix matching
            tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))
        else:
            # Process the structured keyword format
            try:
                # Extract each group of keywords within parentheses
                import re
                groups = re.findall(r'\(([^)]+)\)', keywords_text)

                for group in groups:
                    # Split the group into individual terms and clean them
                    terms = [term.strip().lower() for term in group.split(',')]
                    # Filter out empty terms
                    terms = [term for term in terms if term and len(term) > 2]
                    if terms:
                        keyword_groups.append(terms)

                if not keyword_groups:
                    # Fall back if no valid groups were found
                    simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', query.lower()).split() if word and len(word) > 2)
                    tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))
                else:
                    # Construct a tsquery that requires at least one term from each group
                    # Format: (term1:* | term2:* | ...) & (term3:* | term4:* | ...)
                    group_queries = []
                    for group in keyword_groups:
                        # Add :* to each term for prefix matching
                        term_queries = [f"{term.replace(' ', '&')}:*" for term in group]
                        # Join terms within a group with OR (|)
                        group_query = f"({' | '.join(term_queries)})"
                        group_queries.append(group_query)

                    # Join groups with AND (&)
                    tsquery = ' & '.join(group_queries)
            except Exception as e:
                logging.error(f"Error parsing keywords: {e}\n{traceback.format_exc()}")
                # Fall back to simple keyword extraction
                simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', query.lower()).split() if word and len(word) > 2)
                tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))

        logging.info(f"Fulltext search query: {tsquery}")

        with get_cursor() as cursor:
            # Only search documents that have abstract embeddings
            # Use to_tsvector for fulltext search on title and abstract
            # Calculate rank using ts_rank_cd
            query_sql = """
            SELECT
                d.id, d.title, d.abstract, d.source_id, d.authors,
                ts_rank_cd(to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')), to_tsquery('english', %s)) as rank,
                ts_rank_cd(to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')), to_tsquery('english', %s)) as similarity
            FROM document d
            JOIN unified_multiembeddings e ON d.id = e.document_id
            JOIN embedding_source s ON e.embed_source_id = s.id
            WHERE to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')) @@ to_tsquery('english', %s)
            AND s.name = 'abstract'
            GROUP BY d.id
            ORDER BY rank DESC
            LIMIT %s
            """

            cursor.execute(query_sql, (tsquery, tsquery, tsquery, max_results))
            results = [dict(row) for row in cursor.fetchall()]

            return results
    except Exception as e:
        logging.error(f"Error in fulltext search: {e}\n{traceback.format_exc()}")
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

# Path to icons
PUBMED_ICON_PATH = "localknowledge/ui/icons/pubmed_tag.png"
MEDRXIV_ICON_PATH = "localknowledge/ui/icons/medrxiv_tag.png"

# Search method emoji tags
SEARCH_METHOD_TAGS = {
    "semantic": "🔍S",
    "keyword": "🔑K",
    "fulltext": "📝F",
    "hyde": "💭H",
    "hybrid": "🔄H+S",
    "synthetic": "🤖Q",
    # Combined methods for hybrid search
    "semantic+hyde": "🔍S+💭H",
    "hyde+semantic": "💭H+🔍S",
    "semantic+keyword": "🔍S+🔑K",
    "keyword+semantic": "🔑K+🔍S",
    "semantic+fulltext": "🔍S+📝F",
    "fulltext+semantic": "📝F+🔍S",
    "hyde+keyword": "💭H+🔑K",
    "keyword+hyde": "🔑K+💭H",
    "hyde+fulltext": "💭H+📝F",
    "fulltext+hyde": "📝F+💭H",
    "semantic+hyde+keyword": "🔍S+💭H+🔑K",
    "semantic+hyde+fulltext": "🔍S+💭H+📝F"
}


class TitleItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering title items with source icons and search method tags."""

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
        # QListWidget stores items differently than QStandardItemModel
        item = index.model().itemFromIndex(index) if hasattr(index.model(), 'itemFromIndex') else None

        # If we can't get the item directly, try to get it from the list widget
        if not item or not isinstance(item, TitleListItem):
            # Try to get the list widget and the item from it
            list_widget = self.parent()
            if isinstance(list_widget, QListWidget):
                item = list_widget.item(index.row())

            # If we still don't have a valid item, fall back to default rendering
            if not item or not isinstance(item, TitleListItem):
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
        source_id = item.source_id
        icon_rect = QRect(rect.left() + 4, rect.top() + (rect.height() - icon_size.height()) // 2,
                         icon_size.width(), icon_size.height())

        if source_id == 1:  # PubMed
            self.pubmed_icon.paint(painter, icon_rect)
        elif source_id == 2:  # medRxiv
            self.medrxiv_icon.paint(painter, icon_rect)

        # Calculate text position (after the icon)
        text_left = icon_rect.right() + 8

        # Draw search method tag if available
        search_method = item.search_method
        if search_method:
            tag = SEARCH_METHOD_TAGS.get(search_method, "")
            if tag:
                # Draw the tag
                tag_rect = QRect(text_left, rect.top(), 40, rect.height())
                painter.drawText(tag_rect, Qt.AlignVCenter, tag)
                text_left = tag_rect.right() + 4

        # Draw the title text
        text_rect = QRect(text_left, rect.top(), rect.width() - text_left - 4, rect.height())

        # Use bold font for the title
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        # Draw the text
        painter.drawText(text_rect, Qt.AlignVCenter, item.document.get('title', 'Untitled'))

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
        return QSize(size.width(), max(size.height(), 24))


class TitleListItem(QListWidgetItem):
    """List widget item to display document title with metadata."""

    def __init__(self, document: Dict[str, Any], similarity: float = None, search_method: str = None):
        """
        Initialize a title list item.

        Args:
            document: Document data dictionary
            similarity: Similarity score (optional)
            search_method: The search method that produced this result (optional)
        """
        # Get the document title
        title = document.get('title', 'Untitled')

        # Get the source information
        source_id = document.get('source_id')

        # Create display text with title only (icons will be added in the view)
        display_text = title

        # Initialize the list item with the display text
        super().__init__(display_text)

        # Store the document data and similarity for later use
        self.document = document
        self.similarity = similarity

        # Check if the document has a search_source field (used by hybrid search)
        # If it does, use that instead of the provided search_method
        self.search_method = document.get('search_source', search_method)
        self.source_id = source_id

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

            tooltip = f"{title}\n\nSource: {'PubMed' if source_id == 1 else 'medRxiv' if source_id == 2 else 'Unknown'}"

            if search_method:
                # Format the search method nicely
                if '+' in search_method:
                    # For combined methods, show which methods found this document
                    methods = search_method.split('+')
                    formatted_methods = []
                    for m in methods:
                        if m == 'semantic':
                            formatted_methods.append('Semantic Search')
                        elif m == 'hyde':
                            formatted_methods.append('HyDE Search')
                        elif m == 'keyword':
                            formatted_methods.append('Keyword Search')
                        elif m == 'fulltext':
                            formatted_methods.append('Fulltext Search')
                        else:
                            formatted_methods.append(m.capitalize())
                    tooltip += f"\nFound by: {' and '.join(formatted_methods)}"
                else:
                    # For single methods
                    method_name = search_method.capitalize()
                    if search_method == 'semantic':
                        method_name = 'Semantic Search'
                    elif search_method == 'hyde':
                        method_name = 'HyDE Search'
                    elif search_method == 'keyword':
                        method_name = 'Keyword Search'
                    elif search_method == 'fulltext':
                        method_name = 'Fulltext Search'
                    tooltip += f"\nSearch Method: {method_name}"

            tooltip += f"\nAuthors: {authors_str}"

            if similarity is not None:
                tooltip += f"\n\nSimilarity: {similarity:.2f}"

            self.setToolTip(tooltip)


class DocumentDisplayWidget(QWidget):
    """Widget to display a list of titles and the selected document's abstract."""

    # Signal emitted when a document is selected
    documentSelected = Signal(dict)

    # Signal emitted when search method is changed
    searchMethodChanged = Signal(str, bool)  # method, use_reranker

    # Signal emitted when keywords are edited and search again is requested
    keywordsEdited = Signal(str, str)  # method, edited_keywords

    # Signal emitted to update the keywords text box from a background thread
    updateKeywords = Signal(str)  # keywords

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

        # Connect signals
        self.updateKeywords.connect(self._on_update_keywords)

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout with minimal spacing
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(3)  # Reduce spacing between elements

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
        controls_layout.setSpacing(3)  # Reduce spacing between elements

        # Import size policy if not already imported
        from PySide6.QtWidgets import QSizePolicy

        # Top row: Search method and reranker
        search_method_layout = QHBoxLayout()

        # Search method combo box
        self.search_method_combo = QComboBox()
        self.search_method_combo.addItem("Semantic", "semantic")
        self.search_method_combo.addItem("Keyword", "keyword")
        self.search_method_combo.addItem("Fulltext", "fulltext")
        self.search_method_combo.addItem("HyDE", "hyde")
        self.search_method_combo.addItem("Hybrid", "hybrid")
        self.search_method_combo.addItem("Synthetic Q&A", "synthetic")
        self.search_method_combo.currentIndexChanged.connect(self._on_search_method_changed)

        # Reranker checkbox
        self.reranker_checkbox = QCheckBox("Use Reranker")
        self.reranker_checkbox.toggled.connect(self._on_reranker_toggled)

        # Add to top row layout
        search_method_layout.addWidget(QLabel("Search Method:"))
        search_method_layout.addWidget(self.search_method_combo)  # 1 is stretch factor
        search_method_layout.addWidget(self.reranker_checkbox)

        controls_layout.addLayout(search_method_layout)

        # Create a stacked widget to hold either similarity slider or keywords box
        self.controls_stack = QStackedWidget()
        self.controls_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.controls_stack.setMaximumHeight(80)  # Fixed maximum height

        # Page 1: Similarity threshold slider
        similarity_widget = QWidget()
        similarity_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        similarity_widget.setMaximumHeight(40)  # Fixed height for similarity controls
        similarity_layout = QHBoxLayout(similarity_widget)
        similarity_layout.setContentsMargins(0, 0, 0, 0)

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
        similarity_layout.addWidget(self.similarity_slider)  # 1 is stretch factor

        # Similarity value label
        self.similarity_value_label = QLabel("0.30")
        self.similarity_value_label.setMinimumWidth(40)
        similarity_layout.addWidget(self.similarity_value_label)

        # Add similarity widget to stack
        self.controls_stack.addWidget(similarity_widget)

        # Page 2: Keywords box for keyword and fulltext searches
        keywords_widget = QWidget()
        keywords_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        keywords_widget.setMaximumHeight(80)  # Fixed height for keywords controls
        keywords_layout = QVBoxLayout(keywords_widget)
        keywords_layout.setContentsMargins(0, 0, 0, 0)

        # Keywords label
        #keywords_label = QLabel("Extracted Keywords:")
        #keywords_layout.addWidget(keywords_label)

        # Keywords text box - make it more compact
        self.keywords_text_box = QTextEdit()
        self.keywords_text_box.setMaximumHeight(60)  # Reduce height
        self.keywords_text_box.setPlaceholderText("Keywords will appear here after search")
        self.keywords_text_box.textChanged.connect(self._on_keywords_edited)
        keywords_layout.addWidget(self.keywords_text_box)

        # "Again with these" button
        self.search_again_button = QPushButton("Search Again with These Keywords")
        self.search_again_button.clicked.connect(self._on_search_again_clicked)
        self.search_again_button.setVisible(False)  # Initially hidden
        keywords_layout.addWidget(self.search_again_button)

        # Add keywords widget to stack
        self.controls_stack.addWidget(keywords_widget)

        # Add the stacked widget to the controls layout
        controls_layout.addWidget(self.controls_stack)

        # Create a container for the controls with fixed height policy
        controls_container = QWidget()
        controls_container.setLayout(controls_layout)
        controls_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        controls_container.setMaximumHeight(100)  # Set a maximum height for the controls section

        # Add the controls container to the main layout
        main_layout.addWidget(controls_container)

        # Create a splitter for the title list and abstract view
        self.splitter = QSplitter(Qt.Vertical)

        # Title list
        self.title_list = QListWidget()
        self.title_list.setMinimumHeight(100)
        self.title_list.currentItemChanged.connect(self._on_title_selected)

        # Set custom delegate for rendering items with icons and tags
        self.item_delegate = TitleItemDelegate(self.title_list)
        self.title_list.setItemDelegate(self.item_delegate)

        # Set item height to accommodate icons and tags
        self.title_list.setIconSize(QSize(16, 16))

        # Abstract view
        self.abstract_view = QTextEdit()
        self.abstract_view.setReadOnly(True)

        # Add widgets to splitter
        self.splitter.addWidget(self.title_list)
        self.splitter.addWidget(self.abstract_view)

        # Set initial sizes (1:1 ratio)
        self.splitter.setSizes([200, 200])

        # Add splitter to main layout with a high stretch factor
        main_layout.addWidget(self.splitter, 100)  # Very high stretch factor to ensure this is the only expanding widget

        # Set size policy to make the splitter expand to fill available space
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
        # Get the current search method
        method = self.search_method_combo.currentData()

        # Create item with search method
        item = TitleListItem(document, similarity, method)
        self.title_list.addItem(item)

    def set_documents(self, documents: List[Dict[str, Any]], search_method: str = None):
        """
        Set the list of documents to display.

        Args:
            documents: List of document data dictionaries
            search_method: The search method that produced these results (optional)
        """
        self.clear()

        # Store the search method for future use
        if search_method:
            # Update the combo box to match the search method
            for i in range(self.search_method_combo.count()):
                if self.search_method_combo.itemData(i) == search_method:
                    self.search_method_combo.setCurrentIndex(i)
                    break

        for doc in documents:
            # Make a copy of the document to avoid modifying the original
            doc_copy = doc.copy() if isinstance(doc, dict) else doc
            similarity = doc_copy.pop('similarity', None) if isinstance(doc_copy, dict) else None
            self.add_document(doc_copy, similarity)

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
        # Only semantic, HyDE, and hybrid searches can use reranking
        self.reranker_checkbox.setVisible(method in ["semantic", "hyde", "hybrid"])

        # Switch between similarity slider and keywords box based on method
        # Only semantic, HyDE, and hybrid searches use similarity threshold
        # Only keyword and fulltext searches show the keywords text box
        similarity_methods = ["semantic", "hyde", "hybrid"]
        keyword_methods = ["keyword", "fulltext"]

        # Switch the stacked widget to show the appropriate control
        if hasattr(self, 'controls_stack'):
            if method in keyword_methods:
                # Show keywords box (index 1)
                self.controls_stack.setCurrentIndex(1)

                # Reset the "Again with these" button state
                if hasattr(self, 'search_again_button'):
                    self.search_again_button.setVisible(False)
            else:
                # Show similarity slider (index 0)
                self.controls_stack.setCurrentIndex(0)

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

    def _on_keywords_edited(self):
        """Handle editing of the keywords text box."""
        # Show the "Search Again" button when keywords are edited
        if hasattr(self, 'search_again_button') and hasattr(self, 'keywords_text_box'):
            # Only show the button if there's text and it's different from the original
            if self.keywords_text_box.toPlainText().strip():
                self.search_again_button.setVisible(True)
            else:
                self.search_again_button.setVisible(False)

    def _on_search_again_clicked(self):
        """Handle click of the "Search Again with These Keywords" button."""
        # Get the current search method
        method = self.search_method_combo.currentData()

        # Get the edited keywords
        keywords = self.keywords_text_box.toPlainText().strip()

        # Emit a custom signal to trigger a new search with the edited keywords
        self.keywordsEdited.emit(method, keywords)

    @Slot(str)
    def _on_update_keywords(self, keywords):
        """
        Update the keywords text box with the given keywords.
        This slot is connected to the updateKeywords signal and runs in the main thread.

        Args:
            keywords: The keywords to display
        """
        if hasattr(self, 'keywords_text_box'):
            self.keywords_text_box.setText(keywords)

            # Hide the "Search Again" button initially
            if hasattr(self, 'search_again_button'):
                self.search_again_button.setVisible(False)

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
        # Main layout with minimal spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)  # Reduce spacing between elements
        main_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins

        # Import size policy constants
        from PySide6.QtWidgets import QSizePolicy

        # Search bar at the top
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)  # Reduce spacing between elements

        # Question input
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Enter your question...")
        self.question_input.returnPressed.connect(self._on_search)

        # Max results label and spinner
        max_results_label = QLabel("Max Results:")
        self.max_results_spinner = QSpinBox()
        self.max_results_spinner.setRange(1, 100)
        self.max_results_spinner.setValue(self.search_settings['max_results'])
        self.max_results_spinner.valueChanged.connect(self._on_max_results_changed)

        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)

        # Add to search layout
        search_layout.addWidget(self.question_input)  # 1 is the stretch factor
        search_layout.addWidget(max_results_label)
        search_layout.addWidget(self.max_results_spinner)
        search_layout.addWidget(self.search_button)

        # Create a container widget for the search bar to apply size policy
        search_container = QWidget()
        search_container.setLayout(search_layout)
        search_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Add search container to main layout
        main_layout.addWidget(search_container, 0)  # 0 stretch factor

        # Create horizontal splitter for left and right panels
        self.main_splitter = QSplitter(Qt.Horizontal)


        # Left panel - Direct Semantic Search by default
        self.left_panel = DocumentDisplayWidget(title="Baseline search")
        self.left_panel.search_method_combo.setCurrentText("Semantic")
        self.left_panel.reranker_checkbox.setChecked(self.search_settings['left_use_reranker'])
        self.left_panel.searchMethodChanged.connect(self._on_left_search_method_changed)
        self.left_panel.keywordsEdited.connect(self._on_left_keywords_edited)

        # Right panel - HyDE Search by default
        self.right_panel = DocumentDisplayWidget(title="Experimental search")
        self.right_panel.search_method_combo.setCurrentText("HyDE")
        self.right_panel.reranker_checkbox.setChecked(self.search_settings['right_use_reranker'])
        self.right_panel.searchMethodChanged.connect(self._on_right_search_method_changed)
        self.right_panel.keywordsEdited.connect(self._on_right_keywords_edited)

        # Add panels to main splitter
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)

        # Set initial sizes (1:1 ratio)
        self.main_splitter.setSizes([400, 400])

        # Set size policy to make the splitter expand to fill available space
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add main splitter to layout - give it a very high stretch factor to ensure it's the only thing that stretches
        main_layout.addWidget(self.main_splitter, 100)  # Very high stretch factor to ensure this is the only expanding widget

        # Status bar and progress indicators
        status_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label, stretch=0)  # 1 is stretch factor

        # Left panel progress bar
        self.left_progress = QProgressBar()
        self.left_progress.setRange(0, 100)
        self.left_progress.setValue(0)
        self.left_progress.setVisible(False)
        self.left_progress.setMaximumWidth(150)
        status_layout.addWidget(self.left_progress, stretch=0)

        # Right panel progress bar
        self.right_progress = QProgressBar()
        self.right_progress.setRange(0, 100)
        self.right_progress.setValue(0)
        self.right_progress.setVisible(False)
        self.right_progress.setMaximumWidth(150)
        status_layout.addWidget(self.right_progress, stretch=0)

        # Create a container widget for the status bar to apply size policy
        status_container = QWidget()
        status_container.setLayout(status_layout)
        status_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Add status container to main layout
        main_layout.addWidget(status_container, 0)  # 0 stretch factor

        # Add a label to show the hypothetical abstract - make it compact and fixed size
        self.hyde_container = QWidget()
        hyde_abstract_layout = QVBoxLayout(self.hyde_container)
        hyde_abstract_layout.setSpacing(2)  # Minimal spacing
        hyde_abstract_layout.setContentsMargins(0, 0, 0, 0)  # No margins

        self.hyde_abstract_label = QLabel("HyDE Abstract:")

        # Create a text edit with fixed height of approximately 6 lines of text
        self.hyde_abstract_view = QTextEdit()
        self.hyde_abstract_view.setReadOnly(True)

        # Set a fixed height for approximately 6 lines of text (assuming ~16px per line)
        line_height = 16  # Approximate height of a line of text
        self.hyde_abstract_view.setFixedHeight(line_height * 6)  # 6 lines of text

        # Make sure it's scrollable
        self.hyde_abstract_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.hyde_abstract_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Add to hyde abstract layout
        hyde_abstract_layout.addWidget(self.hyde_abstract_label)
        hyde_abstract_layout.addWidget(self.hyde_abstract_view)

        # Set size policy for the container
        self.hyde_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Hide by default
        self.hyde_container.setVisible(False)

        # Add HyDE container to main layout with minimal stretch
        main_layout.addWidget(self.hyde_container, 0)  # 0 stretch factor to minimize space

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
        elif method == "fulltext":
            self.left_panel.title_text = "Fulltext Search"
        elif method == "hyde":
            self.left_panel.title_text = "HyDE Search"
        elif method == "hybrid":
            self.left_panel.title_text = "Hybrid Search"
        elif method == "synthetic":
            self.left_panel.title_text = "Synthetic Q&A"

        # Update the left panel's similarity slider and max results spinner
        # based on the panel's settings
        if hasattr(self.left_panel, 'similarity_slider') and hasattr(self.left_panel, 'max_results_spinner'):
            self.left_panel.similarity_slider.setValue(int(self.search_settings['similarity_threshold'] * 100))
            self.left_panel.max_results_spinner.setValue(self.search_settings['max_results'])

        # Check if we need to show/hide the HyDE Abstract section
        self._update_hyde_abstract_visibility()

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
        elif method == "fulltext":
            self.right_panel.title_text = "Fulltext Search"
        elif method == "hyde":
            self.right_panel.title_text = "HyDE Search"
        elif method == "hybrid":
            self.right_panel.title_text = "Hybrid Search"
        elif method == "synthetic":
            self.right_panel.title_text = "Synthetic Q&A"

        # Update the right panel's similarity slider and max results spinner
        # based on the panel's settings
        if hasattr(self.right_panel, 'similarity_slider') and hasattr(self.right_panel, 'max_results_spinner'):
            self.right_panel.similarity_slider.setValue(int(self.search_settings['similarity_threshold'] * 100))
            self.right_panel.max_results_spinner.setValue(self.search_settings['max_results'])

        # Check if we need to show/hide the HyDE Abstract section
        self._update_hyde_abstract_visibility()

    def _update_hyde_abstract_visibility(self):
        """
        Update the visibility of the HyDE Abstract section based on the current search methods.
        Show it only if either panel is using HyDE or hybrid search.
        """
        # Check if either panel is using HyDE or hybrid search
        left_method = self.search_settings.get('left_search_method', '')
        right_method = self.search_settings.get('right_search_method', '')

        # Show the HyDE Abstract section if either panel is using HyDE or hybrid search
        should_show = left_method in ['hyde', 'hybrid'] or right_method in ['hyde', 'hybrid']

        # Update visibility of the HyDE container
        if hasattr(self, 'hyde_container'):
            self.hyde_container.setVisible(should_show)

    @Slot()
    def _on_max_results_changed(self, value):
        """
        Handle change of max results spinner.

        Args:
            value: New spinner value
        """
        # Update the search settings
        self.search_settings['max_results'] = value
        logger.info(f"Max results changed to {value}")

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

        # Update HyDE abstract visibility based on current search methods
        self._update_hyde_abstract_visibility()

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

    @Slot(str, str)
    def _on_left_keywords_edited(self, method, keywords):
        """
        Handle edited keywords from the left panel.

        Args:
            method: The search method (keyword or fulltext)
            keywords: The edited keywords
        """
        logger.info(f"Left panel keywords edited: {keywords}")

        # Get the current question
        question = self.question_input.text().strip()

        if not question:
            self.status_label.setText("Please enter a question first")
            return

        # Perform search with the edited keywords
        self._perform_panel_search_with_keywords(
            question=question,
            panel=self.left_panel,
            method=method,
            keywords=keywords,
            progress_callback=self._left_progress_callback
        )

    @Slot(str, str)
    def _on_right_keywords_edited(self, method, keywords):
        """
        Handle edited keywords from the right panel.

        Args:
            method: The search method (keyword or fulltext)
            keywords: The edited keywords
        """
        logger.info(f"Right panel keywords edited: {keywords}")

        # Get the current question
        question = self.question_input.text().strip()

        if not question:
            self.status_label.setText("Please enter a question first")
            return

        # Perform search with the edited keywords
        self._perform_panel_search_with_keywords(
            question=question,
            panel=self.right_panel,
            method=method,
            keywords=keywords,
            progress_callback=self._right_progress_callback
        )

    def _perform_keyword_search_with_keywords(self, keywords, max_results):
        """
        Perform a keyword search with custom keywords.

        Args:
            keywords: Custom keywords to search for
            max_results: Maximum number of results to return

        Returns:
            List of search results
        """
        try:
            # Use the keywords directly for search
            # Split by commas, spaces, or newlines
            terms = re.split(r'[,\s\n]+', keywords)
            # Filter out empty terms
            terms = [term.strip() for term in terms if term.strip()]

            if not terms:
                return []

            # Construct a query with OR between terms
            query_parts = []
            query_params = []

            for term in terms:
                # Use ILIKE for case-insensitive search
                query_parts.append("(d.title ILIKE %s OR d.abstract ILIKE %s)")
                # Add wildcards for partial matching
                query_params.extend([f"%{term}%", f"%{term}%"])

            with get_cursor() as cursor:
                # Only search documents that have abstract embeddings
                query_sql = f"""
                SELECT d.id, d.title, d.abstract, d.source_id, d.authors FROM document d
                JOIN unified_multiembeddings e ON d.id = e.document_id
                JOIN embedding_source s ON e.embed_source_id = s.id
                WHERE ({" OR ".join(query_parts)})
                AND s.name = 'abstract'
                GROUP BY d.id
                LIMIT %s
                """

                # Add the max_results parameter
                query_params.append(max_results)

                cursor.execute(query_sql, query_params)
                results = [dict(row) for row in cursor.fetchall()]

                return results
        except Exception as e:
            logging.error(f"Error in keyword search with custom keywords: {e}\n{traceback.format_exc()}")
            return []

    def _perform_fulltext_search_with_keywords(self, keywords, max_results):
        """
        Perform a fulltext search with custom keywords.

        Args:
            keywords: Custom keywords to search for
            max_results: Maximum number of results to return

        Returns:
            List of search results
        """
        try:
            # Parse the keywords and synonyms
            # Format is: (keywordA, synonymA1, synonymA2...), (keywordB, synonymB1...)
            keyword_groups = []

            # Handle the case where the keywords might not be in the expected format
            if not keywords or '(' not in keywords:
                # Treat as simple keywords
                simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', keywords.lower()).split() if word and len(word) > 2)
                if not simple_keywords:
                    return []

                # Add :* to each term for prefix matching
                tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))
            else:
                # Process the structured keyword format
                try:
                    # Extract each group of keywords within parentheses
                    groups = re.findall(r'\(([^)]+)\)', keywords)

                    for group in groups:
                        # Split the group into individual terms and clean them
                        terms = [term.strip().lower() for term in group.split(',')]
                        # Filter out empty terms
                        terms = [term for term in terms if term and len(term) > 2]
                        if terms:
                            keyword_groups.append(terms)

                    if not keyword_groups:
                        # Fall back if no valid groups were found
                        simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', keywords.lower()).split() if word and len(word) > 2)
                        tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))
                    else:
                        # Construct a tsquery that requires at least one term from each group
                        # Format: (term1:* | term2:* | ...) & (term3:* | term4:* | ...)
                        group_queries = []
                        for group in keyword_groups:
                            # Add :* to each term for prefix matching
                            term_queries = [f"{term.replace(' ', '&')}:*" for term in group]
                            # Join terms within a group with OR (|)
                            group_query = f"({' | '.join(term_queries)})"
                            group_queries.append(group_query)

                        # Join groups with AND (&)
                        tsquery = ' & '.join(group_queries)
                except Exception as e:
                    logging.error(f"Error parsing keywords: {e}\n{traceback.format_exc()}")
                    # Fall back to simple keyword extraction
                    simple_keywords = ' & '.join(word for word in re.sub(r'[^\w\s]', ' ', keywords.lower()).split() if word and len(word) > 2)
                    tsquery = ' & '.join(f"{term}:*" for term in simple_keywords.split(' & '))

            logging.info(f"Fulltext search query with custom keywords: {tsquery}")

            with get_cursor() as cursor:
                # Only search documents that have abstract embeddings
                # Use to_tsvector for fulltext search on title and abstract
                # Calculate rank using ts_rank_cd
                query_sql = """
                SELECT
                    d.id, d.title, d.abstract, d.source_id, d.authors,
                    ts_rank_cd(to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')), to_tsquery('english', %s)) as rank,
                    ts_rank_cd(to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')), to_tsquery('english', %s)) as similarity
                FROM document d
                JOIN unified_multiembeddings e ON d.id = e.document_id
                JOIN embedding_source s ON e.embed_source_id = s.id
                WHERE to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')) @@ to_tsquery('english', %s)
                AND s.name = 'abstract'
                GROUP BY d.id
                ORDER BY rank DESC
                LIMIT %s
                """

                cursor.execute(query_sql, (tsquery, tsquery, tsquery, max_results))
                results = [dict(row) for row in cursor.fetchall()]

                return results
        except Exception as e:
            logging.error(f"Error in fulltext search with custom keywords: {e}\n{traceback.format_exc()}")
            return []

    def _perform_panel_search_with_keywords(self, question, panel, method, keywords, progress_callback):
        """
        Perform a search for a panel with custom keywords.

        Args:
            question: The search query (unused but kept for consistency)
            panel: The panel to display results in
            method: The search method
            keywords: The custom keywords to use
            progress_callback: Callback for progress updates
        """
        # Show progress
        progress_callback(10)

        # Update status
        self.status_label.setText(f"Searching with custom keywords...")

        try:
            # Perform search based on method
            results = None

            if method == "keyword":
                progress_callback(20)
                # Use the custom keywords directly for keyword search
                results = self._perform_keyword_search_with_keywords(keywords, self.search_settings['max_results'])
                progress_callback(90)
            elif method == "fulltext":
                progress_callback(20)
                # Use the custom keywords directly for fulltext search
                results = self._perform_fulltext_search_with_keywords(keywords, self.search_settings['max_results'])
                progress_callback(90)
            else:
                # Unsupported method for custom keywords
                self.status_label.setText(f"Custom keywords only supported for keyword and fulltext search")
                progress_callback(0)
                return

            # Display results
            if results:
                panel.set_documents(results, method)
                self.status_label.setText(f"Found {len(results)} results with custom keywords")
            else:
                panel.clear()
                self.status_label.setText("No results found with custom keywords")

            # Complete progress
            progress_callback(100)

            # Hide progress after a delay
            QTimer.singleShot(500, lambda: progress_callback(0))

        except Exception as e:
            logger.error(f"Error in search with custom keywords: {e}\n{traceback.format_exc()}")
            self.status_label.setText(f"Error: {str(e)}")
            progress_callback(0)

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
        max_results = self.search_settings['max_results']
        left_threshold = self.left_panel.similarity_slider.value() / 100.0 if hasattr(self.left_panel, 'similarity_slider') else self.search_settings['similarity_threshold']
        left_use_reranker = self.search_settings['left_use_reranker']

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
            question, left_method, self.search_settings['max_results'], left_threshold, left_use_reranker, self.left_panel, update_left_progress
        ))
        left_thread.daemon = True  # Make thread a daemon so it exits when the main thread exits
        left_thread.start()

        # Perform right panel search in a separate thread
        right_thread = threading.Thread(target=self._perform_panel_search, args=(
            question, right_method, self.search_settings['max_results'], right_threshold, right_use_reranker, self.right_panel, update_right_progress
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
            elif method == "hybrid":
                progress_callback(20)
                # Import the hybrid search function
                from localknowledge.ai.hybrid_search import perform_hybrid_search

                # Perform hybrid search
                hybrid_result = perform_hybrid_search(
                    embedding_manager=self.embedding_manager,
                    query=question,
                    max_results=max_results,
                    threshold=threshold,
                    use_reranker=use_reranker,
                    reranker_model=self.search_settings['reranker_model'],
                    hyde_model=self.search_settings['hyde_model']
                )
                progress_callback(90)

                # Handle hybrid result which includes the abstract
                if hybrid_result and 'abstract' in hybrid_result:
                    # Display the hypothetical abstract in the main thread
                    if hybrid_result['abstract']:
                        # We need to update the UI in the main thread
                        # Create a custom event
                        event = QEvent(QEvent.Type.User)
                        # Store data as a property of the event
                        event.data = lambda: {
                            'type': 'update_hyde_abstract',
                            'abstract': hybrid_result['abstract']
                        }
                        QApplication.instance().postEvent(self, event)

                    # Use the actual results
                    results = hybrid_result.get('results', [])
            elif method == "keyword":
                progress_callback(20)
                # Extract keywords from the question
                from localknowledge.textprocessing.llm_keyword_extractor import extract_keywords
                extracted_keywords = extract_keywords(question)

                # Display the extracted keywords in the panel's keywords text box using the signal
                # This ensures thread safety
                if hasattr(panel, 'updateKeywords'):
                    panel.updateKeywords.emit(extracted_keywords)

                # Perform the keyword search
                results = perform_keyword_search(
                    query=question,
                    max_results=max_results
                )
                progress_callback(90)
            elif method == "fulltext":
                progress_callback(20)
                # Extract keywords from the question
                from localknowledge.textprocessing.llm_keyword_extractor import extract_keywords
                extracted_keywords = extract_keywords(question)

                # Display the extracted keywords in the panel's keywords text box using the signal
                # This ensures thread safety
                if hasattr(panel, 'updateKeywords'):
                    panel.updateKeywords.emit(extracted_keywords)

                # Perform the fulltext search
                results = perform_fulltext_search(
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
                        panel.set_documents(results, method)

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

                        # Make sure the container is visible if using HyDE or hybrid search
                        self._update_hyde_abstract_visibility()

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

                    # Update HyDE abstract visibility based on current search methods
                    self._update_hyde_abstract_visibility()

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
            except Exception:
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
            except Exception:
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
            except Exception:
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
