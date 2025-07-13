#!/usr/bin/env python3
"""
Fill Missing MedRxiv Records

This script identifies potential gaps in the medRxiv database and ensures all papers
published between the earliest record date and January 16, 2021 are properly stored.
"""
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from tqdm import tqdm

# Set up logging for performance monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path to import localknowledge as a module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.medrxiv.medrxiv_import_new import fetch_medrxiv_metadata, process_papers, split_date_range_into_weeks

def ensure_optimized_indexes(db_manager):
    """
    Ensure that optimized indexes exist for medRxiv queries.
    
    Args:
        db_manager: Database manager instance
    """
    indexes_to_create = [
        {
            'name': 'idx_document_source_publication_date',
            'query': '''
            CREATE INDEX IF NOT EXISTS idx_document_source_publication_date 
            ON document (source_id, publication_date) 
            WHERE publication_date IS NOT NULL
            '''
        },
        {
            'name': 'idx_document_source_doi',
            'query': '''
            CREATE INDEX IF NOT EXISTS idx_document_source_doi 
            ON document (source_id, doi) 
            WHERE doi IS NOT NULL
            '''
        }
    ]
    
    print("Checking for optimized indexes...")
    for index in indexes_to_create:
        try:
            # Check if index exists
            check_query = """
            SELECT 1 FROM pg_indexes 
            WHERE indexname = %s
            """
            result = db_manager.execute(check_query, (index['name'],), timeout=60)
            
            if not result:
                print(f"Creating index {index['name']}...")
                # Create index with longer timeout
                db_manager.execute(index['query'], commit=True, timeout=1800)  # 30 minute timeout for index creation
                print(f"✓ Created index {index['name']}")
            else:
                print(f"✓ Index {index['name']} already exists")
                
        except Exception as e:
            print(f"Warning: Could not create index {index['name']}: {e}")
            # Continue without this optimization

def get_paper_counts_by_date(db_manager):
    """
    Get a count of papers for each date in the database.
    Optimized for large datasets with proper indexing and longer timeout.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Dictionary of date -> count of papers
    """
    # Get medRxiv source_id first to avoid subquery
    source_query = "SELECT id FROM sources WHERE name = 'medRxiv'"
    source_result = db_manager.execute(source_query, timeout=60)
    
    if not source_result:
        print("Warning: medRxiv source not found in database")
        return {}
    
    source_id = source_result[0]['id']
    
    # Optimized query with direct source_id lookup and extended timeout
    query = """
    SELECT publication_date, COUNT(*) as paper_count 
    FROM document 
    WHERE publication_date IS NOT NULL 
    AND source_id = %s
    GROUP BY publication_date 
    ORDER BY publication_date
    """
    
    print("Fetching paper counts by date (this may take a few minutes for large datasets)...")
    start_time = time.time()
    results = db_manager.execute(query, params=(source_id,), timeout=300)  # 5 minute timeout
    query_time = time.time() - start_time
    logger.info(f"Paper counts query completed in {query_time:.2f} seconds")
    
    if results:
        print(f"Found {len(results)} dates with medRxiv papers")
    
    counts_by_date = {}
    for row in results:
        # Convert date to string format
        publication_date = row['publication_date']
        if publication_date:
            date_str = publication_date.strftime('%Y-%m-%d') if hasattr(publication_date, 'strftime') else str(publication_date)
            counts_by_date[date_str] = row['paper_count']
        
    return counts_by_date


