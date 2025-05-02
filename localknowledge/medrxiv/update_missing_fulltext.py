#!/usr/bin/env python3
"""
Update Missing MedRxiv Fulltext

This script identifies preprints in the database that do not have fulltext,
and uses multiple strategies to retrieve the fulltext:

1. First tries to find the fulltext link by examining the page source of the DOI landing page
2. If that fails, tries to fetch plain text files directly using URL pattern matching
3. If both plain text methods fail, falls back to fetching XML files and converting them to markdown

This is designed to be efficient and fast for processing thousands of records.
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Tuple, Generator
import concurrent.futures
from tqdm import tqdm

from localknowledge.medrxiv.medrxiv_fetcher import MedRxivFetcher
from localknowledge.medrxiv.medrxiv_to_markdown import MedRxivMarkdownConverter
from localknowledge.db.medrxiv import MedRxivDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('update_missing_fulltext')


class MissingFulltextUpdater:
    """
    Process all medRxiv records without fulltext, using multiple strategies to retrieve fulltext:
    1. Extract fulltext link from page source
    2. Try direct URL pattern matching
    3. Fall back to XML download and conversion
    """

    def __init__(self, output_dir="./output", batch_size=100, max_workers=4, delay=0.5):
        """
        Initialize the updater.

        Args:
            output_dir (str): Directory to save downloaded files
            batch_size (int): Number of records to process in a batch
            max_workers (int): Maximum number of concurrent workers
            delay (float): Delay between API requests to avoid rate limiting
        """
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.fetcher = MedRxivFetcher(output_dir=output_dir, delay_between_requests=delay)
        self.db = MedRxivDatabaseManager()

        # Create a specialized converter that doesn't download images
        self.converter = MedRxivMarkdownConverter(
            output_dir=output_dir,
            save_files=False  # Don't save files to disk, just return the content
        )

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def get_missing_fulltext_records(self, limit=None) -> Generator[Dict[str, Any], None, None]:
        """
        Get records without fulltext from the database.

        Args:
            limit: Optional limit on the number of records to retrieve

        Yields:
            Records from the database missing fulltext
        """
        # Use the dedicated method from MedRxivDatabaseManager
        records = self.db.get_preprints_without_fulltext(limit)

        # Yield each record
        for record in records:
            yield record

    def count_missing_fulltext_records(self) -> int:
        """Count the number of records without fulltext."""
        # Use the dedicated method from MedRxivDatabaseManager
        return self.db.count_preprints_without_fulltext()

    def process_record(self, record: Dict[str, Any]) -> Tuple[str, bool, str]:
        """
        Process a single record: download plain text or XML and convert to markdown.

        Args:
            record: Database record with DOI

        Returns:
            Tuple of (DOI, success boolean, markdown or error message)
        """
        doi = record['doi']
        try:
            # First try to find fulltext from page source
            text_url = self.fetcher._find_fulltext_from_page_source(doi)

            if text_url:
                # If plain text is available from page source, download it directly
                try:
                    response = self.fetcher.session.get(text_url, timeout=10)
                    response.raise_for_status()
                    markdown_content = response.text
                    logger.info(f"Successfully downloaded plain text from page source for DOI {doi}")
                    return doi, True, markdown_content
                except Exception as e:
                    logger.error(f"Failed to download plain text from page source for DOI {doi}: {e}, trying direct URL...")
                    # Fall back to direct URL if page source method fails

            # If page source method fails, try direct URL pattern matching
            if not text_url:
                text_url = self.fetcher._try_direct_text_url(doi)

                if text_url:
                    # If plain text is available via direct URL, download it
                    try:
                        response = self.fetcher.session.get(text_url, timeout=10)
                        response.raise_for_status()
                        markdown_content = response.text
                        logger.info(f"Successfully downloaded plain text via direct URL for DOI {doi}")
                        return doi, True, markdown_content
                    except Exception as e:
                        logger.error(f"Failed to download plain text via direct URL for DOI {doi}: {e}, trying XML...")
                        # Fall back to XML if direct URL method fails

            # Only try XML if both plain text methods failed
            logger.info(f"Plain text not available for DOI {doi}, trying XML...")
            download_result = self.fetcher.download_preprint(doi, formats=['xml'])

            # Check if XML was downloaded
            if 'xml' not in download_result:
                return doi, False, f"Failed to download XML for {doi}"

            # Convert to markdown
            result = self.converter.convert_doi_to_markdown(doi)

            if not result or not result['markdown']:
                return doi, False, "Failed to convert to markdown"

            # Return success with markdown content
            return doi, True, result['markdown']

        except Exception as e:
            logger.error(f"Error processing DOI {doi}: {e}")
            return doi, False, str(e)

    def update_fulltext_in_db(self, doi: str, markdown: str) -> bool:
        """
        Update fulltext in the database.

        Args:
            doi: DOI of the preprint
            markdown: Markdown content

        Returns:
            Success boolean
        """
        # Use the dedicated method from MedRxivDatabaseManager instead of direct SQL
        try:
            return self.db.update_full_text(doi, markdown)
        except Exception as e:
            logger.error(f"Error updating fulltext for DOI {doi}: {e}")
            return False

    def process_batch(self, records: List[Dict[str, Any]], progress_bar: tqdm) -> Tuple[int, int]:
        """
        Process a batch of records with a thread pool.

        Args:
            records: List of records to process
            progress_bar: Progress bar to update

        Returns:
            Tuple of (successful updates, failed updates)
        """
        success_count = 0
        failure_count = 0

        # Process records in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_record = {executor.submit(self.process_record, record): record for record in records}

            for future in concurrent.futures.as_completed(future_to_record):
                doi, success, result = future.result()
                progress_bar.update(1)

                if success:
                    # If successful, update the database
                    if self.update_fulltext_in_db(doi, result):
                        success_count += 1
                    else:
                        failure_count += 1
                else:
                    # Log the failure but don't stop processing
                    logger.error(f"Failed to process DOI {doi}: {result}")
                    failure_count += 1

        return success_count, failure_count

    def update_all_missing_fulltext(self, limit=None) -> Tuple[int, int, int]:
        """
        Update all records missing fulltext.

        Args:
            limit: Optional limit on the number of records to process

        Returns:
            Tuple of (total processed, success count, failure count)
        """
        # Count records for progress bar
        total_missing = self.count_missing_fulltext_records()
        if limit:
            total_missing = min(total_missing, limit)

        if total_missing == 0:
            logger.info("No records missing fulltext were found.")
            return 0, 0, 0

        logger.info(f"Found {total_missing} records missing fulltext. Starting update process...")

        success_count = 0
        failure_count = 0
        total_processed = 0

        # Create progress bar
        with tqdm(total=total_missing, desc="Processing records") as progress_bar:
            batch = []

            # Process in batches for memory efficiency
            for record in self.get_missing_fulltext_records(limit):
                batch.append(record)

                # Process batch when it reaches the batch size
                if len(batch) >= self.batch_size:
                    batch_success, batch_failure = self.process_batch(batch, progress_bar)
                    success_count += batch_success
                    failure_count += batch_failure
                    total_processed += len(batch)
                    batch = []

            # Process any remaining items
            if batch:
                batch_success, batch_failure = self.process_batch(batch, progress_bar)
                success_count += batch_success
                failure_count += batch_failure
                total_processed += len(batch)

        return total_processed, success_count, failure_count


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Update missing fulltext for medRxiv preprints.')
    parser.add_argument('--output-dir', '-o', default='./output', help='Output directory')
    parser.add_argument('--batch-size', '-b', type=int, default=100, help='Batch size for processing')
    parser.add_argument('--max-workers', '-w', type=int, default=4, help='Maximum number of concurrent workers')
    parser.add_argument('--delay', '-d', type=float, default=0.5, help='Delay between API requests (seconds)')
    parser.add_argument('--limit', '-l', type=int, help='Limit the number of records to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.INFO)

    try:
        # Check for required dependencies
        try:
            # Just check if these modules can be imported
            __import__('lxml')
            __import__('tqdm')
        except ImportError as e:
            logger.error(f"Required dependency missing: {e}")
            logger.error("Please install the required dependencies using:")
            logger.error("pip install requests beautifulsoup4 markdownify lxml tqdm")
            sys.exit(1)

        updater = MissingFulltextUpdater(
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            max_workers=args.max_workers,
            delay=args.delay
        )

        # Run the update process
        total_processed, success_count, failure_count = updater.update_all_missing_fulltext(limit=args.limit)

        # Print summary
        print(f"\nUpdate Complete:")
        print(f"  Total records processed: {total_processed}")
        print(f"  Successful updates: {success_count}")
        print(f"  Failed updates: {failure_count}")

        if failure_count > 0:
            print(f"\nSome records failed to update. Check the log for details.")
            if not args.verbose:
                print("Run with --verbose for more detailed error information.")

    except Exception as e:
        logger.error(f"Error: {e}")
        # Add more detailed error information for debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
