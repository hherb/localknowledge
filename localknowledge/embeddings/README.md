# Vector Embeddings Module

This module provides functionality for creating and searching vector embeddings using Ollama models and storing them in a PostgreSQL database with pgvector.

## Requirements

- PostgreSQL with pgvector extension installed
- Ollama with embedding models available

## Installation

### PostgreSQL pgvector Extension

1. Install the pgvector extension in your PostgreSQL database:

```sql
CREATE EXTENSION vector;
```

2. Make sure the extension is installed:

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Ollama Setup

1. Install Ollama following the instructions at [ollama.ai](https://ollama.ai)

2. Pull the embedding model:

```bash
ollama pull snowflake-arctic-embed2:latest
```

## Usage

### Creating Embeddings

```python
from localknowledge.embeddings import EmbeddingManager

# Initialize the embedding manager
embedding_manager = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Process a document
chunks = embedding_manager.process_document(
    source_id='medrxiv',
    document_id='10.1101/2023.01.01.12345',
    text="This is the full text of the document..."
)

print(f"Processed {chunks} chunks")

# Close the connection when done
embedding_manager.close()
```

### Searching Embeddings

```python
from localknowledge.embeddings import EmbeddingManager

# Initialize the embedding manager
embedding_manager = EmbeddingManager()

# Search for similar documents
results = embedding_manager.search(
    query="What is the effect of COVID-19 on the lungs?",
    limit=5,
    threshold=0.7
)

# Print the results
for i, result in enumerate(results):
    print(f"\nResult {i+1} (similarity: {result['similarity']:.4f}):")
    print(f"Source: {result['source_id']}, Document: {result['document_id']}")
    print(f"Text: {result['text'][:200]}...")

# Close the connection when done
embedding_manager.close()
```

### Deleting Embeddings

```python
from localknowledge.embeddings import EmbeddingManager

# Initialize the embedding manager
embedding_manager = EmbeddingManager()

# Delete all embeddings for a specific document
deleted = embedding_manager.delete_document(
    source_id='medrxiv',
    document_id='10.1101/2023.01.01.12345'
)

print(f"Deleted {deleted} embeddings")

# Close the connection when done
embedding_manager.close()
```

## Database Migrations

### Vector Size Migration

If you need to change the vector size in the database (e.g., from 1536 to 1024 dimensions), use the provided migration script:

```bash
# First, run in dry-run mode to see what would happen
python -m localknowledge.embeddings.migrations.migrate_vector_size

# If everything looks good, execute the migration
python -m localknowledge.embeddings.migrations.migrate_vector_size --execute
```

The migration script is designed to be safe and non-destructive. It will only change the vector size if there are no existing embeddings in the database. If there are existing embeddings, it will provide instructions for a more complex migration strategy.

## Example Script

See the `examples/embedding_example.py` script for a complete example of how to use the embeddings module.

## API Reference

### EmbeddingManager

- `__init__(model_name="snowflake-arctic-embed2:latest")`: Initialize the embedding manager
- `create_embedding(text)`: Create an embedding for the given text
- `chunk_text(text, chunk_size=1000, overlap=200)`: Split text into chunks for embedding
- `extract_keywords(text, max_keywords=10)`: Extract keywords from text
- `process_document(source_id, document_id, text, page_info=None, chunk_size=1000, overlap=200)`: Process a document by chunking, embedding, and storing in the database
- `search(query, limit=10, threshold=0.7, source_id=None)`: Search for similar documents using semantic search
- `delete_document(source_id, document_id)`: Delete all embeddings for a specific document
- `close()`: Close the database connection

### EmbeddingDatabaseManager

- `__init__()`: Initialize the embedding database manager
- `create_tables()`: Create embedding-related tables if they don't exist
- `create_indices()`: Create indices for the embeddings table
- `store_embedding(source_id, document_id, chunk_no, text, embedding, model_name, page_no=None, keywords=None)`: Store an embedding in the database
- `store_embeddings_batch(embeddings)`: Store multiple embeddings in the database
- `search_similar(query_embedding, limit=10, threshold=0.7, source_id=None)`: Search for similar documents using vector similarity
- `get_document_embeddings(source_id, document_id)`: Get all embeddings for a specific document
- `delete_document_embeddings(source_id, document_id)`: Delete all embeddings for a specific document
- `close()`: Close the database connection
