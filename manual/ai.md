# AI Module

## Overview

The AI Module provides artificial intelligence capabilities to the Local Knowledge system. It leverages local models through Ollama to provide embeddings, question-answer generation, and other AI-powered features without requiring external API calls.

## Core Components

### Embeddings

The embeddings functionality is implemented in `localknowledge.ai.embeddings`:

- Vector embeddings for text using Ollama models
- Semantic similarity search
- Integration with the database for storing and retrieving embeddings

### QA Finder

The QA finder functionality is implemented in `localknowledge.ai.qafinder`:

- Question generation from text
- Question-answer pair generation from text
- Embeddings for question-answer pairs
- Semantic search for question-answer pairs

### Rerankers

The rerankers functionality is implemented in `localknowledge.ai.rerankers`:

- Reranking of search results using cross-encoder models
- Support for multiple reranker models
- Integration with search functionality

### HyDE (Hypothetical Document Embeddings)

The HyDE functionality is implemented in `localknowledge.ai.HyDE`:

- Improved semantic search using hypothetical document generation
- Generation of hypothetical abstracts that answer queries
- Creation of embeddings from hypothetical abstracts
- Benchmarking tools for comparing different models

## Models

The AI module uses several models through Ollama:

| Model | Purpose | Default |
|-------|---------|---------|
| snowflake-arctic-embed2:latest | Text embeddings | Yes |
| gemma3:4b | Question-answer generation, HyDE | Yes |
| llama3.2:3b-instruct-q8_0 | Alternative for HyDE | No |
| qwen2.5:3b-instruct-q8_0 | Alternative for HyDE | No |
| BAAI/bge-reranker-base | Search result reranking | No |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | Search result reranking | No |

Models can be configured through environment variables or application settings.

## Usage Examples

### Creating Embeddings

```python
from localknowledge.ai.embeddings import create_embedding

# Create an embedding for a text
text = "This is a sample text for embedding."
embedding = create_embedding(text)

# Print the embedding dimension
print(f"Embedding dimension: {len(embedding)}")
```

### Generating Questions and Answers

```python
from localknowledge.ai.qafinder import find_questions_and_answers

# Generate question-answer pairs from text
text = """
Background: Traumatic brain injury (TBI) is a leading cause of death and disability worldwide.
Methods: We conducted a retrospective study of 1,000 TBI patients.
Results: We found that early intervention improved outcomes.
Conclusion: Early intervention is critical for TBI patients.
"""

qa_pairs = find_questions_and_answers(text)

# Print the question-answer pairs
for qa in qa_pairs:
    print(f"Q: {qa['question']}")
    print(f"A: {qa['answer']}")
    print()
```

### Using the QA Embedding Manager

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

# Search for similar QA pairs
results = manager.search(
    query='What is the effect of treatment X on condition Y?',
    limit=10,
    threshold=0.7
)

# Close the manager when done
manager.close()
```

### Using Rerankers

```python
from localknowledge.ai.rerankers import Reranker

# Create a reranker
reranker = Reranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")

# Rerank search results
query = "What is the effect of treatment X on condition Y?"
documents = [
    {"id": 1, "text": "Treatment X has significant effects on condition Y."},
    {"id": 2, "text": "Condition Y is often treated with medication Z."},
    {"id": 3, "text": "Treatment X is a novel approach to managing condition Y."}
]

# Rerank the documents
reranked_documents = reranker.rerank(query, documents)

# Print the reranked documents
for doc in reranked_documents:
    print(f"Score: {doc['score']}, Text: {doc['text']}")
```

### Using HyDE for Semantic Search

```python
from localknowledge.ai.HyDE import generate_hypothetical_abstract, generate_hyde_embedding
from localknowledge.embeddings.database import EmbeddingDatabaseManager

# Initialize the embedding database manager
embedding_db = EmbeddingDatabaseManager()

# 1. Direct semantic search with a query
query = "What is the cut-off for ultrasound optic nerve sheath diameter for diagnosing raised intracranial pressure?"

# Get embedding for the query directly
from localknowledge.ai.embeddings import create_embedding
direct_embedding = create_embedding(query)

# Search for similar documents
direct_results = embedding_db.search_similar(
    query_embedding=direct_embedding,
    limit=5,
    threshold=0.5
)

print(f"Direct search found {len(direct_results)} results")

# 2. HyDE semantic search
# Generate a hypothetical abstract that answers the query
hypothetical_abstract = generate_hypothetical_abstract(
    question=query,
    model="gemma3:4b"  # You can also try other models
)

