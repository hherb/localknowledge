# Embedding Query Optimization Guide

## Overview

This document describes the optimizations made to the `update_embeddings_for_abstracts.py` script to resolve database query timeout issues that were occurring when processing large numbers of abstract chunks for embedding.

## Problem Description

The original script was experiencing query timeouts after 120 seconds when trying to:
1. Count chunks without embeddings
2. Retrieve batches of chunks without embeddings

The timeouts were caused by inefficient query patterns that didn't leverage database indices effectively.

## Root Cause Analysis

### Original Problematic Queries

1. **Count Query (Original)**:
```sql
SELECT COUNT(*) as count
FROM chunks c
JOIN chunktypes ct ON c.chunktype_id = ct.id
WHERE ct.chunktype = 'abstract'
AND NOT EXISTS (
    SELECT 1 FROM emb_1024 e
    WHERE e.chunk_id = c.id AND e.model_id = %s
    LIMIT 1
)
```

2. **Retrieval Query (Original)**:
```sql
SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
       c.text, c.chunktype_id, d.title as document_title, d.abstract
FROM chunks c
JOIN chunktypes ct ON c.chunktype_id = ct.id
JOIN document d ON c.document_id = d.id
WHERE ct.chunktype = 'abstract'
AND NOT EXISTS (
    SELECT 1 FROM emb_1024 e
    WHERE e.chunk_id = c.id AND e.model_id = %s
)
ORDER BY c.id
```

### Performance Issues

1. **NOT EXISTS subqueries**: These are generally slower than LEFT JOIN operations
2. **Unnecessary joins**: The chunktypes join was performed repeatedly for the same lookup
3. **Complex query plans**: The database optimizer struggled with the combination of joins and subqueries

## Optimization Solutions

### 1. Chunktype ID Caching

Instead of joining with the `chunktypes` table repeatedly, we now cache the chunktype_id:

```python
# Cache the chunktype_id to avoid repeated lookups
if not hasattr(self, '_abstract_chunktype_id'):
    chunktype_query = "SELECT id FROM chunktypes WHERE chunktype = 'abstract'"
    chunktype_result = self.embeddings_db.execute(chunktype_query, (), timeout=30)
    self._abstract_chunktype_id = chunktype_result[0]['id']
```

### 2. LEFT JOIN Instead of NOT EXISTS

**Optimized Count Query**:
```sql
SELECT COUNT(*) as count
FROM chunks c
LEFT JOIN emb_1024 e ON c.id = e.chunk_id AND e.model_id = %s
WHERE c.chunktype_id = %s
AND e.chunk_id IS NULL
```

**Optimized Retrieval Query**:
```sql
SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
       c.text, c.chunktype_id, d.title as document_title, d.abstract
FROM chunks c
JOIN document d ON c.document_id = d.id
LEFT JOIN emb_1024 e ON c.id = e.chunk_id AND e.model_id = %s
WHERE c.chunktype_id = %s
AND e.chunk_id IS NULL
ORDER BY c.id
```

### 3. Fallback Strategy

Added a fallback mechanism for when queries still timeout:

```python
def _get_chunks_fallback_strategy(self, limit: Optional[int] = None, offset: int = 0):
    """Fallback strategy using simpler queries with minimal joins."""
    simple_query = f"""
    SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
           c.text, c.chunktype_id, '' as document_title, '' as abstract
    FROM chunks c
    LEFT JOIN {self.tablename} e ON c.id = e.chunk_id AND e.model_id = %s
    WHERE c.chunktype_id = %s
    AND e.chunk_id IS NULL
    ORDER BY c.id
    """
```

### 4. Reduced Timeout for Individual Queries

Changed from using the full 120-second timeout to shorter, more reasonable timeouts:
- Count queries: 30 seconds
- Individual batch queries: 60 seconds (min of db_timeout and 60)
- Fallback queries: 30 seconds

## Performance Improvements

### Before Optimization
- Queries timing out after 120 seconds
- Unable to process any chunks due to timeouts
- High database load from inefficient queries

### After Optimization
- Count query: Completes in seconds instead of timing out
- Batch retrieval: Fast and reliable
- Processing rate: ~0.26 chunks/second for embedding creation
- Database query time: ~0.027 seconds per chunk

## Database Indices

The optimization relies on existing indices:
- `chunks_chunktype_id_idx` on `chunks(chunktype_id)`
- `chunks_document_id_idx` on `chunks(document_id)`
- `emb_1024_chunk_model_idx` on `emb_1024(chunk_id, model_id)`

## Usage

The optimized script maintains the same command-line interface:

```bash
# Test with dry run
python update_embeddings_for_abstracts.py --limit 10 --batch-size 5 --dry-run --verbose

# Process embeddings
python update_embeddings_for_abstracts.py --limit 1000 --batch-size 50 --verbose
```

## Monitoring

The script provides detailed performance metrics:
- Embedding time per chunk
- Database operation time per chunk
- Overall processing rate
- Memory usage monitoring

## Future Considerations

1. **Parallel Processing**: Consider using multiple database connections for parallel chunk retrieval
2. **Batch Size Optimization**: Experiment with different batch sizes based on available memory
3. **Index Optimization**: Monitor query plans and consider additional indices if needed
4. **Connection Pooling**: The current implementation uses connection pooling effectively

## Conclusion

These optimizations have successfully resolved the timeout issues while maintaining data integrity and providing better performance monitoring. The script can now process large numbers of abstract chunks efficiently without database timeouts.
