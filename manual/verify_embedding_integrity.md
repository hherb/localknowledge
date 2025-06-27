# Embedding Integrity Verification Tool

## Overview

The `verify_embedding_integrity.py` script is a comprehensive tool for verifying the integrity of embeddings stored in the `emb_1024` table against their corresponding chunks in the `chunks` table. This tool helps ensure data consistency and identify potential issues in the embedding database.

## Purpose

This script addresses the need to verify that:
1. Each embedding in `emb_1024` references a valid chunk in the `chunks` table
2. Referenced chunks contain valid, non-empty text
3. Model references are valid
4. Chunk type references are valid
5. **CRITICAL**: The embedding vector actually corresponds to the chunk text it claims to represent
6. Optionally, identify chunks that don't have any embeddings (orphaned chunks)

## Features

- **Batch Processing**: Efficiently processes large numbers of embeddings in configurable batches
- **Content Verification**: Re-embeds chunk text and compares with stored embeddings to detect mismatches
- **Performance Monitoring**: Tracks verification speed and provides performance metrics
- **Issue Classification**: Categorizes issues by type and severity (ERROR, WARNING, INFO)
- **Flexible Sampling**: Supports testing with limited sample sizes
- **Orphaned Chunk Detection**: Optional feature to find chunks without embeddings
- **CSV Export**: Export detailed issue reports for further analysis
- **Connection Pooling**: Uses database connection pooling for optimal performance

## Usage

### Basic Usage

```bash
# Verify a sample of 1000 embeddings
python verify_embedding_integrity.py --sample-size 1000

# Verify all embeddings (can take a long time)
python verify_embedding_integrity.py

# Enable verbose logging
python verify_embedding_integrity.py --sample-size 100 --verbose
```

### Advanced Usage

```bash
# Check for orphaned chunks (slower)
python verify_embedding_integrity.py --sample-size 1000 --check-orphans

# CRITICAL: Verify embedding content matches chunk text (detects race conditions)
python verify_embedding_integrity.py --sample-size 100 --verify-content

# Content verification with custom similarity threshold
python verify_embedding_integrity.py --sample-size 100 --verify-content --similarity-threshold 0.90

# Export issues to CSV file
python verify_embedding_integrity.py --sample-size 5000 --export-issues issues.csv

# Adjust database connection pool
python verify_embedding_integrity.py --min-connections 5 --max-connections 15
```

## Command Line Options

- `--verbose`: Enable detailed logging output
- `--sample-size N`: Limit verification to N embeddings (useful for testing)
- `--check-orphans`: Also check for chunks without embeddings (can be slow)
- `--verify-content`: **CRITICAL** - Verify embeddings match their chunk text (detects race conditions)
- `--model MODEL`: Model name for content verification (default: snowflake-arctic-embed2:latest)
- `--similarity-threshold FLOAT`: Minimum similarity for content verification (default: 0.95)
- `--export-issues FILE.csv`: Export detailed issue report to CSV file
- `--min-connections N`: Minimum database connections in pool (default: 2)
- `--max-connections N`: Maximum database connections in pool (default: 5)

## Issue Types

The script identifies several types of integrity issues:

### Errors (Severity: ERROR)
- **missing_chunk**: Embedding references a chunk ID that doesn't exist in the chunks table
- **content_mismatch**: **CRITICAL** - Embedding vector doesn't match the chunk text (indicates race condition or data corruption)

### Warnings (Severity: WARNING)
- **empty_chunk_text**: Referenced chunk has empty or null text
- **missing_model**: Embedding references a model ID that doesn't exist
- **missing_chunktype**: Chunk references an invalid chunk type ID

### Information (Severity: INFO)
- **orphaned_chunk**: Chunk exists but has no corresponding embeddings

## Output

The script provides a comprehensive summary including:
- Total embeddings checked
- Success rate percentage
- Number of errors, warnings, and orphaned chunks
- Verification time and performance metrics
- Detailed breakdown of issues by type

### Example Output

```
================================================================================
EMBEDDING INTEGRITY VERIFICATION SUMMARY
================================================================================
Total embeddings checked: 1,000
Successfully verified: 998
Success rate: 99.80%
Errors found: 2
Warnings found: 0
Orphaned chunks: 0
Verification time: 2.25 seconds
Verification rate: 444.4 embeddings/second

ISSUES FOUND (2 total):
----------------------------------------

By severity:
  ERROR: 2

MISSING CHUNK (2 issues):
  - Embedding 1234 references non-existent chunk 5678
  - Embedding 2345 references non-existent chunk 6789
```

## Exit Codes

- `0`: No issues found (success)
- `1`: Errors found (critical issues)
- `2`: Warnings found (non-critical issues)

## Performance Considerations

- The script processes embeddings in batches of 1000 for optimal performance
- Use `--sample-size` for quick testing or when working with very large datasets
- The orphaned chunk check can be slow on large databases; use `--check-orphans` only when needed
- Adjust connection pool settings based on your database configuration and load

## Database Schema Requirements

The script expects the following database structure:
- `emb_1024` table inheriting from `embedding_base` with columns: `id`, `chunk_id`, `model_id`, `embedding`
- `chunks` table with columns: `id`, `document_id`, `text`, `document_title`, `chunktype_id`
- `chunktypes` table with columns: `id`, `chunktype`
- `embedding_models` table with columns: `id`, `model_name`

## Integration

This tool can be integrated into:
- Data quality monitoring pipelines
- Automated testing suites
- Database maintenance procedures
- CI/CD workflows for embedding system validation

## Troubleshooting

### Common Issues

1. **Connection timeouts**: Increase connection pool size or reduce batch size
2. **Memory issues**: Use smaller sample sizes for testing
3. **Slow orphaned chunk detection**: This is expected for large databases; consider running separately

### Performance Tuning

- Ensure proper database indices exist on `chunk_id` and `model_id` columns
- Monitor database connection pool usage
- Consider running during off-peak hours for full verification
