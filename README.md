# LocalKnowledge

A Python library for local PubMed and medRxiv database access with semantic search capabilities. LocalKnowledge enables researchers to create, maintain, and search a local copy of medical literature using vector embeddings and AI-powered features.

## Features

- **Local Database**: Store PubMed articles and medRxiv preprints locally in PostgreSQL
- **Semantic Search**: Find relevant documents using vector similarity (pgvector)
- **Hybrid Search**: Combine semantic search with HyDE (Hypothetical Document Embeddings)
- **AI-Powered Evaluation**: Automatically evaluate document relevance to research questions
- **Multiple Embedding Models**: Support for Ollama models and PubMedBERT
- **Full-Text Processing**: PDF to markdown conversion, text chunking, keyword extraction
- **MCP Server**: Model Context Protocol server for LLM integration (Claude, etc.)
- **Desktop GUI**: PySide6-based interface for browsing and managing documents
- **Project Management**: Organize documents into research projects

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ with pgvector extension
- Ollama (for embeddings and LLM features)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge

# Install package
pip install -e .

# Install spaCy language model
python -m spacy download en_core_web_sm
```

### Database Setup

```sql
-- Create database with pgvector
CREATE DATABASE localknowledge;
\c localknowledge
CREATE EXTENSION IF NOT EXISTS vector;
```

### Configuration

Create a `.env` file:

```bash
POSTGRES_DB=localknowledge
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### Initialize Database

```bash
# Create tables
python -m localknowledge.db.create_baseline_db

# Run migrations
python -m localknowledge.db.migrations_system.run_migrations
```

### Install Ollama Models

```bash
ollama pull snowflake-arctic-embed2  # For embeddings
ollama pull gemma3:4b                 # For AI features
```

## Usage

### Semantic Search

```python
from localknowledge.embeddings.embedding_manager import EmbeddingManager

# Initialize embedding manager
em = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Search for similar documents
results = em.search(
    query="effects of aspirin on cardiovascular outcomes",
    limit=20,
    threshold=0.5
)

for doc in results:
    print(f"{doc['title']} - Similarity: {doc['similarity']:.2f}")

em.close()
```

### Hybrid Search (Semantic + HyDE)

```python
from localknowledge.ai.hybrid_search import perform_hybrid_search
from localknowledge.embeddings.multiembeddings import EmbeddingManager

em = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

results = perform_hybrid_search(
    embedding_manager=em,
    query="What are the neurological effects of long COVID?",
    max_results=20,
    threshold=0.3,
    use_reranker=True
)

print(f"Found {len(results['results'])} documents")
print(f"HyDE Abstract: {results['abstract'][:200]}...")
```

### Document Evaluation

```python
from localknowledge.ai.document_evaluator import DocumentEvaluator

evaluator = DocumentEvaluator(model_name="gemma3:4b")

result = evaluator.evaluate(
    question="What is the efficacy of mRNA vaccines against COVID-19?",
    document_id=123
)

print(f"Rating: {result.rating}/3")
print(f"Reason: {result.reason_for_rating}")
```

### Database Access

```python
from localknowledge.db.document import DocumentDatabaseManager

db = DocumentDatabaseManager()

# Get document by ID
doc = db.get_document(123)

# Search documents
results = db.search_documents("covid vaccine", limit=50)

# Get by DOI
doc = db.get_document_by_doi("10.1234/example.doi")

db.close()
```

### Text Processing

```python
from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker
from localknowledge.textprocessing.keywords.pytextrank_extractor import PyTextRankExtractor

# Chunk text
chunker = TextChunker(chunk_size=1000, overlap=200)
chunks = chunker.chunk("Long document text...")

# Markdown-aware chunking
md_chunker = MarkdownChunker(max_chunk_size=1000)
chunks = md_chunker.chunk(markdown_text)

# Extract keywords
extractor = PyTextRankExtractor()
keywords = extractor.extract("Medical document text...", max_keywords=10)
```

## Data Pipeline

### Download PubMed Updates

```bash
python -m localknowledge.pubmed.async_download_cli
```

