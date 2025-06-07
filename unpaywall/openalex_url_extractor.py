#!/usr/bin/env python3
"""
OpenAlex DOI and Full Text URL Extractor
========================================

This script extracts DOI and full text URL pairs directly from the OpenAlex snapshot
without importing into a database. Useful for integration with existing systems.

Features:
- Processes compressed JSONL files directly
- Extracts multiple URLs per DOI when available
- Filters by open access status, publication year, etc.
- Outputs to CSV, JSON, or TSV format
- Progress tracking and resumption capability

Usage:
    python extract_urls.py --snapshot-dir /path/to/openalex-snapshot --output urls.csv
"""

import argparse
import csv
import gzip
import json
import logging
import os
import sys
import glob
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union, Tuple, TextIO
from urllib.parse import urlparse
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('openalex_url_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OpenAlexURLExtractor:
    """
    Extracts DOI and full text URL pairs from OpenAlex snapshot data.

    This class processes compressed JSONL files from OpenAlex snapshots to extract
    DOI and URL pairs for academic works. It supports filtering by various criteria
    and can output results in multiple formats (CSV, JSON, TSV).

    Attributes:
        snapshot_dir (Path): Path to the OpenAlex snapshot directory
        output_file (Path): Path to the output file
        output_format (str): Output format ('csv', 'json', or 'tsv')
        resume (bool): Whether to resume from a previous incomplete run
        processed_files (Set[str]): Set of already processed file paths
        progress_file (Path): Path to the progress tracking file
        stats (Dict[str, int]): Statistics about the extraction process
    """

    def __init__(self, snapshot_dir: str, output_file: str,
                 output_format: str = 'csv', resume: bool = False) -> None:
        """
        Initialize the OpenAlex URL extractor.

        Args:
            snapshot_dir: Path to the OpenAlex snapshot directory
            output_file: Path to the output file
            output_format: Output format ('csv', 'json', or 'tsv'). Defaults to 'csv'
            resume: Whether to resume from a previous incomplete run. Defaults to False

        Raises:
            ValueError: If output_format is not one of the supported formats
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.output_file = Path(output_file)
        self.output_format = output_format.lower()
        self.resume = resume

        # Validate output format
        if self.output_format not in {'csv', 'json', 'tsv'}:
            raise ValueError(f"Unsupported output format: {output_format}")

        # Track processed files for resumption
        self.processed_files: Set[str] = set()
        self.progress_file = self.output_file.with_suffix('.progress')

        if self.resume and self.progress_file.exists():
            self._load_progress()

        # Statistics
        self.stats: Dict[str, int] = {
            'total_works_processed': 0,
            'works_with_doi': 0,
            'works_with_urls': 0,
            'total_url_records': 0,
            'files_processed': 0
        }

    def _load_progress(self) -> None:
        """
        Load progress from a previous incomplete run.

        Reads the progress file to restore the list of processed files and
        extraction statistics, allowing the extraction to resume from where
        it left off.

        Raises:
            Warning: If the progress file cannot be read or parsed
        """
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                self.processed_files = set(progress_data.get('processed_files', []))
                self.stats = progress_data.get('stats', self.stats)
            logger.info(f"Resuming from previous run. {len(self.processed_files)} files already processed.")
        except Exception as e:
            logger.warning(f"Could not load progress file: {e}")

    def _save_progress(self) -> None:
        """
        Save current progress to enable resumption of incomplete runs.

        Writes the list of processed files and current statistics to a progress
        file that can be used to resume extraction if the process is interrupted.

        Raises:
            Warning: If the progress file cannot be written
        """
        try:
            progress_data = {
                'processed_files': list(self.processed_files),
                'stats': self.stats,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save progress: {e}")

    def extract_urls_from_work(self, work: Dict[str, Any],
                              filters: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract DOI and URL pairs from a single OpenAlex work record.

        Processes a work record to extract all available URLs along with metadata
        such as DOI, title, publication year, and access information. URLs are
        extracted from primary location, alternate locations, and best OA location.

        Args:
            work: OpenAlex work record as a dictionary
            filters: Dictionary of filters to apply (year range, OA status, etc.)

        Returns:
            List of dictionaries, each containing DOI, URL, and metadata for one
            URL found in the work record. Empty list if no valid URLs found or
            if the work doesn't pass the filters.

        Note:
            Each returned dictionary contains the following keys:
            - doi, openalex_id, title, publication_year, url, location_type,
              version, license, host_type, oa_status, is_oa
        """
        # Validate input
        if not work or not isinstance(work, dict):
            return []

        # Check if work has DOI
        doi = work.get('doi')
        if not doi:
            return []

        # Additional validation for critical fields
        try:
            # Test access to potentially problematic nested structures
            _ = work.get('open_access', {})
            _ = work.get('primary_location', {})
            _ = work.get('locations', [])
            _ = work.get('best_oa_location', {})
        except Exception as e:
            logger.warning(f"Invalid work structure detected: {e}")
            return []

        # Apply filters
        if not self._passes_filters(work, filters):
            return []
        
        url_records = []
        work_id = work.get('id', '')
        publication_year = work.get('publication_year')
        title = work.get('title', '')

        # Safely access nested open_access data
        open_access_data = work.get('open_access') or {}
        oa_status = open_access_data.get('oa_status', 'closed')
        is_oa = open_access_data.get('is_oa', False)
        
        # Helper function to create URL record
        def create_url_record(url: str, location_type: str,
                            version: Optional[str] = None,
                            license_info: Optional[str] = None,
                            host_type: Optional[str] = None) -> Dict[str, str]:
            """
            Create a standardized URL record dictionary.

            Args:
                url: The URL to include in the record
                location_type: Type of location (primary, alternate, best_oa, etc.)
                version: Version information (publishedVersion, acceptedVersion, etc.)
                license_info: License information if available
                host_type: Type of host (journal, repository, preprint_server, etc.)

            Returns:
                Dictionary containing all URL record fields
            """
            return {
                'doi': doi,
                'openalex_id': work_id,
                'title': title,
                'publication_year': str(publication_year) if publication_year else '',
                'url': url,
                'location_type': location_type,  # primary, alternate, publisher, repository
                'version': version or '',
                'license': license_info or '',
                'host_type': host_type or '',
                'oa_status': oa_status,
                'is_oa': str(is_oa)
            }
        
        # Extract from primary location
        if primary_location := work.get('primary_location'):
            url = primary_location.get('landing_page_url')
            if url and self._is_valid_url(url):
                url_records.append(create_url_record(
                    url=url,
                    location_type='primary',
                    version=primary_location.get('version'),
                    license_info=primary_location.get('license'),
                    host_type=self._get_host_type(primary_location)
                ))
        
        # Extract from all locations (including alternates)
        locations = work.get('locations', [])
        for i, location in enumerate(locations):
            url = location.get('landing_page_url')
            if url and self._is_valid_url(url):
                # Skip if it's the same as primary location
                primary_location = work.get('primary_location') or {}
                if primary_location.get('landing_page_url') == url:
                    continue
                
                location_type = 'alternate' if i > 0 else 'secondary'
                url_records.append(create_url_record(
                    url=url,
                    location_type=location_type,
                    version=location.get('version'),
                    license_info=location.get('license'),
                    host_type=self._get_host_type(location)
                ))
        
        # Extract from best OA location if different
        if best_oa_location := work.get('best_oa_location'):
            url = best_oa_location.get('landing_page_url')
            if url and self._is_valid_url(url):
                # Check if we already have this URL
                existing_urls = {record['url'] for record in url_records}
                if url not in existing_urls:
                    url_records.append(create_url_record(
                        url=url,
                        location_type='best_oa',
                        version=best_oa_location.get('version'),
                        license_info=best_oa_location.get('license'),
                        host_type=self._get_host_type(best_oa_location)
                    ))
        
        return url_records

    def _passes_filters(self, work: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if a work record passes the specified filters.

        Applies various filters to determine if a work should be included in
        the extraction results. Filters can include publication year range,
        open access status, work types, and retraction status.

        Args:
            work: OpenAlex work record as a dictionary
            filters: Dictionary containing filter criteria:
                - year_range: Tuple of (min_year, max_year) or None values
                - oa_only: Boolean, if True only include open access works
                - language: String, language code to filter by
                - types: List of work types to include
                - exclude_retracted: Boolean, if True exclude retracted works

        Returns:
            True if the work passes all specified filters, False otherwise
        """
        # Publication year filter
        if year_range := filters.get('year_range'):
            pub_year = work.get('publication_year')
            if pub_year:
                if year_range[0] and pub_year < year_range[0]:
                    return False
                if year_range[1] and pub_year > year_range[1]:
                    return False

        # Open access filter
        if filters.get('oa_only'):
            open_access_data = work.get('open_access') or {}
            if not open_access_data.get('is_oa', False):
                return False

        # Language filter (if available in future OpenAlex versions)
        if language := filters.get('language'):
            work_language = work.get('language')
            if work_language and work_language != language:
                return False

        # Type filter
        if work_types := filters.get('types'):
            work_type = work.get('type')
            if work_type and work_type not in work_types:
                return False

        # Exclude retracted works
        if filters.get('exclude_retracted', True):
            if work.get('is_retracted', False):
                return False

        return True

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid and potentially useful for full-text access.

        Performs basic URL validation and filters out URLs that are unlikely
        to provide access to full-text content (e.g., mailto links, JavaScript
        URLs, fragment-only URLs).

        Args:
            url: The URL string to validate

        Returns:
            True if the URL appears to be valid and useful, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
        except Exception:
            return False

        # Filter out obvious non-fulltext URLs
        url_lower = url.lower()
        exclude_patterns = [
            'mailto:',
            'javascript:',
            'about:',
            '#',  # Fragment-only URLs
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        return True

    def _get_host_type(self, location: Dict[str, Any]) -> str:
        """
        Determine the type of host for a given location.

        Analyzes the source information in a location record to classify
        the type of host (journal, repository, preprint server, etc.).
        This helps users understand the nature of the URL source.

        Args:
            location: Location dictionary from OpenAlex work record

        Returns:
            String indicating the host type. Possible values:
            - 'doaj_journal': Journal listed in Directory of Open Access Journals
            - 'preprint_server': Preprint servers like arXiv, bioRxiv
            - 'repository': Institutional or subject repositories
            - 'journal': Regular journal
            - 'other': Unknown or other type of host
        """
        if not location or not isinstance(location, dict):
            return 'other'

        source = location.get('source') or {}
        if not isinstance(source, dict):
            return 'other'

        # Check if it's in DOAJ (Directory of Open Access Journals)
        if source.get('is_in_doaj'):
            return 'doaj_journal'

        # Check host organization type
        host_org_name = source.get('host_organization_name')
        host_org = (host_org_name or '').lower()

        if any(term in host_org for term in ['arxiv', 'preprint', 'biorxiv', 'medrxiv']):
            return 'preprint_server'
        elif any(term in host_org for term in ['pubmed', 'pmc', 'europepmc']):
            return 'repository'
        elif source.get('type') == 'repository':
            return 'repository'
        elif source.get('type') == 'journal':
            return 'journal'
        else:
            return 'other'

    def process_works_file(self, jsonl_file: str,
                          output_writer: Union[csv.DictWriter, TextIO],
                          filters: Dict[str, Any]) -> Dict[str, int]:
        """
        Process a single compressed JSONL file containing OpenAlex works.

        Reads through a gzipped JSONL file line by line, extracts URL records
        from each work that passes the filters, and writes them to the output.

        Args:
            jsonl_file: Path to the compressed JSONL file to process
            output_writer: CSV writer or file object for writing output
            filters: Dictionary of filters to apply to works

        Returns:
            Dictionary containing statistics about the processed file:
            - works_processed: Total number of works processed
            - works_with_doi: Number of works that have a DOI
            - works_with_urls: Number of works that yielded URL records
            - url_records_created: Total number of URL records created
        """
        file_stats = {
            'works_processed': 0,
            'works_with_doi': 0,
            'works_with_urls': 0,
            'url_records_created': 0
        }
        
        try:
            with gzip.open(jsonl_file, 'rt', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Skip empty lines
                        line = line.strip()
                        if not line:
                            continue

                        work = json.loads(line)

                        # Validate that work is a dictionary and not None
                        if not isinstance(work, dict):
                            logger.warning(f"Invalid work data in {jsonl_file} line {line_num}: expected dict, got {type(work)}")
                            continue

                        file_stats['works_processed'] += 1

                        # Extract URL records for this work
                        try:
                            url_records = self.extract_urls_from_work(work, filters)
                        except Exception as e:
                            logger.error(f"Error extracting URLs from work in {jsonl_file} line {line_num}: {e}")
                            # Log work structure for debugging
                            work_keys = list(work.keys()) if isinstance(work, dict) else "Not a dict"
                            logger.debug(f"Work keys: {work_keys}")
                            if isinstance(work, dict) and 'id' in work:
                                logger.debug(f"Work ID: {work.get('id')}")
                            url_records = []

                        if work.get('doi'):
                            file_stats['works_with_doi'] += 1
                        
                        if url_records:
                            file_stats['works_with_urls'] += 1
                            file_stats['url_records_created'] += len(url_records)
                            
                            # Write records
                            for record in url_records:
                                if self.output_format == 'csv':
                                    output_writer.writerow(record)
                                elif self.output_format == 'json':
                                    output_writer.write(json.dumps(record) + '\n')
                                elif self.output_format == 'tsv':
                                    # TSV writer
                                    output_writer.writerow(record)
                        
                        if file_stats['works_processed'] % 50000 == 0:
                            logger.info(f"Processed {file_stats['works_processed']} works in {jsonl_file}")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error in {jsonl_file} line {line_num}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing work in {jsonl_file} line {line_num}: {e}")
                        # Log the problematic line for debugging (first 200 chars)
                        logger.debug(f"Problematic line content: {line[:200]}...")
                        continue
                        
        except Exception as e:
            logger.error(f"Error reading file {jsonl_file}: {e}")
            return file_stats
        
        return file_stats

    def extract_urls(self, filters: Optional[Dict[str, Any]] = None,
                    max_workers: int = 4) -> None:
        """
        Extract DOI and URL pairs from all OpenAlex works files.

        Main method that orchestrates the extraction process. Finds all works
        files in the snapshot directory, processes them according to the
        specified filters, and writes the results to the output file.

        Args:
            filters: Optional dictionary of filters to apply. If None, no filters
                    are applied. See _passes_filters() for supported filter types.
            max_workers: Number of parallel workers for processing (currently
                        not used as processing is sequential to avoid file conflicts)

        Note:
            This method handles progress tracking and can resume from incomplete
            runs if the resume option was enabled during initialization.
        """
        if filters is None:
            filters = {}
        
        logger.info("Starting URL extraction from OpenAlex works...")
        
        # Find all works files
        works_pattern = self.snapshot_dir / 'data' / 'works' / '*' / '*.gz'
        works_files = list(glob.glob(str(works_pattern)))
        
        if not works_files:
            logger.error(f"No works files found at {works_pattern}")
            return
        
        # Filter out already processed files if resuming
        if self.resume:
            works_files = [f for f in works_files if f not in self.processed_files]
        
        logger.info(f"Found {len(works_files)} works files to process")
        
        # Prepare output file
        output_mode = 'a' if (self.resume and self.output_file.exists()) else 'w'
        
        if self.output_format == 'csv':
            fieldnames = [
                'doi', 'openalex_id', 'title', 'publication_year', 'url',
                'location_type', 'version', 'license', 'host_type', 
                'oa_status', 'is_oa'
            ]
            
            with open(self.output_file, output_mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if output_mode == 'w':  # Write header only for new files
                    writer.writeheader()
                
                self._process_files_parallel(works_files, writer, filters, max_workers)
                
        elif self.output_format == 'json':
            with open(self.output_file, output_mode, encoding='utf-8') as jsonfile:
                self._process_files_parallel(works_files, jsonfile, filters, max_workers)
                
        elif self.output_format == 'tsv':
            fieldnames = [
                'doi', 'openalex_id', 'title', 'publication_year', 'url',
                'location_type', 'version', 'license', 'host_type', 
                'oa_status', 'is_oa'
            ]
            
            with open(self.output_file, output_mode, newline='', encoding='utf-8') as tsvfile:
                writer = csv.DictWriter(tsvfile, fieldnames=fieldnames, delimiter='\t')
                if output_mode == 'w':
                    writer.writeheader()
                
                self._process_files_parallel(works_files, writer, filters, max_workers)
        
        # Clean up progress file on successful completion
        if self.progress_file.exists():
            self.progress_file.unlink()
        
        self._print_final_stats()

    def _process_files_parallel(self, works_files: List[str],
                               output_writer: Union[csv.DictWriter, TextIO],
                               filters: Dict[str, Any], max_workers: int) -> None:
        """
        Process multiple works files sequentially.

        Despite the name suggesting parallel processing, this method currently
        processes files sequentially to avoid file writing conflicts. Future
        versions could implement proper synchronization for parallel processing.

        Args:
            works_files: List of file paths to process
            output_writer: CSV writer or file object for writing output
            filters: Dictionary of filters to apply to works
            max_workers: Number of workers (currently unused)
        """
        # For simplicity, process files sequentially to avoid file writing conflicts
        # Could be optimized with proper synchronization if needed
        for i, works_file in enumerate(works_files):
            logger.info(f"Processing file {i+1}/{len(works_files)}: {works_file}")
            
            file_stats = self.process_works_file(works_file, output_writer, filters)
            
            # Update global stats
            self.stats['total_works_processed'] += file_stats['works_processed']
            self.stats['works_with_doi'] += file_stats['works_with_doi']
            self.stats['works_with_urls'] += file_stats['works_with_urls']
            self.stats['total_url_records'] += file_stats['url_records_created']
            self.stats['files_processed'] += 1
            
            # Mark file as processed
            self.processed_files.add(works_file)
            
            # Save progress periodically
            if (i + 1) % 10 == 0:
                self._save_progress()
            
            logger.info(f"File completed. {file_stats['works_with_urls']} works with URLs, "
                       f"{file_stats['url_records_created']} URL records created")

    def _print_final_stats(self) -> None:
        """
        Print final extraction statistics to the log.

        Displays a summary of the extraction process including the number
        of files processed, works processed, URL coverage statistics, and
        the output file location.
        """
        logger.info("=" * 60)
        logger.info("URL EXTRACTION COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Total works processed: {self.stats['total_works_processed']:,}")
        logger.info(f"Works with DOI: {self.stats['works_with_doi']:,}")
        logger.info(f"Works with URLs: {self.stats['works_with_urls']:,}")
        logger.info(f"Total URL records: {self.stats['total_url_records']:,}")

        if self.stats['works_with_doi'] > 0:
            url_percentage = (self.stats['works_with_urls'] / self.stats['works_with_doi']) * 100
            logger.info(f"URL coverage: {url_percentage:.1f}% of DOI works have URLs")

        logger.info(f"Output saved to: {self.output_file}")


def main() -> None:
    """
    Main function that handles command-line arguments and runs the extraction.

    Parses command-line arguments, builds filter configuration, creates an
    OpenAlexURLExtractor instance, and runs the URL extraction process.

    Command-line Arguments:
        --snapshot-dir: Path to OpenAlex snapshot directory (required)
        --output: Output file path (required)
        --format: Output format (csv, json, tsv) - default: csv
        --year-from: Include works from this year onwards
        --year-to: Include works up to this year
        --oa-only: Only include open access works
        --types: Include only specific work types
        --exclude-retracted: Exclude retracted works (default: True)
        --resume: Resume from previous incomplete run
        --max-workers: Number of parallel workers (default: 4)
    """
    parser = argparse.ArgumentParser(
        description='Extract DOI and URL pairs from OpenAlex snapshot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction to CSV
  python openalex_url_extractor.py --snapshot-dir /path/to/snapshot --output urls.csv

  # Extract only open access works from 2020 onwards
  python openalex_url_extractor.py --snapshot-dir /path/to/snapshot --output urls.csv --oa-only --year-from 2020

  # Extract only journal articles to JSON format
  python openalex_url_extractor.py --snapshot-dir /path/to/snapshot --output urls.json --format json --types journal-article
        """
    )

    parser.add_argument('--snapshot-dir', required=True,
                        help='Path to OpenAlex snapshot directory')
    parser.add_argument('--output', required=True,
                        help='Output file path')
    parser.add_argument('--format', choices=['csv', 'json', 'tsv'], default='csv',
                        help='Output format (default: csv)')
    parser.add_argument('--year-from', type=int,
                        help='Include works from this year onwards')
    parser.add_argument('--year-to', type=int,
                        help='Include works up to this year')
    parser.add_argument('--oa-only', action='store_true',
                        help='Only include open access works')
    parser.add_argument('--types', nargs='+',
                        help='Include only specific work types (e.g., journal-article, book-chapter)')
    parser.add_argument('--exclude-retracted', action='store_true', default=True,
                        help='Exclude retracted works (default: True)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous incomplete run')
    parser.add_argument('--max-workers', type=int, default=4,
                        help='Number of parallel workers (default: 4)')

    args = parser.parse_args()

    # Build filters dictionary from command-line arguments
    filters: Dict[str, Any] = {}

    if args.year_from or args.year_to:
        filters['year_range'] = (args.year_from, args.year_to)

    if args.oa_only:
        filters['oa_only'] = True

    if args.types:
        filters['types'] = args.types

    filters['exclude_retracted'] = args.exclude_retracted

    # Create extractor and run
    try:
        extractor = OpenAlexURLExtractor(
            snapshot_dir=args.snapshot_dir,
            output_file=args.output,
            output_format=args.format,
            resume=args.resume
        )

        extractor.extract_urls(filters=filters, max_workers=args.max_workers)

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
