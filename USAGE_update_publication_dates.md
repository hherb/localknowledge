# Quick Usage Guide: Update Publication Dates Script

## Purpose
This script fixes empty `publication_date` fields in the `tmpdocument` table by reading PubMed XML files and updating only the publication date field. It's much faster than a full re-import.

## Quick Start

```bash
# Basic usage - update from XML files directory
python update_tmpdocument_publication_dates.py /path/to/xml/files

# With custom batch size (start small, increase if no timeout issues)
python update_tmpdocument_publication_dates.py /path/to/xml/files --batch-size 200
```

## What It Does

1. **Reads XML Files**: Processes all `.xml.gz` files in the specified directory
2. **Extracts Data**: Gets PMID and publication date from each PubMed article
3. **Updates Database**: Updates only the `publication_date` field in `tmpdocument` table
4. **Shows Progress**: Real-time progress bar and statistics

## Key Features

- ✅ **Fast**: Only extracts and updates publication dates
- ✅ **Safe**: Only updates existing records, doesn't create new ones
- ✅ **Robust**: Handles various date formats and continues on errors
- ✅ **Efficient**: Batch updates for optimal database performance
- ✅ **Logged**: Creates detailed log file for monitoring

## Expected Output

```
Processing XML files: 100%|████████| 50/50 [02:15<00:00, 2.70s/file]
INFO - Update completed:
INFO -   Total articles processed: 125,432
INFO -   Total records updated: 118,756
```

## Error Handling

The script handles:
- **Type Casting**: Properly converts text dates to PostgreSQL DATE type
- **NULL Values**: Skips articles without valid publication dates
- **Batch Errors**: Continues processing even if some batches fail
- **File Errors**: Logs errors and continues with next file

## Log File

Check `update_publication_dates.log` for:
- Detailed progress information
- Error messages and troubleshooting info
- Final statistics and timing

## Prerequisites

- `tmpdocument` table exists with records to update
- XML files are in gzipped format (`.xml.gz`)
- Database connection properly configured
- Python packages: `tqdm`, `xml.etree.ElementTree`

## Performance Tips

- **Batch Size**: Start with default (100), increase gradually if no timeout issues (try 200-500)
- **Monitor**: Watch the log file for any errors during processing
- **Database Load**: Run during low-usage periods for large datasets
- **Timeout Handling**: Script uses `execute_without_timeout` to avoid database timeouts

## Troubleshooting

If you see errors:
1. Check the log file for specific error messages
2. Verify database connection and permissions
3. Ensure XML files are not corrupted
4. Try with a smaller batch size if memory issues occur
