"""
Module for importing downloaded PubMed XML files into the tmpdocument table.

This module processes PubMed XML files from a backup directory and imports them into
the tmpdocument table for data recovery purposes. It does not modify any other tables
or tracking systems.
"""
import os
import gzip
import xml.etree.ElementTree as ET
import logging
from typing import Dict, Any, List, Optional, Tuple
import time
from tqdm import tqdm
import argparse

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.pubmed.file_verification import check_xml_integrity

# Modified database managers for tmpdocument table
class TmpDocumentDatabaseManager(DocumentDatabaseManager):
    """Modified DocumentDatabaseManager that uses tmpdocument table instead of document."""
    
    def add_document(self, document_data: Dict[str, Any]) -> Optional[int]:
        """Add a new document to the tmpdocument table."""
        # Get source ID
        source_name = document_data.get('source_name')
        if not source_name:
            logger.error("Source name is required")
            return None

        source_id = self.get_source_id(source_name)
        if not source_id:
            logger.error(f"Source '{source_name}' not found")
            return None

        # Get category ID if provided
        category_id = None
        category_name = document_data.get('category_name')
        if category_name:
            category_id = self.get_category_id(category_name)

        # Prepare parameters
        params = (
            source_id,
            document_data.get('external_id', ''),
            document_data.get('doi', ''),
            document_data.get('title', ''),
            document_data.get('abstract', ''),
            category_id,
            document_data.get('keywords', []),
            document_data.get('augmented_keywords', []),
            document_data.get('mesh_terms', []),
            document_data.get('authors', []),
            document_data.get('publication', ''),
            document_data.get('publication_date'),
            document_data.get('url', ''),
            document_data.get('pdf_url', ''),
            document_data.get('pdf_filename', ''),
            document_data.get('full_text', '')
        )

        # Insert document into tmpdocument table
        query = """
        INSERT INTO tmpdocument (
            source_id, external_id, doi, title, abstract, category_id,
            keywords, augmented_keywords, mesh_terms, authors,
            publication, publication_date, url, pdf_url, pdf_filename, full_text
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (source_id, external_id) DO UPDATE SET
            doi = EXCLUDED.doi,
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            category_id = EXCLUDED.category_id,
            keywords = EXCLUDED.keywords,
            augmented_keywords = EXCLUDED.augmented_keywords,
            mesh_terms = EXCLUDED.mesh_terms,
            authors = EXCLUDED.authors,
            publication = EXCLUDED.publication,
            publication_date = EXCLUDED.publication_date,
            url = EXCLUDED.url,
            pdf_url = EXCLUDED.pdf_url,
            pdf_filename = EXCLUDED.pdf_filename,
            full_text = EXCLUDED.full_text,
            updated_date = CURRENT_TIMESTAMP
        RETURNING id
        """

        try:
            # Use execute_without_timeout for document insertion to prevent timeouts during import
            result = self.execute_without_timeout(query, params, commit=True)
            if result:
                document_id = result[0]['id']
                logger.debug(f"Document added to tmpdocument with ID: {document_id}")
                return document_id
            logger.error("No result returned from tmpdocument insertion query")
            return None
        except Exception as e:
            logger.error(f"Error adding document to tmpdocument: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


class TmpPubMedDatabaseManager(DatabaseManager):
    """Modified PubMedDatabaseManager that uses tmpdocument table."""
    
    def __init__(self):
        """Initialize the temporary PubMed database manager."""
        super().__init__()
        logger.info("Initializing temporary PubMed database manager for tmpdocument")
        self.document_db = TmpDocumentDatabaseManager()
        self.source_id = self._get_pubmed_source_id()

    def _get_pubmed_source_id(self) -> int:
        """Get the source ID for PubMed."""
        source_id = self.document_db.get_source_id('pubmed')
        if not source_id:
            logger.error("PubMed source not found in the database")
            raise ValueError("PubMed source not found in the database")
        return source_id

    def store_article(self, article: Dict[str, Any]) -> Optional[int]:
        """Store a PubMed article in the tmpdocument table."""
        # Convert PubMed article data to document format
        document_data = {
            'source_name': 'pubmed',
            'external_id': article.get('pmid', ''),
            'doi': article.get('doi', ''),
            'title': article.get('title', ''),
            'abstract': article.get('abstract', ''),
            'authors': article.get('authors', '').split(', ') if article.get('authors') else [],
            'publication_date': article.get('publication_date', ''),  # Use actual publication date
            'publication': article.get('journal', ''),
            'mesh_terms': article.get('mesh_terms', '').split('; ') if article.get('mesh_terms') else [],
            'keywords': article.get('keywords', '').split('; ') if article.get('keywords') else [],
            'url': f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}" if article.get('pmid') else '',
            'pdf_filename': article.get('pdf_path', '')
        }

        try:
            document_id = self.document_db.add_document(document_data)
            if document_id:
                logger.debug(f"Stored PubMed article with PMID {article.get('pmid')} as tmpdocument ID {document_id}")
            else:
                logger.error(f"Failed to store PubMed article with PMID {article.get('pmid')} in tmpdocument")
            return document_id
        except Exception as e:
            logger.error(f"Error storing PubMed article in tmpdocument: {e}")
            return None

    def store_articles_batch(self, articles: List[Dict[str, Any]]) -> int:
        """Store multiple PubMed articles in the tmpdocument table."""
        if not articles:
            return 0

        count = 0
        for article in articles:
            try:
                document_id = self.store_article(article)
                if document_id:
                    count += 1
            except Exception as e:
                logger.error(f"Error storing article with PMID {article.get('pmid', 'unknown')} in tmpdocument: {e}")
                continue

        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about articles in tmpdocument table."""
        query = "SELECT COUNT(*) as total_articles FROM tmpdocument WHERE source_id = %s"
        try:
            result = self.execute(query, (self.source_id,))
            return {'total_articles': result[0]['total_articles'] if result else 0}
        except Exception as e:
            logger.error(f"Error getting tmpdocument stats: {e}")
            return {'total_articles': 0}

    def close(self):
        """Close database connections."""
        if hasattr(self, 'document_db'):
            self.document_db.close()
        super().close()


# Set up logging - Configure file handler for all logs, and stream handler only for errors
# Create logger
logger = logging.getLogger()
logger.setLevel(logging.WARNING)

# Remove any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler that logs all messages
file_handler = logging.FileHandler('pubmed_import_tmpdocument.log')
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# Create console handler that logs INFO and higher (for better visibility)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Show INFO, WARNING, ERROR and CRITICAL in console
console_format = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)




def get_element_text(elem) -> str:
    """
    Get complete text from an XML element, handling mixed content.

    This function properly extracts text from elements that contain both
    text and child elements (like subscripts, superscripts, etc.).
    Unlike elem.text which only returns text before the first child element,
    this function returns all text content.

    Args:
        elem: XML element to extract text from

    Returns:
        Complete text content of the element
    """
    if elem is None:
        return ""

    # If element has no children, just return its text
    if not list(elem):
        return elem.text or ""

    # Build text from element text + all child text + tail text
    text = elem.text or ""
    for child in elem:
        # Get text from child element recursively
        child_text = get_element_text(child)
        text += child_text

        # Add tail text (text that comes after the child element)
        if child.tail:
            text += child.tail

    return text


def extract_date(date_elem) -> Optional[str]:
    """
    Extract date from a PubMed date element.

    Handles both administrative dates (DateCreated, DateCompleted, DateRevised)
    and publication dates (PubDate) which may have different structures.
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
        title = get_element_text(title_elem) if title_elem is not None else ""

        # Extract abstract - use proper text extraction to handle mixed content
        abstract_texts = article_elem.findall('.//AbstractText')
        abstract_parts = []
        for t in abstract_texts:
            if t is not None:
                text = get_element_text(t)
                if text:
                    abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        # Extract authors
        author_elems = article_elem.findall('.//Author')
        authors = []
        for author in author_elems:
            last_name = author.find('.//LastName')
            fore_name = author.find('.//ForeName')

            author_name = ""
            if last_name is not None:
                last_name_text = get_element_text(last_name)
                if last_name_text:
                    author_name += last_name_text
            if fore_name is not None:
                fore_name_text = get_element_text(fore_name)
                if fore_name_text:
                    author_name += f" {fore_name_text}" if author_name else fore_name_text

            if author_name:
                authors.append(author_name)

        author_string = ", ".join(authors)

        # Extract publication date from PubDate element
        pubdate_elem = article_elem.find('.//PubDate')
        publication_date = None
        year = ""

        if pubdate_elem is not None:
            # Try to extract full publication date
            publication_date = extract_date(pubdate_elem)

            # Also extract year for backward compatibility
            year_elem = pubdate_elem.find('Year')
            year = year_elem.text if year_elem is not None and year_elem.text else ""

        # If no PubDate found, try alternate locations for year only
        if not year:
            year_elem = article_elem.find('.//PubMedPubDate[@PubStatus="pubmed"]/Year')
            year = year_elem.text if year_elem is not None and year_elem.text else ""

        # Extract journal
        journal_elem = article_elem.find('.//Journal/Title')
        journal = get_element_text(journal_elem) if journal_elem is not None else ""

        # Extract MeSH terms
        mesh_elems = article_elem.findall('.//MeshHeading/DescriptorName')
        mesh_parts = []
        for m in mesh_elems:
            if m is not None:
                text = get_element_text(m)
                if text:
                    mesh_parts.append(text)
        mesh_terms = ", ".join(mesh_parts)

        # Extract keywords
        keyword_elems = article_elem.findall('.//Keyword')
        keyword_parts = []
        for k in keyword_elems:
            if k is not None:
                text = get_element_text(k)
                if text:
                    keyword_parts.append(text)
        keywords = ", ".join(keyword_parts)

        # Extract DOI
        doi_elem = article_elem.find('.//ArticleId[@IdType="doi"]')
        doi = get_element_text(doi_elem) if doi_elem is not None else ""

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
            'publication_date': publication_date,
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


