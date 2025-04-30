# Embeddings Module

## Overview

The Embeddings Module provides functionality for creating, storing, and searching vector embeddings in the Local Knowledge system. These embeddings enable semantic search and other AI-powered features.

## Core Components

### Embedders

The system supports multiple embedder types:

- `OllamaEmbedder`: Uses Ollama models for creating embeddings
- `PubMedBERTEmbedder`: Uses the PubMedBERT model for biomedical text embeddings

Each embedder implements the `BaseEmbedder` interface, providing consistent methods for embedding text.

### Database Manager

The `EmbeddingsDatabaseManager` class in `localknowledge.db.embeddings` handles database operations for embeddings:

- Creating and managing embedding tables based on vector size
- Storing and retrieving embeddings
- Performing similarity searches
- Managing indices for efficient search

## Database Schema

The system uses a flexible table structure for storing embeddings:

1. A base table `embedding_base` with common fields:
   ```sql
   CREATE TABLE embedding_base (
       id SERIAL PRIMARY KEY,
       chunk_id INTEGER NOT NULL REFERENCES chunks(id),
       model_id INTEGER REFERENCES embedding_models(id)
   );
   ```

2. Model-specific tables that inherit from the base table and add a vector field with the appropriate dimension:
   ```sql
   CREATE TABLE emb_1024 (
       embedding vector(1024)
   ) INHERITS (embedding_base);

   CREATE TABLE emb_768 (
       embedding vector(768)
   ) INHERITS (embedding_base);
   ```

This structure allows efficient storage and retrieval of embeddings with different dimensions.

### Related Tables

- `embedding_models`: Stores information about embedding models
- `embedding_provider`: Stores information about embedding providers (e.g., Ollama, Hugging Face)
- `chunks`: Stores text chunks that are embedded
- `chunktypes`: Defines different types of chunks (e.g., abstract, fulltext)

## Usage Examples

### Creating and Storing Embeddings

```python
from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.embeddings import OllamaEmbedder

# Create an embedder
embedder = OllamaEmbedder(model_name="snowflake-arctic-embed2:latest")

# Get the embeddings database manager
embeddings_db = get_embeddings_db()

# Create an embedding
text = "This is a sample text for embedding."
embedding = embedder.embed(text)

# Get the model ID
model_id = embeddings_db.get_model_id("snowflake-arctic-embed2:latest")

# Store the embedding
embedding_id = embeddings_db.add_embedding(
    chunk_id=123,  # ID of the chunk in the chunks table
    model_id=model_id,
    embedding=embedding
)

print(f"Stored embedding with ID: {embedding_id}")
```

### Searching for Similar Embeddings

```python
from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.embeddings import OllamaEmbedder

# Create an embedder
embedder = OllamaEmbedder(model_name="snowflake-arctic-embed2:latest")

# Get the embeddings database manager
embeddings_db = get_embeddings_db()

# Create an embedding for the query
query = "This is a search query."
query_embedding = embedder.embed(query)

# Search for similar embeddings
results = embeddings_db.search_similar(
    embedding=query_embedding,
    embed_source="abstract",  # Source type (e.g., abstract, fulltext)
    model_name="snowflake-arctic-embed2:latest",
    limit=10,
    threshold=0.7
)

# Print search results
for result in results:
    print(f"Document: {result['document_id']}")
    print(f"Similarity: {result['similarity']:.2f}")
    print(f"Text: {result['text'][:100]}...")
    print()
```

### Batch Processing with AbstractEmbeddingUpdater

The `AbstractEmbeddingUpdater` class provides a convenient way to update embeddings for chunks without embeddings:

