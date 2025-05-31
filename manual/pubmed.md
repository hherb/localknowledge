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

### Import Tracking System (2024)

**Purpose**: The import tracking system prevents reprocessing of the same files when restarting interrupted import or fix processes, improving efficiency and avoiding duplicate work.

**Components**:
- `localknowledge.db.import_tracker.ImportTracker`: Database manager for tracking file processing status
- `import_tracker` table: Database table storing processing status for each XML file

**Tracking States**:
- `imported`: File has been successfully imported into the database
- `chunked`: File's content has been chunked for embedding processing
- `embedded`: File's chunks have been embedded with vector representations
- `md5checked`: File's MD5 checksum has been verified

**Integration**:
- **PubMed Import**: `localknowledge.pubmed.import_downloads` now uses import tracking to skip already imported files and mark successful imports
- **Corruption Fix**: `localknowledge.pubmed.fix_corrupt_pubmed_imports` uses import tracking to only process files that have been imported and to mark re-chunked/re-embedded files

**Usage Example**:
```python
from localknowledge.db.import_tracker import ImportTracker

# Create tracker
tracker = ImportTracker()

# Check if file has been imported
if not tracker.is_file_imported('pubmed24n0001.xml.gz'):
    # Process the file
    process_file('pubmed24n0001.xml.gz')
    # Mark as imported
    tracker.mark_file_imported('pubmed24n0001.xml.gz')

# Get processing statistics
stats = tracker.get_processing_stats()
print(f"Total files: {stats['total_files']}")
print(f"Imported files: {stats['imported_files']}")
print(f"Embedded files: {stats['embedded_files']}")

tracker.close()
```

### Download Corruption Fixes (2025-05-29)

**Issue**: The PubMed download system was experiencing corruption issues including:
- File size mismatches between downloaded and expected sizes
- Block decoding errors during gzip decompression
- MD5 checksum verification failures
- CRC check failures during file reading

**Root Causes**:
1. **Complex Size-Limiting Logic**: The original download code used a `StopDownloadException` mechanism that could cause premature termination and incomplete writes
2. **Overly Complex Resume Logic**: Nested file handling during resume operations could cause state inconsistencies
3. **Multiple Conflicting Integrity Checks**: Integrity checks performed during download could interfere with the download process
4. **Insufficient Error Recovery**: Failed downloads didn't properly clean up state for retries

**Solution**: Implemented a simplified, more robust download system:

**Files Modified**:
- `localknowledge/pubmed/download.py`: Completely refactored `download_single_file()` function with simplified logic
- `localknowledge/pubmed/file_verification.py`: Simplified download logic to avoid corruption
- Added comprehensive test script: `localknowledge/pubmed/test_download_fix.py`

**Key Improvements**:
1. **Simplified Download Logic**: Removed complex size-limiting mechanisms and implemented straightforward download approach
2. **Enhanced File Validation**: Comprehensive verification after download completion including size checks and complete gzip integrity testing
3. **Better Error Recovery**: Proper cleanup on failures with improved retry logic and FTP connection management
4. **Separated Concerns**: Clear separation between download and verification processes

**Testing**: The fixes have been verified with real PubMed file downloads, showing successful detection and recovery from corruption issues.

**Impact**: This fix eliminates download corruption issues and provides more reliable file integrity, ensuring complete and valid PubMed data downloads.

### Publication Date Extraction Fix (2025-01-03)

**Issue**: The `publication_date` field in imported PubMed records was always empty, causing problems with date-based searches and statistics.

**Root Cause**: The code was incorrectly mapping the administrative `DateCreated` field (when the PubMed record was created in the database) to the `publication_date` field instead of using the actual publication date from the `<PubDate>` element.

**Date Fields in PubMed XML**:
- `<PubDate>`: The actual publication date of the article (what should be used for `publication_date`)
- `<DateCreated>`: When the PubMed record was added to the database (administrative date)
- `<DateCompleted>`: When PubMed indexing was completed (administrative date)
- `<DateRevised>`: When the PubMed record was last updated (administrative date)

