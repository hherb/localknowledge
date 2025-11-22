# Troubleshooting

This guide helps you resolve common issues with LocalKnowledge.

## Application Won't Start

### Python Version Error

**Symptom:** "Python 3.12 or higher required"

**Solution:**
```bash
# Check your Python version
python --version

# Use specific Python version
python3.12 -m localknowledge.ui.pyside6_main_window
```

### Missing Dependencies

**Symptom:** ImportError for various modules

**Solution:**
```bash
# Reinstall dependencies
pip install -e .

# Or install specific missing package
pip install <package_name>
```

### PySide6 Issues

**Symptom:** GUI doesn't open, Qt errors

**Solution:**
```bash
# Reinstall PySide6
pip uninstall PySide6 PySide6-Essentials PySide6-Addons
pip install PySide6

# On Linux, install Qt dependencies
sudo apt install libxcb-xinerama0 libxcb-cursor0
```

### Database Connection Failed

**Symptom:** "Failed to connect to PostgreSQL"

**Solution:**
1. Verify PostgreSQL is running:
   ```bash
   # macOS
   brew services list | grep postgresql

   # Linux
   systemctl status postgresql
   ```

2. Check credentials in `.env`:
   ```bash
   cat .env
   ```

3. Test connection:
   ```bash
   psql -U your_user -d localknowledge -h localhost
   ```

## Search Problems

### No Search Results

**Possible causes and solutions:**

1. **Database is empty**
   - Import documents first (see [Data Management](data-management.md))

2. **No embeddings generated**
   - Run `python update_embeddings_for_abstracts.py`

3. **Threshold too high**
   - Lower similarity threshold to 0.3

4. **Query issue**
   - Try different wording
   - Use simpler terms

### Slow Search

**Possible causes and solutions:**

1. **Ollama not running**
   ```bash
   # Start Ollama
   ollama serve
   ```

2. **Large result set**
   - Reduce max results to 20-50
   - Increase threshold

3. **Missing indexes**
   ```sql
   -- Create indexes
   CREATE INDEX IF NOT EXISTS idx_document_search_vector
   ON document USING GIN(search_vector);
   ```

4. **Database needs vacuum**
   ```sql
   VACUUM ANALYZE document;
   VACUUM ANALYZE unified_multiembeddings;
   ```

### Irrelevant Results

**Solutions:**

1. Refine your query (see [Search Guide](search-guide.md))
2. Enable HyDE for better semantic matching
3. Use domain-specific medical terminology
4. Enable reranking

## Embedding Issues

### Embeddings Not Generating

**Symptom:** Embedding generation hangs or fails

**Solutions:**

1. **Check Ollama status**
   ```bash
   ollama list
   curl http://localhost:11434/api/tags
   ```

2. **Pull required model**
   ```bash
   ollama pull snowflake-arctic-embed2
   ```

3. **Check memory**
   - Embeddings require significant RAM
   - Close other applications
   - Use smaller model if needed

### Wrong Embedding Model

**Symptom:** Search results inconsistent

**Solution:**
- Verify you're using the same model for search and indexing
- Check Settings > Embedding Model

### Embedding Takes Too Long

**Solutions:**

1. Use smaller model
2. Process in batches:
   ```bash
   python update_embeddings_for_abstracts.py --batch-size 100
   ```
3. Let it run overnight

## Document Evaluation Issues

### Evaluation Fails

**Symptom:** "Error generating evaluation"

**Solutions:**

1. **Check Ollama**
   ```bash
   ollama run gemma3:4b "test"
   ```

2. **Try different model**
   - Change model in Evaluator Settings
   - Use smaller model for testing

3. **Check document exists**
   - Document may have been deleted
   - Abstract may be empty

### Inconsistent Ratings

**Solutions:**

1. Lower temperature (0.1-0.2)
2. Refine research question
3. Use larger model
4. Customize evaluation prompt

### Evaluation Too Slow

**Solutions:**

1. Use smaller model (gemma3:2b)
2. Reduce batch size
3. Check system resources

## PDF Issues

### PDFs Not Displaying

**Symptom:** "PDF not found" or blank viewer

**Solutions:**

1. **Check PDF_BASE_DIR**
   ```bash
   echo $PDF_BASE_DIR
   ls ~/knowledgebase/pdf
   ```

