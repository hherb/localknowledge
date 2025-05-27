# PubMed Module

## Overview

The PubMed Module provides functionality for working with publications from the PubMed database. It includes capabilities for downloading, parsing, storing, and analyzing publication data from PubMed.

## Recent Fixes

### Abstract Truncation Fix (2024)

**Issue**: Abstracts were being truncated when encountering special characters like subscripts, superscripts, or other XML formatting elements. For example, text like "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n<sub>5</sub>)" would be truncated to "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n".

**Root Cause**: The original code used `element.text` to extract text content from XML elements, but this only returns text before the first child element, not the complete text content including text after child elements.

**Solution**: Implemented a new `get_element_text()` function in `localknowledge.pubmed.import_downloads` that recursively extracts all text content from XML elements, including:
- Text before child elements (`element.text`)
- Text content from child elements (recursive)
- Text after child elements (`child.tail`)

**Files Modified**:
- `localknowledge/pubmed/import_downloads.py`: Added `get_element_text()` function and updated text extraction for titles, abstracts, authors, journal names, MeSH terms, keywords, and DOIs.

**Testing**: Added comprehensive unit tests in `tests/test_pubmed_text_extraction.py` and verified with real PubMed article PMID 28675679.

**Impact**: This fix ensures that all text content from PubMed abstracts is properly imported, including complex chemical formulas, mathematical expressions, and other formatted content that was previously being truncated.

## Core Components

### PubMed Client

The `PubMedClient` class in `localknowledge.pubmed` provides the main interface for working with PubMed data:

- Downloading publications from the PubMed API
- Storing publication metadata in the database
- Retrieving and searching publications
- Downloading PDF files for publications
- Updating embeddings and QA embeddings

### Database Manager

The `PubMedDatabaseManager` class in `localknowledge.db.pubmed` handles database operations for PubMed data:

- Creating and managing the pubmed table
- Storing and retrieving publication metadata
- Searching publications by various criteria
- Managing PDF file paths

### Update Tools

The module includes several tools for updating the database:

- `update_database.py`: Updates the database with new publications
- `update_pdf_paths.py`: Updates PDF file paths in the database
- `embed_abstracts.py`: Creates embeddings for publication abstracts
- `update_qaembeddings.py`: Creates QA embeddings for publication abstracts

## Database Schema

The `pubmed` table stores PubMed publication metadata:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| pmid | TEXT | PubMed ID |
| title | TEXT | Publication title |
| abstract | TEXT | Publication abstract |
| authors | TEXT | JSON array of authors |
| date | DATE | Publication date |
| journal | TEXT | Journal name |
| volume | TEXT | Journal volume |
| issue | TEXT | Journal issue |
| pages | TEXT | Page range |
| doi | TEXT | Digital Object Identifier |
| url | TEXT | URL to the publication |
| pdf_url | TEXT | URL to the PDF file |
| local_pdf_path | TEXT | Path to the local PDF file |
| created_at | TIMESTAMP | Record creation timestamp |
| updated_at | TIMESTAMP | Record update timestamp |

## Usage Examples

### Basic Usage

```python
from localknowledge.pubmed import PubMedClient

# Create a client
client = PubMedClient()

# Get recent publications
publications = client.get_recent_publications(limit=10)

# Print publication information
for pub in publications:
    print(f"PMID: {pub['pmid']}")
    print(f"Title: {pub['title']}")
    print(f"Authors: {pub['authors']}")
    print(f"Date: {pub['date']}")
    print()

# Close the client
client.close()
```

### Searching Publications

```python
from localknowledge.pubmed import PubMedClient

# Create a client
client = PubMedClient()

# Search for publications
results = client.search_publications(
    query="traumatic brain injury",
    limit=10,
    sort_by="date",
    sort_order="desc"
)

# Print search results
print(f"Found {len(results)} publications:")
for pub in results:
    print(f"PMID: {pub['pmid']}")
    print(f"Title: {pub['title']}")
    print(f"Date: {pub['date']}")
    print()

# Close the client
client.close()
```

