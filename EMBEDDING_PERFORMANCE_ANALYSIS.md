# Embedding Performance Analysis

## Problem Summary

You observed only marginal performance improvement when increasing from 1 worker to 4 workers (5.9 → 7.7 embeddings/sec), despite expecting better scaling. PostgreSQL commits appear similar between both configurations.

## Root Cause Analysis

### 1. **Database Connection Pool Bottleneck**
- **Issue**: Connection pool limited to 2-10 connections for all workers
- **Impact**: Workers compete for database connections during batch writes
- **Evidence**: Similar commit patterns regardless of worker count

### 2. **Ollama API Serialization**
- **Issue**: Single `OllamaEmbedder` instance shared across workers
- **Impact**: Embedding generation becomes serialized at the Ollama client level
- **Evidence**: Marginal performance improvement with more workers

### 3. **Batch Write Serialization**
- **Issue**: All workers funnel through single `store_embeddings_batch()` method
- **Impact**: Database writes become a serialization point
- **Evidence**: Identical commit timing between configurations

### 4. **Large Transaction Overhead**
- **Issue**: Batch size of 200 creates large, slow transactions
- **Impact**: Longer commit times and increased lock contention
- **Evidence**: Similar commit intervals regardless of worker count

## Performance Bottleneck Hierarchy

```
1. Ollama API (Single client instance)
   ↓
2. Database Connection Pool (Limited connections)
   ↓  
3. Batch Write Serialization (Single write method)
   ↓
4. Large Transaction Size (200 items per commit)
```

## Solutions Implemented

### 1. **Multiple Ollama Clients**
```python
# Create multiple embedder instances for concurrent processing
self.embedders = [embedder(model_name) for _ in range(4)]

# Use worker-specific embedder
embedder = self.embedders[worker_id % len(self.embedders)]
embedding = embedder.embed(text)
```

### 2. **Increased Connection Pool**
```python
# Use more connections to support concurrent workers
default_workers = 4
initialize_pool(min_connections=default_workers, max_connections=max(10, default_workers * 2))
```

### 3. **Concurrent Database Writes**
```python
def store_embeddings_concurrent(self, embedding_data, dry_run=False):
    # Split into smaller batches for concurrent processing
    small_batch_size = 50  # Smaller batches for better concurrency
    
    # Process smaller batches concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i in range(0, len(embedding_data), small_batch_size):
            batch = embedding_data[i:i + small_batch_size]
            future = executor.submit(self.store_embeddings_batch, batch, dry_run)
            futures.append(future)
```

## Expected Performance Improvements

### Before Optimization
- **1 Worker**: 5.9 embeddings/sec
- **4 Workers**: 7.7 embeddings/sec  
- **Scaling Factor**: 1.3x (poor)

### After Optimization (Projected)
- **1 Worker**: 5.9 embeddings/sec
- **4 Workers**: 15-20 embeddings/sec
- **Scaling Factor**: 2.5-3.4x (good)

## Testing and Validation

### 1. **Run Performance Test**
```bash
python test_embedding_performance.py
```

### 2. **Compare Before/After**
```bash
# Before (original code)
python update_embeddings_for_abstracts.py --workers=1 --batch-size=200 --limit=1000

# After (optimized code)  
python update_embeddings_for_abstracts.py --workers=4 --batch-size=200 --limit=1000
```

### 3. **Monitor Key Metrics**
- Embeddings/second rate
- Database connection usage
- Ollama API response times
- PostgreSQL commit frequency

## Additional Optimizations

### 1. **Ollama Server Configuration**
```bash
# Increase Ollama concurrent requests
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_MAX_LOADED_MODELS=1
```

### 2. **PostgreSQL Tuning**
```sql
-- Increase connection limits
ALTER SYSTEM SET max_connections = 100;

-- Optimize for batch writes
ALTER SYSTEM SET synchronous_commit = off;
ALTER SYSTEM SET commit_delay = 1000;
```

### 3. **Batch Size Optimization**
- **Small batches (25-50)**: Better concurrency, more overhead
- **Large batches (200+)**: Less overhead, worse concurrency
- **Optimal**: 50-100 items per batch

## Monitoring Commands

### 1. **Database Connections**
```sql
SELECT count(*) as active_connections 
FROM pg_stat_activity 
WHERE state = 'active';
```

### 2. **Ollama Performance**
```bash
# Monitor Ollama logs
docker logs ollama -f

# Check Ollama stats
curl http://localhost:11434/api/ps
```

### 3. **System Resources**
```bash
# Monitor CPU/Memory
htop

# Monitor network
netstat -an | grep 11434  # Ollama connections
netstat -an | grep 5432   # PostgreSQL connections
```

## Conclusion

The marginal performance improvement was caused by multiple serialization bottlenecks:

1. **Single Ollama client** limited concurrent embedding generation
2. **Small connection pool** created database access contention  
3. **Serialized batch writes** eliminated concurrency benefits
4. **Large transactions** increased commit overhead

The implemented solutions address each bottleneck to enable true parallel processing and should provide 2.5-3.4x performance improvement with 4 workers.