def find_missing_dates(all_dates, end_date):
    """
    Find potentially missing dates by identifying gaps in the sequence.
    
    Args:
        all_dates: List of date strings (sorted)
        end_date: End date for the analysis
        
    Returns:
        List of potentially missing dates
    """
    if not all_dates:
        return []
        
    # Convert to datetime objects
    date_objects = [datetime.strptime(d, '%Y-%m-%d') for d in all_dates]
    
    # Get the earliest and latest dates
    earliest_date = min(date_objects)
    latest_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Generate all dates in the range
    all_possible_dates = []
    current_date = earliest_date
    while current_date <= latest_date:
        all_possible_dates.append(current_date)
        current_date += timedelta(days=1)
        
    # Convert to set for faster lookup
    existing_dates_set = set(date_objects)
    possible_dates_set = set(all_possible_dates)
    
    # Find missing dates
    missing_dates = possible_dates_set - existing_dates_set
    missing_dates = sorted(list(missing_dates))
    
    # Convert back to string format
    missing_dates_str = [d.strftime('%Y-%m-%d') for d in missing_dates]
    
    return missing_dates_str


def find_dates_with_low_counts(date_counts, threshold=5):
    """
    Find dates that have suspiciously low counts (possible incomplete data).
    
    Args:
        date_counts: Dictionary of date -> count
        threshold: Minimum expected papers per day
        
    Returns:
        List of dates with low counts
    """
    low_count_dates = []
    
    # Calculate the average number of papers per day
    if len(date_counts) > 7:  # Need at least a week of data
        counts = list(date_counts.values())
        avg_count = sum(counts) / len(counts)
        
        # Find dates with counts significantly below average
        for date, count in date_counts.items():
            if count < max(threshold, avg_count * 0.3):  # Either below threshold or 30% of average
                low_count_dates.append(date)
    
    return low_count_dates


