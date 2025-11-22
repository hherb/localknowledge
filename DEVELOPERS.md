# LocalKnowledge Developer Reference

This document provides comprehensive technical documentation for developers working on the LocalKnowledge project.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Database Layer](#database-layer)
3. [AI Module](#ai-module)
4. [Embeddings Module](#embeddings-module)
5. [Data Sources](#data-sources)
6. [Text Processing](#text-processing)
7. [User Interface](#user-interface)
8. [MCP Server](#mcp-server)
9. [Context Management](#context-management)
10. [Migration System](#migration-system)
11. [Configuration](#configuration)
12. [API Reference](#api-reference)

---

## Architecture Overview

LocalKnowledge is a modular Python library for managing local medical literature databases with semantic search capabilities. The architecture follows several key patterns:

### Design Patterns

#### Abstract Base Classes
All major components inherit from abstract base classes:
- `LocalKnowledgeBase` - Base for data source clients
- `DatabaseManager` - Base for all database operations
- `BaseEmbedder` - Base for embedding implementations
- `BaseChunker` - Base for text chunking strategies
- `PluginBase` - Base for UI plugins

#### Dependency Injection
Database connections and configurations are injected rather than hardcoded, enabling:
- Testing with mock/test databases
- Multiple concurrent connections
- Clean separation of concerns

#### Singleton Pattern
The `ContextManager` uses thread-safe singleton pattern for sharing state across modules.

#### Plugin Architecture
The UI system uses dynamic plugin loading for extensibility.

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Knowledge   │  │ News        │  │ Document                │  │
│  │ Browser     │  │ Browser     │  │ Evaluator               │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
┌─────────▼────────────────▼─────────────────────▼────────────────┐
│                        AI Layer                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Hybrid      │  │ Document    │  │ Summarizer              │  │
│  │ Search      │  │ Evaluator   │  │                         │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
┌─────────▼────────────────▼─────────────────────▼────────────────┐
│                     Embedding Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Embedding   │  │ Ollama      │  │ PubMedBERT              │  │
│  │ Manager     │  │ Embedder    │  │ Embedder                │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
┌─────────▼────────────────▼─────────────────────▼────────────────┐
│                     Database Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Document    │  │ Embeddings  │  │ Connection              │  │
│  │ Manager     │  │ Manager     │  │ Pool                    │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          └────────────────┼─────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  PostgreSQL + pgvector  │
              └─────────────────────────┘
```

---

## Database Layer

Location: `localknowledge/db/`

The database layer provides a comprehensive abstraction over PostgreSQL with pgvector for vector operations.

### Base DatabaseManager

**File**: `localknowledge/db/base.py`

```python
from localknowledge.db.base import DatabaseManager

class DatabaseManager:
    """Base class for database operations."""

    def __init__(self, check_infrastructure: bool = True, dotenv_path: str = None):
        """
        Initialize database connection.

        Args:
            check_infrastructure: Run infrastructure checks on init
            dotenv_path: Path to .env file
        """

    def execute(self, query: str, params: tuple = None, commit: bool = False, timeout: int = 30):
        """Execute SQL query with timeout."""

    def execute_many(self, query: str, params_list: list, commit: bool = True, timeout: int = 60):
        """Execute query with multiple parameter sets."""

    def execute_without_timeout(self, query: str, params: tuple = None, commit: bool = False):
        """Execute long-running query without timeout (for migrations)."""

    def close(self):
        """Close database connection."""
```

**Usage**:
```python
from localknowledge.db.base import DatabaseManager

class MyManager(DatabaseManager):
    def get_items(self):
        return self.execute("SELECT * FROM items LIMIT 10")

    def add_item(self, name):
        return self.execute(
            "INSERT INTO items (name) VALUES (%s) RETURNING id",
            (name,),
            commit=True
        )
```

### Connection Pool

**File**: `localknowledge/db/connection_pool.py`

Thread-safe connection pooling using psycopg2's `ThreadedConnectionPool`.

```python
from localknowledge.db.connection_pool import (
    initialize_pool,
    get_connection,
    get_cursor,
    close_pool,
    get_pool_status
)

# Initialize pool (automatic on first use)
initialize_pool(min_connections=1, max_connections=10)

# Context manager for connections
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT 1")

# Context manager for cursors (with auto-commit)
with get_cursor(commit=True) as cursor:
    cursor.execute("INSERT INTO table (col) VALUES (%s)", (value,))

# Check pool status
status = get_pool_status()
# {'status': 'active', 'minconn': 1, 'maxconn': 10, 'closed': False}
```

### Database Managers Reference

| Manager | File | Purpose |
|---------|------|---------|
| `DocumentDatabaseManager` | `db/document.py` | Unified document CRUD operations |
| `DocumentSearchManager` | `db/document_search.py` | Full-text and vector search |
| `EmbeddingsDatabaseManager` | `db/embeddings.py` | Embedding storage and retrieval |
| `EmbeddingTableManager` | `db/multiembeddings.py` | Multi-model embedding tables |
| `ChunkingDatabaseManager` | `db/chunker.py` | Text chunk management |
| `EvaluationsDatabaseManager` | `db/evaluations.py` | Document evaluations |
| `ProjectDatabaseManager` | `db/project.py` | Research project management |
| `UserDatabaseManager` | `db/user.py` | User accounts |
| `TaskQueueManager` | `db/task_queue.py` | Thread-safe task processing |
| `HypothesesDatabaseManager` | `db/hypotheses.py` | Research hypothesis tracking |
| `ResearchQuestionsManager` | `db/research_questions.py` | Research questions |
| `ReadingTrackerManager` | `db/reading_tracker.py` | Reading history |
| `ReadingSuggestionsManager` | `db/reading_suggestions.py` | Reading recommendations |
| `ModelsDatabaseManager` | `db/models.py` | LLM model registry |
| `PubMedDatabaseManager` | `db/pubmed.py` | PubMed-specific operations |
| `MedRxivDatabaseManager` | `db/medrxiv.py` | medRxiv-specific operations |

### DocumentDatabaseManager

**File**: `localknowledge/db/document.py`

Primary interface for document operations.

```python
from localknowledge.db.document import DocumentDatabaseManager

db = DocumentDatabaseManager()

# Get document by ID
doc = db.get_document(document_id=123)

# Get document by DOI
doc = db.get_document_by_doi("10.1234/example")

# Get documents by source
docs = db.get_documents_by_source(source_id=1, limit=100)

# Search documents
results = db.search_documents(
    query="covid treatment",
    limit=50,
    offset=0
)

# Insert document
new_id = db.insert_document(
    title="Document Title",
    abstract="Abstract text...",
    authors=["Author 1", "Author 2"],
    publication="Journal Name",
    publication_date="2024-01-15",
    source_id=1,
    external_id="PMID12345"
)

# Update document
db.update_document(
    document_id=123,
    title="Updated Title",
    abstract="Updated abstract..."
)

db.close()
```

### EmbeddingsDatabaseManager

**File**: `localknowledge/db/embeddings.py`

Manages vector embeddings with pgvector.

```python
from localknowledge.db.embeddings import EmbeddingsDatabaseManager

db = EmbeddingsDatabaseManager()

# Add embedding
db.add_embedding(
    document_id=123,
    embedding=[0.1, 0.2, ...],  # Vector
    model_name="snowflake-arctic-embed2:latest",
    embed_source="abstract"
)

# Search similar documents
results = db.search_similar(
    embedding=[0.1, 0.2, ...],
    embed_source="abstract",
    model_name="snowflake-arctic-embed2:latest",
    limit=10,
    threshold=0.5
)

# Get models with embeddings
models = db.get_models_with_embeddings()
# {1: 'snowflake-arctic-embed2:latest', 2: 'pubmedbert'}

db.close()
```

### TaskQueueManager

**File**: `localknowledge/db/task_queue.py`

Thread-safe parallel task processing using PostgreSQL `SKIP LOCKED`.

```python
from localknowledge.db.task_queue import TaskQueueManager

tq = TaskQueueManager()

# Add tasks
task_ids = tq.add_tasks([
    {"type": "embed", "document_id": 1},
    {"type": "embed", "document_id": 2},
])

# Claim next available task (thread-safe)
task = tq.claim_next_task()
if task:
    try:
        # Process task
        process(task['payload'])
        tq.complete_task(task['id'], success=True)
    except Exception as e:
        tq.complete_task(task['id'], success=False, error=str(e))

# Get queue status
status = tq.get_queue_status()
# {'pending': 10, 'processing': 2, 'completed': 50, 'failed': 1}

tq.close()
```

### Database Schema Overview

#### Core Tables

```sql
-- Main document storage
CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    authors TEXT[],
    publication TEXT,
    publication_date DATE,
    source_id INTEGER REFERENCES sources(id),
    external_id TEXT,
    doi TEXT,
    url TEXT,
    pdf_url TEXT,
    pdf_filename TEXT,
    full_text TEXT,
    keywords TEXT[],
    search_vector tsvector,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Data sources (pubmed, medrxiv, etc.)
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- Multi-model embeddings
CREATE TABLE unified_multiembeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document(id),
    embedding vector,
    model_name TEXT,
    embed_source_id INTEGER REFERENCES embedding_source(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Embedding sources (abstract, full_text, chunk, etc.)
CREATE TABLE embedding_source (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- Document evaluations
CREATE TABLE evaluations (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document(id),
    evaluator_id INTEGER REFERENCES evaluators(id),
    project_id INTEGER REFERENCES projects(id),
    question TEXT,
    rating INTEGER CHECK (rating >= 0 AND rating <= 3),
    reason TEXT,
    evaluated_at TIMESTAMP DEFAULT NOW()
);

-- Research projects
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## AI Module

Location: `localknowledge/ai/`

The AI module provides LLM-powered features for search, evaluation, and summarization.

### Hybrid Search

**File**: `localknowledge/ai/hybrid_search.py`

Combines semantic search with HyDE (Hypothetical Document Embeddings).

```python
from localknowledge.ai.hybrid_search import (
    perform_hybrid_search,
    perform_semantic_search,
    perform_hyde_search
)
from localknowledge.embeddings.multiembeddings import EmbeddingManager

em = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Full hybrid search
results = perform_hybrid_search(
    embedding_manager=em,
    query="What are the effects of aspirin on cardiovascular outcomes?",
    max_results=20,
    threshold=0.3,
    use_reranker=True,
    reranker_model='BAAI/bge-reranker-base',
    hyde_model='gemma3:4b'
)
# Returns: {'results': [...], 'abstract': 'hypothetical abstract text...'}

# Semantic search only
semantic_results = perform_semantic_search(
    embedding_manager=em,
    query="aspirin cardiovascular",
    max_results=10,
    threshold=0.3
)

# HyDE search only
hyde_results = perform_hyde_search(
    embedding_manager=em,
    query="What are the effects of aspirin?",
    max_results=10,
    hyde_model='gemma3:4b'
)
```

### Document Evaluator

**File**: `localknowledge/ai/document_evaluator.py`

AI-powered document relevance evaluation.

```python
from localknowledge.ai.document_evaluator import DocumentEvaluator, DocumentOfInterest

evaluator = DocumentEvaluator(
    model_name="gemma3:4b",
    model_options={"temperature": 0.3}
)

# Evaluate a document
result: DocumentOfInterest = evaluator.evaluate(
    question="What is the efficacy of mRNA vaccines against COVID-19?",
    document_id=123
)

print(f"Rating: {result.rating}")  # 0-3 scale
print(f"Reason: {result.reason_for_rating}")
```

Rating scale:
- **0**: Not relevant
- **1**: Somewhat relevant, tangential
- **2**: Very likely relevant, should be cited
- **3**: Essential, must be included

### HyDE (Hypothetical Document Embeddings)

**File**: `localknowledge/ai/HyDE.py`

Generates hypothetical abstracts for improved search.

```python
from localknowledge.ai.HyDE import generate_hypothetical_abstract

abstract = generate_hypothetical_abstract(
    question="What are the neurological effects of long COVID?",
    model="gemma3:4b"
)
# Returns a hypothetical abstract that would answer the question
```

### LLM Query Interface

**File**: `localknowledge/ai/ask_llm.py`

Direct LLM query with optional structured output.

```python
from localknowledge.ai.ask_llm import generate_answer
from pydantic import BaseModel

# Simple query
answer = generate_answer(
    question="Summarize the key findings about aspirin.",
    model_name="gemma3:4b"
)

# Structured output with Pydantic
class Summary(BaseModel):
    main_points: list[str]
    conclusion: str

structured = generate_answer(
    question="Extract main points from this text: ...",
    model_name="gemma3:4b",
    pydantic_model=Summary
)
# Returns: {'main_points': [...], 'conclusion': '...'}
```

### Summarizer

**File**: `localknowledge/ai/summarizer.py`

Document summarization.

```python
from localknowledge.ai.summarizer import Summarizer

summarizer = Summarizer(model_name="gemma3:4b")

summary = summarizer.summarize(
    text="Long document text here...",
    max_length=500
)
```

### Rerankers

**File**: `localknowledge/ai/rerankers.py`

Result reranking using cross-encoder models.

```python
from localknowledge.ai.rerankers import get_reranker

reranker = get_reranker('BAAI/bge-reranker-base')

# Rerank search results
reranked = reranker.rerank(
    query="original search query",
    documents=[
        {'id': 1, 'title': '...', 'abstract': '...'},
        {'id': 2, 'title': '...', 'abstract': '...'},
    ]
)
```

---

## Embeddings Module

Location: `localknowledge/embeddings/`

Manages vector embedding generation and storage.

### Base Embedder

**File**: `localknowledge/embeddings/base_embedder.py`

```python
from localknowledge.embeddings.base_embedder import BaseEmbedder

class BaseEmbedder:
    def __init__(self, model_name: str = None):
        self.model_name = model_name

    def embed(self, text: str) -> list[float]:
        """Embed text into vector."""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        raise NotImplementedError

    def get_vectorsize(self) -> int:
        """Get embedding dimension."""
        raise NotImplementedError

    def list_available_models(self) -> list[str]:
        """List available models."""
        raise NotImplementedError
```

### Embedding Manager

**File**: `localknowledge/embeddings/embedding_manager.py`

High-level API for embeddings.

```python
from localknowledge.embeddings.embedding_manager import EmbeddingManager

# Initialize with model
em = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Change model
em.set_embedding_model("pubmedbert")

# Create embedding
vector = em.create_embedding("Text to embed")

# Search similar documents
results = em.search(
    query="search query",
    limit=10,
    threshold=0.5
)

# Process full document
num_chunks = em.process_document(
    source_id="medrxiv",
    document_id="doi:10.1234",
    text="Full document text...",
    is_markdown=True
)

# Chunk text
chunks = em.chunk_text(
    text="Long text...",
    chunk_size=1000,
    overlap=200
)

# Extract keywords
keywords = em.extract_keywords("Text to analyze", max_keywords=10)

em.close()
```

### Ollama Embedder

**File**: `localknowledge/embeddings/ollama_embedder.py`

Embeddings via Ollama API.

```python
from localknowledge.embeddings.ollama_embedder import OllamaEmbedder

embedder = OllamaEmbedder(model_name="snowflake-arctic-embed2:latest")

# Get vector size
size = embedder.get_vectorsize()  # e.g., 1024

# Embed single text
vector = embedder.embed("Text to embed")

# Embed batch
vectors = embedder.embed_batch(["Text 1", "Text 2", "Text 3"])

# List available models
models = embedder.list_available_models()
```

### PubMedBERT Embedder

**File**: `localknowledge/embeddings/pubmed_embedder.py`

Specialized embeddings for medical text using PubMedBERT.

```python
from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder

embedder = PubMedBERTEmbedder()
vector = embedder.embed("Medical terminology text...")
```

---

## Data Sources

### PubMed Module

Location: `localknowledge/pubmed/`

#### Async Download

**File**: `localknowledge/pubmed/async_download.py`

High-performance async downloading using aioftp.

```python
from localknowledge.pubmed.async_download import PubMedAsyncDownloader

downloader = PubMedAsyncDownloader(
    download_dir="/path/to/downloads",
    max_concurrent=5
)

# Download baseline files
await downloader.download_baseline()

# Download update files
await downloader.download_updates(from_date="2024-01-01")
```

**CLI**:
```bash
python -m localknowledge.pubmed.async_download_cli --help
python -m localknowledge.pubmed.async_download_cli --download-updates
```

#### Import Downloads

**File**: `localknowledge/pubmed/import_downloads.py`

Import downloaded XML files into database.

```python
from localknowledge.pubmed.import_downloads import PubMedImporter

importer = PubMedImporter()
count = importer.import_file("/path/to/pubmed_file.xml.gz")
print(f"Imported {count} articles")
```

### medRxiv Module

Location: `localknowledge/medrxiv/`

#### Fetcher

**File**: `localknowledge/medrxiv/medrxiv_fetcher.py`

Fetch preprints from medRxiv API.

```python
from localknowledge.medrxiv.medrxiv_fetcher import MedRxivFetcher

fetcher = MedRxivFetcher()

# Get recent preprints
preprints = fetcher.fetch_recent(days=7, max_results=100)

# Get preprint by DOI
preprint = fetcher.fetch_by_doi("10.1101/2024.01.15.12345")
```

#### Daily Update

**File**: `localknowledge/medrxiv/medrxiv_daily_update.py`

Automated daily update pipeline.

```bash
# Run as cron job
python -m localknowledge.medrxiv.medrxiv_daily_update
```

#### PDF to Markdown

**File**: `localknowledge/medrxiv/medrxiv_to_markdown.py`

Convert PDFs to markdown using pymupdf4llm.

```python
from localknowledge.medrxiv.medrxiv_to_markdown import convert_pdf_to_markdown

markdown = convert_pdf_to_markdown("/path/to/document.pdf")
```

#### Abstract Embedding

**File**: `localknowledge/medrxiv/embed_abstracts.py`

Generate embeddings for medRxiv abstracts.

```python
from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder

embedder = MedrxivAbstractEmbedder(model_name="snowflake-arctic-embed2:latest")
embedder.embed_missing_abstracts(batch_size=100)
```

---

## Text Processing

Location: `localknowledge/textprocessing/`

### Chunking

Location: `localknowledge/textprocessing/chunking/`

#### Base Chunker

**File**: `localknowledge/textprocessing/chunking/base.py`

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Chunk:
    """Represents a text chunk."""
    text: str
    start: int
    end: int
    metadata: Dict[str, Any]

class BaseChunker:
    """Abstract base class for chunkers."""

    def chunk(self, text: str, metadata: Optional[Dict] = None, **kwargs) -> list[Chunk]:
        """Split text into chunks."""
        raise NotImplementedError
```

#### Text Chunker

**File**: `localknowledge/textprocessing/chunking/text_chunker.py`

Simple fixed-size chunking with overlap.

```python
from localknowledge.textprocessing.chunking import TextChunker

chunker = TextChunker(chunk_size=1000, overlap=200)
chunks = chunker.chunk("Long text to split...")

for chunk in chunks:
    print(f"Chunk: {chunk.text[:50]}...")
    print(f"Position: {chunk.start}-{chunk.end}")
```

#### Markdown Chunker

**File**: `localknowledge/textprocessing/chunking/markdown_chunker.py`

Markdown-aware hierarchical chunking.

```python
from localknowledge.textprocessing.chunking import MarkdownChunker

chunker = MarkdownChunker(
    max_chunk_size=1000,
    min_chunk_size=100,
    preserve_headers=True
)

chunks = chunker.chunk("""
# Introduction
Some text here...

## Methods
More text...

### Subsection
Details...
""")

# Chunks preserve markdown structure
for chunk in chunks:
    print(chunk.metadata.get('header_path', []))
```

### Keyword Extraction

Location: `localknowledge/textprocessing/keywords/`

#### PyTextRank Extractor

**File**: `localknowledge/textprocessing/keywords/pytextrank_extractor.py`

```python
from localknowledge.textprocessing.keywords.pytextrank_extractor import PyTextRankExtractor

extractor = PyTextRankExtractor()
keywords = extractor.extract(
    "Medical text about cardiovascular disease treatment...",
    max_keywords=10
)
# ['cardiovascular disease', 'treatment', 'patient', ...]
```

#### LLM Keyword Extractor

**File**: `localknowledge/textprocessing/llm_keyword_extractor.py`

```python
from localknowledge.textprocessing.llm_keyword_extractor import LLMKeywordExtractor

extractor = LLMKeywordExtractor(model_name="gemma3:4b")
keywords = extractor.extract("Medical text...", max_keywords=10)
```

### BM25 Search

**File**: `localknowledge/textprocessing/BM25/bm25_noindex.py`

Full-text search using BM25 algorithm.

```python
from localknowledge.textprocessing.BM25.bm25_noindex import BM25

bm25 = BM25()
bm25.fit(corpus=["doc1 text", "doc2 text", "doc3 text"])
scores = bm25.search("query terms")
```

---

## User Interface

Location: `localknowledge/ui/`

The UI is built with PySide6 using a plugin architecture.

### Plugin Base

**File**: `localknowledge/ui/plugin_base.py`

```python
from localknowledge.ui.plugin_base import PluginBase
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class MyPlugin(PluginBase):
    plugin_name = "My Plugin"
    plugin_description = "Description here"
    plugin_icon = "/path/to/icon.png"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hello from plugin!"))

    def initialize(self) -> bool:
        """Called when plugin is loaded."""
        return True

    def get_main_widget(self) -> QWidget:
        """Return the main widget."""
        return self

    def get_config_widget(self) -> QWidget:
        """Return configuration widget or None."""
        return None

    def save_state(self) -> dict:
        """Save plugin state."""
        state = super().save_state()
        state['my_setting'] = self.my_setting
        return state

    def restore_state(self, state: dict) -> bool:
        """Restore plugin state."""
        super().restore_state(state)
        self.my_setting = state.get('my_setting', default)
        return True

    def close_plugin(self) -> bool:
        """Cleanup before closing."""
        return True
```

### Built-in Plugins

| Plugin | File | Purpose |
|--------|------|---------|
| Knowledge Browser | `plugins/knowledge_browser.py` | Document search and viewing |
| News Browser | `plugins/news_browser.py` | Preprint discovery |
| Chat Interface | `plugins/chat_interface_plugin.py` | Chat-based interaction |
| Document Evaluator | `plugins/document_evaluator_plugin.py` | Relevance evaluation |
| Project Manager | `plugins/project_manager.py` | Project management |

### Main Window

**File**: `localknowledge/ui/pyside6_main_window.py`

Launch the main application:

```bash
python -m localknowledge.ui.pyside6_main_window
```

### Key UI Components

#### Knowledge Browser

**File**: `localknowledge/ui/knowledgebrowser.py`

Main search and document viewing widget.

```python
from localknowledge.ui.knowledgebrowser import KnowledgeBrowser

browser = KnowledgeBrowser()
browser.search("covid vaccine efficacy")
```

#### PDF Viewer

**File**: `localknowledge/ui/pdfviewer.py`

PDF rendering component.

```python
from localknowledge.ui.pdfviewer import PDFViewer

viewer = PDFViewer()
viewer.load_pdf("/path/to/document.pdf")
viewer.goto_page(5)
```

#### Document Display Widget

**File**: `localknowledge/ui/document_display_widget.py`

Abstract display with metadata.

```python
from localknowledge.ui.abstract_display_widget import AbstractDisplayWidget

widget = AbstractDisplayWidget()
widget.set_document(document_dict)
```

---

## MCP Server

Location: `localknowledge/mcp/` and `mcp_server/`

Model Context Protocol server for LLM integration.

### Server Implementation

**File**: `mcp_server/localknowledge_mcp_server.py`

```python
from mcp.server.fastmcp import FastMCP
from localknowledge.db.connection_pool import get_cursor

mcp = FastMCP("LocalPubmed Server")

@mcp.tool()
def search_pubmed_by_keywords(text: str) -> list | None:
    """Search documents by keywords."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM document WHERE search_vector @@ plainto_tsquery(%s)",
            (text,)
        )
        return cursor.fetchall()

@mcp.tool()
def get_document_details(document_id: int) -> dict | None:
    """Get document by ID."""
    # Implementation...

@mcp.tool()
def get_full_text(document_id: int) -> dict | None:
    """Get full text of document."""
    # Implementation...
```

### Running the Server

```bash
# stdio transport (for local use with Claude Desktop)
python mcp_server/localknowledge_mcp_server.py

# SSE transport (for remote connections)
python mcp_server/localknowledge_mcp_server.py --transport sse --port 8080
```

### Claude Desktop Configuration

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

---

## Context Management

**File**: `localknowledge/context.py`

Thread-safe singleton for sharing state across modules.

```python
from localknowledge.context import (
    context_manager,
    get_context,
    set_context,
    register_context_listener,
    unregister_context_listener,
    get_current_user,
    set_current_user,
    get_current_project,
    set_current_project,
    get_current_evaluator,
    set_current_evaluator,
    get_pdf_base_dir,
    set_pdf_base_dir
)

# Set values
set_context("my_key", "my_value")
set_current_user({"id": 1, "username": "researcher"})
set_current_project(42)

# Get values
value = get_context("my_key")
user = get_current_user()
project_id = get_current_project()

# Listen for changes
def on_user_change(new_user):
    print(f"User changed to: {new_user}")

register_context_listener("current_user", on_user_change)

# Unregister
unregister_context_listener("current_user", on_user_change)
```

### Context Keys

| Key | Purpose |
|-----|---------|
| `current_user` | Currently logged in user |
| `current_project` | Active research project ID |
| `current_evaluator` | Document evaluator configuration |
| `db_connection_params` | Database connection parameters |
| `pdf_base_dir` | PDF storage directory |

---

## Migration System

Location: `localknowledge/db/migrations_system/`

Versioned database migrations with tracking.

### Migration Manager

**File**: `localknowledge/db/migrations_system/manager.py`

```python
from localknowledge.db.migrations_system.manager import MigrationsManager

manager = MigrationsManager()

# Check current version
version = manager.get_current_version()

# Get pending migrations
pending = manager.get_pending_migrations()

# Run all pending migrations
success = manager.run_pending_migrations()

# Create new migration
path = manager.create_migration_template("add_new_feature")
```

### Creating Migrations

Migrations are stored in `localknowledge/db/migrations_system/migrations/` with naming format `NNN_description.py`:

```python
"""
Migration 006: Add new feature

This migration adds the new_feature table.
"""

import logging
from typing import Callable, Optional
from localknowledge.db.migrations_system.manager import MigrationsManager

logger = logging.getLogger(__name__)

def migrate(
    db_manager: MigrationsManager,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> None:
    """
    Run the migration.

    Args:
        db_manager: Database manager
        progress_callback: Optional progress callback (current, total, message)
    """
    logger.info("Starting migration 006")

    # Create table
    db_manager.execute("""
        CREATE TABLE IF NOT EXISTS new_feature (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """, commit=True)

    # Report progress
    if progress_callback:
        progress_callback(1, 1, "Created new_feature table")

    logger.info("Migration 006 completed")
```

### Running Migrations

```bash
# Check migration status
python -m localknowledge.db.migrations_system.check_migrations

# Run pending migrations
python -m localknowledge.db.migrations_system.run_migrations

# Create new migration
python -c "
from localknowledge.db.migrations_system.manager import MigrationsManager
m = MigrationsManager()
m.create_migration_template('my_migration')
"
```

---

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `POSTGRES_DB` | Database name | Required |
| `POSTGRES_USER` | Database user | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `DOTENV_FILE` | Path to .env file | `.env` |
| `PDF_BASE_DIR` | PDF storage directory | `~/knowledgebase/pdf` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | - |

### .env File Example

```bash
# Database
POSTGRES_DB=localknowledge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Storage
PDF_BASE_DIR=~/knowledgebase/pdf

# API Keys (optional)
OPENAI_API_KEY=sk-...
```

### pyproject.toml

```toml
[project]
name = "localknowledge"
version = "0.2.0"
requires-python = ">=3.12"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "isort>=5.0.0",
]
```

---

## API Reference

### Quick Reference

#### Database Operations
```python
# Document operations
from localknowledge.db.document import DocumentDatabaseManager
db = DocumentDatabaseManager()
doc = db.get_document(123)

# Search operations
from localknowledge.db.document_search import DocumentSearchManager
search = DocumentSearchManager()
results = search.search("query", limit=50)

# Embeddings
from localknowledge.db.embeddings import EmbeddingsDatabaseManager
emb_db = EmbeddingsDatabaseManager()
emb_db.add_embedding(doc_id, vector, model_name, source)
```

#### AI Operations
```python
# Hybrid search
from localknowledge.ai.hybrid_search import perform_hybrid_search
from localknowledge.embeddings.multiembeddings import EmbeddingManager
em = EmbeddingManager()
results = perform_hybrid_search(em, "query")

# Document evaluation
from localknowledge.ai.document_evaluator import DocumentEvaluator
evaluator = DocumentEvaluator()
result = evaluator.evaluate("question", doc_id)

# LLM query
from localknowledge.ai.ask_llm import generate_answer
answer = generate_answer("question", model_name="gemma3:4b")
```

#### Embeddings
```python
from localknowledge.embeddings.embedding_manager import EmbeddingManager
em = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")
vector = em.create_embedding("text")
results = em.search("query", limit=10)
```

#### Text Processing
```python
# Chunking
from localknowledge.textprocessing.chunking import TextChunker, MarkdownChunker
chunker = TextChunker(chunk_size=1000)
chunks = chunker.chunk("long text")

# Keywords
from localknowledge.textprocessing.keywords.pytextrank_extractor import PyTextRankExtractor
extractor = PyTextRankExtractor()
keywords = extractor.extract("text", max_keywords=10)
```

#### Context
```python
from localknowledge.context import (
    set_current_user, get_current_user,
    set_current_project, get_current_project,
    register_context_listener
)
set_current_user({"id": 1, "name": "User"})
```

---

## Appendix: File Locations

### Core Files

| Purpose | Location |
|---------|----------|
| Package init | `localknowledge/__init__.py` |
| Abstract base class | `localknowledge/base.py` |
| Context manager | `localknowledge/context.py` |
| Database base | `localknowledge/db/base.py` |
| Connection pool | `localknowledge/db/connection_pool.py` |
| Document manager | `localknowledge/db/document.py` |
| Embeddings manager | `localknowledge/db/embeddings.py` |
| Hybrid search | `localknowledge/ai/hybrid_search.py` |
| Document evaluator | `localknowledge/ai/document_evaluator.py` |
| Embedding manager | `localknowledge/embeddings/embedding_manager.py` |
| Text chunker | `localknowledge/textprocessing/chunking/text_chunker.py` |
| Plugin base | `localknowledge/ui/plugin_base.py` |
| MCP server | `mcp_server/localknowledge_mcp_server.py` |
| Migrations manager | `localknowledge/db/migrations_system/manager.py` |

### Test Files

| Purpose | Location |
|---------|----------|
| Test runner | `run_tests.py` |
| AI tests | `localknowledge/ai/tests/` |
| DB tests | `localknowledge/db/tests/` |
| Embedding tests | `localknowledge/embeddings/tests/` |
| UI tests | `localknowledge/ui/tests/` |
| Integration tests | `tests/` |

### Example Files

| Purpose | Location |
|---------|----------|
| Embedding example | `examples/embedding_example.py` |
| Task queue example | `examples/task_queue_example.py` |
| Knowledge browser | `examples/knowledgebrowser_with_projects.py` |