**Solution**: Modified the import process to properly extract and use the publication date:

**Files Modified**:
- `localknowledge/pubmed/import_downloads.py`: Updated `process_article()` to extract publication date from `<PubDate>` element
- `localknowledge/db/pubmed.py`: Updated `store_article()` to use `publication_date` instead of `date_created`
- `localknowledge/pubmed/import_to_tmpdocument.py`: Applied same fixes for consistency

**Key Improvements**:
1. **Correct Date Source**: `publication_date` now comes from `<PubDate>` element (actual publication date)
2. **Enhanced Date Parsing**: Improved `extract_date()` function handles both numeric and text month formats (e.g., "03", "Mar", "March")
3. **Robust Defaults**: Provides sensible defaults for missing day/month information
4. **Preserved Administrative Dates**: Administrative dates (`date_created`, `date_completed`, `date_revised`) are still extracted and stored separately

**Date Format Handling**:
- Numeric months: `<Month>03</Month>` → "2023-03-15"
- Text months: `<Month>Mar</Month>` → "2023-03-15"
- Year only: `<Year>2023</Year>` → "2023-01-01"
- Year and month: `<Year>2023</Year><Month>Jun</Month>` → "2023-06-01"

**Testing**: Comprehensive unit tests verify correct extraction of publication dates from various PubMed XML date formats.

**Impact**: This fix ensures that publication dates are properly populated, enabling accurate date-based searches, statistics, and chronological sorting of PubMed articles.

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

### Import Downloads with Tracking

```bash
# Import PubMed XML files with automatic import tracking
python -m localknowledge.pubmed.import_downloads --process_type updates

# Import baseline files with tracking
python -m localknowledge.pubmed.import_downloads --process_type baseline

# Force reprocess all files (ignoring tracking)
python -m localknowledge.pubmed.import_downloads --force_reprocess

# Import from specific directories
python -m localknowledge.pubmed.import_downloads \
    --baseline_dir /path/to/baseline \
    --updates_dir /path/to/updates \
    --imported_dir /path/to/imported
```

### Fix Corrupt Imports with Tracking

```bash
# Fix corrupt imports (only processes files that have been imported)
python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml

# Dry run to identify corruption without fixing
python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --dry-run

# Fix corruption in first 10 files
python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --max-files 10

# Fix with larger batch size
python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --batch-size 2000
```

### Import to tmpdocument Table (Data Recovery)

For data recovery purposes, a specialized import script is available that imports PubMed data into a temporary `tmpdocument` table without affecting any other tables or tracking systems:

```bash
# Import all PubMed files from backup directory into tmpdocument table
python localknowledge/pubmed/import_to_tmpdocument.py /path/to/backup/directory

# Example with specific backup directory
python localknowledge/pubmed/import_to_tmpdocument.py ~/backup/pubmed_data/
```

**Key Features**:
- **Safe Import**: Only affects the `tmpdocument` table, no other tables are modified
- **No Tracking**: Does not use or modify any tracking systems
- **No File Movement**: Source files remain untouched in the backup directory
- **Comprehensive Processing**: Processes both baseline and update files
- **Progress Tracking**: Shows detailed progress with file-by-file and article-by-article progress bars
- **Error Handling**: Skips corrupt files and continues processing
- **Detailed Logging**: Creates logs in `pubmed_import_tmpdocument.log`

**Use Cases**:
- Data recovery from backup files
- Testing import processes without affecting production data
- Comparing data integrity between main and backup sources
- Rebuilding corrupted document tables

**Prerequisites**:
- The `tmpdocument` table must exist with the same structure as the `document` table
- Backup directory must contain PubMed XML.gz files
- Database connection must be properly configured

See `localknowledge/pubmed/README_tmpdocument_import.md` for detailed documentation.

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
