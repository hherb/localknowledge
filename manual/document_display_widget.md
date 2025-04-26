# Document Display Widget

The `DocumentDisplayWidget` is a reusable component for displaying document content in a tabbed interface. It provides a consistent way to display documents across different parts of the application.

## Overview

The document display widget provides:

1. A tabbed interface for displaying different aspects of a document
2. Controls for rating documents (thumbs up/down)
3. Controls for bookmarking documents (personal and project bookmarks)
4. Integration with the context management system to track current user and project

## Components

The document display widget is composed of several specialized components:

1. **AbstractDisplayWidget**: Displays the document abstract and metadata
2. **SummaryDisplayWidget**: Displays a document summary if available, or provides a button to generate one
3. **PDFDisplayWidget**: Displays the document PDF with search and navigation controls

## Usage

### Basic Usage

```python
from localknowledge.ui.document_display_widget import DocumentDisplayWidget

# Create the widget
document_display = DocumentDisplayWidget(
    parent=self,  # Parent widget
    status_bar=self.status_bar,  # Optional status bar for messages
    db_manager=self.db_manager,  # Database manager for bookmark/rating operations
    pdf_base_dir="/path/to/pdf/directory"  # Base directory for PDF files
)

# Display a document
document_display.display_document(document_data)

# Connect to signals
document_display.documentRated.connect(self._on_document_rated)
document_display.documentBookmarked.connect(self._on_document_bookmarked)
```

### Setting a Summary Generator

You can provide a function to generate summaries for documents that don't have one:

```python
def generate_summary(document):
    """Generate a summary for a document."""
    # Your summary generation logic here
    title = document.get('title', '')
    abstract = document.get('abstract', '')

    # Example: Just take the first sentence of the abstract
    first_sentence = abstract.split('.')[0] + '.' if '.' in abstract else abstract

    return f"Summary of '{title}': {first_sentence}"

# Set the summary generator
document_display.set_summary_generator(generate_summary)
```

### Handling Signals

The widget emits signals when a document is rated or bookmarked:

```python
def _on_document_rated(self, document, rating):
    """
    Handle document rating.

    Args:
        document: Document data dictionary
        rating: Rating value (1 for positive, -1 for negative)
    """
    print(f"Document '{document['title']}' rated: {rating}")

def _on_document_bookmarked(self, document, bookmark_type, is_bookmarked):
    """
    Handle document bookmarking.

    Args:
        document: Document data dictionary
        bookmark_type: Type of bookmark ("personal" or "project")
        is_bookmarked: Whether the document was bookmarked or unbookmarked
    """
    action = "bookmarked" if is_bookmarked else "unbookmarked"
    print(f"Document '{document['title']}' {action} as {bookmark_type}")
```

## Integration with Context Management

The widget automatically connects to the context management system to track the current user and project. When these values change, the widget updates its state accordingly:

- When the user changes, the widget updates bookmark and rating information
- When the project changes, the widget updates project bookmark information and enables/disables the project bookmark checkbox

## Document Format

The document display widget expects documents in a dictionary format with the following fields:

- `title`: Document title
- `authors`: List of author names
- `publication_date`: Publication date as a string
- `source_name`: Source name (e.g., 'pubmed', 'medrxiv')
- `external_id`: External ID in the source system
- `doi`: DOI (Digital Object Identifier)
- `abstract`: Document abstract
- `summary` (optional): Pre-generated summary
- `keywords`: List of keywords
- `journal`: Journal name
- `url`: URL to the document

## Example: Integration with Document List

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from localknowledge.ui.document_list_widget import DocumentListWidget
from localknowledge.ui.document_display_widget import DocumentDisplayWidget

class DocumentBrowserWidget(QWidget):
    """Widget for browsing and viewing documents."""

    def __init__(self, parent=None, db_manager=None):
        """Initialize the widget."""
        super().__init__(parent)
        self.db_manager = db_manager

        # Set up UI
        layout = QVBoxLayout(self)

        # Create splitter
        splitter = QSplitter()

        # Document list on the left
        self.document_list = DocumentListWidget()
        self.document_list.documentSelected.connect(self._on_document_selected)

        # Document display on the right
        self.document_display = DocumentDisplayWidget(
            parent=self,
            db_manager=self.db_manager
        )

        # Add widgets to splitter
        splitter.addWidget(self.document_list)
        splitter.addWidget(self.document_display)

        # Add splitter to layout
        layout.addWidget(splitter)

    def _on_document_selected(self, document):
        """
        Handle document selection.

        Args:
            document: Selected document data
        """
        self.document_display.display_document(document)
```

## Best Practices

1. **Always provide a database manager** for bookmark and rating operations
2. **Connect to the documentRated and documentBookmarked signals** to handle user interactions
3. **Use the widget in a splitter** with a document list for a complete browsing experience
4. **Clear the widget** when no document is selected by calling `clear()`
5. **Provide a summary generator** if you want to enable on-demand summary generation