def process_xml_file(xml_file_path: str, db_manager: TmpPubMedDatabaseManager, batch_size: int = 100) -> Tuple[int, int]:
    """
    Process a PubMed XML file and store articles in tmpdocument table.

    Args:
        xml_file_path: Path to the XML file
        db_manager: Database manager instance
        batch_size: Batch size for database inserts

    Returns:
        Tuple of (processed_count, successful_count)
    """
    try:
        file_name = os.path.basename(xml_file_path)
        logger.info(f"Processing {file_name}...")
        processed_count = 0
        successful_count = 0

        # First count the number of articles for the progress bar
        article_count = 0
        try:
            with gzip.open(xml_file_path, 'rb') as count_f:
                for _, line in enumerate(count_f):
                    if b'<PubmedArticle>' in line:
                        article_count += 1
        except Exception as e:
            # If we can't even count the articles, the file is likely corrupt
            error_msg = str(e)
            if "CRC check failed" in error_msg or "decompressing data" in error_msg:
                logger.error(f"CRC check failed while counting articles in {file_name}: {error_msg}")
                raise ValueError(f"File {file_name} appears to be corrupt (decompression error): {error_msg}")
            else:
                logger.error(f"Error counting articles in {file_name}: {error_msg}")
                raise

        # Now process with a progress bar
        try:
            with gzip.open(xml_file_path, 'rb') as f:
                # Use iterparse to avoid loading entire file into memory
                context = ET.iterparse(f, events=('end',))

                batch = []

                # Create article processing progress bar
                article_pbar = tqdm(
                    total=article_count,
                    desc=f"Articles in {file_name}",
                    unit="article",
                    position=1,  # Position below the main progress bar
                    leave=False  # Don't leave this bar when done
                )

                for _, elem in context:
                    if elem.tag == 'PubmedArticle':
                        processed_count += 1

                        article_data = process_article(elem)
                        # Update the progress bar
                        article_pbar.update(1)
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

        except Exception as e:
            # If we can't open the file for processing, it's likely corrupt
            error_msg = str(e)
            if "CRC check failed" in error_msg or "decompressing data" in error_msg:
                logger.error(f"CRC check failed while processing {file_name}: {error_msg}")
                raise ValueError(f"File {file_name} appears to be corrupt (decompression error): {error_msg}")
            else:
                logger.error(f"Error processing {file_name}: {error_msg}")
                raise

        logger.info(f"Completed processing {os.path.basename(xml_file_path)}: "
                   f"{successful_count} articles stored out of {processed_count} processed")
        return processed_count, successful_count

    except Exception as e:
        logger.error(f"Error processing file {xml_file_path}: {e}")
        return processed_count, successful_count