### Update medRxiv Preprints

```bash
python -m localknowledge.medrxiv.medrxiv_daily_update
```

### Generate Embeddings

```bash
python update_embeddings_for_abstracts.py
```

## MCP Server

LocalKnowledge includes a Model Context Protocol (MCP) server for integration with Claude and other LLMs.

### Start Server

```bash
# stdio transport (for Claude Desktop)
python mcp_server/localknowledge_mcp_server.py

# SSE transport (for remote connections)
python mcp_server/localknowledge_mcp_server.py --transport sse --port 8080
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "localknowledge": {
      "command": "python",
      "args": ["/path/to/localknowledge/mcp_server/localknowledge_mcp_server.py"]
    }
  }
}
```

### Available Tools

- `search_pubmed_by_keywords`: Search documents by keywords
- `get_document_details`: Get document metadata
- `get_full_text`: Get full text of a document

## Desktop Application

Launch the PySide6-based GUI:

```bash
python -m localknowledge.ui.pyside6_main_window
```

Features:
- Knowledge Browser: Search and view documents
- News Browser: Discover new preprints
- Document Evaluator: AI-powered relevance evaluation
- Project Manager: Organize research projects

## Project Structure

```
localknowledge/
├── localknowledge/
│   ├── ai/                 # AI features (search, evaluation, summarization)
│   ├── db/                 # Database layer and managers
│   ├── embeddings/         # Vector embedding generation
│   ├── medrxiv/            # medRxiv data source
│   ├── pubmed/             # PubMed data source
│   ├── textprocessing/     # Text chunking and keywords
│   ├── ui/                 # PySide6 GUI components
│   ├── mcp/                # MCP integration
│   ├── base.py             # Abstract base class
│   └── context.py          # Context manager
├── mcp_server/             # Standalone MCP server
├── examples/               # Example scripts
├── tests/                  # Integration tests
├── CONTRIBUTING.md         # Developer quickstart guide
├── DEVELOPERS.md           # Detailed programmer's reference
└── pyproject.toml          # Project configuration
```

## Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
# All tests
python run_tests.py

# Skip baseline tests (faster)
python run_tests.py --skip-baseline

# Cleanup after tests
python run_tests.py --cleanup
```

### Code Formatting

```bash
black localknowledge/
isort localknowledge/
```

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) - Developer quickstart guide
- [DEVELOPERS.md](DEVELOPERS.md) - Detailed programmer's reference
- [CLAUDE.md](CLAUDE.md) - AI assistant instructions

## Requirements

### Core Dependencies

- `psycopg2` - PostgreSQL adapter
- `pgvector` - Vector similarity search
- `ollama` - Local LLM and embeddings
- `pydantic-ai` - Structured LLM outputs
- `sentence-transformers` - Embedding models
- `PySide6` - Desktop GUI
- `pymupdf4llm` - PDF to markdown
- `fastmcp` - MCP server

### Optional Dependencies

- `spacy` + `pytextrank` - Keyword extraction
- `beautifulsoup4` - Web scraping
- `aiohttp` + `aioftp` - Async downloads

See `pyproject.toml` for complete dependency list.

## Architecture

LocalKnowledge uses several key architectural patterns:

- **Abstract Base Classes**: Common interfaces for data sources, embedders, chunkers
- **Dependency Injection**: Database connections passed rather than hardcoded
- **Singleton Pattern**: Thread-safe context manager for shared state
- **Plugin Architecture**: Extensible UI with dynamically loaded plugins
- **Migration System**: Versioned database migrations with tracking

## Database Schema

Key tables:
- `document` - Main article storage with search vectors
- `unified_multiembeddings` - Multi-model vector embeddings
- `evaluations` - Document relevance ratings
- `projects` - Research project management
- `users` - User accounts

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

- [PubMed](https://pubmed.ncbi.nlm.nih.gov/) for medical literature
- [medRxiv](https://www.medrxiv.org/) for preprints
- [Ollama](https://ollama.com/) for local LLM support
- [pgvector](https://github.com/pgvector/pgvector) for vector operations