```python
from update_embeddings_for_abstracts import AbstractEmbeddingUpdater
from localknowledge.embeddings import OllamaEmbedder

# Create an updater with the default Ollama embedder
updater = AbstractEmbeddingUpdater(
    embedder=OllamaEmbedder,
    model_name="snowflake-arctic-embed2:latest"
)

# Count chunks without embeddings
count = updater.count_chunks_without_embeddings()
print(f"Found {count} chunks without embeddings")

# Update embeddings for chunks without embeddings
processed = updater.update_abstract_embeddings(
    limit=1000,  # Maximum number of chunks to process
    batch_size=20,  # Number of chunks to process in each batch
    workers=4  # Number of worker threads
)

print(f"Successfully processed {processed} chunks")
```

## Command-Line Tools

The module provides command-line tools for working with embeddings:

### Update Embeddings for Abstracts

```bash
# Create embeddings for abstracts using the default Ollama embedder
python update_embeddings_for_abstracts.py

# Specify a limit
python update_embeddings_for_abstracts.py --limit 1000

# Specify a batch size
python update_embeddings_for_abstracts.py --batch-size 50

# Specify number of worker threads
python update_embeddings_for_abstracts.py --workers 8

# Use the PubMedBERT embedder
python update_embeddings_for_abstracts.py --embedder pubmedbert

# Specify a model
python update_embeddings_for_abstracts.py --model "nomic-embed-text:latest"

# Perform a dry run without modifying the database
python update_embeddings_for_abstracts.py --dry-run

# Show detailed information
python update_embeddings_for_abstracts.py --verbose
```

## Supported Embedders and Models

### Ollama Embedder

The `OllamaEmbedder` class supports various models:

| Model | Dimension | Default |
|-------|-----------|---------|
| snowflake-arctic-embed2:latest | 1024 | Yes |
| nomic-embed-text | 768 | No |
| jina/jina-embeddings-v2-base-en | 768 | No |
| bge-m3 | 1024 | No |
| granite-embedding:278m | 768 | No |
| mxbai-embed-large | 1024 | No |

### PubMedBERT Embedder

The `PubMedBERTEmbedder` class uses the PubMedBERT model for biomedical text:

| Model | Dimension | Default |
|-------|-----------|---------|
| microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext | 768 | Yes |
| pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb | 768 | No |

## Configuration

### Model Configuration

Embedding models can be configured when creating an embedder:

```python
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder

# Use a specific Ollama model
ollama_embedder = OllamaEmbedder(model_name="nomic-embed-text")

# Use a specific PubMedBERT model
pubmed_embedder = PubMedBERTEmbedder(model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb")
```

### Database Configuration

Database connection parameters are configured in `.env` file or environment variables:

- `DB_HOST`: Database host
- `DB_PORT`: Database port
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password

## Performance Considerations

### Embedding Generation

Creating embeddings can be resource-intensive. To optimize:

- Process in batches to amortize model loading time
- Use a GPU if available for faster processing
- Use multiple worker threads for parallel processing
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
- Regularly vacuum and analyze the tables

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
REINDEX INDEX emb_1024_embedding_idx;
```

### Monitoring

Monitor embedding performance using:

- Logging at appropriate levels
- Performance metrics (time per operation)
- Database query statistics

## Troubleshooting

### Common Issues

1. **Dimension Mismatch**: If you see errors about vector dimensions, ensure the embedding model produces vectors of the expected dimension.

2. **Performance Issues**: If embedding generation is slow, consider:
   - Using a smaller model
   - Processing in batches
   - Using more worker threads
   - Using a GPU

3. **Search Quality Issues**: If search results are poor, consider:
   - Adjusting the similarity threshold
   - Using a different embedding model
   - Implementing reranking
   - Using HyDE (Hypothetical Document Embeddings) instead of direct query embedding

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.db.embeddings').setLevel(logging.DEBUG)
   ```

2. Test embedding generation directly:
   ```python
   from localknowledge.embeddings import OllamaEmbedder

   embedder = OllamaEmbedder()
   embedding = embedder.embed("Test text")
   print(f"Embedding dimension: {len(embedding)}")
   ```