def import_downloads_to_tmp(backup_dir: str) -> Tuple[int, int]:
    """
    Process PubMed XML files from backup directory and import them into tmpdocument table.

    Args:
        backup_dir: Directory containing backup PubMed XML files

    Returns:
        Tuple of (total_articles_processed, total_articles_stored)
    """
    # Ensure path is fully expanded
    backup_dir = os.path.abspath(os.path.expanduser(backup_dir))

    logger.info(f"Starting PubMed import from backup directory: {backup_dir}")

    # Check if backup directory exists
    if not os.path.exists(backup_dir):
        logger.error(f"Backup directory {backup_dir} does not exist")
        return 0, 0

    # Get all XML.gz files in the directory (both baseline and updates)
    xml_files = [f for f in os.listdir(backup_dir) if f.endswith('.xml.gz')]

    if not xml_files:
        logger.info(f"No XML.gz files to process in {backup_dir}")
        return 0, 0

    # Sort files to process them in order
    xml_files.sort()

    logger.info(f"Found {len(xml_files)} files to process")

    # Create database manager
    try:
        db_manager = TmpPubMedDatabaseManager()
        logger.info(f"Temporary Database Manager instantiated successfully")
    except Exception as e:
        logger.error(f"ERROR creating temporary database manager: {e}")
        raise

    total_processed = 0
    total_stored = 0

    # Process files with a progress bar
    main_pbar = tqdm(total=len(xml_files), desc="Importing PubMed files to tmpdocument",
                    unit="file", position=0, leave=True,
                    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
    logger.info("Starting file processing...")
    for xml_file in xml_files:
        xml_path = os.path.join(backup_dir, xml_file)

        # Update progress bar description to show current file
        main_pbar.set_description(f"Processing {xml_file}")

        # Basic file integrity check
        try:
            # Display that we're checking file integrity
            main_pbar.set_postfix(status="Checking integrity")

            # Perform basic integrity check
            if not check_xml_integrity(xml_path):
                logger.warning(f"File {xml_file} appears to be corrupt, skipping")
                tqdm.write(f"⚠️ File integrity check failed for {xml_file}, skipping")
                main_pbar.set_postfix(status="Corrupt file")
                main_pbar.update(1)
                continue
        except Exception as e:
            logger.error(f"Error during file verification: {e}")
            tqdm.write(f"✗ Error checking file integrity for {xml_file}: {e}")
            main_pbar.set_postfix(status="Verification error")
            main_pbar.update(1)
            continue

        # Process the file
        try:
            # Show that we're now processing articles
            main_pbar.set_postfix(status="Processing articles")

            processed, stored = process_xml_file(xml_path, db_manager)
            total_processed += processed
            total_stored += stored

            # Update progress bar to include article counts
            main_pbar.set_postfix(articles=f"{stored}/{processed}",
                                 total=f"{total_stored}/{total_processed}")

            if processed > 0:
                tqdm.write(f"✓ Processed {xml_file}: {stored} articles stored out of {processed} processed")
            else:
                tqdm.write(f"⚠️ No articles processed from {xml_file}")

        except Exception as e:
            logger.error(f"Error processing file {xml_file}: {e}")
            tqdm.write(f"✗ Error processing file {xml_file}: {e}")
            main_pbar.set_postfix(status="Processing failed")

        # Update the main progress bar
        main_pbar.update(1)

        # Sleep a tiny bit to avoid overwhelming the database
        time.sleep(0.1)

    # Close progress bar
    main_pbar.close()

    # Show final statistics
    logger.info(f"Import to tmpdocument completed: {total_stored} articles stored out of {total_processed} processed")

    # Get updated statistics from the database
    stats = db_manager.get_stats()
    logger.info(f"Total articles in tmpdocument table: {stats['total_articles']}")

    # Close the database connection
    db_manager.close()

    return total_processed, total_stored


if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Import PubMed XML files into tmpdocument table from backup directory')
    parser.add_argument('backup_dir',
                        help='Directory containing backup PubMed XML files')

    args = parser.parse_args()

    # Process files from backup directory
    logger.info("Starting PubMed import to tmpdocument table")
    total_processed, total_stored = import_downloads_to_tmp(args.backup_dir)
    logger.info(f"Import process completed: {total_stored} articles stored out of {total_processed} processed")
