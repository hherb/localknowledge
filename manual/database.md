# Database Module

## Overview

The Database Module provides a foundation for all data storage and retrieval operations in the Local Knowledge system. It implements a PostgreSQL-based storage solution with specialized extensions for vector operations and full-text search.

## Core Components

### Base Database Manager

The `DatabaseManager` class in `localknowledge.db.base` provides core database functionality:

- Connection management
- Transaction handling
- Query execution
- Error handling

All specialized database managers inherit from this base class.

### Specialized Database Managers

The system includes several specialized database managers:

- `MedRxivDatabaseManager`: Manages preprint data from MedRxiv
- `PubMedDatabaseManager`: Manages publication data from PubMed
- `UserDatabaseManager`: Manages user data and preferences
- `ReadingTrackerManager`: Tracks reading history and annotations
- `EmbeddingDatabaseManager`: Manages vector embeddings for semantic search
- `QAEmbeddingDatabaseManager`: Manages question-answer pairs and their embeddings
- `TaskQueueManager`: Manages parallel task processing with thread-safe operations

## Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| preprints | Stores preprint metadata from MedRxiv |
| pubmed | Stores publication metadata from PubMed |
| users | Stores user information and preferences |
| reading_tracker | Tracks reading history and annotations |
| embeddings | Stores vector embeddings for semantic search |
| qaembeddings | Stores question-answer pairs and their embeddings |
| import_tracker | Tracks PubMed file processing status (imported, chunked, embedded, md5checked) |
| task | Stores task type definitions (id, description) |
| processing_queue | Manages document processing queue with status tracking |

### Schema Management

The database schema is managed through:

- `localknowledge.db.createdb`: Creates and initializes the database
- Migration scripts: Handle schema changes while preserving data

## Usage Examples

### Basic Database Operations

```python
from localknowledge.db.base import DatabaseManager

# Create a database manager
db = DatabaseManager()

# Execute a query
results = db.execute("SELECT * FROM preprints LIMIT 10")

# Process results
for row in results:
    print(row['doi'], row['title'])

# Close the connection
db.close()
```

### Using Specialized Managers

```python
from localknowledge.db.medrxiv import MedRxivDatabaseManager

# Create a MedRxiv database manager
medrxiv_db = MedRxivDatabaseManager()

# Get recent preprints
preprints = medrxiv_db.get_recent_preprints(limit=10)

# Process preprints
for preprint in preprints:
    print(preprint['doi'], preprint['title'])

# Close the connection
medrxiv_db.close()
```

### Task Queue Management

The `TaskQueueManager` provides thread-safe parallel task processing:

```python
from localknowledge.db.task_queue import TaskQueueManager

# Create a task queue manager
queue_manager = TaskQueueManager()

# Create task types
chunking_task_id = queue_manager.add_task("Document Chunking")
embedding_task_id = queue_manager.add_task("Generate Embeddings")

# Queue documents for processing
for doc_id in range(1, 101):
    queue_manager.queue_document_for_task(doc_id, chunking_task_id)

# Process tasks (typically in worker threads)
for processing_queue_id, document_id in queue_manager.get_pending_tasks(chunking_task_id):
    try:
        # Process the document
        process_document(document_id)

        # Mark as completed and chain to next task
        queue_manager.task_done(processing_queue_id, next_task=embedding_task_id)

    except Exception as e:
        # Mark as failed
        queue_manager.task_error(processing_queue_id, str(e))

# Get processing statistics
stats = queue_manager.get_queue_stats(chunking_task_id)
print(f"Pending: {stats['pending']}, Processing: {stats['processing']}, "
      f"Finished: {stats['finished']}, Errors: {stats['error']}")

queue_manager.close()
```

#### Thread Safety

The TaskQueueManager uses `SELECT FOR UPDATE SKIP LOCKED` to ensure thread-safe task claiming:

- Multiple workers can safely process tasks in parallel
- No task will be processed by multiple workers simultaneously
- Workers automatically skip locked tasks and move to the next available task

#### Status Values

The processing queue uses integer status values:

- `NULL`: Unprocessed (pending)
- `1`: Currently being processed
- `2`: Successfully completed
- `3`: Failed with error

#### Task Chaining

