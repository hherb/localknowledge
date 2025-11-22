# Database Module

This module provides the database layer for LocalKnowledge, including database managers, connection pooling, and schema migrations.

## Directory Structure

```
db/
├── base.py                    # Base DatabaseManager class
├── connection_pool.py         # Connection pooling utilities
├── document.py                # DocumentDatabaseManager
├── document_search.py         # DocumentSearchManager (semantic search)
├── embeddings.py              # EmbeddingsDatabaseManager
├── medrxiv.py                 # MedRxivDatabaseManager
├── pubmed.py                  # PubMedDatabaseManager
├── project.py                 # ProjectDatabaseManager
├── evaluations.py             # EvaluationsDatabaseManager
├── hypotheses.py              # HypothesesDatabaseManager
├── research_questions.py      # ResearchQuestionsManager
├── compatibility.py           # Legacy compatibility adapters
├── migrations/                # One-time migration scripts
└── migrations_system/         # Versioned migration framework
```

## Migration Systems

LocalKnowledge has **two complementary migration systems**:

### 1. `migrations/` - One-Time Migration Scripts

This directory contains migration scripts for major schema changes that are run once during significant architectural transitions. These are typically used for:

- Initial setup of new table structures
- Large data migrations between schema versions
- One-time cleanup operations

**Usage:**
```bash
python -m localknowledge.db.migrations.run_all_migrations --execute
```

See `migrations/README.md` for detailed documentation.

### 2. `migrations_system/` - Versioned Migration Framework

This is the ongoing migration system for incremental schema changes. It provides:

- Automatic version tracking
- Sequential migration execution
- Rollback support (where implemented)

**Usage:**
```bash
# Check migration status
python -m localknowledge.db.migrations_system.check_migrations

# Run pending migrations
python -m localknowledge.db.migrations_system.run_migrations

# Create a new migration
python -m localknowledge.db.migrations_system.create_migration "description"
```

**When to use which:**

| Use Case | Which System |
|----------|--------------|
| Initial database setup | `migrations/` |
| Major schema redesign | `migrations/` |
| Adding a new column | `migrations_system/` |
| Creating a new table | `migrations_system/` |
| Incremental improvements | `migrations_system/` |

## Database Managers

### DocumentDatabaseManager

The primary manager for unified document access across all sources (PubMed, medRxiv, etc.).

```python
from localknowledge.db.document import DocumentDatabaseManager

db = DocumentDatabaseManager()
doc = db.get_document(document_id)
```

### DocumentSearchManager

Provides semantic search capabilities using vector embeddings.

```python
from localknowledge.db.document_search import DocumentSearchManager

search = DocumentSearchManager()
results = search.semantic_search(query_embedding, limit=10)
```

### Connection Pool

For concurrent database access, use the connection pool:

```python
from localknowledge.db.connection_pool import get_cursor

with get_cursor() as cursor:
    cursor.execute("SELECT * FROM document LIMIT 10")
    results = cursor.fetchall()
```

## Environment Configuration

Database connection is configured via environment variables:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledgebase
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

Or use a `.env` file and set `DOTENV_FILE` to its path.