def fill_missing_medrxiv_records(start_date=None, end_date="2021-01-16", max_retries=5):
    """
    Fill in any missing medRxiv records between the earliest record and the specified end date.
    
    Args:
        start_date: Specific start date to begin checking from (None to use earliest in DB)
        end_date: End date to check until (default: 2021-01-16)
        max_retries: Maximum number of retry attempts
    
    Returns:
        Total number of added records
    """
    try:
        print(f"Starting process to fill missing medRxiv records up to {end_date}")
        
        # Create database manager
        db_manager = MedRxivDatabaseManager()
        
        # Ensure optimized indexes exist for better performance
        ensure_optimized_indexes(db_manager)
        
        # Get the earliest date if not specified
        if not start_date:
            # Get medRxiv source_id first for optimized query
            source_query = "SELECT id FROM sources WHERE name = 'medRxiv'"
            source_result = db_manager.execute(source_query, timeout=60)
            
            if not source_result:
                print("No medRxiv source found in database. Please run the regular import first.")
                db_manager.close()
                return 0
                
            source_id = source_result[0]['id']
            
            query = """
            SELECT MIN(publication_date) as earliest 
            FROM document 
            WHERE publication_date IS NOT NULL 
            AND source_id = %s
            """
            print("Finding earliest medRxiv record date...")
            start_time = time.time()
            result = db_manager.execute(query, params=(source_id,), timeout=180)  # 3 minute timeout
            query_time = time.time() - start_time
            logger.info(f"Earliest date query completed in {query_time:.2f} seconds")
            
            if result and result[0]['earliest']:
                earliest_date = result[0]['earliest']
                # Convert to string format
                start_date = earliest_date.strftime('%Y-%m-%d') if hasattr(earliest_date, 'strftime') else str(earliest_date)
            else:
                print("No medRxiv records found in database. Please run the regular import first.")
                db_manager.close()
                return 0
        
        print(f"Checking for missing records from {start_date} to {end_date}")
        
        # Get paper counts by date
        date_counts = get_paper_counts_by_date(db_manager)
        all_dates = sorted(date_counts.keys())
        
        # Find missing dates and dates with low counts
        missing_dates = find_missing_dates(all_dates, end_date)
        low_count_dates = find_dates_with_low_counts(date_counts)
        
        # Combine the dates that need checking
        dates_to_check = list(set(missing_dates + low_count_dates))
        dates_to_check.sort()
        
        if not dates_to_check:
            print("No missing or suspicious dates found. Database appears complete for this period.")
            db_manager.close()
            return 0
        
        print(f"Found {len(dates_to_check)} dates that need checking:")
        if len(dates_to_check) < 20:  # Only print if not too many
            print(", ".join(dates_to_check))
        
        # Group dates into weekly chunks for API efficiency
        weekly_chunks = []
        current_week = []
        
        for date_str in dates_to_check:
            if not current_week or (datetime.strptime(date_str, '%Y-%m-%d') - 
                                   datetime.strptime(current_week[-1], '%Y-%m-%d')).days <= 7:
                current_week.append(date_str)
            else:
                weekly_chunks.append(current_week)
                current_week = [date_str]
        
        if current_week:  # Add the last chunk
            weekly_chunks.append(current_week)
        
        # Process each week
        total_added = 0
        for week in tqdm(weekly_chunks, desc="Processing weeks"):
            week_start = week[0]
            week_end = week[-1]
            
            print(f"Fetching papers from {week_start} to {week_end}...")
            papers = fetch_medrxiv_metadata(week_start, week_end, max_retries=max_retries)
            
            if papers:
                print(f"Found {len(papers)} papers for period {week_start} to {week_end}")
                
                # Group papers by date for better processing
                papers_by_date = {}
                for paper in papers:
                    date_posted = paper.get('date', '').split()[0] if ' ' in paper.get('date', '') else paper.get('date', '')
                    if date_posted not in papers_by_date:
                        papers_by_date[date_posted] = []
                    papers_by_date[date_posted].append(paper)
                
                # Process papers for each date in the week
                for date_str, date_papers in papers_by_date.items():
                    # Check if we need to process this date
                    if date_str in dates_to_check:
                        print(f"Processing {len(date_papers)} papers for {date_str}")
                        
                        # First, get list of existing DOIs for this date
                        # Use the source_id we already have for optimized query
                        source_query = "SELECT id FROM sources WHERE name = 'medRxiv'"
                        source_result = db_manager.execute(source_query, timeout=60)
                        source_id = source_result[0]['id'] if source_result else None
                        
                        if source_id:
                            query = """
                            SELECT doi FROM document 
                            WHERE publication_date = %s 
                            AND source_id = %s
                            AND doi IS NOT NULL
                            """
                            existing = db_manager.execute(query, (date_str, source_id), timeout=120)
                            existing_dois = set(r['doi'] for r in existing if r['doi']) if existing else set()
                        else:
                            existing_dois = set()
                        
                        # Filter to only papers we don't have
                        new_papers = [p for p in date_papers if p.get('doi') not in existing_dois]
                        
                        if new_papers:
                            print(f"Adding {len(new_papers)} missing papers for {date_str}")
                            process_papers(new_papers, db_manager, download_pdfs=False)
                            total_added += len(new_papers)
                        else:
                            print(f"No new papers to add for {date_str}")
                    
                # Be nice to the API
                time.sleep(2)
        
        db_manager.close()
        print(f"Process complete! Added {total_added} missing papers.")
        return total_added
        
    except Exception as e:
        print(f"An error occurred while filling missing records: {str(e)}")
        # Make sure we close the connection in case of errors
        try:
            if 'db_manager' in locals():
                db_manager.close()
        except:
            pass
        return 0


def main():
    """Main function that parses command line arguments and runs the appropriate actions"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fill missing medRxiv records")
    parser.add_argument('--start-date', type=str, 
                      help='Start date to check from (format: YYYY-MM-DD). If not provided, will use earliest date in database.')
    parser.add_argument('--end-date', type=str, default="2021-01-16",
                      help='End date to check until (format: YYYY-MM-DD). Default is 2021-01-16.')
    parser.add_argument('--retries', type=int, default=5,
                      help='Maximum number of retry attempts for API requests')
    
    args = parser.parse_args()
    
    fill_missing_medrxiv_records(
        start_date=args.start_date,
        end_date=args.end_date,
        max_retries=args.retries
    )


if __name__ == "__main__":
    main()
