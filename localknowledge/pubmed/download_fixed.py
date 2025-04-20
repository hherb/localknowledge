"""This script downloads the complete PubMed baseline dataset and updates from the NCBI FTP server.
It includes functionality to resume downloads in case of interruptions and handles large files efficiently.
It also includes logging for tracking the download process and errors.

The script uses the `ftplib` library for FTP connections and `gzip` for handling compressed files.
It also uses `xml.etree.ElementTree` for parsing XML files and `pandas` for data manipulation.
It is designed to be run from the command line with options to download the complete dataset or just the updates.

By default, it will only download updates unless specified otherwise.

The script is structured to allow for easy integration into a larger system, with functions for downloading and processing the data.
It also includes error handling and retry mechanisms to ensure robust operation in the face of network issues.

It uses a PostgreSQL database to track which files have been downloaded and processed to avoid
downloading and processing the same files multiple times when run on a schedule.

It also downloads and verifies MD5 checksums for each file to ensure data integrity.
"""
import os
import requests
import gzip
import hashlib
import xml.etree.ElementTree as ET
import concurrent.futures
import time
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from tqdm import tqdm
import socket
import sys

# Import the download tracker
from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medknowledge_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Constants for FTP connection
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
FTP_TIMEOUT = 300  # Increase timeout to 5 minutes for large files
MAX_RETRIES = 5
RETRY_DELAY = 15  # seconds

def create_ftp_connection():
    """Create and return a new FTP connection with appropriate timeout settings"""
    from ftplib import FTP
    ftp = FTP(timeout=FTP_TIMEOUT)
    ftp.connect(FTP_HOST)
    ftp.login()
    # Don't set directory here - will be set by the calling function
    
    # Set a keepalive option if possible
    if hasattr(ftp.sock, 'setsockopt') and hasattr(socket, 'SO_KEEPALIVE'):
        ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    # Increase buffer size if possible
    if hasattr(ftp, 'sock') and hasattr(socket, 'SO_RCVBUF'):
        ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8388608)  # 8MB buffer
        
    return ftp

# Use backoff for implementing retry with exponential backoff
try:
    import backoff
