# Unified Document Structure Migration

This directory contains scripts for migrating to the unified document structure.

## Overview

The migration process involves:

1. Creating the new document table structure
2. Migrating data from the original tables to the new document table
3. Updating embeddings references to point to the new document IDs
4. Updating QA embeddings references to point to the new document IDs
5. Migrating summaries to reference the document table
6. Migrating reading records to reference the document table
7. Populating document_keywords table from the document table
8. Migrating embeddings to the unified multiembeddings system
9. Verifying the migration was successful

## Migration Scripts

### Main Migration Scripts

- `init_document_tables.py`: Creates the new document table structure
- `migrate_to_unified_document.py`: Migrates data from the original tables to the new document table
- `migrate_to_unified_document_no_indices.py`: Same as above but without creating indices (for faster migration)
- `migrate_with_checkpoint.py`: Migration with checkpoint support to resume from where it left off

### Supporting Migration Scripts

- `update_embeddings_references.py`: Updates embeddings references to point to the new document IDs
- `update_qaembeddings_references.py`: Updates QA embeddings references to point to the new document IDs
- `migrate_embeddings.py`: Migrates embeddings to reference the document table
- `migrate_summaries.py`: Migrates summaries to reference the document table
- `migrate_reading_records.py`: Migrates reading records to reference the document table
- `populate_document_keywords.py`: Populates document_keywords table from the document table
- `migrate_to_unified_multiembeddings.py`: Migrates embeddings to the unified multiembeddings system
- `verify_migration.py`: Verifies the migration was successful
- `check_migration_status.py`: Checks the current status of the migration

### Utility Scripts

- `run_all_migrations.py`: Runs all migrations in the correct order
- `optimize_postgres_for_migration.py`: Optimizes PostgreSQL for migration
- `fix_postgres_wal.py`: Fixes PostgreSQL WAL settings
- `monitor_migration_progress.py`: Monitors migration progress

## Running the Migration

### Prerequisites

1. Backup your database before running the migration
2. Ensure you have enough disk space for the migration
3. Set up the environment variables for database connection

### Step 1: Optimize PostgreSQL for Migration

```bash
# Optimize PostgreSQL for migration
python scripts/optimize_postgres_for_migration.py --execute

# Drop indices for faster migration
python scripts/optimize_postgres_for_migration.py --drop-indices
```

### Step 2: Run the Main Migration

```bash
# Run the main migration with checkpoint support
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 20000

# Monitor progress
python scripts/monitor_migration_progress.py --interval 30 --total 38616116
```

If the migration slows down, you can restart PostgreSQL and continue:

```bash
# Fix PostgreSQL WAL settings
python scripts/fix_postgres_wal.py --optimize --data-dir <postgres_data_dir>

# Restart PostgreSQL
# For Postgres.app: open -a Postgres

# Resume migration
python -m localknowledge.db.migrations.migrate_with_checkpoint --execute --batch-size 20000
```

### Step 3: Run the Supporting Migrations

```bash
# Run all supporting migrations
python -m localknowledge.db.migrations.run_all_migrations --execute --batch-size 1000
```

### Step 4: Restore Normal PostgreSQL Settings

```bash
# Create indices
python scripts/optimize_postgres_for_migration.py --create-indices

# Restore normal PostgreSQL settings
python scripts/optimize_postgres_for_migration.py --restore

# Update statistics
python scripts/optimize_postgres_for_migration.py --analyze
```

### Step 5: Verify the Migration

```bash
python -m localknowledge.db.migrations.verify_migration
```

## Checking Migration Status

To check the current status of the migration:

```bash
python -m localknowledge.db.migrations.check_migration_status
```

## Compatibility Layer

A compatibility layer is provided to allow existing code to work with the new document structure. This layer provides adapters that mimic the behavior of the original database managers but use the new unified document structure internally.

Example usage:

```python
from localknowledge.db.compatibility import MedRxivCompatibilityAdapter, PubMedCompatibilityAdapter

# Use the compatibility adapters
medrxiv_adapter = MedRxivCompatibilityAdapter()
pubmed_adapter = PubMedCompatibilityAdapter()

# Get a preprint by DOI
preprint = medrxiv_adapter.get_preprint_by_doi("10.1101/2020.01.01.12345")

# Get a PubMed article by PMID
article = pubmed_adapter.get_article_by_pmid("12345678")

# Search for preprints
preprints = medrxiv_adapter.search_preprints("covid", limit=10)

# Search for PubMed articles
articles = pubmed_adapter.search_articles("cancer", limit=10)
```

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
# Fix WAL level setting
python scripts/fix_postgres_wal.py --fix --data-dir <postgres_data_dir>

# Then restart PostgreSQL
# For Postgres.app: open -a Postgres
```

## Rollback

If you need to roll back the migration, you can drop the new tables:

```sql
DROP TABLE IF EXISTS document_keywords;
DROP TABLE IF EXISTS document_embeddings;
DROP TABLE IF EXISTS document;
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS categories;
```

Note that this will permanently delete all data in these tables, so make sure you have a backup before proceeding.
