# Task Queue System

## Overview

The Task Queue System provides thread-safe parallel processing capabilities for the LocalKnowledge project. It allows multiple workers to process documents concurrently without conflicts, supporting task chaining and comprehensive error handling.

## Architecture

The system consists of two main database tables:

### `task` Table
- `id`: Serial primary key
- `description`: Text description of the task type

### `processing_queue` Table
- `id`: Serial primary key
- `document_id`: Foreign key to document(id)
- `task_id`: Foreign key to task(id)
- `status`: Integer status (NULL=unprocessed, 1=processing, 2=finished, 3=error)
- `error`: Text error message (if applicable)
- `created`: Timestamp when queued
- `updated`: Timestamp when last updated

## TaskQueueManager Class

The `TaskQueueManager` class in `localknowledge.db.task_queue` provides all functionality for managing the task queue system.

### Core Methods

#### `get_pending_tasks(task_id: int) -> Generator[Tuple[int, int], None, None]`

Returns a generator that yields pending tasks for a specific task type. This method is thread-safe and uses `SELECT FOR UPDATE SKIP LOCKED` to ensure that multiple workers can safely claim tasks without conflicts.

**Parameters:**
- `task_id`: The task type ID to get pending work for

**Returns:**
- Generator yielding tuples of `(processing_queue_id, document_id)`

**Example:**
```python
queue_manager = TaskQueueManager()
for processing_queue_id, document_id in queue_manager.get_pending_tasks(chunking_task_id):
    # Process the document
    process_document(document_id)
    # Mark as completed
    queue_manager.task_done(processing_queue_id)
```

#### `task_done(processing_queue_id: int, next_task: Optional[int] = None) -> None`

Marks a task as completed. If `next_task` is provided, creates a new task for the same document.

**Parameters:**
- `processing_queue_id`: The processing queue entry ID to update
- `next_task`: Optional task_id for chaining to the next task

**Example:**
```python
# Mark as finished
queue_manager.task_done(processing_queue_id)

# Mark as finished and chain to next task
queue_manager.task_done(processing_queue_id, next_task=embedding_task_id)
```

#### `task_error(processing_queue_id: int, error_message: str) -> None`

Marks a task as failed with an error message.

**Parameters:**
- `processing_queue_id`: The processing queue entry ID to update
- `error_message`: Description of the error that occurred

### Task Management Methods

#### `add_task(description: str) -> int`

Creates a new task type.

**Parameters:**
- `description`: Description of the task type

**Returns:**
- The ID of the newly created task

#### `get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]`

Retrieves task information by ID.

#### `get_all_tasks() -> List[Dict[str, Any]]`

Returns all available task types.

#### `queue_document_for_task(document_id: int, task_id: int) -> int`

Queues a document for processing with a specific task.

**Parameters:**
- `document_id`: The document ID to process
- `task_id`: The task type ID

**Returns:**
- The processing queue entry ID

### Statistics and Monitoring

#### `get_queue_stats(task_id: Optional[int] = None) -> Dict[str, int]`

Returns statistics about the processing queue.

**Parameters:**
- `task_id`: If provided, get stats for specific task only

**Returns:**
- Dictionary with keys: `total`, `pending`, `processing`, `finished`, `error`

#### `get_failed_tasks(task_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]`

Returns tasks that failed with error status.

#### `reset_processing_tasks(task_id: Optional[int] = None) -> int`

Resets tasks stuck in 'processing' status back to pending. Useful for recovering from worker crashes.

## Thread Safety

The TaskQueueManager is designed for safe concurrent access:

1. **Atomic Task Claiming**: Uses `SELECT FOR UPDATE SKIP LOCKED` to ensure only one worker can claim a specific task
2. **Transaction Safety**: All status updates are performed within database transactions
3. **Connection Management**: Each worker should use its own TaskQueueManager instance for separate database connections

## Usage Patterns

### Basic Worker Pattern

```python
def worker_thread(worker_id: int, task_id: int):
    queue_manager = TaskQueueManager()
    
    try:
        for processing_queue_id, document_id in queue_manager.get_pending_tasks(task_id):
            try:
                # Process the document
                result = process_document(document_id)
                
                # Mark as completed
                queue_manager.task_done(processing_queue_id)
                
            except Exception as e:
                # Mark as failed
                queue_manager.task_error(processing_queue_id, str(e))
                
    finally:
        queue_manager.close()
```

### Task Chaining Pattern

```python
# Set up task chain: chunking -> embedding -> summarization
chunking_task_id = queue_manager.add_task("Document Chunking")
embedding_task_id = queue_manager.add_task("Generate Embeddings")
summary_task_id = queue_manager.add_task("Generate Summary")

# Process chunking and chain to embedding
for processing_queue_id, document_id in queue_manager.get_pending_tasks(chunking_task_id):
    try:
        chunk_document(document_id)
        queue_manager.task_done(processing_queue_id, next_task=embedding_task_id)
    except Exception as e:
        queue_manager.task_error(processing_queue_id, str(e))
```

### Parallel Processing Setup

```python
import threading

def start_workers(task_id: int, num_workers: int = 3):
    threads = []
    
    for i in range(num_workers):
        thread = threading.Thread(
            target=worker_thread,
            args=(i + 1, task_id),
            name=f"Worker-{i + 1}"
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all workers to complete
    for thread in threads:
        thread.join()
```

## Error Handling and Recovery

### Handling Worker Crashes

If workers crash or are terminated, tasks may be left in 'processing' status. Use `reset_processing_tasks()` to recover:

```python
# Reset all stuck processing tasks
reset_count = queue_manager.reset_processing_tasks()
print(f"Reset {reset_count} stuck tasks")

# Reset stuck tasks for specific task type only
reset_count = queue_manager.reset_processing_tasks(task_id=chunking_task_id)
```

### Monitoring Failed Tasks

```python
# Get failed tasks for review
failed_tasks = queue_manager.get_failed_tasks(limit=50)
for task in failed_tasks:
    print(f"Document {task['document_id']}: {task['error']}")
```

## Performance Considerations

1. **Index Usage**: The system creates an index on `(status, task_id)` for efficient pending task queries
2. **Connection Pooling**: Each worker should have its own database connection
3. **Batch Processing**: Consider processing multiple documents per transaction for better performance
4. **Monitoring**: Regularly check queue statistics to ensure healthy processing rates

## Best Practices

1. **Error Handling**: Always wrap document processing in try-catch blocks
2. **Resource Cleanup**: Use try-finally blocks to ensure database connections are closed
3. **Logging**: Log processing progress and errors for debugging
4. **Graceful Shutdown**: Implement signal handlers to allow workers to finish current tasks before shutdown
5. **Health Checks**: Monitor queue statistics and reset stuck tasks periodically
