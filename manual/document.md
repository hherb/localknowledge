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

#### Using DocumentDatabaseManager (Legacy)

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

#### Using DocumentSearchManager (Recommended)

The `DocumentSearchManager` class in `localknowledge.db.document_search` provides specialized search functions that return generators for memory-efficient processing of large result sets. It supports threadsafe operation, asynchronous mode, and configurable timeouts:

```python
from localknowledge.db.document_search import DocumentSearchManager

# Create a document search manager
search_manager = DocumentSearchManager()

# Basic keyword search with included and excluded terms
# Returns a generator that yields documents in batches
result_count = 0
for doc in search_manager.keywords(
    included=['covid', 'vaccine'],
    excluded=['children'],
    limit=10
):
    # Process each document as it's retrieved
    print(f"{doc['title']} ({doc['source_name']})")
    result_count += 1
print(f"Found {result_count} documents")

# Keyword search with source filter
# If you need all results at once, convert to a list
results = list(search_manager.keywords(
    included=['covid', 'vaccine'],
    source_name='pubmed',
    limit=10
))
print(f"Found {len(results)} PubMed documents")

# For very large result sets, use batch_size to control memory usage
# and set limit=0 for no limit on total results
for doc in search_manager.keywords(
    included=['covid'],
    batch_size=100,  # Fetch 100 documents at a time
    limit=0  # No limit on total results
):
    # Process each document without loading all into memory
    process_document(doc)

# For long-running queries, use a longer timeout or disable it completely
for doc in search_manager.keywords(
    included=['rare', 'disease'],
    timeout=300,  # 5 minutes timeout
    limit=1000
):
    process_document(doc)

# For unlimited timeout, set timeout to None
for doc in search_manager.keywords(
    included=['comprehensive', 'analysis'],
    timeout=None,  # No timeout
    limit=1000
):
    process_document(doc)

# For asynchronous processing, use async_mode=True
# Results will be yielded as they become available
for doc in search_manager.keywords(
    included=['covid'],
    limit=1000,
    async_mode=True  # Run in background thread
):
    # Process results as they arrive, even while query is still running
    process_document(doc)

# Close the connection
search_manager.close()
```

The `keywords` method supports the following parameters:

- `included`: List of keywords to include in the search
- `excluded`: List of keywords to exclude from the search (optional)
- `source_name`: Filter by source name (optional)
- `limit`: Maximum number of results to return (use 0 for no limit)
- `offset`: Number of results to skip
- `batch_size`: Number of results to fetch in each database query
- `timeout`: Query timeout in seconds (default: 30, None for no timeout)
- `async_mode`: Whether to run the query in asynchronous mode (default: False)

#### Semantic Search

The `DocumentSearchManager` also provides semantic search capabilities through the `semantic` method:

```python
from localknowledge.db.document_search import DocumentSearchManager

# Create a document search manager
search_manager = DocumentSearchManager()

# Basic semantic search
for doc in search_manager.semantic(
    question="What are the long-term effects of COVID-19?",
    similarity_threshold=0.6,
    max_results=20
):
    print(f"{doc['title']} (Similarity: {doc['similarity']:.4f})")

# Semantic search with source filter
results = list(search_manager.semantic(
    question="What are the long-term effects of COVID-19?",
    source_name='pubmed',
    max_results=10
))
print(f"Found {len(results)} PubMed documents")

# For long-running semantic searches, use a longer timeout or disable it completely
for doc in search_manager.semantic(
    question="What is the mechanism of action for remdesivir?",
    timeout=300,  # 5 minutes timeout
    max_results=50
):
    process_document(doc)

# For asynchronous semantic search, use async_mode=True
for doc in search_manager.semantic(
    question="What are the latest treatments for Alzheimer's disease?",
    max_results=100,
    async_mode=True  # Run in background thread
):
    # Process results as they arrive, even while query is still running
    process_document(doc)

# Custom reranking function
def rerank_results(question, results):
    # Implement custom reranking logic
    # For example, boost results with certain keywords in the title
    for result in results:
        if 'alzheimer' in result['title'].lower():
            result['similarity'] += 0.1

    # Sort by similarity again
    return sorted(results, key=lambda x: x['similarity'], reverse=True)

# Semantic search with custom reranker
for doc in search_manager.semantic(
    question="What are the latest treatments for Alzheimer's disease?",
    reranker=rerank_results
):
    print(f"{doc['title']} (Similarity: {doc['similarity']:.4f})")

# Close the connection
search_manager.close()
```

The `semantic` method supports the following parameters:

- `question`: The question or query to search for
- `similarity_threshold`: Minimum similarity score (0-1) for results (default: 0.5)
- `max_results`: Maximum number of results to return (default: 50)
- `source_name`: Filter by source name (optional)
- `embed_source`: Embedding source to search (default: 'abstract')
- `timeout`: Query timeout in seconds (default: 30, None for no timeout)
- `async_mode`: Whether to run the query in asynchronous mode (default: False)
- `reranker`: Optional function to rerank results (takes question and results as input)

#### HyDE Search

The `DocumentSearchManager` also provides HyDE (Hypothetical Document Embeddings) search capabilities through the `hyde` method. HyDE improves semantic search by generating a hypothetical document that answers the query, then using that document's embedding for search instead of directly embedding the query:

```python
from localknowledge.db.document_search import DocumentSearchManager

# Create a document search manager
search_manager = DocumentSearchManager()

# Basic HyDE search
for doc in search_manager.hyde(
    question="What are the long-term effects of COVID-19?",
    similarity_threshold=0.6,
    max_results=20
):
    print(f"{doc['title']} (Similarity: {doc['similarity']:.4f})")
    # Each result includes the generated hypothetical document
    if 'hyde_document' in doc:
        print(f"HyDE document: {doc['hyde_document'][:100]}...")

# HyDE search with custom model
for doc in search_manager.hyde(
    question="What are the latest treatments for Alzheimer's disease?",
    model_name="llama3.2:3b-instruct-q8_0"  # Use a different model for generation
):
    process_document(doc)

# HyDE search with pre-generated hypothetical document
hypothetical_doc = """
Objective: To evaluate the long-term neurological effects of COVID-19 infection.
Methods: A prospective cohort study of 1,000 patients with confirmed COVID-19 was conducted with 12-month follow-up.
Results: Neurological symptoms persisted in 30% of patients, with fatigue, cognitive impairment, and headaches being most common.
Conclusion: COVID-19 has significant long-term neurological effects that require ongoing monitoring and management.
"""

for doc in search_manager.hyde(
    question="What are the neurological effects of COVID-19?",
    hydeprompt=hypothetical_doc  # Use pre-generated document
):
    process_document(doc)

# Asynchronous HyDE search
for doc in search_manager.hyde(
    question="What is the mechanism of action for remdesivir?",
    async_mode=True  # Run in background thread
):
    # Process results as they arrive, even while query is still running
    process_document(doc)

# Close the connection
search_manager.close()
```

The `hyde` method supports the following parameters:

- `question`: The question or query to search for
- `similarity_threshold`: Minimum similarity score (0-1) for results (default: 0.5)
- `max_results`: Maximum number of results to return (default: 50)
- `source_name`: Filter by source name (optional)
- `embed_source`: Embedding source to search (default: 'abstract')
- `timeout`: Query timeout in seconds (default: 30, None for no timeout)
- `async_mode`: Whether to run the query in asynchronous mode (default: False)
- `reranker`: Optional function to rerank results (takes question and results as input)
- `hydeprompt`: Optional pre-generated hypothetical document (if None, one will be generated)
- `model_name`: Model to use for generating the hypothetical document (default: gemma3:4b)

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
