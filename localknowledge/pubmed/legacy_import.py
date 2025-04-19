"""
Legacy import utility for adding existing PubMed files to the tracking database.

This script scans directories containing previously downloaded PubMed files
and registers them in the pubmed_download_log table to integrate them with
the new tracking system.

It also verifies file integrity using MD5 checksums, downloading missing MD5 files
from the NCBI FTP server when necessary.
"""
import os
import re
import hashlib
import logging
import argparse
import time
import ftplib
import socket
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# FTP connection parameters for NCBI PubMed
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
BASELINE_PATH = '/pubmed/baseline'
UPDATES_PATH = '/pubmed/updatefiles'
FTP_TIMEOUT = 60  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pubmed_legacy_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def create_ftp_connection():
    """
    Create an FTP connection to the NCBI PubMed server.
    
    Returns:
        FTP connection object
    """
    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=FTP_TIMEOUT)
        ftp.login()  # Anonymous login
        logger.info(f"Connected to FTP server {FTP_HOST}")
        return ftp
    except Exception as e:
        logger.error(f"Failed to connect to FTP server: {e}")
        raise


def download_md5_file(xml_file: str, md5_file_path: str) -> bool:
    """
    Download a missing MD5 file from the NCBI FTP server.
    
    Args:
        xml_file: Name of the XML file (e.g. 'pubmed25n0001.xml.gz')
        md5_file_path: Local path where to save the MD5 file
        
    Returns:
        True if download was successful, False otherwise
    """
    # Determine if it's a baseline or update file based on the sequence number
    match = re.search(r'pubmed\d+n(\d+)\.xml\.gz', xml_file)
    if not match:
        logger.warning(f"Cannot determine file type for {xml_file}, filename format not recognized")
        return False
        
    seq_number = int(match.group(1))
    # The update files typically have higher sequence numbers than baseline files
    # For 2025, updates start at 1275 according to documentation
    ftp_path = BASELINE_PATH if seq_number < 1275 else UPDATES_PATH
    
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            ftp = create_ftp_connection()
            ftp.cwd(ftp_path)
            
            md5_filename = f"{xml_file}.md5"
            
            # Check if the file exists on the server
            try:
                file_size = ftp.size(md5_filename)
            except:
                logger.warning(f"MD5 file {md5_filename} not found on FTP server in {ftp_path}")
                return False
            
            logger.info(f"Downloading MD5 file {md5_filename} from {ftp_path}")
            
            # Download the file
            with open(md5_file_path, 'wb') as f:
                ftp.retrbinary(f'RETR {md5_filename}', f.write)
            
            ftp.quit()
            logger.info(f"Successfully downloaded MD5 file to {md5_file_path}")
            return True
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"Error downloading MD5 file (attempt {retry_count}/{MAX_RETRIES}): {e}")
            
            # Sleep before retrying
            time.sleep(RETRY_DELAY)
            
            try:
                ftp.quit()
            except:
                pass
                
    logger.error(f"Failed to download MD5 file after {MAX_RETRIES} attempts")
    return False


