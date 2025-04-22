# Unified Document Database

## Overview

The Unified Document Database provides a centralized storage solution for all document types in the Local Knowledge system. It replaces the separate tables for different data sources (e.g., PubMed, MedRxiv) with a single document table that references source-specific information.

## Benefits

- **Simplified Schema**: One table for all documents, regardless of source
- **Reduced Complexity**: Common operations work the same way for all document types
- **Future-Proof Design**: Easy to add new data sources without schema changes
- **Improved Maintainability**: Less code duplication across database modules

## Core Components

### DocumentDatabaseManager

The `DocumentDatabaseManager` class in `localknowledge.db.document` provides core functionality for working with the unified document table:

- Creating and managing document tables
- Storing and retrieving documents from any source
- Searching documents across all sources
- Managing document metadata like tags and categories

### Database Schema

The unified document database consists of several tables:

#### sources

Stores information about different data sources:

```sql
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    url TEXT,
    is_reputable BOOLEAN DEFAULT FALSE,
    is_free BOOLEAN DEFAULT TRUE
)
```

#### categories

Stores document categories:

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
)
```

#### document

The main document table that stores all document metadata:

```sql
CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    external_id TEXT NOT NULL,  -- e.g., DOI or PMID
    doi TEXT,
    title TEXT,
    abstract TEXT,
    category_id INTEGER REFERENCES categories(id),
    keywords TEXT[],
    augmented_keywords TEXT[],  -- keywords expanded and AI generated
    mesh_terms TEXT[],
    authors TEXT[],
    publication TEXT,
    publication_date DATE,
    url TEXT,
    pdf_url TEXT,
    pdf_filename TEXT,
    full_text TEXT,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn_date TIMESTAMP,
    withdrawn_reason TEXT,
    UNIQUE (source_id, external_id)
)
```

#### keywords and document_keywords

Normalized storage for document keywords:

```sql
CREATE TABLE keywords (
    keyword TEXT PRIMARY KEY
)

CREATE TABLE document_keywords (
    document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
    keyword TEXT REFERENCES keywords(keyword) ON DELETE CASCADE,
    PRIMARY KEY (document_id, keyword)
)
```

#### tags

User-specific document tags:

```sql
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
    user_id INTEGER,  -- References users table
    tag TEXT NOT NULL,
    UNIQUE (document_id, user_id, tag)
)
```

## Usage Examples

### Basic Document Operations

```python
from localknowledge.db.document import DocumentDatabaseManager

# Create a document manager
doc_db = DocumentDatabaseManager()

# Add a document
document_data = {
    'source_name': 'medrxiv',
    'external_id': '10.1101/2023.01.01.12345',
    'doi': '10.1101/2023.01.01.12345',
    'title': 'Example MedRxiv Preprint',
    'abstract': 'This is an example abstract.',
    'category_name': 'Infectious Diseases',
    'keywords': ['covid-19', 'research'],
    'authors': ['John Doe', 'Jane Smith'],
    'publication_date': '2023-01-01',
    'pdf_url': 'https://www.medrxiv.org/content/10.1101/2023.01.01.12345.pdf',
    'pdf_filename': 'medrxiv/2023.01.01.12345.pdf'. # the pdf basepath is provided to the system
}

document_id = doc_db.add_document(document_data)
print(f"Added document with ID: {document_id}")

# Get a document by external ID
document = doc_db.get_document_by_external_id('medrxiv', '10.1101/2023.01.01.12345')
print(f"Retrieved document: {document['title']}")

# Get a document by DOI
document = doc_db.get_document_by_doi('10.1101/2023.01.01.12345')
print(f"Retrieved document by DOI: {document['title']}")

# Close the connection
doc_db.close()
```

### Searching Documents

```python
from localknowledge.db.document import DocumentDatabaseManager

# Create a document manager
doc_db = DocumentDatabaseManager()

# Search for documents
results = doc_db.search_documents('covid-19', limit=10)
print(f"Found {len(results)} documents")

# Search with source filter
results = doc_db.search_documents('covid-19', source_name='pubmed', limit=10)
print(f"Found {len(results)} PubMed documents")

# Get recent documents
recent = doc_db.get_recent_documents(limit=10)
print(f"Recent documents: {[doc['title'] for doc in recent]}")

# Close the connection
doc_db.close()
```

### Working with Tags

```python
from localknowledge.db.document import DocumentDatabaseManager

# Create a document manager
doc_db = DocumentDatabaseManager()

# Add a tag to a document
doc_db.add_tag('medrxiv', '10.1101/2023.01.01.12345', user_id=1, tag='important')

# Get tags for a document
tags = doc_db.get_document_tags('medrxiv', '10.1101/2023.01.01.12345', user_id=1)
print(f"Tags: {[tag['tag'] for tag in tags]}")

# Remove a tag
doc_db.remove_tag(tags[0]['id'])

# Close the connection
doc_db.close()
```

## Migration

To migrate from the old database structure to the unified document structure, use the migration scripts in `localknowledge.db.migrations`:

### Running Individual Migrations

```bash
# Run in dry-run mode first to see what would be done
python -m localknowledge.db.migrations.migrate_to_unified_document

# Execute the migration
python -m localknowledge.db.migrations.migrate_to_unified_document --execute

# Update embeddings references (both regular and multiembeddings)
python -m localknowledge.db.migrations.update_embeddings_references --execute

# Update QA embeddings references
python -m localknowledge.db.migrations.update_qaembeddings_references --execute
```

### Running All Migrations

Alternatively, you can run all migrations in the correct order using the `run_all_migrations.py` script:

```bash
# Run in dry-run mode first to see what would be done
python -m localknowledge.db.migrations.run_all_migrations

# Execute all migrations
python -m localknowledge.db.migrations.run_all_migrations --execute
```

### Migration Process

The migration process consists of the following steps:

1. **Create Document Tables**: Creates the new unified document tables if they don't exist
2. **Migrate Data**: Moves data from the existing tables (preprints, pubmed_articles) to the new document table
3. **Update Embeddings**: Updates embeddings references to point to the new document structure
4. **Update QA Embeddings**: Updates QA embeddings references to point to the new document structure

### Important Considerations

- Always backup your database before running migrations
- Run migrations during a maintenance window when no other processes are accessing the database
- Use the `--batch-size` parameter to control the number of records processed in each batch
- Monitor the migration logs for any errors or warnings

## Compatibility Layer

During the transition period, you can use the compatibility adapters in `localknowledge.db.compatibility` to maintain backward compatibility with existing code:

```python
from localknowledge.db.compatibility import MedRxivCompatibilityAdapter

# Create a compatibility adapter
adapter = MedRxivCompatibilityAdapter()

# Use the adapter with the old API
preprint = adapter.get_preprint_by_doi('10.1101/2023.01.01.12345')
print(f"Retrieved preprint: {preprint['title']}")
```

## Best Practices

- Always use parameterized queries to avoid SQL injection
- Use transactions for batch operations
- Close database connections when done
- Use the compatibility layer during the transition period
- Update code to use the new API when possible