### Downloading PDFs

```python
from localknowledge.pubmed import PubMedClient

# Create a client
client = PubMedClient()

# Get a publication by PMID
pmid = "12345678"
publication = client.get_publication_by_pmid(pmid)

if publication:
    # Download the PDF
    pdf_path = client.download_pdf(publication)
    print(f"Downloaded PDF to: {pdf_path}")
else:
    print(f"Publication with PMID {pmid} not found")

# Close the client
client.close()
```

### Updating QA Embeddings

```python
from localknowledge.pubmed import PubMedClient

# Create a client
client = PubMedClient()

# Count abstracts without QA embeddings
count = client.count_abstracts_without_qa_embeddings()
print(f"Found {count} abstracts without QA embeddings")

# Update QA embeddings for a limited number of abstracts
processed = client.update_qa_embeddings(limit=100, batch_size=10)
print(f"Successfully processed {processed} abstracts")

# Close the client
client.close()
```

## Command-Line Tools

The module provides several command-line tools:

### Update Database

```bash
# Update the database with new publications
python -m localknowledge.pubmed.update_database

# Update with a specific date range
python -m localknowledge.pubmed.update_database --from-date 2023-01-01 --to-date 2023-01-31

# Update with a specific limit
python -m localknowledge.pubmed.update_database --limit 1000
```

### Update PDF Paths

```bash
# Update PDF paths in the database
python -m localknowledge.pubmed.update_pdf_paths

# Specify a PDF directory
python -m localknowledge.pubmed.update_pdf_paths --pdf-dir /path/to/pdfs
```

### Embed Abstracts

```bash
# Create embeddings for abstracts
python -m localknowledge.pubmed.embed_abstracts

# Specify a limit
python -m localknowledge.pubmed.embed_abstracts --limit 1000

# Specify a model
python -m localknowledge.pubmed.embed_abstracts --model "nomic-embed-text:latest"
```

### Update QA Embeddings

```bash
# Count abstracts without QA embeddings
python -m localknowledge.pubmed.update_qaembeddings_cli --count

# Process all abstracts without QA embeddings
python -m localknowledge.pubmed.update_qaembeddings_cli

# Process a limited number of abstracts
python -m localknowledge.pubmed.update_qaembeddings_cli --limit 1000

# Use a different QA model
python -m localknowledge.pubmed.update_qaembeddings_cli --qa-model "llama3:8b"

# Use a different embedding model
python -m localknowledge.pubmed.update_qaembeddings_cli --embedding-model "nomic-embed-text:latest"
```

## Configuration

### API Configuration

The PubMed API configuration is defined in `localknowledge.pubmed.config`:

```python
# PubMed API configuration
API_CONFIG = {
    'base_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils',
    'api_key': None,  # Optional API key
    'tool': 'LocalKnowledge',
    'email': 'user@example.com',
    'timeout': 30,
    'max_retries': 3,
    'retry_delay': 1
}
```

### PDF Storage Configuration

PDF storage configuration is defined in `localknowledge.pubmed.config`:

```python
# PDF storage configuration
PDF_CONFIG = {
    'pdf_dir': '/path/to/pdfs',
    'filename_template': '{pmid}.pdf',
    'max_retries': 3,
    'retry_delay': 1
}
```

Environment variables can override these settings:

- `LK_PUBMED_PDF_DIR`: Directory for storing PDFs
- `LK_PUBMED_API_KEY`: PubMed API key
- `LK_PUBMED_EMAIL`: Email for PubMed API
- `LK_PUBMED_API_TIMEOUT`: API timeout in seconds

## Performance Considerations

### API Rate Limiting

The PubMed API has rate limits. To avoid hitting these limits:

- Use an API key for higher rate limits
- Use batch operations where possible
- Implement exponential backoff for retries
- Limit concurrent requests

### PDF Downloads

Downloading PDFs can be resource-intensive. To optimize:

- Download PDFs in parallel using a thread pool
- Implement caching to avoid re-downloading
- Verify file integrity after download

