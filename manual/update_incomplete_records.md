# Update Incomplete Records

The `update_incomplete_records.py` module provides functionality to update PubMed records with missing or incomplete details by fetching data from various external APIs.

## Overview

Some PubMed records may be imported with missing abstracts or other details. This module attempts to retrieve missing information from several external sources:

1. Europe PMC API
2. Semantic Scholar API
3. Crossref API
4. Unpaywall API
5. arXiv API
6. CORE API

The module works with the unified document database and uses the `missing_details` flag to identify records that need updating.

## Database Requirements

This module requires the `missing_details` column to be added to the `document` table. You can add this column by running the migration:

```bash
python -m localknowledge.db.migrations_system.run_migrations
```

## Usage

### Basic Usage

```python
from localknowledge.pubmed.update_incomplete_records import fix_missing_abstracts, mark_documents_for_update
from localknowledge.db.document import DocumentDatabaseManager

# First mark documents that need updating
doc_db = DocumentDatabaseManager()
try:
    # Mark documents with missing abstracts
    mark_documents_for_update(doc_db, condition="abstract IS NULL OR abstract = ''")
finally:
    doc_db.close()

# Then fix the marked documents
fixed_count = fix_missing_abstracts(batch_size=100, limit=1000)
print(f"Fixed {fixed_count} documents")
```

### Command Line Usage

You can also run the module directly from the command line:

```bash
python -m localknowledge.pubmed.update_incomplete_records
```

This will:
1. Mark all PubMed documents with missing abstracts for update
2. Process these documents in batches, attempting to retrieve missing information from external sources

## Functions

### mark_documents_for_update

```python
def mark_documents_for_update(doc_db: DocumentDatabaseManager, source_name: str = 'pubmed', 
                             condition: str = "abstract IS NULL") -> int:
```

Marks documents that need updating by setting the `missing_details` flag.

**Parameters:**
- `doc_db`: Document database manager
- `source_name`: Name of the source (e.g., 'pubmed')
- `condition`: SQL condition to identify documents that need updating

**Returns:**
- Number of documents marked for update

### fix_missing_abstracts

```python
def fix_missing_abstracts(batch_size: int = 100, limit: int = 1000) -> int:
```

Main function to fix documents with missing details.

**Parameters:**
- `batch_size`: Number of documents to process in each batch
- `limit`: Maximum number of documents to process in total

**Returns:**
- Number of successfully updated documents

## External APIs

The module attempts to retrieve missing information from the following APIs:

1. **Europe PMC API**: Provides comprehensive access to biomedical literature
2. **Semantic Scholar API**: Academic search engine with focus on semantics and context
3. **Crossref API**: Database of academic publication metadata
4. **Unpaywall API**: Database of open access articles
5. **arXiv API**: Repository of electronic preprints
6. **CORE API**: Aggregator of open access research outputs

## Configuration

Some APIs may require API keys or other configuration:

- **CORE API**: Requires an API key. Register at [core.ac.uk](https://core.ac.uk/services/api)
- **Unpaywall API**: Requires an email address

Update the corresponding functions with your credentials before use.

## Error Handling

The module includes robust error handling to ensure that failures with one API or document don't affect the processing of others. All errors are logged for later review.

## Performance Considerations

- The module uses a thread pool to process multiple documents concurrently
- Rate limiting is implemented to avoid overwhelming external APIs
- Processing is done in batches to manage memory usage
