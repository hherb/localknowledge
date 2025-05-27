# Test Module for Corrupt PubMed Import Fixer

This document describes the test module `test_fix_corrupt_pubmed_imports.py` which provides safe testing of the corrupt import fixer without modifying the live database.

## Overview

The test module creates mock database managers that simulate all database operations without actually executing them. This allows you to:

- Test the corruption detection logic
- Verify the fix process workflow
- See what database operations would be performed
- Get statistics on what would be changed
- Debug issues without risk to the live database

## Features

### Mock Database Managers

The test module includes mock versions of all database managers:

- `MockPubMedDatabaseManager`: Simulates PubMed article queries
- `MockDocumentDatabaseManager`: Simulates document table operations
- `MockChunkerDatabaseManager`: Simulates chunk operations
- `MockEmbeddingsDatabaseManager`: Simulates embedding operations

### Operation Logging

All database operations are logged with details about:
- Operation type (SELECT, UPDATE, INSERT, DELETE)
- Target table
- Query that would be executed
- Parameters that would be used
- Number of rows that would be affected

### Statistics Tracking

The test module tracks comprehensive statistics:
- Files processed
- Articles reprocessed
- Corrupted records found
- Records that would be updated
- Chunks that would be deleted/created
- Embeddings that would be deleted/created
- Errors encountered
- Corruption rate percentage

## Usage

### Basic Testing

Test with existing XML files:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml/files
```

### Create Sample XML Files

Create sample XML files for testing:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --create-sample-xml /tmp/test_xml
```

This creates 3 sample XML files that you can then use for testing:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /tmp/test_xml
```

### Limited Testing

Test with only a few files:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml --max-files 5
```

### Batch Size Testing

Test with different batch sizes:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml --batch-size 2000
```

### Debug Mode

Enable debug logging for detailed information:
```bash
python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml --log-level DEBUG
```

## Command Line Options

- `--xml-dir DIR`: Directory containing PubMed XML files (required unless using --create-sample-xml)
- `--batch-size N`: Number of records to process in each batch (default: 1000)
- `--max-files N`: Maximum number of XML files to process (default: all)
- `--log-level LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR; default: INFO)
- `--create-sample-xml DIR`: Create sample XML files for testing in the specified directory

## Sample Output

```
2025-05-27 11:39:45,862 - __main__ - INFO - *** THIS IS A TEST RUN - NO ACTUAL DATABASE CHANGES WILL BE MADE ***
2025-05-27 11:39:45,862 - __main__ - INFO - Found 3 XML files to process
2025-05-27 11:39:45,863 - __main__ - INFO - Found corruption in PMID 12345678: ['title', 'abstract', 'authors', 'mesh_terms']
2025-05-27 11:39:45,863 - __main__ - INFO - [MOCK] Would update corrupted record for PMID 12345678
2025-05-27 11:39:45,863 - __main__ - INFO - [MOCK] Would re-process chunks and embeddings for PMID 12345678

============================================================
MOCK CORRUPTION FIX TEST COMPLETED
============================================================
TEST MODE - SIMULATED RESULTS
Files processed: 2
Articles reprocessed: 2
Corrupted records found: 2
Records that would be updated: 2
Chunks that would be deleted: 4
Chunks that would be created: 4
Embeddings that would be deleted: 4
Embeddings that would be created: 4
Errors: 0
Corruption rate: 100.00%

Database operations that would have been performed:
  SELECT_document: 4
  UPDATE_document: 2
  SELECT_chunks: 2
  DELETE_embedding_base: 4
  DELETE_chunks: 4
  INSERT_chunks: 4
  INSERT_embedding_base: 4
Total database operations: 24
```

## Safety Features

1. **No Database Connections**: The mock managers don't connect to any real database
2. **Clear Labeling**: All output is clearly marked as "[MOCK]" or "TEST MODE"
3. **Operation Logging**: Every database operation is logged but not executed
4. **Statistics Only**: Only statistics and simulation results are provided

## Integration with Real Fixer

The test module uses the same logic as the real `fix_corrupt_pubmed_imports.py` module but with mock database operations. This ensures that:

- The corruption detection logic is identical
- The fix workflow is the same
- The statistics are accurate representations
- Any bugs in the logic will be caught during testing

## Recommended Workflow

1. **Create Sample Data**: Use `--create-sample-xml` to create test XML files
2. **Initial Test**: Run the test with sample data to verify basic functionality
3. **Limited Real Test**: Run with `--max-files 5` on real XML files to test with actual data
4. **Full Test**: Run on all XML files to get complete statistics
5. **Review Results**: Analyze the output to understand what would be changed
6. **Run Real Fixer**: Only after testing, run the real fixer with confidence

## Log Files

The test module creates a log file `test_fix_corrupt_imports.log` with detailed information about the test run, including all mock database operations and any errors encountered.
