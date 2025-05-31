# PubMed Import to tmpdocument Table

This script (`import_to_tmpdocument.py`) is designed to import PubMed XML files from a backup directory into the `tmpdocument` table for data recovery purposes.

## Purpose

The script was created to help recover from data corruption in the main `document` table by re-importing all PubMed data from backup files into a temporary table (`tmpdocument`) that has the same structure as the main `document` table.

## Features

- **Safe Import**: Imports into `tmpdocument` table without affecting any other tables
- **No Tracking**: Does not use or modify any tracking systems (download_tracker, import_tracker)
- **No File Movement**: Does not move or modify source files
- **Comprehensive Processing**: Processes both baseline and update files from the backup directory
- **Progress Tracking**: Shows detailed progress with file-by-file and article-by-article progress bars
- **Error Handling**: Skips corrupt files and continues processing
- **Logging**: Creates detailed logs in `pubmed_import_tmpdocument.log`

## Prerequisites

1. The `tmpdocument` table must exist and have the same structure as the `document` table
2. The backup directory must contain PubMed XML.gz files
3. Database connection must be configured properly

## Usage

```bash
python localknowledge/pubmed/import_to_tmpdocument.py /path/to/backup/directory
```

### Example

```bash
python localknowledge/pubmed/import_to_tmpdocument.py ~/backup/pubmed_data/
```

## What the Script Does

1. **Scans the backup directory** for all `.xml.gz` files (both baseline and updates)
2. **Sorts files** to process them in order
3. **Creates a temporary database manager** that targets the `tmpdocument` table
4. **For each file**:
   - Performs basic integrity check
   - Counts articles for progress tracking
   - Processes articles in batches
   - Stores articles in `tmpdocument` table
   - Shows progress and statistics
5. **Provides final statistics** including total articles processed and stored

## Database Tables Used

- **tmpdocument**: Target table for imported articles (same structure as `document`)
- **sources**: Referenced for PubMed source ID
- **categories**: Referenced for category IDs (if applicable)

## Tables NOT Modified

- **document**: Main document table (not touched)
- **pubmed_download_log**: Download tracking (not used)
- **import_tracker**: Import tracking (not used)
- **chunks**: Chunking data (not modified)
- **embeddings**: Embedding data (not modified)

## Output

The script provides:
- Real-time progress bars showing file and article processing
- Console output with key information
- Detailed log file (`pubmed_import_tmpdocument.log`)
- Final statistics showing total articles imported

## Error Handling

- **Corrupt files**: Skipped with warning, processing continues
- **Database errors**: Logged with details, processing continues for other files
- **Missing files**: Script exits if backup directory doesn't exist

## Performance

The script is optimized for:
- Memory efficiency (streaming XML processing)
- Database performance (batch inserts)
- Progress visibility (detailed progress bars)
- Error recovery (continues on individual file failures)

## After Import

After successful import, you can:
1. Compare data between `document` and `tmpdocument` tables
2. Verify data integrity in `tmpdocument`
3. Use the data for recovery operations
4. Copy corrected data back to the main `document` table (separate process)

## Notes

- The script uses the same XML parsing logic as the original import script
- All PubMed-specific data extraction is preserved
- The script is designed to be run multiple times safely (uses ON CONFLICT DO UPDATE)
- Processing time depends on the number and size of XML files in the backup directory
