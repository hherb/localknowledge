# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalKnowledge is a Python library for local PubMed and medRxiv database access with semantic search capabilities. It enables creating and maintaining a local copy of medical literature with vector embeddings for research and analysis.

## Key Architecture Components

### Core Modules
- `localknowledge/`: Main package with modular architecture
  - `pubmed/`: PubMed downloading, importing, and management
  - `medrxiv/`: medRxiv preprint fetching and processing
  - `db/`: Database infrastructure, models, and connections
  - `embeddings/`: Vector embedding generation and management
  - `ai/`: AI-powered features (search, summarization, evaluation)
  - `ui/`: PySide6-based GUI components
  - `textprocessing/`: Text chunking, keyword extraction
  - `mcp/`: Model Context Protocol server implementation

### Database Schema
The project uses PostgreSQL with pgvector extension for vector operations. Key tables:
- `document`: Main article storage with generated search vectors
- `chunks`: Text chunks for embedding
- `emb_*`: Embedding tables for different vector dimensions (768, 1024)
- `evaluations`: Document quality ratings and research relevance
- `projects`: Research project management
- `users`: User accounts and preferences

## Development Commands

### Testing
```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --skip-baseline
python run_tests.py --cleanup

# Test with specific environment
DOTENV_FILE=.env.test python run_tests.py
```

### Database Operations
```bash
# Set up test database
python test_env.py

# Run database migrations
python -m localknowledge.db.migrations_system.run_migrations

# Verify embedding integrity
python verify_embedding_integrity.py
```

### Data Processing
```bash
# Download PubMed updates
python -m localknowledge.pubmed.async_download_cli

# Generate embeddings
python update_embeddings_for_abstracts.py

# Process medRxiv updates
python -m localknowledge.medrxiv.medrxiv_daily_update
```

### MCP Server
```bash
# Start MCP server (stdio transport)
python mcp_server/localknowledge_mcp_server.py

# Test MCP functionality
python mcp_server/test_mcp_server.py
```

## Common Development Tasks

### Adding New Document Sources
1. Create new module in `localknowledge/`
2. Implement abstract base class from `localknowledge.base`
3. Add database tables and migrations
4. Update unified document interface

### Embedding Model Integration
1. Add model to `embedding_models` table
2. Create embedding table inheriting from `embedding_base`
3. Implement embedder in `localknowledge/embeddings/`
4. Update embedding manager

### UI Plugin Development
1. Inherit from `localknowledge.ui.plugin_base.PluginBase`
2. Implement required methods: `get_widget()`, `get_menu_text()`
3. Register in `localknowledge/ui/plugins/`

## Configuration

### Environment Variables
- `POSTGRES_*`: Database connection parameters
- `DOTENV_FILE`: Environment file to load (default: `.env`)
- `OPENAI_API_KEY`: For OpenAI embedding models

### Database Connection
Uses connection pooling via `localknowledge.db.connection_pool`. Configure in environment or `.env` file.

## Testing Strategy

The project includes comprehensive testing:
- Unit tests for individual modules
- Integration tests for database operations
- Performance tests for embedding operations
- MCP server protocol tests

Test files follow `test_*.py` naming convention. Use `run_tests.py` for coordinated test execution with proper environment setup.

## Architecture Patterns

### Dependency Injection
Database connections and configurations are injected rather than hardcoded.

### Abstract Base Classes
Common interfaces for different document sources and embedding providers.

### Migration System
Structured database migrations in `localknowledge/db/migrations_system/`.

### Vector Operations
Leverages pgvector for efficient similarity search and vector operations.

### Plugin Architecture
Extensible UI system with plugin-based components.