#!/usr/bin/env python3
"""
Update publication dates in tmpdocument table from PubMed XML files.

This script reads PubMed XML files and updates only the publication_date field
in the tmpdocument table for existing records. It's much faster than a full
re-import since it only updates the publication date field.

Usage:
    python update_tmpdocument_publication_dates.py /path/to/xml/files

The script will:
1. Read XML files from the specified directory
2. Extract PMID and publication date from each article
3. Update the publication_date field in tmpdocument table
4. Show progress and statistics
"""

import os
import sys
import gzip
import xml.etree.ElementTree as ET
import logging
from typing import Dict, Any, Optional
from tqdm import tqdm
import argparse

from localknowledge.db.document import DocumentDatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_publication_dates.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def extract_date(date_elem) -> Optional[str]:
    """
    Extract date from a PubMed date element.
    
    Handles both administrative dates and publication dates which may have different structures.
    """
    if date_elem is None:
        return None

    year = date_elem.find('Year')
    month = date_elem.find('Month')
    day = date_elem.find('Day')

    if year is not None and year.text:
        year_text = year.text
        
        # Handle month - could be numeric or text (e.g., "Jan", "Feb")
        month_text = "01"  # Default to January
        if month is not None and month.text:
            month_val = month.text.strip()
            # Try to convert month name to number
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            if month_val in month_map:
                month_text = month_map[month_val]
            elif month_val.isdigit():
                month_text = month_val.zfill(2)
            else:
                # Try to parse as full month name
                month_val_lower = month_val.lower()
                for name, num in month_map.items():
                    if month_val_lower.startswith(name.lower()):
                        month_text = num
                        break
        
        day_text = day.text if day is not None and day.text else "01"
        if day_text.isdigit():
            day_text = day_text.zfill(2)
        else:
            day_text = "01"

        try:
            # Try to parse as ISO format
            return f"{year_text}-{month_text}-{day_text}"
        except Exception:
            return year_text

    return None


def extract_pmid_and_publication_date(article_elem) -> Optional[Dict[str, str]]:
    """
    Extract PMID and publication date from a PubMed article element.
    
    Returns:
        Dictionary with 'pmid' and 'publication_date' keys, or None if PMID not found
    """
    try:
        # Extract PMID
        pmid_elem = article_elem.find('.//PMID')
        if pmid_elem is None or not pmid_elem.text:
            return None

        pmid = pmid_elem.text

        # Extract publication date from PubDate element
        pubdate_elem = article_elem.find('.//PubDate')
        publication_date = None
        
        if pubdate_elem is not None:
            # Try to extract full publication date
            publication_date = extract_date(pubdate_elem)

        return {
            'pmid': pmid,
            'publication_date': publication_date
        }

    except Exception as e:
        logger.error(f"Error processing article: {e}")
        return None


def process_xml_file(xml_file_path: str) -> Dict[str, str]:
    """
    Process a PubMed XML file and extract PMID -> publication_date mappings.
    
    Args:
        xml_file_path: Path to the XML file
        
    Returns:
        Dictionary mapping PMID to publication_date
    """
    pmid_to_date = {}
    
    try:
        with gzip.open(xml_file_path, 'rb') as f:
            # Use iterparse to avoid loading entire file into memory
            context = ET.iterparse(f, events=('end',))
            
            for _, elem in context:
                if elem.tag == 'PubmedArticle':
                    article_data = extract_pmid_and_publication_date(elem)
                    if article_data and article_data['publication_date']:
                        pmid_to_date[article_data['pmid']] = article_data['publication_date']
                    
                    # Clear element to free up memory
                    elem.clear()
                    
    except Exception as e:
        logger.error(f"Error processing file {xml_file_path}: {e}")
        
    return pmid_to_date


