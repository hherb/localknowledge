#!/usr/bin/env python3
"""
Update Missing Markdown Script

This script updates records in the database with markdown converted from HTML/XML sources
from medRxiv. It processes records with missing fulltext by default, but can also
override existing fulltext when requested.

Usage:
    python update_missing_markdown.py --limit 100
    python update_missing_markdown.py --override-existing --days 30
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from tqdm import tqdm

# Fix import path issue - we need to add appropriate paths
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)  # For importing from this directory
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)  # For importing from parent directory

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file if it exists

# Set up logging
logging.basicConfig(
    level=logging.ERROR,  # Changed from INFO to ERROR
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser('~/medrxiv_markdown_update.log'))
    ]
)
logger = logging.getLogger('medrxiv_markdown_update')

# Import required modules
try:
    from localknowledge.db.medrxiv import MedRxivDatabaseManager
    from localknowledge.medrxiv.medrxiv_to_markdown import MedRxivMarkdownConverter
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    sys.exit(1)


def update_missing_markdown(limit=None, override_existing=False, days_back=None, max_retries=3, delay=1):
    """
    Update database records with markdown fulltext from HTML/XML sources.
    
    Args:
        limit: Maximum number of records to process
        override_existing: Whether to override records that already have fulltext
        days_back: Number of days to look back for records (None for all records)
        max_retries: Maximum number of retry attempts for failed conversions
        delay: Delay between requests in seconds (to avoid hammering the server)
        
    Returns:
        Tuple of (records_processed, success_count)
    """
    # Connect to the database
    db_manager = MedRxivDatabaseManager()
    
    # Create markdown converter (without file saving)
    converter = MedRxivMarkdownConverter(save_files=False)
    
    # Get records to process
    if override_existing and days_back is not None:
        # Get all records within the date range
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        query = """
        SELECT * FROM preprints 
        WHERE date_posted >= %s
        ORDER BY date_posted DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        records = db_manager.execute(query, (cutoff_date,))
        logger.info(f"Found {len(records)} records from the last {days_back} days")
        
    elif override_existing:
        # Get all records
        query = "SELECT * FROM preprints ORDER BY date_posted DESC"
        
        if limit:
            query += f" LIMIT {limit}"
            
        records = db_manager.execute(query)
        logger.info(f"Found {len(records)} total records in the database")
        
    elif days_back is not None:
        # Get only records with missing fulltext within the date range
        records = db_manager.get_recent_preprints_without_fulltext(days_back=days_back, limit=limit)
        logger.info(f"Found {len(records)} records with missing fulltext from the last {days_back} days")
        
    else:
        # Get all records with missing fulltext
        query = """
        SELECT * FROM preprints 
        WHERE full_text IS NULL OR full_text = ''
        ORDER BY date_posted DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        records = db_manager.execute(query)
        logger.info(f"Found {len(records)} records with missing fulltext")
    
    # Process each record
    success_count = 0
    records_processed = len(records)
    
    if records_processed == 0:
        logger.info("No records to process")
        db_manager.close()
        return (0, 0)
        
    # Use tqdm for progress tracking
    for record in tqdm(records, desc="Processing records", unit="record"):
        doi = record['doi']
        #tqdm.write(f"Processing {doi}")
        
        # Try to convert with retries
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                # Convert HTML/XML to markdown
                result = converter.convert_doi_to_markdown(doi)
                
                if result and result['markdown']:
                    # Update the database
                    db_manager.update_full_text(doi, result['markdown'])
                    success = True
                    success_count += 1
                    #tqdm.write(f"Successfully updated {doi}")
                else:
                    retry_count += 1
                    tqdm.write(f"Conversion failed for {doi}. Retry {retry_count}/{max_retries}")
                    time.sleep(delay * retry_count)  # Exponential backoff
            except Exception as e:
                retry_count += 1
                tqdm.write(f"Error converting {doi}: {str(e)}. Retry {retry_count}/{max_retries}")
                if retry_count >= max_retries:
                    tqdm.write(f"Giving up on {doi} after {max_retries} attempts")
                time.sleep(delay * retry_count)  # Exponential backoff
                
        # Delay between records to avoid hammering the server
        time.sleep(delay)
    
    # Log results
    logger.info(f"Processed {records_processed} records, successfully updated {success_count}")
    
    # Close database connection
    db_manager.close()
    
    return (records_processed, success_count)


def main():
    """Parse command-line arguments and run the script."""
    parser = argparse.ArgumentParser(description="Update database records with markdown fulltext")
    
    parser.add_argument('--limit', type=int, 
                      help='Maximum number of records to process')
    parser.add_argument('--override-existing', action='store_true',
                      help='Override records that already have fulltext')
    parser.add_argument('--days', type=int, 
                      help='Number of days to look back for records')
    parser.add_argument('--retries', type=int, default=3,
                      help='Maximum number of retry attempts for failed conversions')
    parser.add_argument('--delay', type=float, default=1,
                      help='Delay between requests in seconds')
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    records_processed, success_count = update_missing_markdown(
        limit=args.limit,
        override_existing=args.override_existing,
        days_back=args.days,
        max_retries=args.retries,
        delay=args.delay
    )
    
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    
    logger.info(f"Update completed in {duration} seconds")
    logger.info(f"Processed {records_processed} records, successfully updated {success_count}")
    
    # Return non-zero exit code if no records were processed successfully
    if records_processed > 0 and success_count == 0:
        logger.error("No records were successfully updated")
        sys.exit(1)


if __name__ == "__main__":
    main()
