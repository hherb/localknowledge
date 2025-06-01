# LocalKnowledge AI Agent

A pydantic-ai based intelligent agent that uses Ollama LLMs and provides web search capabilities for the LocalKnowledge system.

## Features

- **Ollama Integration**: Uses local Ollama models via OpenAI-compatible API
- **Web Search**: DuckDuckGo search integration for current information
- **Local Knowledge Search**: Integration with LocalKnowledge database
- **Structured Responses**: Pydantic models for consistent output
- **Async/Sync Support**: Both asynchronous and synchronous operation modes
- **Streaming Responses**: Real-time streaming for faster time-to-first-token
- **Configurable Tools**: Enable/disable search capabilities as needed

## Quick Start

### Prerequisites

1. **Ollama**: Install and run Ollama with a model
   ```bash
   # Install Ollama (see https://ollama.com)
   ollama pull qwen3:8b
   ollama run qwen3:8b
   ```

2. **Dependencies**: Install required packages
   ```bash
   pip install pydantic-ai aiohttp beautifulsoup4 requests
   ```

### Basic Usage

```python
from localknowledge.ai.agent import LocalKnowledgeAgent
import asyncio

async def main():
    # Create an agent
    agent = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=True,
        enable_local_search=True
    )
    
    # Ask a question
    result = await agent.run("What is machine learning?")
    
    print(f"Answer: {result.output.answer}")
    print(f"Sources: {len(result.output.sources)}")
    print(f"Confidence: {result.output.confidence}")
    
    # Clean up
    agent.close()

# Run the example
asyncio.run(main())
```

### Streaming Usage

For real-time responses with faster time-to-first-token:

```python
from localknowledge.ai.agent import ask_agent_stream
import asyncio

async def streaming_example():
    print("Streaming response:")
    async for event in ask_agent_stream(
        "Explain quantum computing briefly",
        model_name="qwen3:8b",
        enable_web_search=False
    ):
        if event.event_type == "text_delta":
            print(event.content, end="", flush=True)
        elif event.event_type == "final_result":
            print(f"\nConfidence: {event.metadata.get('confidence', 0.0)}")

asyncio.run(streaming_example())
```

### Synchronous Usage

```python
from localknowledge.ai.agent import ask_agent_sync

# Quick synchronous usage
response = ask_agent_sync(
    "Explain quantum computing",
    model_name="qwen3:8b",
    enable_web_search=True
)

print(response.answer)
```

## Configuration

### Agent Parameters

- `model_name`: Ollama model to use (default: "qwen3:8b")
- `embedding_model`: Model for embeddings (default: "snowflake-arctic-embed2:latest")
- `ollama_host`: Ollama server URL (default: "http://localhost:11434")
- `enable_web_search`: Enable web search (default: True)
- `enable_local_search`: Enable local database search (default: True)

### Environment Variables

```bash
export OLLAMA_HOST="http://localhost:11434"
export LK_DEFAULT_MODEL="qwen3:8b"
export LK_EMBEDDING_MODEL="snowflake-arctic-embed2:latest"
```

## Web Search

The agent uses the official pydantic-ai DuckDuckGo search tool. No API key required.

```python
from localknowledge.ai.agent import LocalKnowledgeAgent
import asyncio

async def search_example():
    # Web search is integrated into the agent
    agent = LocalKnowledgeAgent(
        enable_web_search=True,
        enable_local_search=False
    )

    result = await agent.run("What is the latest AI research in 2024?")
    print(f"Answer: {result.output.answer}")
    print(f"Search performed: {result.output.search_performed}")

    agent.close()

asyncio.run(search_example())
```

## Response Format

The agent returns structured responses:

```python
class AgentResponse(BaseModel):
    answer: str                    # The agent's answer
    sources: List[Dict[str, Any]]  # Sources used
    search_performed: bool         # Whether search was used
    confidence: float              # Confidence score (0.0-1.0)
```

## Context and Dependencies

Use `AgentContext` to provide additional context:

```python
from localknowledge.ai.agent import AgentContext

context = AgentContext(
    user_id=123,
    project_id=456,
    max_search_results=10,
    enable_web_search=True,
    enable_local_search=True
)

result = await agent.run("Your question", context)
```

## Error Handling

The agent handles various error conditions gracefully:

```python
try:
    result = await agent.run("Your question")
    print(result.output.answer)
except Exception as e:
    print(f"Agent error: {e}")
finally:
    agent.close()
```

## Testing

Run the test suite:

```bash
python -m pytest localknowledge/ai/tests/test_agent.py -v
```

Run the example script:

```bash
python localknowledge/ai/examples/agent_example.py
```

## Architecture

### Components

1. **LocalKnowledgeAgent**: Main agent class
2. **Official DuckDuckGo Tool**: Web search functionality via pydantic-ai
3. **URLFetchTool**: URL content extraction (optional utility)
4. **AgentResponse**: Structured response model
5. **AgentContext**: Context and configuration

### Integration

- **Ollama**: Via OpenAI-compatible API
- **pydantic-ai**: Agent framework with official DuckDuckGo tool
- **DuckDuckGo**: Web search provider (official integration)
- **LocalKnowledge DB**: Local document search

## Troubleshooting

### Common Issues

1. **Ollama not running**
   ```bash
   ollama serve
   ```

2. **Model not available**
   ```bash
   ollama pull qwen3:8b
   ```

3. **Import errors**
   ```bash
   pip install pydantic-ai aiohttp beautifulsoup4
   ```

4. **Web search fails**
   - Check internet connection
   - DuckDuckGo may rate limit requests

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Follow the existing code patterns
2. Add type hints and docstrings
3. Write unit tests for new features
4. Update documentation

## License

Part of the LocalKnowledge project.
