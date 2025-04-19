"""
Module for importing downloaded PubMed XML files into the database.

This module processes PubMed XML files that have been downloaded using the download.py script.
It parses the XML, extracts article information, and stores it in a PostgreSQL database.
It also tracks which files have been processed to avoid redundant processing when run regularly.
"""
import os
import gzip
import xml.etree.ElementTree as ET
import shutil
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import time
from tqdm import tqdm
import argparse
import sys

from localknowledge.db.pubmed import PubMedDatabaseManager
from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# Set up logging - Configure file handler for all logs, and stream handler only for errors
# Create logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler that logs all messages
file_handler = logging.FileHandler('pubmed_import.log')
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# Create console handler that only logs ERROR and higher
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Only show ERROR and CRITICAL in console
console_format = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)




def extract_date(date_elem) -> Optional[str]:
    """Extract date from a PubMed date element."""
    if date_elem is None:
        return None
    
    year = date_elem.find('Year')
    month = date_elem.find('Month')
    day = date_elem.find('Day')
    
    if year is not None and year.text:
        year_text = year.text
        month_text = month.text if month is not None and month.text else "01"
        day_text = day.text if day is not None and day.text else "01"
        
        try:
            # Try to parse as ISO format
            return f"{year_text}-{month_text.zfill(2)}-{day_text.zfill(2)}"
        except Exception:
            return year_text
    
    return None


def process_article(article_elem) -> Optional[Dict[str, Any]]:
    """
    Process a single PubMedArticle XML element.
    
    Args:
        article_elem: ElementTree element for a PubMedArticle
        
    Returns:
        Dictionary with article data or None if error
    """
    try:
        # Extract PMID
        pmid_elem = article_elem.find('.//PMID')
        if pmid_elem is None or not pmid_elem.text:
            return None
            
        pmid = pmid_elem.text
        
        # Extract title
        title_elem = article_elem.find('.//ArticleTitle')
        title = title_elem.text if title_elem is not None and title_elem.text else ""
        
        # Extract abstract
        abstract_texts = article_elem.findall('.//AbstractText')
        abstract = " ".join([t.text for t in abstract_texts if t is not None and t.text is not None])
        
        # Extract authors
        author_elems = article_elem.findall('.//Author')
        authors = []
        for author in author_elems:
            last_name = author.find('.//LastName')
            fore_name = author.find('.//ForeName')
            
            author_name = ""
            if last_name is not None and last_name.text:
                author_name += last_name.text
            if fore_name is not None and fore_name.text:
                author_name += f" {fore_name.text}" if author_name else fore_name.text
                
            if author_name:
                authors.append(author_name)
        
        author_string = ", ".join(authors)
        
        # Extract publication year
        year_elem = article_elem.find('.//PubDate/Year')
        if year_elem is None:
            # Try alternate locations for year
            year_elem = article_elem.find('.//PubMedPubDate[@PubStatus="pubmed"]/Year')
            
        year = year_elem.text if year_elem is not None and year_elem.text else ""
        
        # Extract journal
        journal_elem = article_elem.find('.//Journal/Title')
        journal = journal_elem.text if journal_elem is not None and journal_elem.text else ""
        
        # Extract MeSH terms
        mesh_elems = article_elem.findall('.//MeshHeading/DescriptorName')
        mesh_terms = ", ".join([m.text for m in mesh_elems if m is not None and m.text is not None])
        
        # Extract keywords
        keyword_elems = article_elem.findall('.//Keyword')
        keywords = ", ".join([k.text for k in keyword_elems if k is not None and k.text is not None])
        
        # Extract DOI
        doi_elem = article_elem.find('.//ArticleId[@IdType="doi"]')
        doi = doi_elem.text if doi_elem is not None and doi_elem.text else ""
        
        # Extract dates
        date_created_elem = article_elem.find('.//DateCreated')
        date_completed_elem = article_elem.find('.//DateCompleted')
        date_revised_elem = article_elem.find('.//DateRevised')
        
        date_created = extract_date(date_created_elem)
        date_completed = extract_date(date_completed_elem)
        date_revised = extract_date(date_revised_elem)
        
        article_data = {
            'pmid': pmid,
            'title': title,
            'abstract': abstract,
            'authors': author_string,
            'publication_year': year,
            'journal': journal,
            'mesh_terms': mesh_terms,
            'keywords': keywords,
            'doi': doi,
            'date_created': date_created,
            'date_completed': date_completed,
            'date_revised': date_revised,
            'pdf_path': ""
        }
        
        return article_data
    
    except Exception as e:
        logger.error(f"Error processing article: {e}")
        return None


