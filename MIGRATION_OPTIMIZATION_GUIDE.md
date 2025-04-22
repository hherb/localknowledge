# Document Migration Optimization Guide

This guide provides step-by-step instructions for optimizing and restarting the document migration process to achieve maximum performance.

## Overview

The migration process can be significantly accelerated by:

1. Dropping indices during migration
2. Optimizing PostgreSQL parameters for bulk loading
3. Using larger batch sizes
4. Disabling foreign key constraints (optional)
5. Monitoring progress

## Step 1: Stop the Current Migration

If the migration is currently running, stop it safely:

```bash
# Find the process ID
ps aux | grep migrate_to_unified_document

# Stop the process
kill <process_id>
```

## Step 2: Optimize PostgreSQL for Migration

Use the provided script to optimize PostgreSQL settings:

```bash
# Optimize PostgreSQL settings
python scripts/optimize_postgres_for_migration.py --execute

# Drop existing indices if they exist
python scripts/optimize_postgres_for_migration.py --drop-indices

# Optionally disable foreign key constraints (use with caution)
python scripts/optimize_postgres_for_migration.py --disable-fk
```

## Step 3: Restart the Migration with Optimized Settings

Use the modified migration script that skips index creation:

```bash
# Run the migration with a large batch size
python -m localknowledge.db.migrations.migrate_to_unified_document_no_indices --execute --batch-size 10000
```

## Step 4: Monitor Migration Progress

In a separate terminal, monitor the progress:

```bash
# Monitor progress (adjust total count if needed)
python scripts/monitor_migration_progress.py --interval 60 --total 38000000
```

## Step 5: After Migration Completes

After the migration completes successfully:

```bash
# Create indices
python scripts/optimize_postgres_for_migration.py --create-indices

# Re-enable foreign key constraints (if disabled)
python scripts/optimize_postgres_for_migration.py --enable-fk

# Restore normal PostgreSQL settings
python scripts/optimize_postgres_for_migration.py --restore

# Update statistics
python scripts/optimize_postgres_for_migration.py --analyze
```

## Performance Expectations

With these optimizations:

- **Without Optimization**: Migration might take days
- **With Optimizations**: Migration could complete in hours (5-20x faster)

## Troubleshooting

### If Migration Fails

If the migration fails, you can safely restart it with the same commands. The migration uses idempotent operations that prevent duplicates.

### If PostgreSQL Performance Degrades

If you notice PostgreSQL performance degrading:

```bash
# Check PostgreSQL activity
psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Check for locks
psql -c "SELECT * FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE a.state = 'active';"
```

### Monitoring System Resources

Monitor system resources during migration:

```bash
# Monitor CPU and memory
top

# Monitor disk I/O
iostat -xm 5

# Monitor PostgreSQL
psql -c "SELECT pg_size_pretty(pg_database_size('localknowledge'));"
```

## Additional Notes

- The migration is designed to be restartable, so you can stop and restart it at any time
- Progress is preserved between runs due to idempotent operations
- Creating indices after migration is much faster than maintaining them during migration
- With 128GB RAM and 2TB disk space, you can be very aggressive with PostgreSQL settings

## Script Reference

### optimize_postgres_for_migration.py

```
Usage:
  python optimize_postgres_for_migration.py --execute    # Optimize for migration
  python optimize_postgres_for_migration.py --restore    # Restore normal settings
  python optimize_postgres_for_migration.py --drop-indices    # Drop indices
  python optimize_postgres_for_migration.py --create-indices  # Create indices
  python optimize_postgres_for_migration.py --disable-fk      # Disable foreign keys
  python optimize_postgres_for_migration.py --enable-fk       # Enable foreign keys
  python optimize_postgres_for_migration.py --analyze         # Update statistics
```

### monitor_migration_progress.py

```
Usage:
  python monitor_migration_progress.py --interval 60 --total 38000000
```

### migrate_to_unified_document_no_indices.py

```
Usage:
  python -m localknowledge.db.migrations.migrate_to_unified_document_no_indices --execute --batch-size 10000
  python -m localknowledge.db.migrations.migrate_to_unified_document_no_indices --execute --batch-size 10000 --create-indices
```
