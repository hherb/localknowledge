# QA Embeddings Module

## Overview

The QA Embeddings module provides functionality to generate question-answer pairs from abstracts and store them with vector embeddings in the database. This enables semantic search capabilities for question-answering over the document collection.

The module consists of several components:
- Database management for QA embeddings
- AI functionality for generating QA pairs and embeddings
- Command-line tools for updating QA embeddings

## Database Structure

The `qaembeddings` table stores question-answer pairs and their embeddings with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| source_id | TEXT | Source identifier (e.g., 'medrxiv', 'pubmed') |
| document_id | TEXT | Document identifier (e.g., DOI, PMID) |
| chunk_no | INTEGER | Chunk number within the document |
| page_no | INTEGER | Page number (optional) |
| qa_pairs | TEXT | JSON string containing question-answer pairs |
| embedding | vector(1024) | Vector embedding of the text |
| model_name | TEXT | Name of the model used to create the embedding |
| created_at | TIMESTAMP | Timestamp when the record was created |

The table has a unique constraint on (source_id, document_id, chunk_no) to prevent duplicates.

## Module Structure

### Database Module (`localknowledge.db.qafinder`)

The `QAEmbeddingDatabaseManager` class provides methods for:
- Creating and managing the `qaembeddings` table
- Storing QA embeddings individually or in batches
- Searching for similar QA pairs using vector similarity
- Retrieving and deleting QA embeddings for specific documents

### AI Module (`localknowledge.ai.qafinder`)

The `QAEmbeddingManager` class provides methods for:
- Generating QA pairs from text using Ollama models
- Creating embeddings for text
- Processing text to generate QA pairs, create embeddings, and store them in the database
- Searching for similar QA pairs using semantic search

The module also includes standalone functions:
- `find_questions`: Extracts important questions from text
- `find_questions_and_answers`: Extracts question-answer pairs from text
- `create_embedding`: Creates a vector embedding for text

### MedRxiv Module (`localknowledge.medrxiv.update_qaembeddings`)

The `MedrxivQAEmbedder` class provides methods for:
- Finding preprint records without QA embeddings
- Counting abstracts without QA embeddings
- Updating QA embeddings for abstracts in batches

## Command-Line Usage

The module provides a command-line interface for updating QA embeddings:

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

# Adjust batch size
python -m localknowledge.medrxiv.update_qaembeddings_cli --batch-size 20
```

## Programmatic Usage

### Generating QA Pairs and Embeddings

```python
from localknowledge.ai.qafinder import QAEmbeddingManager

# Create a QA embedding manager
manager = QAEmbeddingManager()

# Process text to generate QA pairs, create embeddings, and store in the database
result = manager.process_text(
    source_id='medrxiv',
    document_id='10.1101/2023.01.01.12345',
    text='Abstract text goes here...',
    chunk_no=0
)

# Close the manager when done
manager.close()
```

### Searching for Similar QA Pairs

```python
from localknowledge.ai.qafinder import QAEmbeddingManager

# Create a QA embedding manager
manager = QAEmbeddingManager()

# Search for similar QA pairs
results = manager.search(
    query='What is the effect of treatment X on condition Y?',
    limit=10,
    threshold=0.7,
    source_id='medrxiv'  # Optional: filter by source
)

# Process the results
for result in results:
    print(f"Document: {result['document_id']}")
    print(f"Similarity: {result['similarity']:.2f}")
    for qa_pair in result['qa_pairs']:
        print(f"Q: {qa_pair['question']}")
        print(f"A: {qa_pair['answer']}")
    print()

# Close the manager when done
manager.close()
```

### Updating QA Embeddings for MedRxiv Abstracts

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

# Close the client when done
client.close()
```

## Implementation Details

### QA Generation

The module uses Ollama models to generate question-answer pairs from text. The default model is "gemma3:4b", but this can be configured.

The QA generation process:
1. Sends the text to the model with a prompt requesting question-answer pairs
2. Parses the JSON response to extract the QA pairs
3. Handles various response formats and errors gracefully

### Embedding Generation

The module uses Ollama models to create vector embeddings for text. The default model is "snowflake-arctic-embed2:latest", but this can be configured.

The embedding generation process:
1. Sends the text to the model's embedding endpoint
2. Retrieves the 1024-dimensional vector embedding
3. Includes retry logic with exponential backoff for reliability

### Batch Processing

The module processes abstracts in batches to improve efficiency and provide progress feedback:
1. Retrieves a batch of abstracts without QA embeddings
2. Processes each abstract to generate QA pairs and embeddings
3. Stores the results in the database
4. Provides progress bars for monitoring

## Performance Considerations

- Embedding generation takes about 1 second per abstract
- QA generation takes about 3-5 seconds per abstract
- The module uses batch processing to improve throughput
- The database uses indices for efficient retrieval and searching

## Error Handling

The module includes comprehensive error handling:
- Retries for transient errors in embedding generation
- Graceful handling of various response formats from the QA model
- Transaction management to ensure database consistency
- Detailed logging for debugging

## Maintenance

### Adding Support for New Data Sources

To add support for a new data source:

1. Create a new module in the appropriate package (e.g., `localknowledge.pubmed.update_qaembeddings`)
2. Implement a class similar to `MedrxivQAEmbedder` that:
   - Connects to the data source
   - Retrieves documents without QA embeddings
   - Processes them using the `QAEmbeddingManager`
3. Create a command-line interface for the new module

### Updating Models

To update the models used for QA generation or embeddings:

1. Update the default model constants in `localknowledge.ai.qafinder`:
   - `DEFAULT_MODEL` for QA generation
   - `DEFAULT_EMBEDDING_MODEL` for embeddings
2. Ensure the new models are available in Ollama
3. Test the new models with a small batch of documents

### Database Maintenance

Regular maintenance tasks for the QA embeddings database:

1. **Reindexing**: Periodically reindex the vector index for optimal performance:
   ```sql
   REINDEX INDEX idx_qaembeddings_vector;
   ```

2. **Vacuuming**: Regularly vacuum the table to reclaim space and update statistics:
   ```sql
   VACUUM ANALYZE qaembeddings;
   ```

3. **Monitoring**: Monitor the size of the table and the performance of queries:
   ```sql
   SELECT pg_size_pretty(pg_total_relation_size('qaembeddings'));
   ```

## Troubleshooting

### Common Issues

1. **Embedding Dimension Mismatch**: If you see errors about vector dimensions, ensure the embedding model produces vectors of the expected dimension (1024).

2. **JSON Parsing Errors**: If you see errors about parsing JSON, check the model's responses and consider updating the parsing logic in `find_questions_and_answers`.

3. **Performance Issues**: If processing is slow, consider:
   - Increasing the batch size
   - Using a faster model for embeddings
   - Running multiple instances in parallel

### Debugging

For detailed debugging:

1. Set the logging level to DEBUG:
   ```python
   import logging
   logging.getLogger('localknowledge.ai.qafinder').setLevel(logging.DEBUG)
   logging.getLogger('localknowledge.db.qafinder').setLevel(logging.DEBUG)
   ```

2. Check the Ollama logs for model-related issues:
   ```bash
   journalctl -u ollama -f
   ```

3. Use the PostgreSQL query planner to analyze query performance:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM qaembeddings WHERE source_id = 'medrxiv' LIMIT 10;
   ```
