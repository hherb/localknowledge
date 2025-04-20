"""
medRxiv Importer Script

This script downloads metadata and optionally PDFs from medRxiv using their API.
"""
import requests
import os
import sys
import time
import json
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import pymupdf4llm
from tqdm import tqdm  # Using standard tqdm instead of auto to avoid asyncio conflicts

# Fix import path issue - we need to add appropriate paths
import os
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add the parent directory of the script to path
# This allows importing remove_line_numbers directly
sys.path.insert(0, script_dir)

# Add the parent directory of localknowledge to the path
# This is needed to be able to import from localknowledge.db
# Go up from experimental/ to localknowledge/ and then to the parent directory
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)

# Now import our custom modules
from remove_line_numbers import remove_sequential_line_numbers
from medrxiv_fetcher import MedRxivFetcher
from medrxiv_to_markdown import MedRxivMarkdownConverter

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file if it exists

# Now we can import from localknowledge
try:
    from localknowledge.db.medrxiv import MedRxivDatabaseManager
    print("Successfully imported MedRxivDatabaseManager")
except ImportError as e:
    print(f"Error importing MedRxivDatabaseManager: {e}")
    sys.exit(1)

def fetch_medrxiv_metadata(start_date=None, end_date=None, batch_size=100, max_retries=5):
    """
    Fetch medRxiv metadata using their API
    API documentation: https://api.biorxiv.org/

    Parameters:
    - start_date: Start date in YYYY-MM-DD format
    - end_date: End date in YYYY-MM-DD format
    - batch_size: Number of papers per API request
    - max_retries: Maximum number of retry attempts for failed requests

    Returns:
    - List of papers metadata
    """
    if not start_date:
        start_date = "2019-06-06"  # medRxiv launch date
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    base_url = "https://api.biorxiv.org/details/medrxiv"

    all_papers = []
    cursor = 0
    total_fetched = 0

    # First make a request to get total count
    try:
        response = requests.get(f"{base_url}/{start_date}/{end_date}/0", timeout=(10, 30))
        response.raise_for_status()
        data = response.json()
        total_count = data.get('messages', [{}])[0].get('total', 0)
        if total_count == 0:
            print("No papers found in the specified date range.")
            return all_papers

        # Ensure total_count is an integer
        total_count = int(total_count)
        print(f"Found {total_count} papers from {start_date} to {end_date}")
        # Create progress bar
        main_pbar = tqdm(total=total_count, desc="Fetching papers", unit="papers")
    except Exception as e:
        print(f"Error getting paper count: {str(e)}")
        total_count = None
        main_pbar = None

    while True:
        url = f"{base_url}/{start_date}/{end_date}/{cursor}"

        # Try with retries and exponential backoff
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            try:
                # Set timeout (10 seconds for connect, 30 seconds for read)
                response = requests.get(url, timeout=(10, 30))
                response.raise_for_status()  # Raise exception for non-200 status codes
                success = True
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectTimeout) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    tqdm.write(f"Failed to connect to {url} after {max_retries} attempts.")
                    tqdm.write(f"Error: {str(e)}")
                    return all_papers  # Return what we've got so far

                # Exponential backoff: wait 2^retry_count seconds
                wait_time = 2 ** retry_count
                tqdm.write(f"Connection failed. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                tqdm.write(f"Unexpected error: {str(e)}")
                return all_papers  # Return what we've got so far

        if not success:
            return all_papers

        try:
            data = response.json()
            collection = data.get('collection', [])

            if not collection:
                break

            all_papers.extend(collection)
            total_fetched += len(collection)

            # Update progress bar
            if main_pbar is not None:
                main_pbar.update(len(collection))

            # Update cursor for next batch
            cursor += batch_size

            # Check if we've reached the end
            if len(collection) < batch_size:
                break

            # Be nice to the API
            time.sleep(1)
        except Exception as e:
            tqdm.write(f"Error processing API response: {str(e)}")
            break

    # Close progress bar
    if main_pbar is not None:
        main_pbar.close()

    return all_papers


def get_pdf_base_dir():
    """
    Get the base directory for PDF files, ensuring proper path expansion.

    Returns:
    - Fully expanded path to the PDF storage directory
    """
    # Get PDF directory from environment variable or use default
    pdf_base_dir = os.environ.get('PDF_BASE_DIR')
    if not pdf_base_dir:
        home_dir = os.path.expanduser("~")
        pdf_base_dir = os.path.join(home_dir, "knowledgebase", "pdfs")
    else:
        # Expand the tilde if it exists in the path
        pdf_base_dir = os.path.expanduser(pdf_base_dir)

    return pdf_base_dir


def download_pdf(paper):
    """
    Download the PDF for a paper

    Parameters:
    - paper: Paper metadata dict containing 'doi' and 'version'

    Returns:
    - Tuple of (filename, was_downloaded) where:
      - filename is the name of the PDF file or None if download failed
      - was_downloaded is a boolean indicating if the file was newly downloaded (True) or already existed (False)
    """
    # Get PDF directory using the common function
    pdf_base_dir = get_pdf_base_dir()

    # Create directory structure if it doesn't exist
    os.makedirs(pdf_base_dir, exist_ok=True)

    # Create safe filename from DOI
    safe_filename = paper['doi'].replace('/', '_') + '.pdf'
    local_path = os.path.join(pdf_base_dir, safe_filename)

    # Skip if already downloaded
    if os.path.exists(local_path):
        tqdm.write(f"PDF already exists locally: {safe_filename}")
        return safe_filename, False

    # Construct PDF URL
    pdf_url = f"https://www.medrxiv.org/content/{paper['doi']}v{paper['version']}.full.pdf"

    try:
        response = requests.get(pdf_url, stream=True)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            tqdm.write(f"Downloaded {pdf_url}")
            return safe_filename, True
        else:
            tqdm.write(f"Failed to download {pdf_url}: {response.status_code}")
            return None, False
    except Exception as e:
        tqdm.write(f"Error downloading {pdf_url}: {e}")
        return None, False


def extract_full_text(filename):
    """
    Extract content from PDF as markdown using pymupdf4llm with a timeout

    Parameters:
    - filename: Filename of the PDF (not full path)

    Returns:
    - Markdown formatted text extracted from the PDF or empty string if conversion fails
    - Also moves problematic PDFs to a 'failed' subdirectory if they time out
    """
    import signal
    import shutil
    from contextlib import contextmanager

    # Define a timeout exception
    class TimeoutException(Exception):
        pass

    # Define a context manager for timeout
    @contextmanager
    def timeout(seconds):
        def timeout_handler(signum, frame):
            raise TimeoutException(f"PDF processing timed out after {seconds} seconds")

        # Save the original handler
        original_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            # Restore the original handler and cancel the alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)

    try:
        # Get PDF base directory using the common function
        pdf_base_dir = get_pdf_base_dir()

        # Construct full path
        pdf_path = os.path.join(pdf_base_dir, filename)

        # Create failed directory if it doesn't exist
        failed_dir = os.path.join(pdf_base_dir, 'failed')
        os.makedirs(failed_dir, exist_ok=True)

        # Extract text from PDF as markdown with timeout (20 seconds)
        try:
            with timeout(20):  # 20 second timeout
                markdown_text = pymupdf4llm.to_markdown(pdf_path)
                #tqdm.write(f"Successfully converted {filename} to markdown")
                return markdown_text
        except TimeoutException as e:
            tqdm.write(f"Warning: {e}")
            # Move the problematic PDF to the failed directory
            failed_path = os.path.join(failed_dir, filename)
            shutil.move(pdf_path, failed_path)
            tqdm.write(f"Moved problematic PDF {filename} to {failed_dir}")
            return ""

    except Exception as e:
        tqdm.write(f"Error extracting text from {filename}: {e}")
        return ""


def process_papers(papers, db_manager, download_pdfs=True):
    """
    Process papers and store in database

    Parameters:
    - papers: List of papers to process
    - db_manager: MedRxivDatabaseManager instance
    - download_pdfs: Whether to download PDFs for each paper
    """
    # Create progress bar for processing
    pbar = tqdm(papers, desc="Processing papers", unit="paper")

    for paper in pbar:
        try:
            doi = paper.get('doi', '')
            title = paper.get('title', '')
            abstract = paper.get('abstract', '')

            # Handle authors with better error checking
            authors_list = paper.get('authors', [])
            if authors_list:
                try:
                    # Handle both string and dict formats for authors
                    if isinstance(authors_list, list):
                        author_names = []
                        for author in authors_list:
                            if isinstance(author, dict) and 'author' in author:
                                author_names.append(author['author'])
                            elif isinstance(author, str):
                                author_names.append(author)
                        authors = ', '.join(author_names)
                    else:
                        authors = str(authors_list)
                except Exception as e:
                    tqdm.write(f"Error processing authors for {doi}: {e}")
                    authors = "Error processing authors"
            else:
                authors = ""

            date_posted = paper.get('date', '')
            category = paper.get('category', '')

            # Set description to show current paper
            pbar.set_description(f"Processing {doi}")

            # Handle PDF download if requested
            pdf_url = f"https://www.medrxiv.org/content/{doi}v{paper['version']}.full.pdf"
            filename = ""
            full_text = ""

            if download_pdfs:
                filename, was_downloaded = download_pdf(paper)
                if filename:
                    # Only extract text if the file was newly downloaded
                    if was_downloaded:
                        full_text = extract_full_text(filename)
                    # If file already existed, we should check if we have full_text in the database
                    # If not, we could extract it here, but that would be an additional feature

            # Create a preprint dictionary and store in database
            preprint = {
                'doi': doi,
                'title': title,
                'abstract': abstract,
                'authors': authors,
                'date_posted': date_posted,
                'category': category,
                'pdf_url': pdf_url,
                'local_pdf_path': filename,
                'full_text': full_text
            }

            # Store in database
            db_manager.store_preprint(preprint)

        except Exception as e:
            tqdm.write(f"Error processing paper {paper.get('doi', 'unknown')}: {e}")


def split_date_range_into_weeks(start_date_str, end_date_str):
    """
    Split a date range into weekly chunks

    Parameters:
    - start_date_str: Start date in YYYY-MM-DD format
    - end_date_str: End date in YYYY-MM-DD format

    Returns:
    - List of (week_start, week_end) tuples in YYYY-MM-DD format
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    date_ranges = []
    current_date = start_date

    while current_date <= end_date:
        # Calculate the end of this week (7 days later or the end_date, whichever is sooner)
        week_end = min(current_date + timedelta(days=7), end_date)
        date_ranges.append((
            current_date.strftime("%Y-%m-%d"),
            week_end.strftime("%Y-%m-%d")
        ))

        # Move to start of next week
        current_date = week_end + timedelta(days=1)

    return date_ranges


def update_medrxiv_database(download_pdfs=False, max_retries=5, start_date_override=None, days_to_fetch=1095, end_date=None):
    """
    Main function to update the medRxiv database

    Parameters:
    - download_pdfs: Whether to download PDFs for each paper
    - max_retries: Maximum number of retry attempts for API requests
    - start_date_override: Force a specific start date (format: YYYY-MM-DD)
    - days_to_fetch: Number of days back to fetch if no items in database
    - end_date: Optional end date (format: YYYY-MM-DD), defaults to today if not specified
    """
    # Check if required environment variables are set
    db_name = os.environ.get('POSTGRES_DB')
    if not db_name:
        print("\033[91mERROR: POSTGRES_DB environment variable is not set!\033[0m")
        print("Please set the following environment variables before running this script:")
        print("  export POSTGRES_DB=medrxiv")
        print("  export POSTGRES_USER=your_username")
        print("  export POSTGRES_PASSWORD=your_password")
        print("  export POSTGRES_HOST=localhost")
        print("  export POSTGRES_PORT=5432")
        print("\nYou can also create a .env file in this directory with these variables.")
        return

    try:
        # Print database connection info for debugging
        print(f"Connecting to PostgreSQL database '{db_name}' at {os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}")

        # Create database manager
        db_manager = MedRxivDatabaseManager()

        # Determine the start date
        if start_date_override:
            # Use provided start date if specified
            start_date = start_date_override
        else:
            # Try to get the latest date from the database to resume
            resume_date = db_manager.get_resume_date(days_back=1)
            if resume_date:
                tqdm.write(f"Resuming from last imported date: {resume_date}")
                start_date = resume_date
            else:
                # If no data in database, default to papers from the specified number of days
                start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')
                tqdm.write(f"No data in database. Starting from {days_to_fetch} days ago ({start_date})")

        # Use provided end_date or default to today
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        tqdm.write(f"End date for fetch: {end_date}")

        # Split the date range into weekly chunks to avoid hammering the server
        date_ranges = split_date_range_into_weeks(start_date, end_date)
        tqdm.write(f"Splitting request into {len(date_ranges)} weekly chunks")

        # Track stats for final report
        total_processed = 0
        dates_processed = set()

        # Create progress bar for weekly chunks
        chunks_pbar = tqdm(date_ranges, desc="Downloading weekly chunks", unit="week")
        for week_start, week_end in chunks_pbar:
            chunks_pbar.set_description(f"Downloading {week_start} to {week_end}")

            # Fetch papers for this week
            tqdm.write(f"Fetching medRxiv papers from {week_start} to {week_end}...")
            week_papers = fetch_medrxiv_metadata(week_start, week_end, max_retries=max_retries)

            # Process this week's papers immediately
            if week_papers:
                tqdm.write(f"Found {len(week_papers)} papers for {week_start} to {week_end}")

                # Group papers by date for better processing
                papers_by_date = {}
                for paper in week_papers:
                    date_posted = paper.get('date', '').split()[0] if ' ' in paper.get('date', '') else paper.get('date', '')
                    if date_posted not in papers_by_date:
                        papers_by_date[date_posted] = []
                    papers_by_date[date_posted].append(paper)

                dates_to_process = sorted(papers_by_date.keys())

                # Process papers by date
                date_pbar = tqdm(dates_to_process, desc="Processing dates", unit="day")
                for date_str in date_pbar:
                    current_papers = papers_by_date[date_str]
                    date_pbar.set_description(f"Processing date {date_str} ({len(current_papers)} papers)")

                    # Process in batches for better memory management
                    batch_size = 100
                    for i in range(0, len(current_papers), batch_size):
                        batch = current_papers[i:i+batch_size]
                        process_papers(batch, db_manager, download_pdfs)

                    total_processed += len(current_papers)
                    dates_processed.add(date_str)
                    #tqdm.write(f"Processed and committed {len(current_papers)} papers from {date_str}")
            else:
                tqdm.write(f"No papers found for {week_start} to {week_end}")

            # Sleep for 2 seconds between weekly batches to be nice to the server
            if week_end != end_date:
                #tqdm.write("Pausing for 2 seconds to avoid hammering the server...")
                time.sleep(2)

        db_manager.close()
        tqdm.write(f"medRxiv database update complete! Processed {total_processed} papers across {len(dates_processed)} dates.")
    except Exception as e:
        tqdm.write(f"An error occurred during database update: {str(e)}")
        # Make sure we close the connection in case of errors
        try:
            if 'db_manager' in locals():
                db_manager.close()
        except:
            pass


def fetch_missing_pdfs(max_retries=5, limit=None, convert_to_markdown=False, use_html_xml=False):
    """
    Fetch missing PDF files for papers in the database

    This function checks the database for records without downloaded PDFs and attempts
    to download and process them.

    Parameters:
    - max_retries: Maximum number of retry attempts for failed downloads
    - limit: Maximum number of PDFs to fetch (None for no limit)
    - convert_to_markdown: Whether to convert PDFs to markdown text (default: False)
    - use_html_xml: Whether to try HTML/XML conversion first (more accurate) before falling back to PDF (default: False)

    Returns:
    - Number of successfully downloaded PDFs
    """
    # Create database manager
    db_manager = MedRxivDatabaseManager()

    # Get preprints without PDFs
    records = db_manager.get_preprints_without_pdfs(limit)

    if not records:
        tqdm.write("No missing PDFs found in the database.")
        db_manager.close()
        return 0

    tqdm.write(f"Found {len(records)} papers without downloaded PDFs")

    # Process each record
    success_count = 0
    papers_pbar = tqdm(records, desc="Downloading PDFs", unit="paper")

    for record in papers_pbar:
        doi = record['doi']
        title = record['title']
        date_posted = record['date_posted']
        category = record['category']
        pdf_url = record['pdf_url']

        papers_pbar.set_description(f"Processing {doi}")

        # Try to get the version from the PDF URL
        version = "1"  # Default version
        try:
            if pdf_url and "v" in pdf_url:
                version = pdf_url.split("v")[-1].split(".")[0]
        except:
            pass

        # Create a paper dict similar to what we get from the API
        paper = {
            'doi': doi,
            'title': title,
            'date': date_posted,
            'category': category,
            'version': version
        }

        # Variables to track our progress
        filename = None
        retry_count = 0
        full_text = ""

        # First try HTML/XML conversion if requested (usually better quality)
        if convert_to_markdown and use_html_xml:
            try:
                tqdm.write(f"Trying HTML/XML conversion for {doi}")
                full_text = fetch_and_convert_to_markdown(doi, save_files=False)

                if full_text:
                    # If we got markdown from HTML/XML, we can still download the PDF for reference
                    # but we won't use it for text extraction
                    filename, was_downloaded = download_pdf(paper)

                    # Update the database with the markdown text
                    db_manager.update_pdf_path(doi, filename or "", full_text)
                    success_count += 1
                    continue  # Skip to next paper since we've handled this one
            except Exception as e:
                tqdm.write(f"HTML/XML conversion failed for {doi}: {str(e)}. Falling back to PDF.")

        # If HTML/XML conversion failed or wasn't requested, try PDF download
        while retry_count < max_retries and not filename:
            try:
                # Download the PDF (returns tuple of filename and whether it was newly downloaded)
                filename, was_downloaded = download_pdf(paper)

                if filename:
                    # Extract text only if the file was newly downloaded and conversion is requested
                    full_text = ""
                    if was_downloaded and convert_to_markdown:
                        full_text = extract_full_text(filename)
                        #remove line numbers
                        full_text=remove_sequential_line_numbers(full_text)

                    # Always update the database with the local path
                    # If the file already existed, we're just ensuring the database has the correct path
                    db_manager.update_pdf_path(doi, filename, full_text)
                    success_count += 1

                    # Take a short break to avoid hammering the server if we downloaded a new file
                    #if was_downloaded:
                    #    time.sleep(1)
                else:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    tqdm.write(f"Download failed for {doi}. Retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
            except Exception as e:
                retry_count += 1
                tqdm.write(f"Error downloading {doi}: {str(e)}")
                if retry_count >= max_retries:
                    break
                wait_time = 2 ** retry_count
                time.sleep(wait_time)

    tqdm.write(f"Downloaded {success_count} out of {len(records)} missing PDFs")
    db_manager.close()
    return success_count


def rename_pdf_files(dry_run=False):
    """
    Rename PDF files from the old format using '-' as separator to the new format using '_'.

    This function scans the PDF directory for files with '-' in the filename
    and renames them to use '_' instead.

    Parameters:
    - dry_run: If True, only show what would be renamed without actually renaming

    Returns:
    - Number of files renamed
    """
    # Get PDF directory
    pdf_base_dir = get_pdf_base_dir()
    tqdm.write(f"Using PDF directory: {pdf_base_dir}")

    if not os.path.exists(pdf_base_dir):
        tqdm.write(f"ERROR: PDF directory {pdf_base_dir} does not exist!")
        return 0

    # Get all PDF files
    pdf_files = [f for f in os.listdir(pdf_base_dir) if f.endswith('.pdf')]
    tqdm.write(f"Found {len(pdf_files)} PDF files in directory")

    # Filter for files with '-' in the filename
    old_format_files = [f for f in pdf_files if '10.1101-' in f]
    tqdm.write(f"Found {len(old_format_files)} files with old format (using '-' as separator)")

    if not old_format_files:
        tqdm.write("No files to rename.")
        return 0

    # Sample some filenames
    if old_format_files:
        tqdm.write("Sample old format filenames:")
        for i in range(min(5, len(old_format_files))):
            tqdm.write(f"  {old_format_files[i]}")

    # Rename files
    renamed_count = 0
    files_pbar = tqdm(old_format_files, desc="Renaming PDF files", unit="file")

    for old_filename in files_pbar:
        # Create new filename by replacing '-' with '_'
        new_filename = old_filename.replace('10.1101-', '10.1101_')
        old_path = os.path.join(pdf_base_dir, old_filename)
        new_path = os.path.join(pdf_base_dir, new_filename)

        files_pbar.set_description(f"Renaming {old_filename} to {new_filename}")

        # Check if the new filename already exists
        if os.path.exists(new_path):
            tqdm.write(f"WARNING: Cannot rename {old_filename} to {new_filename} - target file already exists")
            continue

        # Rename the file
        if not dry_run:
            try:
                os.rename(old_path, new_path)
                renamed_count += 1
            except Exception as e:
                tqdm.write(f"ERROR: Failed to rename {old_filename}: {str(e)}")
        else:
            tqdm.write(f"Would rename {old_filename} to {new_filename}")
            renamed_count += 1

    action = "Would rename" if dry_run else "Renamed"
    tqdm.write(f"{action} {renamed_count} out of {len(old_format_files)} PDF files")
    return renamed_count


def update_existing_pdfs(limit=None, extract_text=False, diagnostic=False):
    """
    Check for existing PDFs that aren't recorded in the database and update the database.

    This function checks if PDFs exist locally for records that don't have a local_pdf_path
    in the database, and updates the database accordingly.

    Parameters:
    - limit: Maximum number of records to check (None for no limit)
    - extract_text: Whether to extract text from found PDFs
    - diagnostic: Run in diagnostic mode to investigate discrepancies

    Returns:
    - Number of PDFs found and updated in the database
    """
    # Create database manager
    db_manager = MedRxivDatabaseManager()

    # Get PDF directory
    pdf_base_dir = get_pdf_base_dir()
    tqdm.write(f"Using PDF directory: {pdf_base_dir}")

    # Count total records in database
    total_records = db_manager.execute("SELECT COUNT(*) FROM preprints")[0]['count']
    tqdm.write(f"Total records in database: {total_records}")

    # Count records with PDF paths
    records_with_pdfs = db_manager.execute("SELECT COUNT(*) FROM preprints WHERE local_pdf_path IS NOT NULL AND local_pdf_path != ''")[0]['count']
    tqdm.write(f"Records with PDF paths: {records_with_pdfs}")

    # Count records without PDF paths
    records_without_pdfs = db_manager.execute("SELECT COUNT(*) FROM preprints WHERE local_pdf_path IS NULL OR local_pdf_path = ''")[0]['count']
    tqdm.write(f"Records without PDF paths: {records_without_pdfs}")

    # Count PDF files in the directory
    if os.path.exists(pdf_base_dir):
        pdf_files = [f for f in os.listdir(pdf_base_dir) if f.endswith('.pdf')]
        tqdm.write(f"PDF files in directory: {len(pdf_files)}")

        # Sample some PDF filenames
        if diagnostic and pdf_files:
            tqdm.write("Sample PDF filenames:")
            for i in range(min(5, len(pdf_files))):
                tqdm.write(f"  {pdf_files[i]}")
    else:
        tqdm.write(f"WARNING: PDF directory {pdf_base_dir} does not exist!")
        pdf_files = []

    # Get preprints without PDFs
    records = db_manager.get_preprints_without_pdfs(limit)

    if not records:
        tqdm.write("No records without PDF paths found in the database.")
        db_manager.close()
        return 0

    tqdm.write(f"Found {len(records)} records without PDF paths to check")

    # Sample some DOIs
    if diagnostic and records:
        tqdm.write("Sample DOIs without PDF paths:")
        for i in range(min(5, len(records))):
            tqdm.write(f"  {records[i]['doi']}")
            # Show expected filename
            safe_filename = records[i]['doi'].replace('/', '_') + '.pdf'
            tqdm.write(f"  Expected filename: {safe_filename}")
            # Check if this file exists
            local_path = os.path.join(pdf_base_dir, safe_filename)
            tqdm.write(f"  File exists: {os.path.exists(local_path)}")

    # Process each record
    found_count = 0
    papers_pbar = tqdm(records, desc="Checking for existing PDFs", unit="paper")

    for record in papers_pbar:
        doi = record['doi']
        papers_pbar.set_description(f"Checking {doi}")

        # Create safe filename from DOI (new format with underscore)
        safe_filename = doi.replace('/', '_') + '.pdf'
        local_path = os.path.join(pdf_base_dir, safe_filename)

        # Also check old format with hyphen
        old_format_filename = doi.replace('/', '-') + '.pdf'
        old_format_path = os.path.join(pdf_base_dir, old_format_filename)

        # Check if the PDF exists locally in either format
        if os.path.exists(local_path):
            found_filename = safe_filename
        elif os.path.exists(old_format_path):
            found_filename = old_format_filename
            tqdm.write(f"Found PDF with old format filename: {old_format_filename}")
            # Optionally rename the file here if desired
        else:
            continue

        # If we found a file
        tqdm.write(f"Found existing PDF for {doi}: {found_filename}")

        # Extract text if requested
        full_text = ""
        if extract_text:
            tqdm.write(f"Extracting text from {found_filename}")
            full_text = extract_full_text(found_filename)
            if full_text:
                full_text = remove_sequential_line_numbers(full_text)

        # Update the database
        db_manager.update_pdf_path(doi, found_filename, full_text)
        found_count += 1

    tqdm.write(f"Found and updated {found_count} out of {len(records)} missing PDF paths")
    db_manager.close()
    return found_count


def fetch_and_convert_to_markdown(doi, save_files=False, output_dir=None):
    """
    Fetch a preprint by DOI and convert HTML/XML to markdown.

    This function uses the MedRxivMarkdownConverter to fetch either HTML or XML format
    of a preprint and convert it to markdown. This is often more reliable than
    converting PDFs to markdown, especially for text extraction and structure preservation.

    Args:
        doi (str): DOI of the preprint
        save_files (bool): Whether to save the markdown and images to disk
        output_dir (str): Directory to save output files if save_files is True

    Returns:
        str: Markdown text of the preprint or empty string if conversion fails
    """
    try:
        if output_dir is None:
            output_dir = os.path.join(get_pdf_base_dir(), "markdown")

        # Create the converter with file saving option
        converter = MedRxivMarkdownConverter(
            output_dir=output_dir,
            image_dir="assets",
            save_files=save_files
        )

        # Convert the preprint to markdown
        tqdm.write(f"Converting {doi} to markdown...")
        result = converter.convert_doi_to_markdown(doi)

        if result and result['markdown']:
            return result['markdown']
        else:
            tqdm.write(f"Failed to convert {doi} to markdown")
            return ""

    except Exception as e:
        tqdm.write(f"Error converting {doi} to markdown: {str(e)}")
        return ""


def main():
    """Main function that parses command line arguments and runs the appropriate actions"""
    import argparse

    parser = argparse.ArgumentParser(description="Download and manage medRxiv papers")

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Update database command
    update_parser = subparsers.add_parser('update', help='Update the medRxiv database')
    update_parser.add_argument('--pdfs', action='store_true',
                             help='Download PDFs for each paper (requires significant storage)')
    update_parser.add_argument('--retries', type=int, default=5,
                             help='Maximum number of retry attempts for API requests')
    update_parser.add_argument('--start-date', type=str,
                             help='Force a specific start date (format: YYYY-MM-DD)')
    update_parser.add_argument('--days', type=int, default=1095,
                             help='Number of days back to fetch if no items in database')

    # Download missing PDFs command
    pdf_parser = subparsers.add_parser('pdfs', help='Download missing PDFs for papers in the database')
    pdf_parser.add_argument('--retries', type=int, default=5,
                          help='Maximum number of retry attempts for failed downloads')
    pdf_parser.add_argument('--limit', type=int,
                          help='Maximum number of PDFs to fetch')
    pdf_parser.add_argument('--convert', action='store_true',
                          help='Convert PDFs to markdown text')
    pdf_parser.add_argument('--html-xml', action='store_true',
                          help='Try HTML/XML conversion first before falling back to PDF')

    # Markdown conversion command
    md_parser = subparsers.add_parser('markdown', help='Convert papers to markdown using HTML/XML')
    md_parser.add_argument('--doi', type=str, required=True,
                        help='DOI of the paper to convert')
    md_parser.add_argument('--save', action='store_true',
                        help='Save markdown and images to disk')
    md_parser.add_argument('--output-dir', type=str,
                        help='Directory to save output files if --save is used')

    # Update existing PDFs command
    update_parser = subparsers.add_parser('update-paths', help='Check for existing PDFs and update database paths')
    update_parser.add_argument('--limit', type=int,
                           help='Maximum number of records to check')
    update_parser.add_argument('--extract', action='store_true',
                           help='Extract text from found PDFs')
    update_parser.add_argument('--diagnostic', action='store_true',
                           help='Run in diagnostic mode to investigate discrepancies')

    # Rename PDF files command (new)
    rename_parser = subparsers.add_parser('rename-pdfs', help='Rename PDF files from old format to new format')
    rename_parser.add_argument('--dry-run', action='store_true',
                           help='Show what would be renamed without actually renaming')

    args = parser.parse_args()

    if args.command == 'update':
        update_medrxiv_database(
            download_pdfs=args.pdfs,
            max_retries=args.retries,
            start_date_override=args.start_date,
            days_to_fetch=args.days
        )
    elif args.command == 'pdfs':
        fetch_missing_pdfs(
            max_retries=args.retries,
            limit=args.limit,
            convert_to_markdown=args.convert,
            use_html_xml=args.html_xml
        )
    elif args.command == 'markdown':
        markdown_text = fetch_and_convert_to_markdown(
            args.doi,
            save_files=args.save,
            output_dir=args.output_dir
        )
        if markdown_text:
            print(markdown_text)
        else:
            print("Failed to convert to markdown.")
    elif args.command == 'update-paths':
        update_existing_pdfs(
            limit=args.limit,
            extract_text=args.extract,
            diagnostic=args.diagnostic
        )
    elif args.command == 'rename-pdfs':
        rename_pdf_files(
            dry_run=args.dry_run
        )
    else:
        # Default action if no command provided
        parser.print_help()


if __name__ == "__main__":
    main()
