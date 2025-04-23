# Document Migration Optimization Guide

This guide provides step-by-step instructions for optimizing and restarting the document migration process to achieve maximum performance.

## Overview

The migration process can be significantly accelerated by:

1. Dropping indices during migration
2. Optimizing PostgreSQL parameters for bulk loading
3. Using larger batch sizes
4. Disabling foreign key constraints (optional)
5. Monitoring progress
6. Periodically restarting PostgreSQL to prevent slowdowns
7. Using checkpoints to resume from where you left off

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

## Step 5: Handling Slowdowns During Migration

If the migration slows down significantly (usually after 60-70% completion):

```bash
# Stop the current migration process
# Then restart PostgreSQL
sudo systemctl restart postgresql

# Optimize WAL settings for large migrations
python scripts/optimize_postgres_for_migration.py --wal-settings

# Restart the migration with checkpoint support and larger batch size
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 20000
```

You may need to repeat this process multiple times during a very large migration.

## Step 6: Using Segmented Migration for Very Large Datasets

For extremely large datasets, you can split the migration into segments:

```bash
# Migrate first segment (records 0-10M)
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000 --start-id 0 --end-id 10000000

# Restart PostgreSQL
sudo systemctl restart postgresql

# Migrate second segment (records 10M-20M)
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000 --start-id 10000000 --end-id 20000000

# And so on...
```

## Step 7: After Migration Completes

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

If the migration fails, you can safely restart it with the checkpoint-enabled script:

```bash
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000
```

The checkpoint system will resume from where it left off.

### If PostgreSQL Performance Degrades

If you notice PostgreSQL performance degrading:

```bash
# Check PostgreSQL activity
psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Check for locks
psql -c "SELECT * FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE a.state = 'active';"

# Check WAL status
psql -c "SELECT pg_current_wal_lsn(), pg_walfile_name(pg_current_wal_lsn());"
```

### If You Get WAL Streaming Error

If you see an error like "WAL streaming requires wal_level 'replica' or 'logical'":

```bash
# Fix WAL level setting by directly editing configuration files
python scripts/fix_postgres_wal.py --fix

# Then restart PostgreSQL
sudo systemctl start postgresql
```

If you need to optimize WAL settings after fixing the issue:

```bash
# Optimize WAL settings
python scripts/fix_postgres_wal.py --optimize

# Then restart PostgreSQL
sudo systemctl start postgresql
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

# Monitor WAL size
psql -c "SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0'));"
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
  python optimize_postgres_for_migration.py --execute       # Optimize for migration
  python optimize_postgres_for_migration.py --restore       # Restore normal settings
  python optimize_postgres_for_migration.py --drop-indices  # Drop indices
  python optimize_postgres_for_migration.py --create-indices # Create indices
  python optimize_postgres_for_migration.py --disable-fk    # Disable foreign keys
  python optimize_postgres_for_migration.py --enable-fk     # Enable foreign keys
  python optimize_postgres_for_migration.py --analyze       # Update statistics
  python optimize_postgres_for_migration.py --wal-settings  # Optimize WAL settings
```

### fix_postgres_wal.py

```
Usage:
  python scripts/fix_postgres_wal.py --fix        # Fix WAL level setting
  python scripts/fix_postgres_wal.py --optimize   # Optimize WAL settings
  python scripts/fix_postgres_wal.py --restore    # Restore settings from backup
  python scripts/fix_postgres_wal.py --data-dir /path/to/postgres/data  # Specify data directory
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

### migrate_with_checkpoint.py

```
Usage:
  # Resume migration from checkpoint
  python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000

  # Start fresh migration (ignore checkpoint)
  python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000 --reset-checkpoint

  # Migrate specific segment
  python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 10000 --start-id 1000000 --end-id 2000000
```
