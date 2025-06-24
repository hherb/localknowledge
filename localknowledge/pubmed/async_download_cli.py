#!/usr/bin/env python3
"""
Command-line interface for the async PubMed downloader.

This script provides a command-line interface to download PubMed files
using the improved async downloader with aioftp.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from localknowledge.pubmed.async_download import (
        AsyncPubMedDownloader,
        download_pubmed_baseline_async,
        download_pubmed_updates_async,
        ASYNC_DEPS_AVAILABLE
    )
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
        logging.FileHandler('async_pubmed_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Main async function."""
    if not ASYNC_DEPS_AVAILABLE:
        print("Error: Required async dependencies are not available.")
        print("Please install them with: pip install aioftp aiofiles")
        sys.exit(1)
        
    parser = argparse.ArgumentParser(
        description='Download PubMed data using async aioftp (improved reliability)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download only updates (default)
  python async_download_cli.py
  
  # Download complete baseline + updates
  python async_download_cli.py --from_scratch
  
  # Download only baseline files
  python async_download_cli.py --from_scratch --skip_updates
  
  # Use custom directory
  python async_download_cli.py --data_dir ~/my_pubmed_data
  
  # Start from highest processed sequence (resume processing)
  python async_download_cli.py --from_highest_processed_seq
  
  # Use more concurrent downloads (faster but more resource intensive)
  python async_download_cli.py --max_concurrent 5
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
    parser.add_argument('--max_concurrent', type=int, default=3,
                        help='Maximum number of concurrent downloads (default: 3)')
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
            logger.info("Starting baseline download with async downloader...")
            await download_pubmed_baseline_async(
                baseline_dir=str(baseline_dir),
                tracker=tracker,
                from_highest_seq=args.from_highest_seq,
                from_highest_processed_seq=args.from_highest_processed_seq,
                max_concurrent_downloads=args.max_concurrent
            )
            logger.info("Baseline download completed")

        # Download update files unless skipped
        if not args.skip_updates:
            logger.info("Starting updates download with async downloader...")
            await download_pubmed_updates_async(
                updates_dir=str(updates_dir),
                tracker=tracker,
                from_highest_seq=args.from_highest_seq,
                from_highest_processed_seq=args.from_highest_processed_seq,
                max_concurrent_downloads=args.max_concurrent
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


def sync_main():
    """Synchronous entry point that runs the async main function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sync_main()
