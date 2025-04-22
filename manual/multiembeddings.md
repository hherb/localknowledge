# Multi-Embeddings Module

## Overview

The Multi-Embeddings Module provides functionality for creating, storing, and searching vector embeddings using multiple embedding models. This allows for comparing different models' performance and using the most appropriate model for different types of content.

## Core Components

### EmbeddingTableManager

The `EmbeddingTableManager` class in `localknowledge.db.multiembeddings` handles database operations for multiple embedding models:

- Creating and managing model-specific embedding tables
- Dynamically determining vector dimensions by creating test embeddings
- Storing embeddings in the appropriate tables
- Performing similarity searches across different models
- Gathering statistics on model performance

### EmbeddingManager

The `EmbeddingManager` class in `localknowledge.embeddings.multiembeddings` provides the main interface for working with multiple embedding models:

- Creating embeddings using different models
- Storing embeddings in model-specific tables
- Searching for similar embeddings using different models
- Comparing search results across models
- Managing embedding models

## Database Schema

The module creates separate tables for each embedding model, with names derived from the model name:

```
emb_snowflake_arctic_embed2
emb_nomic_embed_text
emb_jina_embeddings_v2_base_en
...
```

Each table has the following schema:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| source_id | TEXT | Source identifier (e.g., 'medrxiv', 'pubmed') |
| document_id | TEXT | Document identifier (e.g., DOI, PMID) |
| chunk_no | INTEGER | Chunk number within the document |
| page_no | INTEGER | Page number (optional) |
| text | TEXT | Text that was embedded |
| keywords | TEXT[] | Array of keywords (optional) |
| embedding | vector(N) | Vector embedding with dimension N specific to the model |
| created_at | TIMESTAMP | Record creation timestamp |

Each table has a unique constraint on (source_id, document_id, chunk_no) to prevent duplicates.

## Usage Examples

### Creating and Storing Embeddings

```python
from localknowledge.embeddings.multiembeddings import EmbeddingManager

# Create an embedding manager with a specific model
manager = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Create and store an embedding
result_id = manager.process_text(
    source_id='medrxiv',
    document_id='10.1101/2023.01.01.12345',
    text='This is a sample text for embedding.',
    chunk_no=0
)

print(f"Stored embedding with ID: {result_id}")

# Close the manager
manager.close()
```

### Searching for Similar Embeddings

```python
from localknowledge.embeddings.multiembeddings import EmbeddingManager

# Create an embedding manager
manager = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Search for similar embeddings
results = manager.search(
    query='This is a search query.',
    limit=10,
    threshold=0.7,
    source_id='medrxiv'  # Optional: filter by source
)

# Process results
for result in results:
    print(f"Document: {result['document_id']}")
    print(f"Similarity: {result['similarity']:.4f}")
    print(f"Text: {result['text'][:100]}...")
    print()

# Close the manager
manager.close()
```

### Comparing Multiple Models

```python
from localknowledge.embeddings.multiembeddings import EmbeddingManager

# Create an embedding manager
manager = EmbeddingManager()

# Compare search results across different models
comparison = manager.compare_models(
    query='This is a search query.',
    models=[
        "snowflake-arctic-embed2:latest",
        "nomic-embed-text:latest",
        "jina-embeddings-v2-base-en:latest"
    ],
    limit=5,
    threshold=0.7
)

# Process comparison results
for model_name, model_data in comparison.items():
    print(f"Model: {model_name}")
    print(f"Results: {model_data['result_count']}")
    print(f"Vector dimension: {model_data['stats']['vector_dim']}")

    # Print top result for each model
    if model_data['results']:
        top_result = model_data['results'][0]
        print(f"Top similarity: {top_result['similarity']:.4f}")
        print(f"Top document: {top_result['document_id']}")
    print()

# Close the manager
manager.close()
```

## Supported Models

The Multi-Embeddings module supports various Ollama embedding models:

| Model | Dimension | Description |
|-------|-----------|-------------|
| snowflake-arctic-embed2 | 1024 | Snowflake's Arctic embedding model |
| nomic-embed-text | 768 | Nomic AI's embedding model |
| jina-embeddings-v2-base-en | 768 | Jina AI's embedding model |
| bge-m3 | 1024 | BGE M3 embedding model |
| granite-embedding | 768 | Granite embedding model |
| mxbai-embed-large | 1024 | MxBai large embedding model |

## Configuration

### Model Selection

You can specify which model to use when creating an `EmbeddingManager`:

```python
# Use a specific model
manager = EmbeddingManager(model_name="nomic-embed-text:latest")
```

### Database Configuration

Database connection parameters are configured through environment variables:

- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_HOST`: Database host
- `POSTGRES_PORT`: Database port

## Performance Considerations

### Dynamic Dimension Detection

The system automatically detects the vector dimension for each model by creating a test embedding and measuring its length. This approach:

- Ensures correct table creation for any embedding model
- Eliminates the need for manual configuration
- Handles new models automatically
- Uses LRU caching to avoid repeated API calls

If the dynamic detection fails, the system falls back to a lookup table of known model dimensions.

### Table Management

Each model gets its own table with the appropriate vector dimension. This approach:

- Avoids dimension conflicts between models
- Allows for efficient storage and retrieval
- Enables performance comparison between models
- Supports models with different vector dimensions

### Statistics Tracking

The module provides statistics for each model:

- Total number of embeddings
- Number of unique sources
- Number of unique documents
- Table size
- Vector dimension

These statistics can help evaluate model performance and storage requirements.

## Troubleshooting

### Common Issues

1. **Model Not Found**: If Ollama doesn't have the requested model, the system will log a warning but continue to operate. You can check available models with:

   ```python
   manager = EmbeddingManager()
   available_models = manager.get_available_models()
   print(available_models)
   ```

2. **Dimension Mismatch**: If you see errors about vector dimensions, ensure the model is correctly identified in the `get_model_dimension` method.

3. **Performance Issues**: If embedding generation is slow, consider:
   - Using a smaller model
   - Processing in batches
   - Using a GPU with Ollama

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.embeddings').setLevel(logging.DEBUG)
   ```

2. Check model statistics:
   ```python
   manager = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")
   stats = manager.db.get_model_stats("snowflake-arctic-embed2:latest")
   print(stats)
   ```