3. Check database queries:
   ```sql
   EXPLAIN ANALYZE SELECT e.*, 1 - (e.embedding <=> '[0.1,0.2,...]'::vector) as similarity
   FROM emb_1024 e
   WHERE 1 - (e.embedding <=> '[0.1,0.2,...]'::vector) > 0.7
   ORDER BY similarity DESC
   LIMIT 10;
   ```

## Advanced Usage

### Implementing Custom Embedders

You can create custom embedders by implementing the `BaseEmbedder` interface:

```python
from localknowledge.embeddings.base_embedder import BaseEmbedder

class CustomEmbedder(BaseEmbedder):
    """Custom embedder implementation."""

    def __init__(self, model_name: str = "custom-model"):
        """Initialize the custom embedder."""
        super().__init__(model_name)
        # Initialize your model here

    def list_available_models(self) -> list[str]:
        """List available models."""
        return ["custom-model"]

    def get_vectorsize(self):
        """Get the size of the embedding vectors."""
        return 768  # Replace with your model's vector size

    def embed(self, text: str) -> list[float]:
        """Create an embedding for the given text."""
        # Implement your embedding logic here
        # Return a list of floats representing the embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts at once."""
        # Implement your batch embedding logic here
        # Return a list of embeddings (each a list of floats)
```

### Working with Different Vector Sizes

The system automatically creates and manages tables for different vector sizes:

```python
from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder

# Get the embeddings database manager
embeddings_db = get_embeddings_db()

# Create embedders with different vector sizes
ollama_embedder = OllamaEmbedder(model_name="snowflake-arctic-embed2:latest")  # 1024 dimensions
pubmed_embedder = PubMedBERTEmbedder()  # 768 dimensions

# Ensure tables exist for both vector sizes
embeddings_db.ensure_table_for_vectorsize(ollama_embedder.get_vectorsize())  # Creates emb_1024 if needed
embeddings_db.ensure_table_for_vectorsize(pubmed_embedder.get_vectorsize())  # Creates emb_768 if needed

# Create embeddings with different models
text = "This is a sample text for embedding."
ollama_embedding = ollama_embedder.embed(text)
pubmed_embedding = pubmed_embedder.embed(text)

# Store embeddings in the appropriate tables
ollama_model_id = embeddings_db.get_model_id("snowflake-arctic-embed2:latest")
pubmed_model_id = embeddings_db.get_model_id("microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext")

embeddings_db.add_embedding(chunk_id=123, model_id=ollama_model_id, embedding=ollama_embedding)
embeddings_db.add_embedding(chunk_id=123, model_id=pubmed_model_id, embedding=pubmed_embedding)
```

### Finding and Deleting Zero Vectors

The system provides methods for finding and deleting zero vectors (which can occur due to errors):

```python
from localknowledge.db.embeddings import get_embeddings_db

# Get the embeddings database manager
embeddings_db = get_embeddings_db()

# Find zero vectors
zero_vectors = embeddings_db.find_zero_vectors()
print(f"Found {len(zero_vectors)} zero vectors")

# Delete zero vectors
deleted = embeddings_db.delete_zero_vectors()
print(f"Deleted {deleted} zero vectors")
```

### Getting Embedding Statistics

The system provides methods for getting statistics about embeddings:

```python
from localknowledge.db.embeddings import get_embeddings_db

# Get the embeddings database manager
embeddings_db = get_embeddings_db()

# Get embedding statistics
stats = embeddings_db.get_embedding_stats()
print(f"Total embeddings: {stats['total_embeddings']}")
print(f"Documents with embeddings: {stats['documents_with_embeddings']}")
print(f"Zero vectors: {stats['zero_vectors']}")

# Print embeddings by source
for source in stats['embeddings_by_source']:
    print(f"Source: {source['name']}, Count: {source['count']}")

# Print embeddings by model
for model in stats['embeddings_by_model']:
    print(f"Model: {model['model_name']}, Count: {model['count']}")

# Print embeddings by table
for table in stats['embeddings_by_table']:
    print(f"Table: {table['table_name']}, Count: {table['count']}")
```