def process_xml_file(xml_file_path: str, db_manager: PubMedDatabaseManager, batch_size: int = 100) -> Tuple[int, int]:
    """
    Process a PubMed XML file and store articles in database.
    
    Args:
        xml_file_path: Path to the XML file
        db_manager: Database manager instance
        batch_size: Batch size for database inserts
        
    Returns:
        Tuple of (processed_count, successful_count)
    """
    try:
        logger.info(f"Processing {os.path.basename(xml_file_path)}...")
        processed_count = 0
        successful_count = 0
        
        with gzip.open(xml_file_path, 'rb') as f:
            # Use iterparse to avoid loading entire file into memory
            context = ET.iterparse(f, events=('end',))
            
            batch = []
            
            for event, elem in context:
                if elem.tag == 'PubmedArticle':
                    processed_count += 1
                    
                    article_data = process_article(elem)
                    if article_data:
                        batch.append(article_data)
                        successful_count += 1
                    
                    # Process batches to avoid excessive memory use
                    if len(batch) >= batch_size:
                        db_manager.store_articles_batch(batch)
                        batch = []
                    
                    # Clear element to free up memory
                    elem.clear()
                
                # Show periodic progress
                if processed_count % 1000 == 0:
                    logger.info(f"Processed {processed_count} articles from {os.path.basename(xml_file_path)}...")
            
            # Process any remaining articles
            if batch:
                db_manager.store_articles_batch(batch)
                
        logger.info(f"Completed processing {os.path.basename(xml_file_path)}: "
                   f"{successful_count} articles stored out of {processed_count} processed")
        return processed_count, successful_count
        
    except Exception as e:
        logger.error(f"Error processing file {xml_file_path}: {e}")
        return processed_count, successful_count


