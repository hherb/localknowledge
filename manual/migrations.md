# Migrations System

## Overview

The Migrations System provides a framework for managing database schema changes in the Local Knowledge application. It tracks the current database version and applies migrations in sequence to ensure the database schema stays in sync with the application code.

## Core Components

### Migrations Manager

The `MigrationsManager` class in `localknowledge.db.migrations_system.manager` is the central component of the migrations system:

- Tracks the current database version
- Discovers available migrations
- Runs migrations in sequence
- Records migration success/failure

### Version Table

The migrations system uses a `version` table in the database to track applied migrations:

| Column | Type | Description |
|--------|------|-------------|
| version | INTEGER | Migration version number (unique) |
| migrated | TIMESTAMP | When the migration was applied |
| migration_success | BOOLEAN | Whether the migration was successful |

### Migration Scripts

Migration scripts are Python files that implement the actual schema changes:

- Located in the migrations directory (configurable via `RWB_MIGRATION_DIR` environment variable)
- Named with a version number prefix (e.g., `001_create_tables.py`)
- Implement a `migrate` function that performs the schema changes

## Usage

### Checking for Migrations

The migrations system automatically checks for pending migrations when the application starts:

```python
from localknowledge.db.migrations_system.check_migrations import check_migrations

# Check for pending migrations
has_pending, current_version, pending_count = check_migrations()

if has_pending:
    print(f"There are {pending_count} pending migrations. Database is at version {current_version}.")
```

### Running Migrations

Migrations can be run manually using the provided script:

```bash
# Run all pending migrations
python -m localknowledge.db.migrations_system.run_migrations

# Check for pending migrations without running them
python -m localknowledge.db.migrations_system.run_migrations --check
```

Or programmatically:

```python
from localknowledge.db.migrations_system import MigrationsManager

# Create a migrations manager
migrations_manager = MigrationsManager()

# Run pending migrations
success = migrations_manager.run_pending_migrations()

if success:
    print(f"Migrations completed successfully. New database version: {migrations_manager.get_current_version()}")
else:
    print("Migration process failed")
```

### Creating New Migrations

New migrations can be created using the provided script:

```bash
# Create a new migration
python -m localknowledge.db.migrations_system.create_migration add_new_column
```

This will create a new migration file with a template:

```python
"""
Migration 002: add_new_column

This migration script adds a new column to a table.
"""

import logging
from typing import Callable, Optional
from localknowledge.db.migrations_system.manager import MigrationsManager

# Configure logging
logger = logging.getLogger(__name__)


def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.
    
    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 002")
    
    # TODO: Implement migration logic here
    
    logger.info("Migration 002 completed")
```

## Configuration

### Migration Directory

The migrations directory can be configured using the `RWB_MIGRATION_DIR` environment variable:

```bash
# Set the migrations directory
export RWB_MIGRATION_DIR=~/custom/migrations/dir
```

If not set, it defaults to `~/localknowledge/migrations`.

### Progress Feedback

The migrations system supports progress feedback through callback functions:

```python
def progress_callback(current: int, total: int, message: str) -> None:
    """
    Handle progress updates.
    
    Args:
        current: Current progress value
        total: Total progress value
        message: Progress message
    """
    print(f"Progress: {current}/{total} - {message}")

# Create a migrations manager with progress callback
migrations_manager = MigrationsManager(progress_callback=progress_callback)
```

For GUI applications, the system can use `tqdm_gui` for progress display:

```python
# Run migrations with GUI progress bar
migrations_manager.run_pending_migrations(use_gui_tqdm=True)
```

## Integration with Application Startup

The migrations system is integrated with the application startup process:

1. When the application starts, it checks for pending migrations
2. If pending migrations are found, it prompts the user to run them
3. If the user chooses to run migrations, they are applied and the application restarts
4. If the user chooses not to run migrations, the application continues with the current schema

This ensures that the database schema stays in sync with the application code while giving the user control over when migrations are applied.

## Best Practices

### Writing Migrations

When writing migrations, follow these best practices:

1. **Idempotent**: Migrations should be idempotent (can be run multiple times without side effects)
2. **Atomic**: Migrations should be atomic (all changes succeed or all fail)
3. **Forward-only**: Migrations should only move forward, not backward
4. **Non-destructive**: Migrations should preserve existing data when possible
5. **Documented**: Migrations should include clear documentation of what they do

### Example Migration

Here's an example of a well-written migration:

```python
def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Add a new column to the users table.
    
    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration")
    
    # Check if column already exists
    result = db_manager.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'last_login';
    """)
    
    if not result:
        # Column doesn't exist, add it
        db_manager.execute("""
        ALTER TABLE users
        ADD COLUMN last_login TIMESTAMP WITH TIME ZONE;
        """, commit=True)
        logger.info("Added last_login column to users table")
    else:
        logger.info("last_login column already exists in users table")
    
    logger.info("Migration completed")
```

### Testing Migrations

Before applying migrations to a production database:

1. Test migrations on a development database
2. Create a backup of the production database
3. Verify that migrations preserve existing data
4. Have a rollback plan in case of failure
