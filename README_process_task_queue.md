# Task Queue Processor for Chunking Operations

## Overview

The `process_task_queue.py` script processes documents from the task queue that need chunking with the adaptive chunker. It's designed to work with the task queue system where task ID 1 represents chunking operations.

## Features

- **Thread-safe processing**: Uses TaskQueueManager with SELECT FOR UPDATE SKIP LOCKED
- **Chunk replacement**: Automatically deletes existing chunks before creating new ones
- **Graceful shutdown**: Handles SIGINT and SIGTERM signals
- **Progress tracking**: Optional progress bar and verbose logging
- **Error handling**: Marks failed tasks with error status

## Usage

### Basic Usage
```bash
python process_task_queue.py
```

### With Options
```bash
# Show progress bar and verbose logging (transitions to task_id=2)
python process_task_queue.py --verbose --progress

# Limit to processing 100 tasks
python process_task_queue.py --max-tasks 100

# Just mark as finished without transitioning to next task
python process_task_queue.py --no-next-task --verbose

# Transition to a different task ID (e.g., task_id=3)
python process_task_queue.py --next-task 3 --verbose

# Show help
python process_task_queue.py --help
```

### Command Line Options

- `--max-tasks N`: Maximum number of tasks to process (default: process until queue is empty)
- `--verbose`: Show detailed logging output
- `--progress`: Show progress bar with statistics
- `--next-task N`: Task ID to transition to after successful chunking (default: 2)
- `--no-next-task`: Don't transition to next task, just mark as finished

## How It Works

1. **Task Retrieval**: Gets pending tasks from the processing_queue table where task_id=1 and status IS NULL
2. **Document Loading**: Retrieves document details (id, title, abstract) from the database
3. **Chunk Deletion**: Removes any existing chunks for the document/strategy/type combination
4. **Text Chunking**: Processes the abstract using AdaptiveTextChunker with these parameters:
   - max_chunk_size: 1500
   - overlap: 100
   - min_chunk_size: 100
5. **Chunk Storage**: Inserts new chunks into the database
6. **Task Completion**: Marks the task as completed (status=2) and optionally transitions to next task (default: task_id=2)

## Task Queue Integration

The script integrates with the task queue system:

- **Task ID 1**: Chunking operations
- **Status Values**:
  - NULL: Unprocessed (pending)
  - 1: Processing (claimed by worker)
  - 2: Finished (completed successfully)
  - 3: Error (failed with error message)

## Parallel Processing

Multiple instances of this script can run simultaneously:
- Each instance claims tasks atomically using database locks
- No conflicts or duplicate processing
- Graceful shutdown preserves task state

## Testing

Use the included test script to verify functionality in READ-ONLY mode:

```bash
# Test the functionality without modifying live task queue data
python test_process_task_queue.py
```

**Important**: The test script operates in READ-ONLY mode to protect live task queue data. It simulates the processing without actually modifying the task queue table.

To run the actual processor on live data:

```bash
# Process actual tasks from the queue
python process_task_queue.py --verbose --progress

# Process with a limit to be safe
python process_task_queue.py --max-tasks 10 --verbose
```

## Configuration

The script uses these constants (can be modified if needed):

```python
CHUNKING_TASK_ID = 1  # Task ID for chunking operations
CHUNKING_STRATEGY_NAME = "adaptive_text_chunker_1500"
CHUNKTYPE_ID = 1  # ID for 'abstract' chunks
```

## Error Handling

- Documents without abstracts are skipped with warning
- Processing errors are logged and marked in the task queue
- Database connection issues trigger reconnection
- Graceful shutdown on interrupt signals

## Logging

By default, only warnings and errors are shown. Use `--verbose` for detailed output including:
- Task claiming and completion
- Chunk deletion and creation counts
- Processing statistics

## Dependencies

- localknowledge.db.task_queue.TaskQueueManager
- localknowledge.db.chunker.ChunkingDatabaseManager
- localknowledge.textprocessing.chunking.AdaptiveTextChunker
- Standard libraries: logging, argparse, time, signal, sys
- Third-party: tqdm (for progress bars)

## Performance

The script processes documents sequentially but can run in parallel with other instances. Processing speed depends on:
- Document length and complexity
- Database performance
- Chunking algorithm efficiency

Typical performance: 10-50 documents per minute depending on abstract length.