def import_downloads(download_dir: str = None, 
                     imported_dir: str = None, 
                     create_imported_dir: bool = True,
                     tracker: PubMedDownloadTracker = None,
                     only_unprocessed: bool = False,
                     file_type: str = None) -> Tuple[int, int]:
    """
    Process downloaded PubMed XML files, import them into database, and move to 'imported' folder.
    
    Args:
        download_dir: Directory containing downloaded PubMed XML files
                     (defaults to ~/knowledgebase/pubmed_data/baseline)
        imported_dir: Directory to move processed files to
                     (defaults to ~/knowledgebase/pubmed_data/imported)
        create_imported_dir: Whether to create the imported directory if it doesn't exist
        tracker: Optional PubMedDownloadTracker instance for tracking processed files
        only_unprocessed: Only process files that haven't been marked as processed in the tracker
        file_type: Optional filter by file type ('baseline' or 'update')
        
    Returns:
        Tuple of (total_articles_processed, total_articles_stored)
    """
    # Set default paths if not provided
    if download_dir is None:
        download_dir = os.path.expanduser('~/knowledgebase/pubmed_data/baseline')
    
    if imported_dir is None:
        imported_dir = os.path.expanduser('~/knowledgebase/pubmed_data/imported')
    
    # Ensure paths are fully expanded
    download_dir = os.path.abspath(os.path.expanduser(download_dir))
    imported_dir = os.path.abspath(os.path.expanduser(imported_dir))
    
    logger.info(f"Starting PubMed import from {download_dir}")
    
    # Determine if we're using database tracking
    using_db_tracker = tracker is not None
    
    # Create imported directory if it doesn't exist
    if create_imported_dir and not os.path.exists(imported_dir):
        try:
            os.makedirs(imported_dir, exist_ok=True)
            logger.info(f"Created directory for imported files: {imported_dir}")
        except Exception as e:
            logger.error(f"Error creating imported directory {imported_dir}: {e}")
            return 0, 0
    
    # Check if download directory exists
    if not os.path.exists(download_dir):
        logger.error(f"Download directory {download_dir} does not exist")
        return 0, 0
    
    # Get list of files to process based on tracking status
    if using_db_tracker and only_unprocessed:
        # Get files from the tracker that are downloaded but not processed
        unprocessed_files = set(tracker.get_unprocessed_files(file_type))
        if unprocessed_files:
            logger.info(f"Found {len(unprocessed_files)} unprocessed files in the database")
            # Filter to those that actually exist in the directory
            all_files = set(os.listdir(download_dir))
            xml_files = sorted(list(unprocessed_files.intersection(all_files)))
            logger.info(f"{len(xml_files)} of these files are available in {download_dir}")
        else:
            logger.info("No unprocessed files found in the tracker database")
            xml_files = []
    else:
        # Get all XML.gz files in the directory
        xml_files = [f for f in os.listdir(download_dir) if f.endswith('.xml.gz')]
        
        # If using tracker but not restricted to unprocessed, still filter out already processed files
        if using_db_tracker:
            original_count = len(xml_files)
            xml_files = [f for f in xml_files if not tracker.is_file_downloaded(f) or 
                        f in tracker.get_unprocessed_files()]
            logger.info(f"Filtered out {original_count - len(xml_files)} already processed files")
    
    if not xml_files:
        logger.info(f"No files to process in {download_dir}")
        return 0, 0
    
    # Sort files to process them in order
    xml_files.sort()
    
    logger.info(f"Found {len(xml_files)} files to process")
    
    # Create database manager
    db_manager = PubMedDatabaseManager()
    
    total_processed = 0
    total_stored = 0
    
    # Process files with a progress bar
    # Main progress bar for files
    main_pbar = tqdm(total=len(xml_files), desc="Importing PubMed files", 
                    unit="file", position=0, leave=True, 
                    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
    
    for i, xml_file in enumerate(xml_files):
        xml_path = os.path.join(download_dir, xml_file)
        
        # Update progress bar description to show current file
        main_pbar.set_description(f"Processing {xml_file}")
        
        # Process file
        processed, stored = process_xml_file(xml_path, db_manager)
        
        total_processed += processed
        total_stored += stored
        
        # Update progress bar to include article counts
        main_pbar.set_postfix(articles=f"{stored}/{processed}", 
                             total=f"{total_stored}/{total_processed}")
        
        # Mark as processed in the tracker if available
        if using_db_tracker and processed > 0:
            tracker.mark_as_processed(xml_file)
        
        # Move file to imported directory if successful
        if processed > 0:
            try:
                dest_path = os.path.join(imported_dir, xml_file)
                shutil.move(xml_path, dest_path)
                # Use tqdm.write for logging to avoid disrupting progress bar
                tqdm.write(f"✓ Moved {xml_file} to {imported_dir}")
            except Exception as e:
                tqdm.write(f"✗ Error moving {xml_file} to {imported_dir}: {e}")
        
        # Update the main progress bar
        main_pbar.update(1)
        
        # Sleep a tiny bit to avoid overwhelming the database
        time.sleep(0.1)
    
    # Close progress bar
    main_pbar.close()
    
    # Show final statistics
    logger.info(f"Import completed: {total_stored} articles stored out of {total_processed} processed")
    
    # Get updated statistics from the database
    stats = db_manager.get_stats()
    logger.info(f"Total articles in database: {stats['total_articles']}")
    
    # Close the database connection
    db_manager.close()
    
    return total_processed, total_stored


if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Import PubMed XML files into database')
    parser.add_argument('--baseline_dir', 
                        help='Directory containing baseline files (default: ~/knowledgebase/pubmed_data/baseline)')
    parser.add_argument('--updates_dir',
                        help='Directory containing update files (default: ~/knowledgebase/pubmed_data/updates)')
    parser.add_argument('--imported_dir',
                        help='Directory to move processed files to (default: ~/knowledgebase/pubmed_data/imported)')
    parser.add_argument('--process_type', choices=['baseline', 'updates', 'both'], default='updates',
                        help='Type of files to process (default: updates)')
    parser.add_argument('--no_db_tracking', action='store_true',
                        help='Do not use database tracking')
    parser.add_argument('--force_reprocess', action='store_true',
                        help='Process files even if they are already marked as processed')
    parser.add_argument('--show_stats', action='store_true',
                        help='Show statistics about downloaded and processed files')
    
    args = parser.parse_args()
    
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
        stats = tracker.get_download_stats()
        logger.info("=== PubMed File Processing Statistics ===")
        logger.info(f"Total tracked files: {stats['total_files']}")
        logger.info(f"Downloaded files: {stats['downloaded_files']}")
        logger.info(f"Processed files: {stats['processed_files']}")
        logger.info(f"Baseline files: {stats['baseline_files']}")
        logger.info(f"Update files: {stats['update_files']}")
        
        if stats['last_download_date']:
            logger.info(f"Last download: {stats['last_download_date']}")
        if stats['last_process_date']:
            logger.info(f"Last processing: {stats['last_process_date']}")
        logger.info("=======================================")
        
        # If only showing stats, exit
        if args.process_type == 'none':
            sys.exit(0)
    
    # Set up directories
    baseline_dir = os.path.expanduser(args.baseline_dir) if args.baseline_dir else os.path.expanduser('~/knowledgebase/pubmed_data/baseline')
    updates_dir = os.path.expanduser(args.updates_dir) if args.updates_dir else os.path.expanduser('~/knowledgebase/pubmed_data/updates')
    imported_dir = os.path.expanduser(args.imported_dir) if args.imported_dir else os.path.expanduser('~/knowledgebase/pubmed_data/imported')
    
    only_unprocessed = not args.force_reprocess
    
    # Process files based on the selected type
    if args.process_type == 'baseline' or args.process_type == 'both':
        logger.info("Processing baseline files")
        import_downloads(
            download_dir=baseline_dir, 
            imported_dir=imported_dir,
            tracker=tracker,
            only_unprocessed=only_unprocessed,
            file_type='baseline'
        )
    
    if args.process_type == 'updates' or args.process_type == 'both':
        logger.info("Processing update files")
        import_downloads(
            download_dir=updates_dir, 
            imported_dir=imported_dir,
            tracker=tracker,
            only_unprocessed=only_unprocessed,
            file_type='update'
        )
    
    logger.info("Import process completed")