Tasks can be chained together by specifying `next_task` in `task_done()`:

```python
# Complete current task and create next task for same document
queue_manager.task_done(processing_queue_id, next_task=embedding_task_id)
```

### Transactions

```python
from localknowledge.db.base import DatabaseManager

# Create a database manager
db = DatabaseManager()

# Begin a transaction
db.begin_transaction()

try:
    # Execute multiple queries as part of the transaction
    db.execute("INSERT INTO users (username, email) VALUES (%s, %s)",
               ("user1", "user1@example.com"), commit=False)
    db.execute("INSERT INTO user_preferences (user_id, key, value) VALUES (%s, %s, %s)",
               (1, "theme", "dark"), commit=False)

    # Commit the transaction
    db.commit_transaction()
except Exception as e:
    # Roll back the transaction on error
    db.rollback_transaction()
    print(f"Error: {e}")
finally:
    # Close the connection
    db.close()
```

## Configuration

Database connection parameters are configured in `localknowledge.db.config`:

```python
# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'localknowledge',
    'user': 'postgres',
    'password': 'password'
}
```

Environment variables can override these settings:

- `LK_DB_HOST`: Database host
- `LK_DB_PORT`: Database port
- `LK_DB_NAME`: Database name
- `LK_DB_USER`: Database user
- `LK_DB_PASSWORD`: Database password

## Extensions

The database uses several PostgreSQL extensions:

- `pgvector`: Provides vector operations for embeddings
- `pg_trgm`: Provides trigram matching for text search
- `fuzzystrmatch`: Provides fuzzy string matching

These extensions must be installed in the PostgreSQL instance.

## Performance Considerations

### Indexing

The database uses several types of indices for optimal performance:

- B-tree indices for primary keys and foreign keys
- GIN indices for full-text search
- IVFFlat indices for vector similarity search

### Query Optimization

For optimal performance:

- Use parameterized queries to avoid SQL injection and improve query planning
- Limit result sets to avoid memory issues
- Use transactions for batch operations
- Use indices for frequently queried columns

### Connection Pooling

For production deployments, consider using connection pooling:

```python
from psycopg2.pool import ThreadedConnectionPool

# Create a connection pool
pool = ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host='localhost',
    port=5432,
    database='localknowledge',
    user='postgres',
    password='password'
)

# Get a connection from the pool
conn = pool.getconn()

# Return the connection to the pool
pool.putconn(conn)
```

## Maintenance

### Backup and Restore

To back up the database:

```bash
pg_dump -U postgres -d localknowledge -F c -f backup.dump
```

To restore from a backup:

```bash
pg_restore -U postgres -d localknowledge -c backup.dump
```

### Database Migrations

When changing the database schema:

1. Create a migration script in `localknowledge.db.migrations`
2. Test the migration on a copy of the production database
3. Apply the migration to the production database

Example migration script:

```python
from localknowledge.db.base import DatabaseManager

def migrate():
    """Add a new column to the preprints table."""
    db = DatabaseManager()
    try:
        db.execute("ALTER TABLE preprints ADD COLUMN abstract_length INTEGER")
        db.execute("UPDATE preprints SET abstract_length = LENGTH(abstract)")
        print("Migration successful")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
```

### Monitoring

Monitor database performance using:

- PostgreSQL logs
- pg_stat_statements for query statistics
- Regular VACUUM and ANALYZE operations

## Troubleshooting

### Common Issues

1. **Connection Errors**: Check network connectivity, credentials, and PostgreSQL service status.

2. **Query Performance**: Use EXPLAIN ANALYZE to identify slow queries and optimize them.

3. **Memory Issues**: Limit result sets and use cursors for large queries.

4. **Extension Errors**: Ensure all required extensions are installed.

### Debugging

For detailed debugging:

1. Enable verbose logging in PostgreSQL:
   ```sql
   ALTER SYSTEM SET log_statement = 'all';
   SELECT pg_reload_conf();
   ```

2. Set the logging level in the application:
   ```python
   import logging
   logging.getLogger('localknowledge.db').setLevel(logging.DEBUG)
   ```

3. Use connection tracing:
   ```python
   import psycopg2.extras
   psycopg2.extras.register_default_jsonb()
   ```
