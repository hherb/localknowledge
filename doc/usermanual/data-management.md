# Data Management

Learn how to import, update, and maintain your LocalKnowledge database.

## Understanding Your Database

LocalKnowledge stores:
- **Documents** - Articles from PubMed and medRxiv
- **Embeddings** - Vector representations for semantic search
- **Evaluations** - Your document relevance ratings
- **Projects** - Research organization
- **Users** - Account information

## Data Sources

### PubMed

PubMed provides:
- ~35 million biomedical citations
- Daily updates with new publications
- Baseline files for initial population
- Update files for keeping current

### medRxiv

medRxiv provides:
- Health sciences preprints
- Daily new submissions
- Full-text PDFs available
- Pre-peer-review research

## Initial Database Population

### Downloading PubMed Baseline

For a complete PubMed database:

```bash
# Download baseline files (large - ~30GB compressed)
python -m localknowledge.pubmed.async_download_cli --download-baseline
```

This downloads the complete PubMed baseline, which takes:
- Several hours to download
- 100GB+ disk space after extraction
- Days to import into database

> **Alternative:** Start with updates only for faster setup.

### Importing PubMed Data

After downloading:

```bash
# Import downloaded files
python -m localknowledge.pubmed.import_downloads
```

Import processes:
1. Parses XML files
2. Extracts article metadata
3. Inserts into database
4. Generates search vectors

### Initial medRxiv Population

For medRxiv preprints:

```bash
# Fetch and import recent preprints
python -m localknowledge.medrxiv.medrxiv_daily_update
```

This fetches the most recent medRxiv submissions.

## Keeping Data Current

### PubMed Updates

PubMed releases daily update files:

```bash
# Download and import updates
python -m localknowledge.pubmed.async_download_cli --download-updates

# Import the downloaded updates
python -m localknowledge.pubmed.import_downloads
```

### medRxiv Updates

Run daily for new preprints:

```bash
python -m localknowledge.medrxiv.medrxiv_daily_update
```

### Automating Updates

#### Using Cron (Linux/macOS)

Edit crontab:
```bash
crontab -e
```

Add entries:
```bash
# PubMed updates - daily at 2 AM
0 2 * * * cd /path/to/localknowledge && python -m localknowledge.pubmed.async_download_cli --download-updates

# medRxiv updates - daily at 3 AM
0 3 * * * cd /path/to/localknowledge && python -m localknowledge.medrxiv.medrxiv_daily_update
```

#### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Set daily trigger
4. Action: Start program
5. Program: `python`
6. Arguments: `-m localknowledge.pubmed.async_download_cli --download-updates`

## Generating Embeddings

Embeddings enable semantic search. Without them, you can only use keyword search.

### Generate All Embeddings

```bash
# Generate embeddings for all abstracts
python update_embeddings_for_abstracts.py
```

This process:
- Reads documents without embeddings
- Generates vector representations
- Stores in database
- Can be stopped and resumed

### Embedding Progress

Monitor embedding generation:
- Progress bar shows completion
- Can take hours for large databases
- Stop anytime with Ctrl+C
- Resumes where it left off

### Embedding Models

LocalKnowledge supports multiple embedding models:

| Model | Vector Size | Best For |
|-------|-------------|----------|
| snowflake-arctic-embed2 | 1024 | General use |
| pubmedbert | 768 | Medical text |

To use a different model:
```bash
# Pull the model first
ollama pull nomic-embed-text

# Generate with specific model
python update_embeddings_for_abstracts.py --model nomic-embed-text
```

## Database Maintenance

### Checking Database Health

```bash
# Run database tests
python run_tests.py --skip-baseline
```

### Database Statistics

View your database statistics in the UI:
1. Open Settings
2. Go to Database tab
3. View document counts, storage usage

Or via SQL:
```sql
-- Document counts by source
SELECT s.name, COUNT(d.id) as count
FROM document d
JOIN sources s ON d.source_id = s.id
GROUP BY s.name;

-- Embedding coverage
SELECT COUNT(*) as docs_with_embeddings
FROM unified_multiembeddings;
```

### Cleanup Operations

Remove orphaned data:
```bash
# Clean up zero vectors
python -m localknowledge.embeddings.cleanup_zero_vectors
```

### Vacuuming

Regularly vacuum PostgreSQL:
```sql
VACUUM ANALYZE document;
VACUUM ANALYZE unified_multiembeddings;
```

## Backup and Recovery

### Database Backup

```bash
# Full database backup
pg_dump localknowledge > localknowledge_backup.sql

# Compressed backup
pg_dump localknowledge | gzip > localknowledge_backup.sql.gz
```

### Database Restore

```bash
# Restore from backup
psql localknowledge < localknowledge_backup.sql

# Restore compressed
gunzip -c localknowledge_backup.sql.gz | psql localknowledge
```

### Backup Schedule

Recommended backup frequency:
- **Weekly** - Full database backup
- **Daily** - Evaluations and projects only (smaller)

### What to Back Up

Priority data:
1. **Evaluations** - Your work, not reproducible
2. **Projects** - Your organization
3. **User data** - Accounts, preferences

Reproducible data (lower priority):
- Documents (can re-download)
- Embeddings (can regenerate)

## Storage Management

### Disk Space Usage

Approximate storage needs:

| Component | Size |
|-----------|------|
| PubMed baseline | 100GB+ |
| medRxiv (all) | 10GB+ |
| Embeddings | 50GB+ |
| PDFs | Varies |

### Reducing Storage

If space is limited:
1. **Skip PDFs** - Store metadata only
2. **Limit date range** - Import only recent years
3. **Single embedding model** - Don't use multiple models
4. **Regular vacuuming** - Reclaim deleted space

### Moving Data Directory

To move PDF storage:

1. Update `.env`:
   ```bash
   PDF_BASE_DIR=/new/path/to/pdfs
   ```

2. Move existing files:
   ```bash
   mv ~/knowledgebase/pdf /new/path/to/pdfs
   ```

3. Update database paths (if needed)

## Data Migration

### Upgrading LocalKnowledge

When upgrading versions:

1. **Backup database** first
2. **Pull latest code**
3. **Run migrations**:
   ```bash
   python -m localknowledge.db.migrations_system.run_migrations
   ```
4. **Verify functionality**

### Migration System

LocalKnowledge tracks database versions:

```bash
# Check migration status
python -m localknowledge.db.migrations_system.check_migrations

# Run pending migrations
python -m localknowledge.db.migrations_system.run_migrations
```

## Troubleshooting Data Issues

### Missing Documents

If expected documents aren't found:
1. Verify import completed successfully
2. Check for import errors in logs
3. Re-run import for specific files

### Missing Embeddings

If semantic search returns poor results:
1. Check embedding count vs document count
2. Run embedding generation
3. Verify Ollama is running

### Corrupted Data

For data corruption:
1. Restore from backup
2. Re-import affected data
3. Regenerate embeddings

### Import Failures

If imports fail:
1. Check disk space
2. Verify database connection
3. Review error logs
4. Try importing in smaller batches

---

Previous: [MCP Integration](mcp-integration.md) | Next: [Troubleshooting](troubleshooting.md)
