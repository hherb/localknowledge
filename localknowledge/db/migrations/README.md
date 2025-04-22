# Unified Document Structure Migration

This directory contains scripts for migrating to the unified document structure.

## Overview

The migration process involves:

1. Creating the new document table structure
2. Migrating data from the original tables to the new document table
3. Updating embeddings references to point to the new document IDs
4. Verifying the migration was successful

## Migration Scripts

- `init_document_tables.py`: Creates the new document table structure
- `migrate_to_unified_document.py`: Migrates data from the original tables to the new document table
- `update_embeddings_references.py`: Updates embeddings references to point to the new document IDs
- `verify_migration.py`: Verifies the migration was successful
- `check_migration_status.py`: Checks the current status of the migration

## Running the Migration

The migration should be run in the following order:

1. Initialize the document tables:
   ```
   python -m localknowledge.db.init_document_tables
   ```

2. Migrate data to the new document table:
   ```
   python -m localknowledge.db.migrations.migrate_to_unified_document --execute
   ```

3. Update embeddings references:
   ```
   python -m localknowledge.db.migrations.update_embeddings_references --execute
   ```

4. Verify the migration:
   ```
   python -m localknowledge.db.migrations.verify_migration
   ```

## Checking Migration Status

To check the current status of the migration:

```
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

## Rollback

If you need to roll back the migration, you can drop the new tables:

```sql
DROP TABLE IF EXISTS document_embeddings;
DROP TABLE IF EXISTS document;
DROP TABLE IF EXISTS sources;
```

Note that this will permanently delete all data in these tables, so make sure you have a backup before proceeding.
