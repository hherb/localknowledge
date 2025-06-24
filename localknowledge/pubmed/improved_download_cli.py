#!/usr/bin/env python3
"""
Command-line interface for the improved PubMed downloader.

This script provides a drop-in replacement for the original download.py
with much better handling of EOFError and connection issues.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from localknowledge.pubmed.improved_download import ImprovedPubMedDownloader
    from localknowledge.pubmed.download_tracker import PubMedDownloadTracker
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you're running from the correct directory and all dependencies are installed.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('improved_pubmed_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def download_pubmed_baseline_improved(
    baseline_dir: str,
    tracker: PubMedDownloadTracker = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False
):
    """Download PubMed baseline files using the improved downloader."""
    baseline_path = Path(baseline_dir).expanduser().resolve()
    baseline_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting improved PubMed baseline download to {baseline_path}")
    
    downloader = ImprovedPubMedDownloader()
    
    # Determine starting point
    last_downloaded_file = None
    if tracker and (from_highest_seq or from_highest_processed_seq):
        highest_seq = tracker.get_highest_sequence_number(processed_only=from_highest_processed_seq)
        if highest_seq > 0:
            last_downloaded_file = f"pubmed25n{highest_seq}.xml.gz"
            logger.info(f"Starting download from sequence number {highest_seq}")
    
    # Get list of files
    ftp = downloader.create_ftp_connection()
    try:
        ftp.cwd('/pubmed/baseline')
        files = ftp.nlst('*.xml.gz')
        files.sort()
        
        # Skip files if we have a checkpoint
        if last_downloaded_file and last_downloaded_file in files:
            start_index = files.index(last_downloaded_file) + 1
            files = files[start_index:]
            logger.info(f"Resuming from file after {last_downloaded_file}")
            
    finally:
        ftp.quit()
    
    total_files = len(files)
    logger.info(f"Found {total_files} PubMed baseline files to download")
    
    # Download files
    for i, xml_file in enumerate(files, 1):
        local_file = baseline_path / xml_file
        
        # Check if file already exists and is valid
        if _should_skip_file(xml_file, local_file, tracker, 'baseline'):
            logger.info(f"Skipping existing valid file {xml_file} ({i}/{total_files})")
            continue
            
        # Download the file
        success, checksum = downloader.download_single_file(
            xml_file, local_file, 'baseline', i, total_files
        )
        
        if success:
            # Log to database if tracker provided
            if tracker:
                try:
                    file_size = local_file.stat().st_size
                    tracker.log_download(xml_file, 'baseline', file_size)
                    
                    if checksum:
                        with tracker.connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE pubmed_download_log SET checksum = %s WHERE file_name = %s",
                                (checksum, xml_file)
                            )
                            tracker.connection.commit()
                except Exception as e:
                    logger.error(f"Error logging download to database: {e}")
        else:
            logger.error(f"Failed to download {xml_file}, continuing with next file")
            
    logger.info("Improved PubMed baseline download completed")


def download_pubmed_updates_improved(
    updates_dir: str,
    tracker: PubMedDownloadTracker = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False
):
    """Download PubMed update files using the improved downloader."""
    updates_path = Path(updates_dir).expanduser().resolve()
    updates_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting improved PubMed updates download to {updates_path}")
    
    downloader = ImprovedPubMedDownloader()
    
    # Determine starting point
    last_downloaded_file = None
    if tracker and (from_highest_seq or from_highest_processed_seq):
        highest_seq = tracker.get_highest_sequence_number(processed_only=from_highest_processed_seq)
        if highest_seq > 0:
            last_downloaded_file = f"pubmed25n{highest_seq}.xml.gz"
            logger.info(f"Starting download from sequence number {highest_seq}")
    
    # Get list of files
    ftp = downloader.create_ftp_connection()
    try:
        ftp.cwd('/pubmed/updatefiles')
        files = ftp.nlst('*.xml.gz')
        files.sort()
        
        # Skip files if we have a checkpoint
        if last_downloaded_file and last_downloaded_file in files:
            start_index = files.index(last_downloaded_file) + 1
            files = files[start_index:]
            logger.info(f"Resuming from file after {last_downloaded_file}")
            
    finally:
        ftp.quit()
    
    total_files = len(files)
    logger.info(f"Found {total_files} PubMed update files to download")
    
    # Download files
    for i, xml_file in enumerate(files, 1):
        local_file = updates_path / xml_file
        
        # Check if file already exists and is valid
        if _should_skip_file(xml_file, local_file, tracker, 'update'):
            logger.info(f"Skipping existing valid file {xml_file} ({i}/{total_files})")
            continue
            
        # Download the file
        success, checksum = downloader.download_single_file(
            xml_file, local_file, 'update', i, total_files
        )
        
        if success:
            # Log to database if tracker provided
            if tracker:
                try:
                    file_size = local_file.stat().st_size
                    tracker.log_download(xml_file, 'update', file_size)
                    
                    if checksum:
                        with tracker.connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE pubmed_download_log SET checksum = %s WHERE file_name = %s",
                                (checksum, xml_file)
                            )
                            tracker.connection.commit()
                except Exception as e:
                    logger.error(f"Error logging download to database: {e}")
        else:
            logger.error(f"Failed to download {xml_file}, continuing with next file")
            
    logger.info("Improved PubMed updates download completed")


def _should_skip_file(xml_file: str, local_file: Path, tracker: PubMedDownloadTracker, file_type: str) -> bool:
    """Check if a file should be skipped (already downloaded and valid)."""
    # Check database first if tracker available
    if tracker:
        if file_type == 'update' and tracker.is_file_processed(xml_file):
            return True
        if tracker.is_file_downloaded(xml_file):
            # Verify file still exists and is valid
            if local_file.exists():
                downloader = ImprovedPubMedDownloader()
                if downloader._verify_file_integrity(local_file):
                    return True
                    
    # Check local file
    if local_file.exists():
        downloader = ImprovedPubMedDownloader()
        if downloader._verify_file_integrity(local_file):
            # Log to database if tracker available and not already logged
            if tracker and not tracker.is_file_downloaded(xml_file):
                try:
                    file_size = local_file.stat().st_size
                    tracker.log_download(xml_file, file_type, file_size)
                except Exception as e:
                    logger.error(f"Error logging existing file to database: {e}")
            return True
                    
    return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Download PubMed data using improved ftplib (better EOFError handling)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download only updates (default)
  python improved_download_cli.py
  
  # Download complete baseline + updates
  python improved_download_cli.py --from_scratch
  
  # Download only baseline files
  python improved_download_cli.py --from_scratch --skip_updates
  
  # Use custom directory
  python improved_download_cli.py --data_dir ~/my_pubmed_data
  
  # Start from highest processed sequence (resume processing)
  python improved_download_cli.py --from_highest_processed_seq
        """
    )
    
    parser.add_argument('--from_scratch', action='store_true',
                        help='Download the complete baseline data in addition to updates')
    parser.add_argument('--data_dir', default='~/knowledgebase/pubmed_data',
                        help='Directory to store downloaded files (default: ~/knowledgebase/pubmed_data)')
    parser.add_argument('--skip_updates', action='store_true',
                        help='Skip downloading updates (only relevant when used with --from_scratch)')
    parser.add_argument('--no_db_tracking', action='store_true',
                        help='Do not use database tracking')
    parser.add_argument('--show_stats', action='store_true',
                        help='Show statistics about downloaded and processed files')
    parser.add_argument('--from_highest_seq', action='store_true',
                        help='Start download from the highest sequence number in the database')
    parser.add_argument('--from_highest_processed_seq', action='store_true',
                        help='Start download from the highest processed sequence number in the database')
    parser.add_argument('--baseline_only', action='store_true',
                        help='Download only baseline files (equivalent to --from_scratch --skip_updates)')
    parser.add_argument('--updates_only', action='store_true',
                        help='Download only update files (default behavior)')

    args = parser.parse_args()
    
    # Handle convenience flags
    if args.baseline_only:
        args.from_scratch = True
        args.skip_updates = True
    elif args.updates_only:
        args.from_scratch = False
        args.skip_updates = False

    # Set up directories
    data_dir = Path(args.data_dir).expanduser().resolve()
    baseline_dir = data_dir / 'baseline'
    updates_dir = data_dir / 'updates'
    
    logger.info(f"Using data directory: {data_dir}")
    
    # Create directories
    data_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    updates_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize database tracker if not disabled
    tracker = None
    if not args.no_db_tracking:
        try:
            tracker = PubMedDownloadTracker()
            logger.info("Database tracking initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tracking: {e}")
            logger.info("Continuing without database tracking")

    # Show statistics if requested
    if args.show_stats and tracker:
        try:
            stats = tracker.get_download_stats()
            logger.info("Download Statistics:")
            logger.info(f"  Total files downloaded: {stats.get('total_downloaded', 0)}")
            logger.info(f"  Baseline files: {stats.get('baseline_count', 0)}")
            logger.info(f"  Update files: {stats.get('update_count', 0)}")
            logger.info(f"  Total size: {stats.get('total_size', 0) / (1024**3):.2f} GB")
            
            processed_stats = tracker.get_processing_stats()
            logger.info(f"  Files processed: {processed_stats.get('total_processed', 0)}")
            logger.info(f"  Articles processed: {processed_stats.get('total_articles', 0)}")
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")

    try:
        # Download baseline files if requested
        if args.from_scratch:
            logger.info("Starting baseline download with improved downloader...")
            download_pubmed_baseline_improved(
                str(baseline_dir),
                tracker=tracker,
                from_highest_seq=args.from_highest_seq,
                from_highest_processed_seq=args.from_highest_processed_seq
            )
            logger.info("Baseline download completed")

        # Download update files unless skipped
        if not args.skip_updates:
            logger.info("Starting updates download with improved downloader...")
            download_pubmed_updates_improved(
                str(updates_dir),
                tracker=tracker,
                from_highest_seq=args.from_highest_seq,
                from_highest_processed_seq=args.from_highest_processed_seq
            )
            logger.info("Updates download completed")

        logger.info("All downloads completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        sys.exit(1)
    finally:
        # Clean up database connection
        if tracker:
            try:
                tracker.close()
            except:
                pass


if __name__ == "__main__":
    main()
