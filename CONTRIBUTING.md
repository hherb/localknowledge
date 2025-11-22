# Contributing to LocalKnowledge

Welcome to LocalKnowledge! This guide will help you get started with development on this project.

## Table of Contents

- [Quick Start](#quick-start)
- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)

## Quick Start

### Prerequisites

- Python 3.12 or higher
- PostgreSQL 14+ with pgvector extension
- Ollama (for local LLM and embedding models)

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge
pip install -e ".[dev]"
```

### 2. Database Setup

Create a PostgreSQL database with pgvector:

```sql
CREATE DATABASE localknowledge;
\c localknowledge
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# Database connection
POSTGRES_DB=localknowledge
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Optional: PDF storage directory
PDF_BASE_DIR=~/knowledgebase/pdf

# Optional: API keys (if using external services)
OPENAI_API_KEY=your_key_here
```

### 4. Initialize Database

```bash
# Create baseline database tables
python -m localknowledge.db.create_baseline_db

# Run any pending migrations
python -m localknowledge.db.migrations_system.run_migrations
```

### 5. Verify Installation

```bash
# Run the test suite
python run_tests.py --skip-baseline
```

## Development Environment Setup

### Installing Dependencies

```bash
# Install all dependencies including dev tools
pip install -e ".[dev]"

# Install spaCy language model (required for keyword extraction)
python -m spacy download en_core_web_sm
```

### Setting Up Ollama

LocalKnowledge uses Ollama for embeddings and LLM operations:

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull snowflake-arctic-embed2  # For embeddings
ollama pull gemma3:4b                 # For document evaluation
```

### IDE Configuration

For VS Code, create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true
}
```

## Project Structure

```
localknowledge/
├── localknowledge/          # Main package
│   ├── ai/                  # AI/LLM features (search, evaluation, summarization)
│   ├── db/                  # Database layer and managers
│   ├── embeddings/          # Vector embedding generation
│   ├── medrxiv/             # medRxiv data source
│   ├── pubmed/              # PubMed data source
│   ├── textprocessing/      # Text chunking and keyword extraction
│   ├── ui/                  # PySide6 GUI components
│   ├── mcp/                 # MCP server integration
│   ├── base.py              # Abstract base class
│   └── context.py           # Thread-safe context manager
├── mcp_server/              # Standalone MCP server
├── tests/                   # Integration tests
├── examples/                # Example scripts
├── run_tests.py             # Test runner
└── pyproject.toml           # Project configuration
```

### Key Modules Overview

| Module | Purpose |
|--------|---------|
| `db/` | Database connections, managers, and migrations |
| `ai/` | LLM integration, document evaluation, hybrid search |
| `embeddings/` | Vector embedding generation and management |
| `pubmed/` | PubMed downloading and importing |
| `medrxiv/` | medRxiv fetching and processing |
| `textprocessing/` | Text chunking, keyword extraction |
| `ui/` | PySide6 GUI with plugin architecture |
| `mcp/` | Model Context Protocol server |

## Running Tests

### Full Test Suite

```bash
python run_tests.py
```

### Specific Test Options

```bash
# Skip baseline database tests (faster)
python run_tests.py --skip-baseline

# Clean up test environment after tests
python run_tests.py --cleanup

# Use test environment
DOTENV_FILE=.env.test python run_tests.py

# Run only cleanup
python run_tests.py --cleanup-only
```

### Module-Specific Tests

```bash
# Test specific modules
python -m pytest localknowledge/ai/tests/
python -m pytest localknowledge/db/tests/
python -m pytest localknowledge/embeddings/tests/
```

## Making Changes

### Adding a New Database Manager

1. Create a new file in `localknowledge/db/`:

```python
from localknowledge.db.base import DatabaseManager

class MyNewManager(DatabaseManager):
    """Manager for my new feature."""

    def __init__(self):
        super().__init__()

    def my_method(self, param):
        query = "SELECT * FROM my_table WHERE id = %s"
        return self.execute(query, (param,))
```

### Adding a New Embedding Model

1. Create embedder in `localknowledge/embeddings/`:

```python
from localknowledge.embeddings.base_embedder import BaseEmbedder

class MyEmbedder(BaseEmbedder):
    def __init__(self, model_name: str):
        super().__init__(model_name)

    def embed(self, text: str) -> list[float]:
        # Implementation here
        pass

    def get_vectorsize(self) -> int:
        return 768  # Your model's vector size
```

2. Register in `EmbeddingManager.set_embedding_model()`

### Adding a New UI Plugin

1. Create plugin in `localknowledge/ui/plugins/`:

```python
from localknowledge.ui.plugin_base import PluginBase

class MyPlugin(PluginBase):
    plugin_name = "My Plugin"
    plugin_description = "Description of my plugin"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # Build your UI here
        pass
```

### Creating a Database Migration

```bash
# Use the migration manager to create a template
python -c "
from localknowledge.db.migrations_system.manager import MigrationsManager
manager = MigrationsManager()
manager.create_migration_template('my_migration_name')
"
```

This creates a file like `localknowledge/db/migrations_system/migrations/006_my_migration_name.py`

## Code Style

### Python Style Guidelines

- Use type hints for function signatures
- Follow PEP 8 conventions
- Use docstrings for public functions and classes
- Keep functions focused and under 50 lines when possible

### Formatting

```bash
# Format code with black
black localknowledge/

# Sort imports with isort
isort localknowledge/
```

### Example Code Style

```python
"""Module docstring describing purpose."""

import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def process_document(
    document_id: int,
    options: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Process a document and return extracted keywords.

    Args:
        document_id: The database ID of the document
        options: Optional processing options

    Returns:
        List of extracted keywords

    Raises:
        ValueError: If document_id is invalid
    """
    if document_id <= 0:
        raise ValueError("document_id must be positive")

    # Implementation here
    return []
```

## Submitting Changes

### Before Submitting

1. Ensure all tests pass:
   ```bash
   python run_tests.py
   ```

2. Format your code:
   ```bash
   black localknowledge/
   isort localknowledge/
   ```

3. Add tests for new functionality

4. Update documentation if needed

### Commit Guidelines

- Use clear, descriptive commit messages
- Reference issue numbers when applicable
- Keep commits focused on single changes

Example commit messages:
```
feat: add HyDE search to hybrid search module
fix: resolve connection pool exhaustion in long-running queries
docs: update embedding model configuration guide
refactor: simplify document evaluation flow
```

### Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with appropriate tests
3. Update documentation as needed
4. Submit a pull request with a clear description
5. Address any review feedback

## Getting Help

- Check existing issues on GitHub
- Review the code documentation in `DEVELOPERS.md`
- Look at example scripts in `examples/`
- Examine test files for usage patterns

## Common Development Tasks

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

### Start MCP Server

```bash
# stdio transport (for local use)
python mcp_server/localknowledge_mcp_server.py

# SSE transport (for remote connections)
python mcp_server/localknowledge_mcp_server.py --transport sse --port 8080
```

### Launch GUI

```bash
python -m localknowledge.ui.pyside6_main_window
```
