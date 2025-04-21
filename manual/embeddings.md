# Embeddings Module

## Overview

The Embeddings Module provides functionality for creating, storing, and searching vector embeddings in the Local Knowledge system. These embeddings enable semantic search and other AI-powered features.

## Core Components

### Embedding Manager

The `EmbeddingManager` class in `localknowledge.embeddings` provides the main interface for working with embeddings:

- Creating embeddings from text
- Storing embeddings in the database
- Searching for similar embeddings
- Managing embedding models

### Database Manager

The `EmbeddingDatabaseManager` class in `localknowledge.embeddings.database` handles database operations for embeddings:

- Creating and managing the embeddings table
- Storing and retrieving embeddings
- Performing similarity searches
- Managing indices for efficient search

## Database Schema

The `embeddings` table stores vector embeddings:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| source_id | TEXT | Source identifier (e.g., 'medrxiv', 'pubmed') |
| document_id | TEXT | Document identifier (e.g., DOI, PMID) |
| chunk_no | INTEGER | Chunk number within the document |
| page_no | INTEGER | Page number (optional) |
| text | TEXT | Text that was embedded |
| embedding | vector(1024) | Vector embedding |
| model_name | TEXT | Name of the model used to create the embedding |
| created_at | TIMESTAMP | Record creation timestamp |

The table has a unique constraint on (source_id, document_id, chunk_no) to prevent duplicates.

## Usage Examples

### Creating and Storing Embeddings

```python
from localknowledge.embeddings import EmbeddingManager

# Create an embedding manager
manager = EmbeddingManager()

# Create and store an embedding
result = manager.process_text(
    source_id='medrxiv',
    document_id='10.1101/2023.01.01.12345',
    text='This is a sample text for embedding.',
    chunk_no=0
)

print(f"Stored embedding with ID: {result}")

# Close the manager
manager.close()
```

### Searching for Similar Embeddings

```python
from localknowledge.embeddings import EmbeddingManager

# Create an embedding manager
manager = EmbeddingManager()

# Search for similar embeddings
results = manager.search(
    query='This is a search query.',
    limit=10,
    threshold=0.7,
    source_id='medrxiv'  # Optional: filter by source
)

# Print search results
for result in results:
    print(f"Document: {result['document_id']}")
    print(f"Similarity: {result['similarity']:.2f}")
    print(f"Text: {result['text'][:100]}...")
    print()

# Close the manager
manager.close()
```

### Batch Processing

```python
from localknowledge.embeddings import EmbeddingManager
from localknowledge.textprocessing.chunking import fixed_size_chunker

# Create an embedding manager
manager = EmbeddingManager()

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Split into chunks
chunks = fixed_size_chunker(text, chunk_size=1000, overlap=100)

# Process each chunk
for i, chunk in enumerate(chunks):
    result = manager.process_text(
        source_id='document',
        document_id='doc-123',
        text=chunk,
        chunk_no=i
    )
    print(f"Processed chunk {i+1}/{len(chunks)}")

# Close the manager
manager.close()
```

## Command-Line Tools

The module provides command-line tools for working with embeddings:

### Embed MedRxiv Abstracts

```bash
# Create embeddings for MedRxiv abstracts
python -m localknowledge.medrxiv.embed_abstracts

# Specify a limit
python -m localknowledge.medrxiv.embed_abstracts --limit 1000

# Specify a model
python -m localknowledge.medrxiv.embed_abstracts --model "nomic-embed-text:latest"
```

### Embed PubMed Abstracts

```bash
# Create embeddings for PubMed abstracts
python -m localknowledge.pubmed.embed_abstracts

# Specify a limit
python -m localknowledge.pubmed.embed_abstracts --limit 1000

# Specify a model
python -m localknowledge.pubmed.embed_abstracts --model "nomic-embed-text:latest"
```

## Models

The Embeddings module uses Ollama models for creating embeddings:

| Model | Dimension | Default |
|-------|-----------|---------|
| snowflake-arctic-embed2:latest | 1024 | Yes |
| nomic-embed-text:latest | 768 | No |

Models can be configured through environment variables or application settings.

## Configuration

### Model Configuration

Embedding models can be configured:

```python
from localknowledge.embeddings import EmbeddingManager

# Use a specific model
manager = EmbeddingManager(model_name="nomic-embed-text:latest")

# Or set an environment variable
# export LK_EMBEDDING_MODEL="nomic-embed-text:latest"
```

### Database Configuration

Database connection parameters are configured in `localknowledge.db.config`:

```python
# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'localknowledge',
    'user': 'postgres',
    'password': 'password'
}
```

Environment variables can override these settings:

