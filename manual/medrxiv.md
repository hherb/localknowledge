# MedRxiv Module

## Overview

The MedRxiv Module provides functionality for working with preprints from the MedRxiv repository. It includes capabilities for downloading, parsing, storing, and analyzing preprint data.

## Core Components

### MedRxiv Client

The `MedRxivClient` class in `localknowledge.medrxiv` provides the main interface for working with MedRxiv data:

- Downloading preprints from the MedRxiv API
- Storing preprint metadata in the database
- Retrieving and searching preprints
- Downloading PDF files for preprints
- Updating embeddings and QA embeddings

### Database Manager

The `MedRxivDatabaseManager` class in `localknowledge.db.medrxiv` handles database operations for MedRxiv data:

- Creating and managing the preprints table
- Storing and retrieving preprint metadata
- Searching preprints by various criteria
- Managing PDF file paths

### Update Tools

The module includes several tools for updating the database:

- `update_database.py`: Updates the database with new preprints
- `update_pdf_paths.py`: Updates PDF file paths in the database
- `embed_abstracts.py`: Creates embeddings for preprint abstracts
- `update_qaembeddings.py`: Creates QA embeddings for preprint abstracts

## Database Schema

The `preprints` table stores MedRxiv preprint metadata:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| doi | TEXT | Digital Object Identifier |
| title | TEXT | Preprint title |
| abstract | TEXT | Preprint abstract |
| authors | TEXT | JSON array of authors |
| date | DATE | Publication date |
| category | TEXT | Category/subject area |
| version | TEXT | Preprint version |
| license | TEXT | License information |
| journal_ref | TEXT | Journal reference (if published) |
| url | TEXT | URL to the preprint |
| pdf_url | TEXT | URL to the PDF file |
| local_pdf_path | TEXT | Path to the local PDF file |
| created_at | TIMESTAMP | Record creation timestamp |
| updated_at | TIMESTAMP | Record update timestamp |

## Usage Examples

### Basic Usage

```python
from localknowledge.medrxiv import MedRxivClient

# Create a client
client = MedRxivClient()

# Get recent preprints
preprints = client.get_recent_preprints(limit=10)

# Print preprint information
for preprint in preprints:
    print(f"DOI: {preprint['doi']}")
    print(f"Title: {preprint['title']}")
    print(f"Authors: {preprint['authors']}")
    print(f"Date: {preprint['date']}")
    print()

# Close the client
client.close()
```

### Searching Preprints

```python
from localknowledge.medrxiv import MedRxivClient

# Create a client
client = MedRxivClient()

# Search for preprints
results = client.search_preprints(
    query="traumatic brain injury",
    limit=10,
    sort_by="date",
    sort_order="desc"
)

# Print search results
print(f"Found {len(results)} preprints:")
for preprint in results:
    print(f"DOI: {preprint['doi']}")
    print(f"Title: {preprint['title']}")
    print(f"Date: {preprint['date']}")
    print()

# Close the client
client.close()
```

### Downloading PDFs

```python
from localknowledge.medrxiv import MedRxivClient

# Create a client
client = MedRxivClient()

# Get a preprint by DOI
doi = "10.1101/2023.01.01.12345"
preprint = client.get_preprint_by_doi(doi)

if preprint:
    # Download the PDF
    pdf_path = client.download_pdf(preprint)
    print(f"Downloaded PDF to: {pdf_path}")
else:
    print(f"Preprint with DOI {doi} not found")

# Close the client
client.close()
```

### Updating QA Embeddings

```python
from localknowledge.medrxiv import MedRxivClient

# Create a client
client = MedRxivClient()

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
# Update the database with new preprints
python -m localknowledge.medrxiv.update_database

# Update with a specific date range
python -m localknowledge.medrxiv.update_database --from-date 2023-01-01 --to-date 2023-01-31

# Update with a specific limit
python -m localknowledge.medrxiv.update_database --limit 1000
```

### Update PDF Paths

```bash
# Update PDF paths in the database
python -m localknowledge.medrxiv.update_pdf_paths

# Specify a PDF directory
python -m localknowledge.medrxiv.update_pdf_paths --pdf-dir /path/to/pdfs
```

### Embed Abstracts

```bash
# Create embeddings for abstracts
python -m localknowledge.medrxiv.embed_abstracts

# Specify a limit
python -m localknowledge.medrxiv.embed_abstracts --limit 1000

# Specify a model
python -m localknowledge.medrxiv.embed_abstracts --model "nomic-embed-text:latest"
```

### Update QA Embeddings

```bash
# Count abstracts without QA embeddings
python -m localknowledge.medrxiv.update_qaembeddings_cli --count

# Process all abstracts without QA embeddings
python -m localknowledge.medrxiv.update_qaembeddings_cli

# Process a limited number of abstracts
python -m localknowledge.medrxiv.update_qaembeddings_cli --limit 1000

# Use a different QA model
python -m localknowledge.medrxiv.update_qaembeddings_cli --qa-model "llama3:8b"

# Use a different embedding model
python -m localknowledge.medrxiv.update_qaembeddings_cli --embedding-model "nomic-embed-text:latest"
```

## Configuration

### API Configuration

The MedRxiv API configuration is defined in `localknowledge.medrxiv.config`:

```python
# MedRxiv API configuration
API_CONFIG = {
    'base_url': 'https://api.medrxiv.org/v1',
    'timeout': 30,
    'max_retries': 3,
    'retry_delay': 1
}
```

### PDF Storage Configuration

PDF storage configuration is defined in `localknowledge.medrxiv.config`:

```python
# PDF storage configuration
PDF_CONFIG = {
    'pdf_dir': '/path/to/pdfs',
    'filename_template': '{doi}.pdf',
    'max_retries': 3,
    'retry_delay': 1
}
```

Environment variables can override these settings:

- `LK_MEDRXIV_PDF_DIR`: Directory for storing PDFs
- `LK_MEDRXIV_API_URL`: MedRxiv API URL
- `LK_MEDRXIV_API_TIMEOUT`: API timeout in seconds

## Performance Considerations

### API Rate Limiting

The MedRxiv API has rate limits. To avoid hitting these limits:

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
   python -m localknowledge.medrxiv.update_database
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
   python -m localknowledge.medrxiv.embed_abstracts
   ```

2. Run the QA embeddings update script periodically:
   ```bash
   python -m localknowledge.medrxiv.update_qaembeddings_cli
   ```

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
   logging.getLogger('localknowledge.medrxiv').setLevel(logging.DEBUG)
   ```

2. Use the `--debug` flag with command-line tools:
   ```bash
   python -m localknowledge.medrxiv.update_database --debug
   ```

3. Check the API response directly:
   ```python
   import requests
   response = requests.get('https://api.medrxiv.org/v1/search?q=covid')
   print(response.status_code)
   print(response.json())
   ```