print(f"Generated abstract:\n{hypothetical_abstract[:300]}...")

# Get embedding for the hypothetical abstract
hyde_embedding = generate_hyde_embedding(
    question=query,
    generation_model="gemma3:4b",
    embedding_model="snowflake-arctic-embed2:latest"
)

# Search for similar documents using the HyDE embedding
hyde_results = embedding_db.search_similar(
    query_embedding=hyde_embedding,
    limit=5,
    threshold=0.5
)

print(f"HyDE search found {len(hyde_results)} results")

# Compare the results
for i, result in enumerate(hyde_results[:3]):
    print(f"{i+1}. {result.get('text', '')[:100]}... (similarity: {result.get('similarity', 0):.4f})")

# Close the database connection when done
embedding_db.close()
```

## Configuration

### Model Configuration

Models can be configured in several ways:

1. **Default Constants**: Default models are defined as constants in each module:
   ```python
   DEFAULT_EMBEDDING_MODEL = "snowflake-arctic-embed2:latest"
   DEFAULT_QA_MODEL = "gemma3:4b"
   ```

2. **Environment Variables**: Environment variables can override defaults:
   ```bash
   export LK_EMBEDDING_MODEL="nomic-embed-text:latest"
   export LK_QA_MODEL="llama3:8b"
   ```

3. **Runtime Configuration**: Models can be specified at runtime:
   ```python
   manager = QAEmbeddingManager(
       model_name="llama3:8b",
       embedding_model="nomic-embed-text:latest"
   )
   ```

### Ollama Configuration

The AI module requires Ollama to be running and accessible. Ollama configuration:

- Default URL: `http://localhost:11434`
- Can be configured with the `OLLAMA_HOST` environment variable

## Performance Considerations

### Model Loading

Ollama loads models on demand, which can cause delays on first use. To pre-load models:

```bash
ollama pull snowflake-arctic-embed2:latest
ollama pull gemma3:4b
```

### Batch Processing

For processing multiple texts:

- Use batch methods where available
- Process in parallel using multiple threads or processes
- Use progress bars (tqdm) for monitoring

### Memory Usage

Large models require significant memory. To manage memory usage:

- Process texts in batches
- Use smaller models for less complex tasks
- Monitor system memory usage

## Error Handling

The AI module includes robust error handling:

- Retries with exponential backoff for transient errors
- Graceful handling of model unavailability
- Detailed logging for debugging

Example with explicit error handling:

```python
import logging
from localknowledge.ai.embeddings import create_embedding

logging.basicConfig(level=logging.INFO)

try:
    embedding = create_embedding("Sample text")
    print(f"Embedding created with dimension {len(embedding)}")
except Exception as e:
    logging.error(f"Error creating embedding: {e}")
    # Fallback behavior
```

## Maintenance

### Adding New Models

To add support for a new model:

1. Pull the model in Ollama:
   ```bash
   ollama pull new-model:tag
   ```

2. Update the default constants or use the model explicitly:
   ```python
   manager = QAEmbeddingManager(model_name="new-model:tag")
   ```

### Updating Models

To update existing models:

1. Pull the latest version:
   ```bash
   ollama pull snowflake-arctic-embed2:latest
   ```

2. Restart any running applications to use the updated model

### Monitoring

Monitor AI performance using:

- Logging at appropriate levels
- Performance metrics (time per operation)
- Memory usage tracking

## Troubleshooting

### Common Issues

1. **Model Not Found**: Ensure the model is pulled in Ollama:
   ```bash
   ollama list
   ollama pull missing-model:tag
   ```

2. **Slow Performance**: Check system resources and consider:
   - Using a smaller model
   - Reducing batch size
   - Adding more memory or GPU resources

3. **Inconsistent Results**: Models can produce different outputs for the same input. Consider:
   - Setting a random seed for reproducibility
   - Using a specific model version instead of 'latest'
   - Implementing post-processing to standardize outputs

4. **HyDE Not Finding Relevant Results**: If HyDE isn't finding relevant documents:
   - Try different generation models (gemma3:4b, llama3.2:3b-instruct-q8_0, etc.)
   - Adjust the similarity threshold (try lower values like 0.3-0.4)
   - Ensure the hypothetical abstract is relevant to the query
   - Compare with direct semantic search to see the difference

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Check Ollama logs:
   ```bash
   journalctl -u ollama -f
   ```

3. Test models directly with the Ollama CLI:
   ```bash
   ollama run gemma3:4b "Generate a question and answer about traumatic brain injury."
   ```
