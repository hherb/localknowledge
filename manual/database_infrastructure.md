# Database Infrastructure

## Overview

The Database Infrastructure module provides a centralized approach to database initialization, infrastructure checks, and schema migrations in the Local Knowledge system. It replaces the previous approach of having individual database managers create their own tables.

## Core Components

### Basic Infrastructure

The `basic_infrastructure.py` module provides functionality to check and ensure that the basic database infrastructure is in place:

- Database connection
- Required PostgreSQL extensions (pgvector)
- Database version

It performs these checks only once at startup and provides clear error messages when infrastructure requirements are not met.

### Baseline Database Creation

The `create_baseline_db.py` script provides a monolithic approach to creating the initial database schema:

- Creates all tables, indices, and extensions in a single transaction
- Should be run only once to initialize a new database
- After the initial setup, all schema changes should be done through migrations

### Migrations System

The migrations system (in the `migrations_system` package) provides a framework for managing database schema changes:

- Tracks the current database version
- Discovers available migrations
- Runs migrations in sequence
- Records migration success/failure

## Usage

### Initializing a New Database

To initialize a new database:

```bash
# Create the baseline database
python -m localknowledge.db.create_baseline_db

# Run any pending migrations
python -m localknowledge.db.migrations_system.run_migrations
```

### Checking Database Infrastructure

To check if the database infrastructure is valid:

```python
from localknowledge.db.basic_infrastructure import check_database_infrastructure

# Check infrastructure
is_valid, error_message = check_database_infrastructure()

if not is_valid:
    print(f"Database infrastructure check failed: {error_message}")
else:
    print("Database infrastructure is valid")
```

### Creating a New Migration

To create a new migration:

```bash
# Create a new migration
python -m localknowledge.db.migrations_system.create_migration add_new_column
```

### Running Migrations

To run pending migrations:

```bash
# Run all pending migrations
python -m localknowledge.db.migrations_system.run_migrations

# Check for pending migrations without running them
python -m localknowledge.db.migrations_system.run_migrations --check
```

## Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| version | Tracks database schema version and migration history |
| users | Stores user information and credentials |
| user_preferences | Stores user preferences |
| document | Unified document table for all content types |
| document_keywords | Stores keywords for documents |
| tags | Stores user-defined tags for documents |
| reading_records | Tracks user reading history |
| embedding_source | Defines sources for embeddings |
| unified_multiembeddings | Stores vector embeddings for documents |

### Legacy Tables (for backward compatibility)

| Table | Description |
|-------|-------------|
| preprints | Stores preprint metadata from MedRxiv (legacy) |
| pubmed_articles | Stores publication metadata from PubMed (legacy) |
| summaries | Stores document summaries (legacy) |
| embeddings | Stores vector embeddings (legacy) |
| qaembeddings | Stores question-answer pairs and embeddings (legacy) |

## Error Handling

The database infrastructure module provides specific exception classes for different types of errors:

- `DatabaseInfrastructureError`: Base exception for all infrastructure errors
- `DatabaseConnectionError`: Raised when database connection fails
- `DatabaseExtensionError`: Raised when required extensions are missing
- `DatabaseVersionError`: Raised when database version is incorrect

These exceptions include detailed error messages to help diagnose and fix issues.

## Best Practices

### Database Initialization

- Use `create_baseline_db.py` for initial database setup
- Use migrations for all schema changes after initial setup
- Always back up your database before running migrations

### Database Access

- Use the `DatabaseManager` class for database operations
- Let the infrastructure check happen automatically on first access
- Handle infrastructure errors appropriately in your application

### Creating Migrations

- Make migrations idempotent (can be run multiple times without side effects)
- Make migrations atomic (all changes succeed or all fail)
- Make migrations forward-only (no backward migrations)
- Make migrations non-destructive (preserve existing data when possible)
- Document migrations clearly

## Configuration

### Database Connection

Database connection parameters are configured through environment variables:

- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_HOST`: Database host
- `POSTGRES_PORT`: Database port

These can be set in a `.env` file in the project root.

### Migrations Directory

The migrations directory can be configured using the `RWB_MIGRATION_DIR` environment variable:

```bash
# Set the migrations directory
export RWB_MIGRATION_DIR=~/custom/migrations/dir
```

If not set, it defaults to `~/localknowledge/migrations`.