except ImportError:
    logger.info("Installing required backoff package...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "backoff"])
    import backoff
    logger.info("Backoff package installed successfully")

@backoff.on_exception(
    backoff.expo, 
    (socket.timeout, socket.error, IOError, EOFError),
    max_tries=5,
    on_backoff=lambda details: logger.warning(
        f"FTP error during download, retrying in {details['wait']:.1f} seconds... "
        f"(Attempt {details['tries']}/{5})"
    )
)
def ftp_download(ftp, xml_file, callback, rest_pos=0):
    """Download a file using FTP - used by ftp_download_with_retry"""
    if rest_pos > 0:
        try:
            return ftp.retrbinary(f'RETR {xml_file}', callback, rest=rest_pos)
        except Exception as e:
            # If we get an invalid REST argument, restart from beginning
            if "invalid REST argument" in str(e):
                logger.warning(f"Invalid resume position for {xml_file}, restarting download from beginning")
                return ftp.retrbinary(f'RETR {xml_file}', callback)
            else:
                raise
    else:
        return ftp.retrbinary(f'RETR {xml_file}', callback)

def ftp_download_with_retry(ftp, xml_file, callback, rest_pos=0, max_retries=3):
    """Download a file with retry capability"""
    for attempt in range(max_retries):
        try:
            return ftp_download(ftp, xml_file, callback, rest_pos)
        except (socket.timeout, socket.error, IOError, EOFError) as e:
            logger.warning(f"FTP connection lost: {e}, attempt {attempt+1}/{max_retries}")
            if attempt + 1 >= max_retries:
                raise
                
            # Connection issues - create new connection
            try:
                ftp.quit()
            except:
                pass
            
            # Create a new connection and set the correct directory
            ftp = create_ftp_connection()
            
            # Set the correct directory based on the file being downloaded
            if '/updatefiles/' in xml_file or xml_file.startswith('pubmed') or xml_file.endswith('xml.gz.md5'):
                # For update files
                ftp.cwd('/pubmed/updatefiles')
            else:
                # For baseline files
                ftp.cwd('/pubmed/baseline')
                
            # Sleep briefly before retry
            time.sleep(RETRY_DELAY)
            
def verify_md5(file_path):
    """
    Verify a file's MD5 checksum against its corresponding .md5 file.
    
    Args:
        file_path: Path to the file to verify
    
    Returns:
        Tuple of (is_valid, checksum_value, error_message)
        is_valid: True if the checksum matches, False otherwise
        checksum_value: The calculated MD5 checksum
        error_message: Error message if any occurred, None otherwise
    """
    md5_file_path = file_path + '.md5'
    
    # Check if the MD5 file exists
    if not os.path.exists(md5_file_path):
        logger.warning(f"MD5 file not found: {md5_file_path}")
        return False, None, "MD5 file not found"
    
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
        
        # Compare the hashes
        is_valid = calculated_hash.lower() == expected_hash.lower()
        
        if is_valid:
            logger.info(f"MD5 checksum verification passed for {file_path}")
        else:
            logger.warning(f"MD5 checksum mismatch for {file_path}: expected {expected_hash}, got {calculated_hash}")
            return False, calculated_hash, f"Checksum mismatch: expected {expected_hash}, got {calculated_hash}"
            
        return True, calculated_hash, None
    
    except Exception as e:
        logger.error(f"Error verifying MD5 for {file_path}: {e}")
        return False, None, f"Error verifying MD5: {e}"

def download_pubmed_baseline(baseline_dir='~/knowledgebase/pubmed_data/baseline', tracker=None):
    """Download the complete PubMed baseline dataset with resume capability
    
    Args:
        baseline_dir (str): Directory to store baseline files
        tracker (PubMedDownloadTracker, optional): Database tracker for downloaded files.
            If None, a local checkpoint file will be used instead.
    """
    # Ensure the path is fully expanded
    baseline_dir = os.path.expanduser(baseline_dir)
    baseline_dir = os.path.abspath(baseline_dir)
    
    # Create directory if it doesn't exist
    os.makedirs(baseline_dir, exist_ok=True)
    
    # If no tracker provided, use the local checkpoint file
    using_db_tracker = tracker is not None
    
    # Define checkpoint file path
    checkpoint_file = os.path.join(baseline_dir, '.download_checkpoint')
    last_downloaded_file = None
    
    # Check if checkpoint exists and load it if no tracker provided
    if not using_db_tracker and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                last_downloaded_file = f.read().strip()
                logger.info(f"Found checkpoint file. Last downloaded file: {last_downloaded_file}")
        except Exception as e:
            logger.warning(f"Error reading checkpoint file: {e}")
    
    logger.info(f"Starting PubMed baseline download to {baseline_dir}")

    ftp = None
    retry_count = 0
    
    while retry_count < MAX_RETRIES:
        try:
            if ftp is None:
                # Create new FTP connection
                ftp = create_ftp_connection()
                ftp.cwd('/pubmed/baseline')
                
            files = ftp.nlst()
            xml_files = [f for f in files if f.endswith('.xml.gz')]
            xml_files.sort()  # Ensure files are processed in order
            total_files = len(xml_files)
            
            logger.info(f"Found {total_files} PubMed baseline files to download")
            
            # If we have a checkpoint, skip files until we reach the last downloaded one
            start_index = 0
            if last_downloaded_file:
                try:
                    start_index = xml_files.index(last_downloaded_file) + 1
                    logger.info(f"Resuming from file {start_index + 1}/{total_files} (after {last_downloaded_file})")
                    # Skip all files before the checkpoint
                    xml_files = xml_files[start_index:]
                except ValueError:
                    logger.warning(f"Checkpoint file {last_downloaded_file} not found in the FTP directory. Starting from the beginning.")
            
            for i, xml_file in enumerate(xml_files, start_index + 1):
                local_file = os.path.join(baseline_dir, xml_file)
                
                # Check if file exists and has correct size
                should_download = True
                try:
                    # First check if the file has been downloaded before and tracked in the database
                    if using_db_tracker and tracker.is_file_downloaded(xml_file):
                        logger.info(f"File {xml_file} already tracked in database as downloaded ({i}/{total_files})")
                        # Always verify it exists and has the correct size
                        if os.path.exists(local_file):
                            ftp.voidcmd('TYPE I')
                            remote_size = ftp.size(xml_file)
                            local_size = os.path.getsize(local_file)
                            
                            if local_size == remote_size:
                                logger.info(f"Skipped existing complete baseline file {xml_file} ({i}/{total_files})")
                                should_download = False
                                
                                # Verify MD5 checksum for existing files periodically
                                if i % 10 == 0:  # Check every 10th file
                                    # Download MD5 file if needed
                                    md5_file = xml_file + '.md5'
                                    local_md5_file = local_file + '.md5'
                                    if not os.path.exists(local_md5_file):
                                        try:
                                            # Create a new connection just for MD5 download to avoid timeout issues
                                            md5_ftp = create_ftp_connection()
                                            md5_ftp.cwd('/pubmed/baseline')
                                            
                                            with open(local_md5_file, 'wb') as md5_fp:
                                                md5_ftp.retrbinary(f'RETR {md5_file}', md5_fp.write)
                                            md5_ftp.quit()
                                            logger.info(f"Downloaded MD5 file for {xml_file}")
                                        except Exception as md5_error:
                                            logger.warning(f"Error downloading MD5 file: {md5_error}")
                                    
                                    # Verify if MD5 file exists
                                    if os.path.exists(local_md5_file):
                                        is_valid, checksum, error = verify_md5(local_file)
                                        if not is_valid:
                                            logger.warning(f"MD5 verification failed for {xml_file}: {error}")
                                            should_download = True  # Re-download if checksum fails
                            else:
                                logger.info(f"Found incomplete baseline file {xml_file}, resuming download")
                                # Will resume download below
                        else:
                            logger.warning(f"File {xml_file} is tracked in database but not found locally, will download")
                    elif os.path.exists(local_file):
                        # Get remote file size
                        ftp.voidcmd('TYPE I')  # Switch to binary mode
                        remote_size = ftp.size(xml_file)
                        local_size = os.path.getsize(local_file)
                        
                        if local_size == remote_size:
                            logger.info(f"Skipped existing complete baseline file {xml_file} ({i}/{total_files})")
                            should_download = False
                            # Track the file in the database if we're using the tracker
                            if using_db_tracker:
                                tracker.log_download(xml_file, 'baseline', local_size)
                        else:
                            logger.info(f"Found incomplete baseline file {xml_file}, resuming download")
                            # Will resume download below
                except Exception as e:
                    logger.warning(f"Error checking file size for {xml_file}: {e}")
                    # Reset the FTP connection
                    try:
                        ftp.quit()
                    except:
                        pass
                    ftp = create_ftp_connection()
                    ftp.cwd('/pubmed/baseline')
                    # Continue with download attempt
                
                if should_download:
                    file_downloaded = False
                    download_retries = 0
                    time.sleep(2)  # Sleep for a second before starting the download
                    
                    while not file_downloaded and download_retries < MAX_RETRIES:
                        # Add a slight delay between attempts
                        if download_retries > 0:
                            time.sleep(RETRY_DELAY)
                            
                        try:
                            # Try to resume download if file exists
                            rest_pos = os.path.getsize(local_file) if os.path.exists(local_file) else 0
                            
                            # Ensure FTP connection is active
                            try:
                                # Get file size for progress bar
                                ftp.voidcmd('TYPE I')  # Switch to binary mode
                                file_size = ftp.size(xml_file)
                            except:
                                # Reconnect if needed
                                try:
                                    ftp.quit()
                                except:
                                    pass
                                ftp = create_ftp_connection()
                                ftp.cwd('/pubmed/baseline')
                                ftp.voidcmd('TYPE I')
                                file_size = ftp.size(xml_file)
                            
                            # Create progress bar
                            pbar = tqdm(
                                total=file_size,
                                initial=rest_pos,
                                unit='B',
                                unit_scale=True,
                                desc=f"File {i}/{total_files}: {xml_file}",
                                ncols=100
                            )
                            
                            # Use a function factory to create the callback
                            # This avoids closure issues with the file pointer
                            def make_callback(fp, progress_bar):
                                def callback(data):
                                    progress_bar.update(len(data))
                                    fp.write(data)
                                return callback
                            
                            with open(local_file, 'ab' if rest_pos > 0 else 'wb') as fp:
                                # Create a proper callback
                                callback = make_callback(fp, pbar)
                                # Use our retry-capable download function
                                ftp_download_with_retry(ftp, xml_file, callback, rest_pos)
                            
                            # Close progress bar
                            pbar.close()
                                
                            logger.info(f"Downloaded {xml_file} ({i}/{total_files})")
                            
                            # Download the MD5 file for verification
                            md5_file = xml_file + '.md5'
                            local_md5_file = local_file + '.md5'
                            
                            # Download MD5 file for checksum verification
                            md5_download_successful = False
                            md5_retries = 0
                            
                            # Use a separate FTP connection for MD5 download to avoid issues
                            md5_ftp = None
                            
                            while not md5_download_successful and md5_retries < 3:
                                try:
                                    if md5_ftp is None:
                                        md5_ftp = create_ftp_connection()
                                        md5_ftp.cwd('/pubmed/baseline')
                                        
                                    # Define callback for MD5 download using a factory function
                                    with open(local_md5_file, 'wb') as md5_fp:
                                        def make_md5_callback(fp):
                                            def callback(data):
                                                fp.write(data)
                                            return callback
                                        
                                        md5_callback = make_md5_callback(md5_fp)
                                        md5_ftp.retrbinary(f'RETR {md5_file}', md5_callback)
                                        
                                    logger.info(f"Downloaded MD5 file for {xml_file}")
                                    md5_download_successful = True
                                except Exception as md5_error:
                                    md5_retries += 1
                                    logger.warning(f"Error downloading MD5 file for {xml_file} (attempt {md5_retries}/3): {md5_error}")
                                    
                                    # Try to reconnect
                                    try:
                                        if md5_ftp:
                                            md5_ftp.quit()
                                    except:
                                        pass
                                    md5_ftp = create_ftp_connection()
                                    md5_ftp.cwd('/pubmed/baseline')
                                    
                                    time.sleep(2)  # Short delay before retry
                            
                            # Close MD5 FTP connection
                            try:
                                if md5_ftp:
                                    md5_ftp.quit()
                            except:
                                pass
                            
                            # Verify MD5 checksum
                            checksum = None
                            if md5_download_successful:
                                is_valid, checksum, error = verify_md5(local_file)
                                if is_valid:
                                    logger.info(f"✓ MD5 verification passed for {xml_file}")
                                else:
                                    logger.warning(f"✗ MD5 verification failed for {xml_file}: {error}")
                                    
                                    # If MD5 verification fails, consider re-downloading the file
                                    # But only if we haven't already retried too many times
                                    if download_retries < MAX_RETRIES - 1:
                                        logger.warning(f"Will retry downloading {xml_file} due to MD5 mismatch")
                                        download_retries += 1
                                        continue
                            
                            file_downloaded = True
                            
                            # Log successful download in database if tracker provided
                            if using_db_tracker:
                                try:
                                    # Get file size for the tracker
                                    ftp.voidcmd('TYPE I')
                                    file_size = ftp.size(xml_file)
                                except:
                                    # Use local file size if FTP size check fails
                                    file_size = os.path.getsize(local_file)
                                
                                # Include checksum in the database if available
                                tracker.log_download(xml_file, 'baseline', file_size)
                                
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
                            
                            # Also update checkpoint file as a backup
                            try:
                                with open(checkpoint_file, 'w') as f:
                                    f.write(xml_file)
                            except Exception as e:
                                logger.warning(f"Error writing checkpoint file: {e}")
                            
                        except Exception as download_error:
                            download_retries += 1
                            logger.error(f"Error downloading {xml_file} (attempt {download_retries}/{MAX_RETRIES}): {download_error}")
                            
                            # Sleep before retrying
                            time.sleep(RETRY_DELAY)
                            
                            # Reset the FTP connection
                            try:
                                ftp.quit()
                            except:
                                pass
                            ftp = create_ftp_connection()
                            ftp.cwd('/pubmed/baseline')
                            
                            if download_retries >= MAX_RETRIES:
                                logger.error(f"Failed to download {xml_file} after {MAX_RETRIES} attempts, moving to next file")
            
            try:
                ftp.quit()
            except:
                pass
                
            logger.info("PubMed baseline download completed")
            return
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Error in PubMed baseline download (attempt {retry_count}/{MAX_RETRIES}): {e}")
            
            # Sleep before retrying
            time.sleep(RETRY_DELAY)
            
            # Reset the FTP connection
            try:
                ftp.quit()
            except:
                pass
            ftp = None
            
    logger.error(f"Failed to complete PubMed baseline download after {MAX_RETRIES} attempts")


def download_pubmed_updates(updates_dir=None, tracker=None):
    """Download PubMed update files with resume capability
    
    Args:
        updates_dir (str, optional): Directory to store update files. 
            Defaults to PUBMED_DIR/updates if None.
        tracker (PubMedDownloadTracker, optional): Database tracker for downloaded files.
            If None, a local checkpoint file will be used instead.
    """
    # Determine the updates directory
    if updates_dir is None:
        updates_dir = os.path.join(PUBMED_DIR, 'updates')
    else:
        updates_dir = os.path.expanduser(updates_dir)
        updates_dir = os.path.abspath(updates_dir)
    
    # Create directory if it doesn't exist
    os.makedirs(updates_dir, exist_ok=True)
    
    # If no tracker provided, use the local checkpoint file
    using_db_tracker = tracker is not None
    
    # Define checkpoint file path (used as fallback if no tracker)
    checkpoint_file = os.path.join(updates_dir, '.download_checkpoint')
    last_downloaded_file = None
    
    # Check if checkpoint exists and load it if no tracker provided
    if not using_db_tracker and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                last_downloaded_file = f.read().strip()
                logger.info(f"Found checkpoint file. Last downloaded update file: {last_downloaded_file}")
        except Exception as e:
            logger.warning(f"Error reading checkpoint file: {e}")
    
    logger.info(f"Starting PubMed updates download to {updates_dir}")
    
    ftp = None
    retry_count = 0
    
    while retry_count < MAX_RETRIES:
        try:
            if ftp is None:
                # Create a new FTP connection with appropriate timeout
                ftp = create_ftp_connection()
                ftp.cwd('/pubmed/updatefiles')
                
            files = ftp.nlst()
            xml_files = [f for f in files if f.endswith('.xml.gz')]
            xml_files.sort()  # Ensure files are processed in order
            total_files = len(xml_files)
            
            logger.info(f"Found {total_files} PubMed update files to download")
            
            # If we have a checkpoint, skip files until we reach the last downloaded one
            start_index = 0
            if last_downloaded_file:
                try:
                    start_index = xml_files.index(last_downloaded_file) + 1
                    logger.info(f"Resuming from file {start_index + 1}/{total_files} (after {last_downloaded_file})")
                    # Skip all files before the checkpoint
                    xml_files = xml_files[start_index:]
                except ValueError:
                    logger.warning(f"Checkpoint file {last_downloaded_file} not found in the FTP directory. Starting from the beginning.")
            
            for i, xml_file in enumerate(xml_files, start_index + 1):
                local_file = os.path.join(updates_dir, xml_file)
                
                # Check if file exists and has correct size
                should_download = True
                try:
                    # First check if the file has been downloaded before and tracked in the database
                    if using_db_tracker and tracker.is_file_downloaded(xml_file):
                        logger.info(f"File {xml_file} already tracked in database as downloaded ({i}/{total_files})")
                        # Always verify it exists and has the correct size
                        if os.path.exists(local_file):
                            ftp.voidcmd('TYPE I')
                            remote_size = ftp.size(xml_file)
                            local_size = os.path.getsize(local_file)
                            
                            if local_size == remote_size:
                                logger.info(f"Skipped existing complete update file {xml_file} ({i}/{total_files})")
                                should_download = False
                                
                                # Verify MD5 checksum for existing files periodically
                                if i % 10 == 0:  # Check every 10th file
                                    # Download MD5 file if needed
                                    md5_file = xml_file + '.md5'
                                    local_md5_file = local_file + '.md5'
                                    if not os.path.exists(local_md5_file):
                                        try:
                                            # Create a new connection just for MD5 download to avoid timeout issues
                                            md5_ftp = create_ftp_connection()
                                            md5_ftp.cwd('/pubmed/updatefiles')
                                            
                                            with open(local_md5_file, 'wb') as md5_fp:
                                                md5_ftp.retrbinary(f'RETR {md5_file}', md5_fp.write)
                                            md5_ftp.quit()
                                            logger.info(f"Downloaded MD5 file for {xml_file}")
                                        except Exception as md5_error:
                                            logger.warning(f"Error downloading MD5 file: {md5_error}")
                                    
                                    # Verify if MD5 file exists
                                    if os.path.exists(local_md5_file):
                                        is_valid, checksum, error = verify_md5(local_file)
                                        if not is_valid:
                                            logger.warning(f"MD5 verification failed for {xml_file}: {error}")
                                            should_download = True  # Re-download if checksum fails
                            else:
                                logger.info(f"Found incomplete update file {xml_file}, resuming download")
                                # Will resume download below
                        else:
                            logger.warning(f"File {xml_file} is tracked in database but not found locally, will download")
                    elif os.path.exists(local_file):
                        # Get remote file size
                        ftp.voidcmd('TYPE I')  # Switch to binary mode
                        remote_size = ftp.size(xml_file)
                        local_size = os.path.getsize(local_file)
                        
                        if local_size == remote_size:
                            logger.info(f"Skipped existing complete update file {xml_file} ({i}/{total_files})")
                            should_download = False
                            # Track the file in the database if we're using the tracker
                            if using_db_tracker:
                                tracker.log_download(xml_file, 'update', local_size)
                        else:
                            logger.info(f"Found incomplete update file {xml_file}, resuming download")
                            # Will resume download below
                except Exception as e:
                    logger.warning(f"Error checking file size for {xml_file}: {e}")
                    # Reset the FTP connection
                    try:
                        ftp.quit()
                    except:
                        pass
                    ftp = create_ftp_connection()
                    ftp.cwd('/pubmed/updatefiles')
                    # Continue with download attempt
                
                if should_download:
                    file_downloaded = False
                    download_retries = 0
                    
                    while not file_downloaded and download_retries < MAX_RETRIES:
                        # Add a slight delay between attempts
                        if download_retries > 0:
                            time.sleep(RETRY_DELAY)
                            
                        try:
                            # Try to resume download if file exists
                            rest_pos = os.path.getsize(local_file) if os.path.exists(local_file) else 0
                            
                            # Ensure FTP connection is active
                            try:
                                # Get file size for progress bar
                                ftp.voidcmd('TYPE I')  # Switch to binary mode
                                file_size = ftp.size(xml_file)
                            except:
                                # Reconnect if needed
                                try:
                                    ftp.quit()
                                except:
                                    pass
                                ftp = create_ftp_connection()
                                ftp.cwd('/pubmed/updatefiles')
                                ftp.voidcmd('TYPE I')
                                file_size = ftp.size(xml_file)
                            
                            # Create progress bar
                            pbar = tqdm(
                                total=file_size,
                                initial=rest_pos,
                                unit='B',
                                unit_scale=True,
                                desc=f"File {i}/{total_files}: {xml_file}",
                                ncols=100
                            )
                            
                            # Use a function factory to create the callback
                            def make_callback(fp, progress_bar):
                                def callback(data):
                                    progress_bar.update(len(data))
                                    fp.write(data)
                                return callback
                            
                            with open(local_file, 'ab' if rest_pos > 0 else 'wb') as fp:
                                # Create a proper callback
                                callback = make_callback(fp, pbar)
                                # Use our retry-capable download function
                                ftp_download_with_retry(ftp, xml_file, callback, rest_pos)
                            
                            # Close progress bar
                            pbar.close()
                                
                            logger.info(f"Downloaded update {xml_file} ({i}/{total_files})")
                            
                            # Download the MD5 file for verification
                            md5_file = xml_file + '.md5'
                            local_md5_file = local_file + '.md5'
                            
                            # Download MD5 file for checksum verification
                            md5_download_successful = False
                            md5_retries = 0
                            
                            # Use a separate FTP connection for MD5 download to avoid issues
                            md5_ftp = None
                            
                            while not md5_download_successful and md5_retries < 3:
                                try:
                                    if md5_ftp is None:
                                        md5_ftp = create_ftp_connection()
                                        md5_ftp.cwd('/pubmed/updatefiles')
                                        
                                    # Define callback for MD5 download using a factory function
                                    with open(local_md5_file, 'wb') as md5_fp:
                                        def make_md5_callback(fp):
                                            def callback(data):
                                                fp.write(data)
                                            return callback
                                        
                                        md5_callback = make_md5_callback(md5_fp)
                                        md5_ftp.retrbinary(f'RETR {md5_file}', md5_callback)
                                        
                                    logger.info(f"Downloaded MD5 file for {xml_file}")
                                    md5_download_successful = True
                                except Exception as md5_error:
                                    md5_retries += 1
                                    logger.warning(f"Error downloading MD5 file for {xml_file} (attempt {md5_retries}/3): {md5_error}")
                                    
                                    # Try to reconnect
                                    try:
                                        if md5_ftp:
                                            md5_ftp.quit()
                                    except:
                                        pass
                                    md5_ftp = create_ftp_connection()
                                    md5_ftp.cwd('/pubmed/updatefiles')
                                    
                                    time.sleep(2)  # Short delay before retry
                            
                            # Close MD5 FTP connection
                            try:
                                if md5_ftp:
                                    md5_ftp.quit()
                            except:
                                pass
                            
                            # Verify MD5 checksum
                            checksum = None
                            if md5_download_successful:
                                is_valid, checksum, error = verify_md5(local_file)
                                if is_valid:
                                    logger.info(f"✓ MD5 verification passed for {xml_file}")
                                else:
                                    logger.warning(f"✗ MD5 verification failed for {xml_file}: {error}")
                                    
                                    # If MD5 verification fails, consider re-downloading the file
                                    # But only if we haven't already retried too many times
                                    if download_retries < MAX_RETRIES - 1:
                                        logger.warning(f"Will retry downloading {xml_file} due to MD5 mismatch")
                                        download_retries += 1
                                        continue
                            
                            file_downloaded = True
                            
                            # Log successful download in database if tracker provided
                            if using_db_tracker:
                                try:
                                    # Get file size for the tracker
                                    ftp.voidcmd('TYPE I')
                                    file_size = ftp.size(xml_file)
                                except:
                                    # Use local file size if FTP size check fails
                                    file_size = os.path.getsize(local_file)
                                
                                # Track the file in the database
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
                            
                            # Also update checkpoint file as a backup
                            try:
                                with open(checkpoint_file, 'w') as f:
                                    f.write(xml_file)
                            except Exception as e:
                                logger.warning(f"Error writing checkpoint file: {e}")
                            
                        except Exception as download_error:
                            download_retries += 1
                            logger.error(f"Error downloading update {xml_file} (attempt {download_retries}/{MAX_RETRIES}): {download_error}")
                            
                            # Sleep before retrying
                            time.sleep(RETRY_DELAY)
                            
                            # Reset the FTP connection
                            try:
                                ftp.quit()
                            except:
                                pass
                            ftp = create_ftp_connection()
                            ftp.cwd('/pubmed/updatefiles')
                            
                            if download_retries >= MAX_RETRIES:
                                logger.error(f"Failed to download update {xml_file} after {MAX_RETRIES} attempts, moving to next file")
            
            try:
                ftp.quit()
            except:
                pass
                
            logger.info("PubMed updates download completed")
            return
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Error in PubMed updates download (attempt {retry_count}/{MAX_RETRIES}): {e}")
            
            # Sleep before retrying
            time.sleep(RETRY_DELAY)
            
            # Reset the FTP connection
            try:
                ftp.quit()
            except:
                pass
            ftp = None
            
    logger.error(f"Failed to complete PubMed updates download after {MAX_RETRIES} attempts")



if __name__ == "__main__":
    # Define the directory to save the downloaded files
    import sys  # For pip install
    import argparse
    
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Download PubMed data')
    parser.add_argument('--from_scratch', action='store_true', 
                        help='Download the complete baseline data in addition to updates')
    parser.add_argument('--data_dir', default='~/knowledgebase/pubmed_data',
                        help='Directory to store downloaded files (default: ~/knowledgebase/pubmed_data)')
    parser.add_argument('--skip_updates', action='store_true',
                        help='Skip downloading updates (only relevant when used with --from_scratch)')
    parser.add_argument('--no_db_tracking', action='store_true',
                        help='Do not use database tracking (use only file-based checkpoints)')
    parser.add_argument('--show_stats', action='store_true',
                        help='Show statistics about downloaded and processed files')
    
    args = parser.parse_args()
    
    # Set up directories
    PUBMED_DIR = os.path.expanduser(args.data_dir)
    PUBMED_DIR = os.path.abspath(PUBMED_DIR)
    logger.info(f"Using directory: {PUBMED_DIR}")
    
    # Check if the directory exists
    if not os.path.exists(PUBMED_DIR):
        logger.info(f"Creating directory: {PUBMED_DIR}")
        os.makedirs(PUBMED_DIR, exist_ok=True)
    else:
        logger.info(f"Directory already exists: {PUBMED_DIR}")
    
    # Check if the baseline directory exists
    BASELINE_DIR = os.path.join(PUBMED_DIR, 'baseline')
    if not os.path.exists(BASELINE_DIR):
        logger.info(f"Creating baseline directory: {BASELINE_DIR}")
        os.makedirs(BASELINE_DIR, exist_ok=True)
    else:
        logger.info(f"Baseline directory already exists: {BASELINE_DIR}")
        
    # Check if the updates directory exists
    UPDATES_DIR = os.path.join(PUBMED_DIR, 'updates')
    if not os.path.exists(UPDATES_DIR):
        logger.info(f"Creating updates directory: {UPDATES_DIR}")
        os.makedirs(UPDATES_DIR, exist_ok=True)
    else:
        logger.info(f"Updates directory already exists: {UPDATES_DIR}")
    
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
        logger.info("=== PubMed Download Statistics ===")
        logger.info(f"Total tracked files: {stats['total_files']}")
        logger.info(f"Downloaded files: {stats['downloaded_files']}")
        logger.info(f"Processed files: {stats['processed_files']}")
        logger.info(f"Baseline files: {stats['baseline_files']}")
        logger.info(f"Update files: {stats['update_files']}")
        
        if stats['last_download_date']:
            logger.info(f"Last download: {stats['last_download_date']}")
        if stats['last_process_date']:
            logger.info(f"Last processing: {stats['last_process_date']}")
        logger.info("=================================")
        
        # If only showing stats, exit
        if not args.from_scratch and not args.skip_updates:
            sys.exit(0)
    
    # Start the download process based on arguments
    if args.from_scratch:
        logger.info("Starting complete download (baseline + updates)")
        download_pubmed_baseline(BASELINE_DIR, tracker)
        if not args.skip_updates:
            download_pubmed_updates(UPDATES_DIR, tracker)
    else:
        # Default: only download updates
        logger.info("Starting updates download only")
        download_pubmed_updates(UPDATES_DIR, tracker)