- `LK_DB_HOST`: Database host
- `LK_DB_PORT`: Database port
- `LK_DB_NAME`: Database name
- `LK_DB_USER`: Database user
- `LK_DB_PASSWORD`: Database password

## Performance Considerations

### Embedding Generation

Creating embeddings can be resource-intensive. To optimize:

- Process in batches to amortize model loading time
- Use a GPU if available for faster processing
- Implement caching to avoid re-embedding the same text

### Similarity Search

For optimal similarity search performance:

- Use appropriate indices (IVFFlat for large collections)
- Adjust the threshold parameter to balance precision and recall
- Limit the number of results to improve response time

### Database Optimization

For optimal database performance:

- Use transactions for batch operations
- Create appropriate indices for frequently queried columns
- Regularly vacuum and analyze the table

## Maintenance

### Updating Models

To update embedding models:

1. Pull the latest model in Ollama:
   ```bash
   ollama pull snowflake-arctic-embed2:latest
   ```

2. Update the default model in the code or environment variables

### Reindexing

To optimize search performance after adding many embeddings:

```sql
REINDEX INDEX idx_embeddings_vector;
```

### Monitoring

Monitor embedding performance using:

- Logging at appropriate levels
- Performance metrics (time per operation)
- Database query statistics

## Troubleshooting

### Common Issues

1. **Dimension Mismatch**: If you see errors about vector dimensions, ensure the embedding model produces vectors of the expected dimension (1024).

2. **Performance Issues**: If embedding generation is slow, consider:
   - Using a smaller model
   - Processing in batches
   - Using a GPU

3. **Search Quality Issues**: If search results are poor, consider:
   - Adjusting the similarity threshold
   - Using a different embedding model
   - Implementing reranking

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.embeddings').setLevel(logging.DEBUG)
   ```

2. Test embedding generation directly:
   ```python
   from localknowledge.embeddings import create_embedding
   
   embedding = create_embedding("Test text")
   print(f"Embedding dimension: {len(embedding)}")
   ```

3. Check database queries:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM embeddings 
   WHERE 1 - (embedding <=> '[0.1,0.2,...]'::vector) > 0.7 
   ORDER BY 1 - (embedding <=> '[0.1,0.2,...]'::vector) DESC 
   LIMIT 10;
   ```

## Advanced Usage

### Hybrid Search

Combine keyword and semantic search for better results:

```python
from localknowledge.embeddings import EmbeddingManager
from localknowledge.db.base import DatabaseManager

# Create managers
embedding_manager = EmbeddingManager()
db_manager = DatabaseManager()

# Perform keyword search
keyword_query = "traumatic brain injury treatment"
keyword_results = db_manager.execute("""
    SELECT document_id, ts_rank(to_tsvector('english', text), to_tsquery('english', %s)) AS rank
    FROM embeddings
    WHERE to_tsvector('english', text) @@ to_tsquery('english', %s)
    ORDER BY rank DESC
    LIMIT 20
""", (keyword_query.replace(' ', ' & '), keyword_query.replace(' ', ' & ')))

# Perform semantic search
semantic_results = embedding_manager.search(
    query=keyword_query,
    limit=20,
    threshold=0.6
)

# Combine results (simple approach)
combined_results = {}
for result in keyword_results:
    combined_results[result['document_id']] = {
        'document_id': result['document_id'],
        'keyword_rank': result['rank'],
        'semantic_rank': 0
    }

for result in semantic_results:
    if result['document_id'] in combined_results:
        combined_results[result['document_id']]['semantic_rank'] = result['similarity']
    else:
        combined_results[result['document_id']] = {
            'document_id': result['document_id'],
            'keyword_rank': 0,
            'semantic_rank': result['similarity']
        }

# Sort by combined score
final_results = sorted(
    combined_results.values(),
    key=lambda x: (x['keyword_rank'] * 0.4 + x['semantic_rank'] * 0.6),
    reverse=True
)

# Print results
for result in final_results[:10]:
    print(f"Document: {result['document_id']}")
    print(f"Keyword Rank: {result['keyword_rank']:.2f}")
    print(f"Semantic Rank: {result['semantic_rank']:.2f}")
    print(f"Combined Score: {result['keyword_rank'] * 0.4 + result['semantic_rank'] * 0.6:.2f}")
    print()

# Close managers
embedding_manager.close()
db_manager.close()
```

### Custom Embedding Models

Use a custom embedding model:

```python
import ollama
from localknowledge.embeddings import EmbeddingManager

# Define a custom embedding function
def custom_embedding_function(text):
    response = ollama.embeddings(model="custom-model:latest", prompt=text)
    return response['embedding']

# Create an embedding manager with the custom function
manager = EmbeddingManager(embedding_function=custom_embedding_function)

# Use the manager as usual
results = manager.search("Query text")

# Close the manager
manager.close()
```