2. **Verify PDF exists**
   - Check the document's pdf_filename field
   - Look for file in PDF directory

3. **Re-download PDF**
   - Use document's pdf_url
   - Save to correct location

### PDF Rendering Issues

**Solutions:**

1. Update PyMuPDF:
   ```bash
   pip install --upgrade pymupdf
   ```

2. Check PDF is valid:
   ```bash
   # Open with system viewer
   open path/to/file.pdf  # macOS
   xdg-open path/to/file.pdf  # Linux
   ```

## Database Issues

### "pgvector extension not found"

**Solution:**
```sql
-- Connect to your database
psql -U postgres -d localknowledge

-- Create extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### Connection Pool Exhausted

**Symptom:** "Too many connections" or timeouts

**Solutions:**

1. Close unused database connections
2. Restart the application
3. Increase pool size:
   ```python
   from localknowledge.db.connection_pool import initialize_pool
   initialize_pool(max_connections=20)
   ```

### Migration Failures

**Symptom:** Migration errors on startup

**Solutions:**

1. **Check current version**
   ```sql
   SELECT * FROM version ORDER BY version DESC LIMIT 5;
   ```

2. **Run migrations manually**
   ```bash
   python -m localknowledge.db.migrations_system.run_migrations
   ```

3. **Restore from backup if needed**

### Database Corruption

**Symptoms:**
- Strange query results
- PostgreSQL errors

**Solutions:**

1. **Run PostgreSQL checks**
   ```bash
   pg_dump localknowledge > /dev/null
   ```

2. **Restore from backup**
   ```bash
   psql localknowledge < backup.sql
   ```

3. **Rebuild if no backup**
   - Re-import data
   - Regenerate embeddings

## MCP Issues

### Claude Can't Find LocalKnowledge

**Solutions:**

1. **Check config file syntax**
   - Must be valid JSON
   - Check for trailing commas

2. **Verify path is absolute**
   ```json
   "args": ["/full/absolute/path/to/mcp_server.py"]
   ```

3. **Restart Claude Desktop completely**

4. **Test server manually first**
   ```bash
   python mcp_server/localknowledge_mcp_server.py
   ```

### MCP Server Won't Start

**Solutions:**

1. **Check environment variables**
   - Set in config or shell

2. **Test database connection**
   ```bash
   psql -U your_user -d localknowledge
   ```

3. **Check for port conflicts** (SSE mode)
   ```bash
   lsof -i :8080
   ```

## Performance Issues

### Application Running Slowly

**Solutions:**

1. **Check system resources**
   - Memory usage
   - CPU load
   - Disk I/O

2. **Reduce data load**
   - Limit search results
   - Close unused plugins

3. **Optimize database**
   ```sql
   VACUUM ANALYZE;
   ```

4. **Clear caches**
   - Restart application
   - Clear temporary files

### High Memory Usage

**Solutions:**

1. Reduce result limits
2. Close PDF viewer when not needed
3. Use smaller embedding model
4. Process large operations in batches

### High Disk Usage

**Solutions:**

1. Remove unused PDFs
2. Vacuum database:
   ```sql
   VACUUM FULL document;
   ```
3. Remove old embeddings:
   ```sql
   DELETE FROM unified_multiembeddings WHERE created_at < '2023-01-01';
   ```

## Getting Help

If your issue isn't covered:

1. **Check logs**
   - Application logs
   - PostgreSQL logs
   - Ollama logs

2. **Search GitHub issues**
   - Your issue may be known
   - Solutions may exist

3. **Gather information**
   - Error messages
   - Steps to reproduce
   - System information

4. **Report issue**
   - GitHub issues page
   - Include all relevant details

## Diagnostic Commands

### Check Installation

```bash
# Python version
python --version

# Package versions
pip show localknowledge psycopg2 pyside6 ollama

# Database connection
psql -U your_user -d localknowledge -c "SELECT version();"
```

### Check Services

```bash
# PostgreSQL
pg_isready

# Ollama
curl http://localhost:11434/api/tags
```

### Check Data

```sql
-- Document count
SELECT COUNT(*) FROM document;

-- Embedding count
SELECT COUNT(*) FROM unified_multiembeddings;

-- Recent imports
SELECT source_id, COUNT(*)
FROM document
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY source_id;
```

---

Previous: [Data Management](data-management.md) | Next: [FAQ](faq.md)