def verify_md5(file_path: str, download_missing: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verify a file's MD5 checksum against its corresponding .md5 file.
    
    Args:
        file_path: Path to the XML.gz file to verify
        download_missing: Whether to try downloading missing MD5 files
        
    Returns:
        Tuple of (verification_result, checksum_value, error_message)
    """
    md5_file_path = file_path + '.md5'
    
    # Check if MD5 file exists, download if missing and requested
    if not os.path.exists(md5_file_path) and download_missing:
        xml_file = os.path.basename(file_path)
        downloaded = download_md5_file(xml_file, md5_file_path)
        if not downloaded:
            return False, None, "MD5 file not found locally and could not be downloaded"
    elif not os.path.exists(md5_file_path):
        return False, None, "MD5 file not found locally"
    
    try:
        # Calculate MD5 hash for the file
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        calculated_hash = md5_hash.hexdigest()
        
        # Read expected hash from .md5 file
        with open(md5_file_path, 'r') as f:
            md5_content = f.read().strip()
            # MD5 files from NCBI typically contain the MD5 followed by the filename
            expected_hash = md5_content.split()[0] if ' ' in md5_content else md5_content
        
        if calculated_hash.lower() == expected_hash.lower():
            return True, calculated_hash, None
        else:
            return False, calculated_hash, f"Checksum mismatch: expected {expected_hash}, got {calculated_hash}"
            
    except Exception as e:
        return False, None, f"Error verifying MD5: {e}"


def register_legacy_files(
    baseline_dir: Optional[str] = None,
    updates_dir: Optional[str] = None,
    imported_dir: Optional[str] = None,
    mark_as_processed: bool = False,
    verify_checksums: bool = False,
    download_missing_md5: bool = False,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Register existing PubMed XML files in the tracking database.
    
    Args:
        baseline_dir: Directory containing baseline files
        updates_dir: Directory containing update files
        imported_dir: Directory containing already imported files
        mark_as_processed: Whether to mark files as processed (True) or just downloaded (False)
        verify_checksums: Whether to verify MD5 checksums if available
        dry_run: If True, don't actually add files to the database
        
    Returns:
        Tuple of (baseline_count, updates_count, imported_count)
    """
    # Initialize counts
    baseline_count = 0
    updates_count = 0
    imported_count = 0
    verified_count = 0
    failed_verification_count = 0
    
    # Initialize tracker
    tracker = PubMedDownloadTracker()
    
    # Process baseline directory
    if baseline_dir and os.path.exists(baseline_dir):
        baseline_dir = os.path.abspath(os.path.expanduser(baseline_dir))
        logger.info(f"Scanning baseline directory: {baseline_dir}")
        baseline_files = [f for f in os.listdir(baseline_dir) if f.endswith('.xml.gz')]
        
        if baseline_files:
            logger.info(f"Found {len(baseline_files)} baseline files")
            pbar = tqdm(baseline_files, desc="Registering baseline files")
            for xml_file in pbar:
                file_path = os.path.join(baseline_dir, xml_file)
                file_size = os.path.getsize(file_path)
                
                # Verify MD5 checksum if requested
                checksum = None
                if verify_checksums:
                    is_verified, checksum, error_msg = verify_md5(file_path, download_missing=download_missing_md5)
                    status = "✓" if is_verified else "✗"
                    pbar.set_description(f"Registering baseline files [{status}]")
                    if is_verified:
                        verified_count += 1
                    else:
                        failed_verification_count += 1
                        logger.warning(f"MD5 verification failed for {xml_file}: {error_msg}")
                
                if not dry_run:
                    tracker.log_download(xml_file, 'baseline', file_size)
                    # Store the checksum if available
                    if checksum:
                        # This requires updating the tracker to accept checksum parameter
                        try:
                            with tracker.connection.cursor() as cursor:
                                cursor.execute(
                                    "UPDATE pubmed_download_log SET checksum = %s WHERE file_name = %s",
                                    (checksum, xml_file)
                                )
                                tracker.connection.commit()
                        except Exception as e:
                            logger.error(f"Error updating checksum: {e}")
                    
                    if mark_as_processed:
                        tracker.mark_as_processed(xml_file)
                
                baseline_count += 1
                pbar.set_postfix(count=baseline_count, verified=verified_count)
    
    # Process updates directory
    if updates_dir and os.path.exists(updates_dir):
        updates_dir = os.path.abspath(os.path.expanduser(updates_dir))
        logger.info(f"Scanning updates directory: {updates_dir}")
        update_files = [f for f in os.listdir(updates_dir) if f.endswith('.xml.gz')]
        
        if update_files:
            logger.info(f"Found {len(update_files)} update files")
            pbar = tqdm(update_files, desc="Registering update files")
            for xml_file in pbar:
                file_path = os.path.join(updates_dir, xml_file)
                file_size = os.path.getsize(file_path)
                
                # Verify MD5 checksum if requested
                checksum = None
                if verify_checksums:
                    is_verified, checksum, error_msg = verify_md5(file_path, download_missing=download_missing_md5)
                    status = "✓" if is_verified else "✗"
                    pbar.set_description(f"Registering update files [{status}]")
                    if is_verified:
                        verified_count += 1
                    else:
                        failed_verification_count += 1
                        logger.warning(f"MD5 verification failed for {xml_file}: {error_msg}")
                
                if not dry_run:
                    tracker.log_download(xml_file, 'update', file_size)
                    # Store the checksum if available
                    if checksum:
                        try:
                            with tracker.connection.cursor() as cursor:
                                cursor.execute(
                                    "UPDATE pubmed_download_log SET checksum = %s WHERE file_name = %s",
                                    (checksum, xml_file)
                                )
                                tracker.connection.commit()
                        except Exception as e:
                            logger.error(f"Error updating checksum: {e}")
                    
                    if mark_as_processed:
                        tracker.mark_as_processed(xml_file)
                
                updates_count += 1
                pbar.set_postfix(count=updates_count, verified=verified_count)
    
    # Process imported directory
    if imported_dir and os.path.exists(imported_dir):
        imported_dir = os.path.abspath(os.path.expanduser(imported_dir))
        logger.info(f"Scanning imported directory: {imported_dir}")
        imported_files = [f for f in os.listdir(imported_dir) if f.endswith('.xml.gz')]
        
        if imported_files:
            logger.info(f"Found {len(imported_files)} imported files")
            pbar = tqdm(imported_files, desc="Registering imported files")
            for xml_file in pbar:
                file_path = os.path.join(imported_dir, xml_file)
                file_size = os.path.getsize(file_path)
                
                # Verify MD5 checksum if requested
                checksum = None
                if verify_checksums:
                    is_verified, checksum, error_msg = verify_md5(file_path, download_missing=download_missing_md5)
                    status = "✓" if is_verified else "✗"
                    pbar.set_description(f"Registering imported files [{status}]")
                    if is_verified:
                        verified_count += 1
                    else:
                        failed_verification_count += 1
                        logger.warning(f"MD5 verification failed for {xml_file}: {error_msg}")
                
                # For imported files, we always mark them as processed
                if not dry_run:
                    # Determine if it's a baseline or update file based on file number
                    # Format is typically pubmed25n0001.xml.gz for baseline or pubmed25n1220.xml.gz for updates
                    # According to NLM docs: The first Update file after the 2025 baseline is pubmed25n1220.xml
                    # So we can use this to distinguish baseline from update files
                    
                    # Extract the sequence number from the filename
                    match = re.search(r'pubmed\d+n(\d+)\.xml\.gz', xml_file)
                    if match:
                        seq_number = int(match.group(1))
                        # The update files typically have higher sequence numbers than baseline files
                        # For 2025, updates start at 1275 according to documentation
                        file_type = 'baseline' if seq_number < 1275 else 'update'
                    else:
                        # Fallback if the filename doesn't match expected pattern
                        file_type = 'update'  # Default to update if unsure
                    
                    tracker.log_download(xml_file, file_type, file_size)
                    tracker.mark_as_processed(xml_file)
                    
                    # Store the checksum if available
                    if checksum:
                        try:
                            with tracker.connection.cursor() as cursor:
                                cursor.execute(
                                    "UPDATE pubmed_download_log SET checksum = %s WHERE file_name = %s",
                                    (checksum, xml_file)
                                )
                                tracker.connection.commit()
                        except Exception as e:
                            logger.error(f"Error updating checksum: {e}")
                
                imported_count += 1
                pbar.set_postfix(count=imported_count)
    
    total_count = baseline_count + updates_count + imported_count
    
    if not dry_run:
        logger.info(f"Successfully registered {total_count} files in the tracking database")
        logger.info(f"- Baseline files: {baseline_count}")
        logger.info(f"- Update files: {updates_count}")
        logger.info(f"- Imported files: {imported_count}")
    else:
        logger.info(f"Dry run complete. Would register {total_count} files in the tracking database")
        logger.info(f"- Baseline files: {baseline_count}")
        logger.info(f"- Update files: {updates_count}")
        logger.info(f"- Imported files: {imported_count}")
    
    # Display final statistics
    if not dry_run:
        stats = tracker.get_download_stats()
        logger.info("=== Final Tracking Statistics ===")
        logger.info(f"Total tracked files: {stats['total_files']}")
        logger.info(f"Processed files: {stats['processed_files']}")
        logger.info(f"Unprocessed files: {stats['downloaded_files']}")
        logger.info(f"Baseline files: {stats['baseline_files']}")
        logger.info(f"Update files: {stats['update_files']}")
    
    return (baseline_count, updates_count, imported_count)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Register existing PubMed files in the tracking database")
    parser.add_argument("--baseline-dir", 
                     help="Directory containing baseline files (default: ~/knowledgebase/pubmed_data/baseline)")
    parser.add_argument("--updates-dir", 
                     help="Directory containing update files (default: ~/knowledgebase/pubmed_data/updates)")
    parser.add_argument("--imported-dir", 
                     help="Directory containing already imported files (default: ~/knowledgebase/pubmed_data/imported)")
    parser.add_argument("--mark-processed", action="store_true", 
                     help="Mark files in baseline and updates directories as already processed")
    parser.add_argument("--verify-checksums", action="store_true",
                     help="Verify MD5 checksums for all files")
    parser.add_argument("--download-missing-md5", action="store_true",
                     help="Download missing MD5 files from NCBI FTP server")
    parser.add_argument("--dry-run", action="store_true", 
                     help="Don't actually add files to the database, just show what would be done")
    
    args = parser.parse_args()
    
    # Set default directories if not provided
    baseline_dir = args.baseline_dir if args.baseline_dir else os.path.expanduser("~/knowledgebase/pubmed_data/baseline")
    updates_dir = args.updates_dir if args.updates_dir else os.path.expanduser("~/knowledgebase/pubmed_data/updates")
    imported_dir = args.imported_dir if args.imported_dir else os.path.expanduser("~/knowledgebase/pubmed_data/imported")
    
    # Run the registration function
    register_legacy_files(
        baseline_dir=baseline_dir,
        updates_dir=updates_dir,
        imported_dir=imported_dir,
        mark_as_processed=args.mark_processed,
        dry_run=args.dry_run
    )
