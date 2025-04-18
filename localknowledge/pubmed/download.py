import os
import requests
import gzip
import xml.etree.ElementTree as ET
import concurrent.futures
import time
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from tqdm import tqdm
import socket

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
FTP_TIMEOUT = 180  # Increase timeout to 3 minutes
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds

def create_ftp_connection():
    """Create and return a new FTP connection with appropriate timeout settings"""
    from ftplib import FTP
    ftp = FTP(timeout=FTP_TIMEOUT)
    ftp.connect(FTP_HOST)
    ftp.login()
    ftp.cwd('/pubmed/baseline')
    # Set a keepalive option if possible
    if hasattr(ftp.sock, 'setsockopt') and hasattr(socket, 'SO_KEEPALIVE'):
        ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    return ftp

import backoff

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
            # If we get an invalid REST error, restart from beginning
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
            ftp = create_ftp_connection()

def download_pubmed_baseline(baseline_dir='~/knowledgebase/pubmed_data/baseline'):
    """Download the complete PubMed baseline dataset with resume capability"""
    # Ensure the path is fully expanded
    baseline_dir = os.path.expanduser(baseline_dir)
    baseline_dir = os.path.abspath(baseline_dir)
    
    # Create directory if it doesn't exist
    os.makedirs(baseline_dir, exist_ok=True)
    
    # Define checkpoint file path
    checkpoint_file = os.path.join(baseline_dir, '.download_checkpoint')
    last_downloaded_file = None
    
    # Check if checkpoint exists and load it
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                last_downloaded_file = f.read().strip()
                logger.info(f"Found checkpoint file. Last downloaded file: {last_downloaded_file}")
        except Exception as e:
            logger.warning(f"Error reading checkpoint file: {e}")
    
    logger.info(f"Starting PubMed baseline download to {baseline_dir}")
    
    # Check if backoff package is available, install if needed
    try:
        import backoff
    except ImportError:
        logger.info("Installing required backoff package...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "backoff"])
        import backoff
        logger.info("Backoff package installed successfully")

    ftp = None
    retry_count = 0
    
    while retry_count < MAX_RETRIES:
        try:
            if ftp is None:
                ftp = create_ftp_connection()
                
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
                    if os.path.exists(local_file):
                        # Get remote file size
                        ftp.voidcmd('TYPE I')  # Switch to binary mode
                        remote_size = ftp.size(xml_file)
                        local_size = os.path.getsize(local_file)
                        
                        if local_size == remote_size:
                            logger.info(f"Skipped existing complete file {xml_file} ({i}/{total_files})")
                            should_download = False
                        else:
                            logger.info(f"Found incomplete file {xml_file}, resuming download")
                            # Will resume download below
                except Exception as e:
                    logger.warning(f"Error checking file size for {xml_file}: {e}")
                    # Reset the FTP connection
                    try:
                        ftp.quit()
                    except:
                        pass
                    ftp = create_ftp_connection()
                    # Continue with download attempt
                
                if should_download:
                    file_downloaded = False
                    download_retries = 0
                    time.sleep(2)  # Sleep for a second before starting the download
                    while not file_downloaded and download_retries < MAX_RETRIES:
                        time.sleep(2)  # Sleep for a second before starting the download
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
                            
                            # Define callback to update progress bar
                            def callback(data):
                                pbar.update(len(data))
                                fp.write(data)
                            
                            with open(local_file, 'ab' if rest_pos > 0 else 'wb') as fp:
                                # Use our retry-capable download function
                                ftp_download_with_retry(ftp, xml_file, callback, rest_pos)
                            
                            # Close progress bar
                            pbar.close()
                                
                            logger.info(f"Downloaded {xml_file} ({i}/{total_files})")
                            file_downloaded = True
                            
                            # Update checkpoint file with the latest successfully downloaded file
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


if __name__ == "__main__":
    # Define the directory to save the downloaded files
    import sys  # For pip install
    
    PUBMED_DIR = '~/knowledgebase/pubmed_data'
    PUBMED_DIR = os.path.expanduser(PUBMED_DIR)
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
    
    # Start the download process
    download_pubmed_baseline()