def update_publication_dates(xml_dir: str, batch_size: int = 100) -> None:
    """
    Update publication dates in tmpdocument table from XML files.
    
    Args:
        xml_dir: Directory containing PubMed XML files
        batch_size: Number of updates to process in each batch
    """
    # Ensure path is fully expanded
    xml_dir = os.path.abspath(os.path.expanduser(xml_dir))
    
    if not os.path.exists(xml_dir):
        logger.error(f"XML directory {xml_dir} does not exist")
        return
    
    # Get all XML.gz files
    xml_files = [f for f in os.listdir(xml_dir) if f.endswith('.xml.gz')]
    
    if not xml_files:
        logger.info(f"No XML.gz files found in {xml_dir}")
        return
    
    xml_files.sort()
    logger.info(f"Found {len(xml_files)} XML files to process")
    
    # Create database manager
    db_manager = DocumentDatabaseManager()
    
    total_processed = 0
    total_updated = 0
    
    # Process files with progress bar
    main_pbar = tqdm(total=len(xml_files), desc="Processing XML files", unit="file")
    
    for xml_file in xml_files:
        xml_path = os.path.join(xml_dir, xml_file)
        main_pbar.set_description(f"Processing {xml_file}")
        
        # Extract PMID -> publication_date mappings
        pmid_to_date = process_xml_file(xml_path)

        if pmid_to_date:
            # Filter out entries with None publication_date
            valid_pmid_to_date = {pmid: date for pmid, date in pmid_to_date.items() if date is not None}

            if not valid_pmid_to_date:
                main_pbar.set_postfix(
                    processed=total_processed,
                    updated=total_updated,
                    file_articles=f"{len(pmid_to_date)} (no valid dates)"
                )
                main_pbar.update(1)
                continue

            # Update database in batches
            pmids = list(valid_pmid_to_date.keys())

            for i in range(0, len(pmids), batch_size):
                batch_pmids = pmids[i:i + batch_size]

                # Use a simpler approach with individual updates in a transaction
                # This is more reliable than complex CASE statements for large batches

                try:
                    # Begin transaction for the batch
                    db_manager.begin_transaction()

                    batch_updated = 0
                    for pmid in batch_pmids:
                        publication_date = valid_pmid_to_date[pmid]

                        # Simple individual update query
                        query = """
                        UPDATE tmpdocument
                        SET publication_date = %s::date,
                            updated_date = CURRENT_TIMESTAMP
                        WHERE source_id = (SELECT id FROM sources WHERE name = 'pubmed')
                        AND external_id = %s
                        """

                        result = db_manager.execute_without_timeout(
                            query,
                            (publication_date, pmid),
                            commit=False
                        )
                        batch_updated += 1

                    # Commit the entire batch
                    db_manager.commit_transaction()
                    total_updated += batch_updated
                    logger.debug(f"Updated {batch_updated} records in batch")

                except Exception as e:
                    # Rollback on error
                    db_manager.rollback_transaction()
                    logger.error(f"Error updating batch of {len(batch_pmids)} records: {e}")
                    logger.error(f"Sample PMIDs in failed batch: {batch_pmids[:5]}")
                    # Continue with next batch instead of failing completely

            total_processed += len(valid_pmid_to_date)
            main_pbar.set_postfix(
                processed=total_processed,
                updated=total_updated,
                file_articles=f"{len(valid_pmid_to_date)}/{len(pmid_to_date)}"
            )
        
        main_pbar.update(1)
    
    main_pbar.close()
    db_manager.close()
    
    logger.info(f"Update completed:")
    logger.info(f"  Total articles processed: {total_processed}")
    logger.info(f"  Total records updated: {total_updated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Update publication dates in tmpdocument table from PubMed XML files'
    )
    parser.add_argument(
        'xml_dir',
        help='Directory containing PubMed XML files'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of updates to process in each batch (default: 100)'
    )
    
    args = parser.parse_args()
    
    logger.info("Starting publication date update process...")
    update_publication_dates(args.xml_dir, args.batch_size)
    logger.info("Publication date update process completed")
