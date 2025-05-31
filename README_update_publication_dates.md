# Update Publication Dates Script

## Overview

The `update_tmpdocument_publication_dates.py` script efficiently updates only the `publication_date` field in the `tmpdocument` table by reading PubMed XML files and updating existing records. This is much faster than a full re-import since it only updates the publication date field.

## Purpose

This script was created to fix the issue where `publication_date` fields were empty in imported PubMed records. Instead of re-importing all data (which would take too long), this script:

1. Reads PubMed XML files from a specified directory
2. Extracts PMID and publication date from each article
3. Updates only the `publication_date` field in the `tmpdocument` table
4. Shows progress and provides statistics

## Usage

```bash
# Basic usage
python update_tmpdocument_publication_dates.py /path/to/xml/files

# With custom batch size
python update_tmpdocument_publication_dates.py /path/to/xml/files --batch-size 2000
```

## Arguments

- `xml_dir`: Directory containing PubMed XML files (required)
- `--batch-size`: Number of updates to process in each batch (default: 1000)

## Features

### Efficient Processing
- **Memory Efficient**: Uses `iterparse` to process large XML files without loading them entirely into memory
- **Batch Updates**: Updates records in batches to optimize database performance
- **Progress Tracking**: Shows real-time progress with file-by-file processing

### Robust Date Extraction
- **Multiple Date Formats**: Handles both numeric ("03") and text ("Mar", "March") month formats
- **Sensible Defaults**: Provides defaults for missing day/month information
- **Error Handling**: Continues processing even if individual articles have issues

### Database Safety
- **Targeted Updates**: Only updates the `publication_date` field, leaving other data unchanged
- **Transaction Safety**: Uses proper database transactions for batch updates
- **Source Filtering**: Only updates records from the 'pubmed' source

## Date Format Handling

The script handles various PubMed date formats:

- **Full Date**: `<Year>2023</Year><Month>06</Month><Day>15</Day>` → "2023-06-15"
- **Text Month**: `<Year>2023</Year><Month>Jun</Month><Day>15</Day>` → "2023-06-15"
- **Year and Month**: `<Year>2023</Year><Month>Mar</Month>` → "2023-03-01"
- **Year Only**: `<Year>2023</Year>` → "2023-01-01"

## Output

The script provides:

1. **Real-time Progress**: Shows current file being processed and statistics
2. **Log File**: Creates `update_publication_dates.log` with detailed information
3. **Final Statistics**: Total articles processed and records updated

Example output:
```
Processing XML files: 100%|████████| 50/50 [02:15<00:00, 2.70s/file]
INFO - Update completed:
INFO -   Total articles processed: 125,432
INFO -   Total records updated: 118,756
```

## Performance

- **Fast Processing**: Only extracts PMID and publication date, ignoring other fields
- **Efficient Updates**: Uses SQL CASE statements for batch updates
- **Minimal I/O**: Processes compressed XML files directly

## Prerequisites

- The `tmpdocument` table must exist and contain records to update
- XML files should be in gzipped format (`.xml.gz`)
- Database connection must be properly configured
- Required Python packages: `tqdm`, `xml.etree.ElementTree`

## Error Handling

- **File Errors**: Logs errors and continues with next file
- **Database Errors**: Logs batch update errors and continues
- **XML Parsing Errors**: Logs article processing errors and continues
- **Graceful Degradation**: Script continues even if some files or records fail

## Logging

The script creates detailed logs in `update_publication_dates.log` including:
- Processing progress
- Error messages
- Final statistics
- Timing information

## Example Use Cases

1. **After Publication Date Fix**: Update existing records after implementing the publication date extraction fix
2. **Data Correction**: Fix publication dates that were incorrectly imported
3. **Selective Updates**: Update only publication dates without affecting other fields
4. **Testing**: Verify publication date extraction on a subset of data

## Safety Notes

- **Backup Recommended**: Consider backing up the `tmpdocument` table before running
- **Test First**: Run on a small subset of files first to verify behavior
- **Monitor Progress**: Watch the log file for any errors during processing
- **Database Load**: Large batch sizes may impact database performance

## Related Files

- `localknowledge/pubmed/import_downloads.py`: Main import script with publication date fix
- `localknowledge/pubmed/import_to_tmpdocument.py`: Import to temporary table
- `manual/pubmed.md`: Documentation of the publication date fix