### Database Operations

For optimal database performance:

- Use transactions for batch operations
- Create appropriate indices for frequently queried columns
- Use parameterized queries to avoid SQL injection and improve query planning

## Maintenance

### Updating the Database

To keep the database up to date:

1. Run the update script periodically:
   ```bash
   python -m localknowledge.pubmed.update_database
   ```

2. Schedule the script to run daily or weekly using cron or a similar scheduler

### Managing PDF Storage

To manage PDF storage:

1. Monitor disk space usage
2. Implement a cleanup policy for old or unused PDFs
3. Consider using a distributed file system for large collections

### Updating Embeddings

To keep embeddings up to date:

1. Run the embedding update script periodically:
   ```bash
   python -m localknowledge.pubmed.embed_abstracts
   ```

2. Run the QA embeddings update script periodically:
   ```bash
   python -m localknowledge.pubmed.update_qaembeddings_cli
   ```

## PubMed API

### API Endpoints

The PubMed API provides several endpoints:

- `esearch.fcgi`: Search for publications
- `efetch.fcgi`: Fetch publication details
- `elink.fcgi`: Find related publications
- `einfo.fcgi`: Get database information
- `esummary.fcgi`: Get publication summaries

### API Parameters

Common API parameters:

- `db`: Database to search (pubmed)
- `term`: Search term
- `retmax`: Maximum number of results
- `retstart`: Result offset for pagination
- `sort`: Sort order
- `api_key`: API key for higher rate limits

### API Response Format

The API returns XML or JSON responses. The module parses these responses into Python dictionaries.

## Troubleshooting

### Common Issues

1. **API Connection Errors**: Check network connectivity and API status.

2. **PDF Download Failures**: Check URL validity, network connectivity, and storage permissions.

3. **Database Errors**: Check database connection, schema, and query syntax.

4. **Embedding Errors**: Check model availability and compatibility.

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.pubmed').setLevel(logging.DEBUG)
   ```

2. Use the `--debug` flag with command-line tools:
   ```bash
   python -m localknowledge.pubmed.update_database --debug
   ```

3. Check the API response directly:
   ```python
   import requests
   response = requests.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=covid&retmax=10&retmode=json')
   print(response.status_code)
   print(response.json())
   ```

## Integration with Other Modules

### Integration with Embeddings

The PubMed module integrates with the embeddings module to create and search embeddings for publication abstracts:

```python
from localknowledge.pubmed import PubMedClient
from localknowledge.embeddings import EmbeddingManager

# Create clients
pubmed_client = PubMedClient()
embedding_manager = EmbeddingManager()

# Get a publication
publication = pubmed_client.get_publication_by_pmid("12345678")

# Create an embedding for the abstract
embedding = embedding_manager.process_text(
    source_id='pubmed',
    document_id=publication['pmid'],
    text=publication['abstract'],
    chunk_no=0
)

# Search for similar publications
results = embedding_manager.search(
    query="traumatic brain injury",
    limit=10,
    threshold=0.7,
    source_id='pubmed'
)

# Close clients
pubmed_client.close()
embedding_manager.close()
```

### Integration with QA Embeddings

The PubMed module integrates with the QA embeddings module to create and search QA embeddings for publication abstracts:

```python
from localknowledge.pubmed import PubMedClient
from localknowledge.ai.qafinder import QAEmbeddingManager

# Create clients
pubmed_client = PubMedClient()
qa_manager = QAEmbeddingManager()

# Get a publication
publication = pubmed_client.get_publication_by_pmid("12345678")

# Create QA embeddings for the abstract
result = qa_manager.process_text(
    source_id='pubmed',
    document_id=publication['pmid'],
    text=publication['abstract'],
    chunk_no=0
)

# Search for similar QA pairs
results = qa_manager.search(
    query="What is the effect of treatment X on condition Y?",
    limit=10,
    threshold=0.7,
    source_id='pubmed'
)

# Close clients
pubmed_client.close()
qa_manager.close()
```
