# AI Module

## Overview

The AI Module provides artificial intelligence capabilities to the Local Knowledge system. It leverages local models through Ollama to provide embeddings, question-answer generation, and other AI-powered features without requiring external API calls.

## Core Components

### Pydantic-AI Agent

The pydantic-ai agent functionality is implemented in `localknowledge.ai.agent`:

- **Intelligent AI agent** using Ollama LLMs via OpenAI-compatible API
- **Web search capabilities** for current information using DuckDuckGo
- **Local knowledge database integration** for searching academic papers
- **Structured responses** with sources and confidence scores using Pydantic models
- **Asynchronous and synchronous operation modes** for flexibility
- **Configurable tools** - enable/disable search capabilities as needed
- **Context support** for user-specific and project-specific queries

Key classes:
- `LocalKnowledgeAgent`: Main agent class with Ollama integration
- `AgentResponse`: Structured response model with answer, sources, and metadata
- `AgentContext`: Context and configuration for agent operations
- `ask_agent()` and `ask_agent_sync()`: Convenience functions for quick usage

### Web Search Tools

The web search functionality now uses the **official pydantic-ai DuckDuckGo search tool**:

- **Official pydantic-ai DuckDuckGo integration** (no API key required)
- **Built-in reliability and error handling** from the pydantic-ai framework
- **Seamless integration** with the agent system
- **Automatic result formatting** for consistent output

The agent automatically includes the DuckDuckGo search tool when `enable_web_search=True`.

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
| qwen3:8b | Question-answer generation, HyDE, Agent | Yes |
| llama3.2:3b-instruct-q8_0 | Alternative for HyDE | No |
| qwen2.5:3b-instruct-q8_0 | Alternative for HyDE | No |
| BAAI/bge-reranker-base | Search result reranking | No |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | Search result reranking | No |

Models can be configured through environment variables or application settings.

## Usage Examples

### Using the Pydantic-AI Agent

#### Basic Usage

```python
from localknowledge.ai.agent import LocalKnowledgeAgent, AgentContext
import asyncio

# Create an agent
agent = LocalKnowledgeAgent(
    model_name="qwen3:8b",
    enable_web_search=True,
    enable_local_search=True
)

# Ask a question asynchronously
async def ask_question():
    result = await agent.run("What is the latest research on COVID-19 vaccines?")
    print(f"Answer: {result.output.answer}")
    print(f"Sources: {len(result.output.sources)}")
    print(f"Confidence: {result.output.confidence}")

    # Close the agent when done
    agent.close()

# Run the async function
asyncio.run(ask_question())
```

#### Synchronous Usage

```python
from localknowledge.ai.agent import ask_agent_sync

# Quick synchronous usage
response = ask_agent_sync(
    "What are the side effects of mRNA vaccines?",
    model_name="qwen3:8b",
    enable_web_search=True
)

print(f"Answer: {response.answer}")
for source in response.sources:
    print(f"Source: {source.get('title', 'Unknown')} - {source.get('url', '')}")
```

#### Using Agent Context

```python
from localknowledge.ai.agent import LocalKnowledgeAgent, AgentContext

# Create agent with context
agent = LocalKnowledgeAgent()
context = AgentContext(
    user_id=123,
    project_id=456,
    max_search_results=10,
    enable_web_search=True,
    enable_local_search=True
)

# Ask with context
result = agent.run_sync("Find papers about machine learning in healthcare", context)
print(result.output.answer)
```

#### Convenience Function

```python
from localknowledge.ai.agent import ask_agent
import asyncio

async def quick_ask():
    response = await ask_agent(
        "What is the current status of Alzheimer's disease research?",
        enable_web_search=True,
        enable_local_search=True
    )
    return response

response = asyncio.run(quick_ask())
print(response.answer)
```

#### Extended Reasoning Support

The LocalKnowledge AI Agent supports extended reasoning modes for complex questions. This feature works with compatible models like `qwen3`, `qwq`, and `deepseek-r1` series.

**Extended Reasoning Control:**

Extended reasoning is controlled through the agent's configuration and can be toggled programmatically:

- **Constructor parameter**: `enable_extended_reasoning=False` (default for fast responses)
- **Toggle method**: `agent.extended_reasoning(True/False)` to change mode after creation
- **Automatic command appending**: The agent automatically appends `/no_think` or `/think` to messages sent to compatible models

**Examples:**

```python
from localknowledge.ai.agent import LocalKnowledgeAgent
import asyncio

async def extended_reasoning_examples():
    # Create agent with extended reasoning disabled (default)
    agent = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_extended_reasoning=False  # Fast mode (default)
    )

    # Fast response (agent appends "/no_think" to message)
    result1 = await agent.run("What is 2+2?")
    print(f"Fast answer: {result1.output.answer}")

    # Toggle to enable extended reasoning
    agent.extended_reasoning(True)

    # Extended reasoning response (agent appends "/think" to message)
    result2 = await agent.run("Analyze the economic implications of climate change")
    print(f"With extended reasoning: {result2.output.answer}")

    # Toggle back to fast mode
    agent.extended_reasoning(False)
    result3 = await agent.run("What is the capital of France?")
    print(f"Back to fast mode: {result3.output.answer}")

    agent.close()

asyncio.run(extended_reasoning_examples())
```

