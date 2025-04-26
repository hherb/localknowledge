# Document Display Components

The document display system is composed of several specialized components that work together to provide a comprehensive document viewing experience.

## AbstractDisplayWidget

The `AbstractDisplayWidget` is responsible for displaying a document's abstract and metadata in a nicely formatted way.

### Features

- Displays document title, authors, publication date, and other metadata
- Formats the abstract with proper styling
- Handles links in the abstract (emits a signal when clicked)

### Usage

```python
from localknowledge.ui.abstract_display_widget import AbstractDisplayWidget

# Create the widget
abstract_widget = AbstractDisplayWidget()

# Display a document
abstract_widget.display_document(document_data)

# Connect to signals
abstract_widget.linkClicked.connect(self._on_link_clicked)
```

## SummaryDisplayWidget

The `SummaryDisplayWidget` is responsible for displaying a document's summary if available, or providing a button to generate one on-demand.

### Features

- Displays pre-generated summaries
- Provides a button to generate summaries when not available
- Shows a progress indicator during summary generation
- Can be configured with a custom summary generator function

### Usage

```python
from localknowledge.ui.summary_display_widget import SummaryDisplayWidget

# Create the widget
summary_widget = SummaryDisplayWidget()

# Set a summary generator function
def generate_summary(document):
    """Generate a summary for a document."""
    # Your summary generation logic here
    return "Generated summary text"

summary_widget.set_summary_generator(generate_summary)

# Display a document
summary_widget.display_document(document_data)

# Connect to signals
summary_widget.summaryRequested.connect(self._on_summary_requested)
```

### Summary Generation

The `SummaryDisplayWidget` can be configured with a custom summary generator function that takes a document dictionary and returns a summary string. This function is called when the user clicks the "Generate Summary" button.

```python
def generate_summary(document):
    """
    Generate a summary for a document.

    Args:
        document: Document data dictionary

    Returns:
        str: Generated summary
    """
    # Extract relevant information from the document
    title = document.get('title', '')
    abstract = document.get('abstract', '')

    # Generate a summary using your preferred method
    # This could involve calling an external API, using a local model, etc.
    summary = "Generated summary based on the document content."

    return summary
```

## PDFDisplayWidget

The `PDFDisplayWidget` is responsible for displaying a document's PDF with navigation, search, and zoom capabilities.

### Features

- Displays PDF documents with navigation controls
- Provides search functionality within the PDF
- Shows a message with options when no PDF is available
- Emits signals when PDF-related actions are requested

### Usage

```python
from localknowledge.ui.pdf_display_widget import PDFDisplayWidget

# Create the widget
pdf_widget = PDFDisplayWidget(
    parent=self,
    status_bar=self.status_bar,
    pdf_base_dir="/path/to/pdf/directory"
)

# Display a document
pdf_widget.display_document(document_data)

# Connect to signals
pdf_widget.pdfNotFound.connect(self._on_pdf_not_found)
pdf_widget.pdfFetchRequested.connect(self._on_pdf_fetch_requested)
pdf_widget.pdfUploadRequested.connect(self._on_pdf_upload_requested)
```

### PDF Loading

The `PDFDisplayWidget` attempts to load PDFs in the following order:

1. From the `pdf_filename` field combined with the `pdf_base_dir`
2. From the `pdf_filename` field as an absolute path
3. From the `pdf_url` field (if implemented)

If no PDF is found, it displays a message with options to fetch or upload a PDF.

## Integration

These components are designed to be used together in the `DocumentDisplayWidget`, which provides a tabbed interface for switching between different views of a document. However, they can also be used independently if needed.

## Best Practices

1. **Use consistent document format** across all components
2. **Handle errors gracefully** in summary generation and other operations
3. **Provide visual feedback** during long-running operations
4. **Connect to signals** to handle user interactions
5. **Clear components** when no document is selected
