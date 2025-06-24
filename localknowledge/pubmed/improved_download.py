"""
Improved PubMed downloader with better error handling and connection management.

This module provides an improved version of the ftplib-based downloader
with better handling of EOFError and connection issues.
"""

import os
import gzip
import hashlib
import logging
import socket
import time
from ftplib import FTP
from pathlib import Path
from typing import Optional, Tuple
from tqdm import tqdm
import backoff

# Import the download tracker
from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# Set up logging
logger = logging.getLogger(__name__)

# Constants for FTP connection
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
FTP_TIMEOUT = 120  # 2 minutes timeout (shorter than before)
MAX_RETRIES = 5
RETRY_DELAY = 5  # Shorter delay between retries
CHUNK_SIZE = 64 * 1024  # Smaller chunks: 64KB instead of 1MB


class ImprovedPubMedDownloader:
    """Improved PubMed downloader with better error handling."""
    
    def __init__(self):
        """Initialize the downloader."""
        self.connection_pool = []
        
    def create_ftp_connection(self) -> FTP:
        """Create and return a new FTP connection with optimized settings."""
        ftp = FTP(timeout=FTP_TIMEOUT)
        
        # Connect with explicit settings
        ftp.connect(FTP_HOST, timeout=FTP_TIMEOUT)
        ftp.login()
        
        # Set binary mode
        ftp.voidcmd('TYPE I')
        
        # Set passive mode for better firewall compatibility
        ftp.set_pasv(True)
        
        # Configure socket options for better reliability
        if hasattr(ftp.sock, 'setsockopt'):
            # Enable keepalive
            ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Set TCP keepalive parameters (Linux/macOS)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                ftp.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                ftp.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, 'TCP_KEEPCNT'):
                ftp.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                
        return ftp
        
    def check_ftp_connection(self, ftp: FTP) -> bool:
        """Check if FTP connection is still alive."""
        try:
            ftp.voidcmd('NOOP')
            return True
        except Exception:
            return False
            
    @backoff.on_exception(
        backoff.expo,
        (socket.timeout, socket.error, IOError, EOFError, ConnectionResetError, BrokenPipeError),
        max_tries=3,
        base=2,
        max_value=30,
        on_backoff=lambda details: logger.warning(
            f"Network error, retrying in {details['wait']:.1f} seconds... "
            f"(Attempt {details['tries']}/3)"
        )
    )
    def download_with_resume(
        self,
        ftp: FTP,
        remote_file: str,
        local_file: Path,
        expected_size: int,
        resume_pos: int = 0
    ) -> bool:
        """
        Download a file with resume capability and improved error handling.
        
        Args:
            ftp: FTP connection
            remote_file: Name of the remote file
            local_file: Local file path
            expected_size: Expected file size
            resume_pos: Position to resume from
            
        Returns:
            True if download successful, False otherwise
        """
        downloaded_bytes = resume_pos
        
        # Open file for writing
        mode = 'ab' if resume_pos > 0 else 'wb'
        
        with open(local_file, mode) as fp:
            def callback(data):
                nonlocal downloaded_bytes
                
                if not data:
                    return
                    
                # Calculate remaining bytes to avoid overshooting
                remaining = expected_size - downloaded_bytes
                if len(data) > remaining:
                    data = data[:remaining]
                    
                fp.write(data)
                downloaded_bytes += len(data)
                
                # Stop if we've reached the expected size
                if downloaded_bytes >= expected_size:
                    # This will cause the FTP transfer to stop
                    raise StopIteration("Download complete")
                    
            try:
                if resume_pos > 0:
                    # Resume from specific position
                    ftp.retrbinary(f'RETR {remote_file}', callback, rest=resume_pos)
                else:
                    # Start from beginning
                    ftp.retrbinary(f'RETR {remote_file}', callback)
                    
            except StopIteration:
                # This is expected when we reach the target size
                pass
            except (socket.timeout, socket.error, EOFError, ConnectionResetError, BrokenPipeError) as e:
                # Network errors - let backoff handle retries
                logger.warning(f"Network error during download: {type(e).__name__}: {e}")
                raise
                
            # Ensure data is written to disk
            fp.flush()
            os.fsync(fp.fileno())
            
        return downloaded_bytes >= expected_size
        
    def download_single_file(
        self,
        remote_file: str,
        local_file: Path,
        file_type: str = 'update',
        file_index: int = 0,
        total_files: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """
        Download a single file with improved error handling and progress tracking.
        
        Args:
            remote_file: Name of the remote file
            local_file: Local file path
            file_type: 'baseline' or 'update'
            file_index: Current file index
            total_files: Total number of files
            
        Returns:
            Tuple of (success, checksum)
        """
        max_attempts = MAX_RETRIES
        
        for attempt in range(max_attempts):
            ftp = None
            try:
                # Create fresh connection for each attempt
                ftp = self.create_ftp_connection()
                
                # Navigate to appropriate directory
                if file_type == 'baseline':
                    ftp.cwd('/pubmed/baseline')
                else:
                    ftp.cwd('/pubmed/updatefiles')
                    
                # Get file size
                ftp.voidcmd('TYPE I')
                expected_size = ftp.size(remote_file)
                
                # Check if we can resume
                resume_pos = 0
                if local_file.exists():
                    current_size = local_file.stat().st_size
                    if current_size < expected_size:
                        resume_pos = current_size
                        logger.info(f"Resuming {remote_file} from byte {resume_pos}")
                    elif current_size == expected_size:
                        # File might be complete, verify
                        if self._verify_file_integrity(local_file):
                            logger.info(f"File {remote_file} already complete and valid")
                            return True, None
                        else:
                            logger.info(f"File {remote_file} corrupt, redownloading")
                            local_file.unlink()
                            resume_pos = 0
                    else:
                        # File is larger than expected, start over
                        logger.warning(f"File {remote_file} larger than expected, redownloading")
                        local_file.unlink()
                        resume_pos = 0
                        
                # Create progress bar
                file_desc = f"File {file_index}/{total_files}: {remote_file}"
                with tqdm(
                    total=expected_size,
                    unit='B',
                    unit_scale=True,
                    desc=file_desc,
                    ncols=100,
                    initial=resume_pos
                ) as pbar:
                    
                    # Track progress
                    last_update = resume_pos
                    
                    def progress_callback(data):
                        nonlocal last_update
                        if data:
                            current_pos = local_file.stat().st_size if local_file.exists() else 0
                            if current_pos > last_update:
                                pbar.update(current_pos - last_update)
                                last_update = current_pos
                                
                    # Download with progress tracking
                    success = self.download_with_resume(
                        ftp, remote_file, local_file, expected_size, resume_pos
                    )
                    
                    if success:
                        # Update progress bar to completion
                        final_size = local_file.stat().st_size if local_file.exists() else 0
                        pbar.update(final_size - last_update)
                        
                        # Verify file integrity
                        if self._verify_file_integrity(local_file):
                            logger.info(f"✓ Successfully downloaded {remote_file}")
                            
                            # Try to get MD5 checksum
                            checksum = self._download_and_verify_md5(ftp, remote_file, local_file)
                            return True, checksum
                        else:
                            logger.error(f"Downloaded file {remote_file} failed integrity check")
                            if local_file.exists():
                                local_file.unlink()
                            continue  # Try again
                    else:
                        logger.warning(f"Download incomplete for {remote_file}")
                        continue  # Try again
                        
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{max_attempts} failed for {remote_file}: {e}")
                
                # Clean up partial file
                if local_file.exists():
                    try:
                        local_file.unlink()
                    except:
                        pass
                        
            finally:
                # Always close FTP connection
                if ftp:
                    try:
                        ftp.quit()
                    except:
                        pass
                        
            # Wait before retrying (except on last attempt)
            if attempt < max_attempts - 1:
                time.sleep(RETRY_DELAY)
                
        logger.error(f"Failed to download {remote_file} after {max_attempts} attempts")
        return False, None
        
    def _verify_file_integrity(self, file_path: Path) -> bool:
        """Verify that a file has valid gzip integrity."""
        try:
            with gzip.open(file_path, 'rb') as gz_file:
                # Read in chunks to avoid memory issues
                while gz_file.read(CHUNK_SIZE):
                    pass
            return True
        except Exception as e:
            logger.debug(f"File integrity check failed for {file_path}: {e}")
            return False
            
    def _download_and_verify_md5(
        self,
        ftp: FTP,
        remote_file: str,
        local_file: Path
    ) -> Optional[str]:
        """Download and verify MD5 checksum if available."""
        md5_file = remote_file + '.md5'
        local_md5_file = local_file.with_suffix(local_file.suffix + '.md5')
        
        try:
            with open(local_md5_file, 'wb') as md5_fp:
                ftp.retrbinary(f'RETR {md5_file}', md5_fp.write)
                
            # Verify checksum
            return self._verify_md5(local_file)
            
        except Exception as e:
            logger.debug(f"Could not download/verify MD5 for {remote_file}: {e}")
            return None
            
    def _verify_md5(self, file_path: Path) -> Optional[str]:
        """Verify MD5 checksum of a file."""
        md5_file_path = file_path.with_suffix(file_path.suffix + '.md5')
        
        if not md5_file_path.exists():
            return None
            
        try:
            # Calculate MD5
            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    md5_hash.update(chunk)
            calculated_hash = md5_hash.hexdigest()
            
            # Read expected hash
            with open(md5_file_path, 'r') as f:
                md5_content = f.read().strip()
                
                if '=' in md5_content:
                    expected_hash = md5_content.split('=', 1)[1].strip()
                elif ' ' in md5_content:
                    expected_hash = md5_content.split()[0]
                else:
                    expected_hash = md5_content
                    
                expected_hash = expected_hash.strip().strip('"').strip("'")
                
            # Compare hashes
            if calculated_hash.lower() == expected_hash.lower():
                logger.debug(f"✓ MD5 verification passed")
                return calculated_hash
            else:
                logger.warning(f"✗ MD5 mismatch: expected {expected_hash}, got {calculated_hash}")
                return None
                
        except Exception as e:
            logger.debug(f"MD5 verification error: {e}")
            return None


# Convenience function
def download_single_file_improved(
    remote_file: str,
    local_file: str,
    file_type: str = 'update'
) -> Tuple[bool, Optional[str]]:
    """
    Download a single PubMed file using the improved downloader.
    
    Args:
        remote_file: Name of the remote file
        local_file: Local path to save the file
        file_type: 'baseline' or 'update'
        
    Returns:
        Tuple of (success, checksum)
    """
    downloader = ImprovedPubMedDownloader()
    return downloader.download_single_file(remote_file, Path(local_file), file_type)