**Creating Agent with Extended Reasoning Enabled:**

```python
from localknowledge.ai.agent import LocalKnowledgeAgent

# Create agent with extended reasoning enabled from start
agent = LocalKnowledgeAgent(
    model_name="qwen3:8b",
    enable_extended_reasoning=True  # Enable extended reasoning
)

# All messages will have "/think" appended automatically
result = await agent.run("Explain quantum computing step by step")
print(result.output.answer)

agent.close()
```

**Convenience Functions with Extended Reasoning:**

```python
from localknowledge.ai.agent import ask_agent_sync, ask_agent_stream

# Synchronous with extended reasoning
response = ask_agent_sync(
    "Explain the relationship between photosynthesis and climate change",
    model_name="qwen3:8b",
    enable_extended_reasoning=True
)
print(response.answer)

# Streaming with extended reasoning
async def stream_with_extended_reasoning():
    async for event in ask_agent_stream(
        "Explain quantum computing step by step",
        model_name="qwen3:8b",
        enable_extended_reasoning=True
    ):
        if event.event_type == "text_delta":
            print(event.content, end="", flush=True)
        elif event.event_type == "final_result":
            print("\nStream completed")
            break

asyncio.run(stream_with_extended_reasoning())
```

**Notes:**
- Extended reasoning only works with compatible models (qwen3, qwq, deepseek-r1 series)
- Default behavior is fast mode (`enable_extended_reasoning=False`) for quicker responses
- Extended reasoning provides more detailed step-by-step reasoning but takes longer
- The agent automatically detects model compatibility and appends appropriate commands
- For non-compatible models, the extended reasoning setting has no effect

### Using Web Search with the Agent

The web search functionality is now integrated directly into the agent using the official pydantic-ai DuckDuckGo tool:

```python
from localknowledge.ai.agent import LocalKnowledgeAgent
import asyncio

async def search_example():
    # Create an agent with web search enabled
    agent = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=True,
        enable_local_search=False
    )

    # Ask a question that will trigger web search
    result = await agent.run("What is the latest news about COVID-19 vaccines?")

    print(f"Answer: {result.output.answer}")
    print(f"Search performed: {result.output.search_performed}")
    print(f"Sources found: {len(result.output.sources)}")

    # The agent automatically handles search and result formatting
    for i, source in enumerate(result.output.sources):
        print(f"Source {i+1}: {source}")

    # Clean up
    agent.close()

asyncio.run(search_example())
```

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
    model="qwen3:8b"  # You can also try other models
)

print(f"Generated abstract:\n{hypothetical_abstract[:300]}...")

# Get embedding for the hypothetical abstract
hyde_embedding = generate_hyde_embedding(
    question=query,
    generation_model="qwen3:8b",
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
   DEFAULT_QA_MODEL = "qwen3:8b"
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

### Agent Configuration

The pydantic-ai agent can be configured in several ways:

1. **Model Selection**: Choose the Ollama model for generation:
   ```python
   agent = LocalKnowledgeAgent(model_name="qwen3:8b")
   ```

2. **Search Configuration**: Enable/disable search capabilities:
   ```python
   agent = LocalKnowledgeAgent(
       enable_web_search=True,
       enable_local_search=True
   )
   ```

3. **Ollama Host**: Configure the Ollama server URL:
   ```python
   agent = LocalKnowledgeAgent(ollama_host="http://localhost:11434")
   ```

4. **Environment Variables**: Set defaults via environment:
   ```bash
   export OLLAMA_HOST="http://localhost:11434"
   export LK_DEFAULT_MODEL="qwen3:8b"
   export LK_EMBEDDING_MODEL="snowflake-arctic-embed2:latest"
   ```

### Web Search Configuration

The web search functionality now uses the official pydantic-ai DuckDuckGo search tool:

1. **DuckDuckGo** (official pydantic-ai tool, no API key required):
   ```python
   # Web search is enabled/disabled at the agent level
   agent = LocalKnowledgeAgent(
       enable_web_search=True,  # Uses official DuckDuckGo tool
       enable_local_search=True
   )
   ```

2. **Configuration options**:
   ```python
   # The DuckDuckGo tool is automatically configured with sensible defaults
   # No additional configuration is needed
   ```

The official tool provides better reliability, error handling, and integration compared to custom implementations.

### Ollama Configuration

The AI module requires Ollama to be running and accessible. Ollama configuration:

- Default URL: `http://localhost:11434`
- Can be configured with the `OLLAMA_HOST` environment variable

## Performance Considerations

### Model Loading

Ollama loads models on demand, which can cause delays on first use. To pre-load models:

```bash
ollama pull snowflake-arctic-embed2:latest
ollama pull qwen3:8b
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
   - Try different generation models (qwen3:8b, llama3.2:3b-instruct-q8_0, etc.)
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
   ollama run qwen3:8b "Generate a question and answer about traumatic brain injury."
   ```
