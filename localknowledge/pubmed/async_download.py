"""
Async PubMed downloader using aioftp for improved reliability.

This module provides an async alternative to the ftplib-based downloader
that should handle network interruptions and large file downloads more robustly.
"""

import asyncio
import os
import gzip
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, AsyncGenerator

try:
    import aiofiles
    import aioftp
    from tqdm.asyncio import tqdm
    ASYNC_DEPS_AVAILABLE = True
except ImportError as e:
    ASYNC_DEPS_AVAILABLE = False
    missing_deps = str(e)
    logging.warning(f"Async dependencies not available: {missing_deps}")
    logging.warning("Please install: pip install aioftp aiofiles tqdm")

# Import the download tracker
from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# Set up logging
logger = logging.getLogger(__name__)

# Constants for FTP connection
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
FTP_TIMEOUT = 300  # 5 minutes timeout
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds
CHUNK_SIZE = 1024 * 1024  # 1MB chunks


class AsyncPubMedDownloader:
    """Async PubMed file downloader using aioftp."""
    
    def __init__(self, max_concurrent_downloads: int = 3):
        """
        Initialize the async downloader.
        
        Args:
            max_concurrent_downloads: Maximum number of concurrent downloads
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        self.semaphore = asyncio.Semaphore(max_concurrent_downloads)
        
    async def create_ftp_client(self) -> aioftp.Client:
        """Create and return a new FTP client connection."""
        client = aioftp.Client()
        await client.connect(FTP_HOST)
        await client.login()
        return client
        
    async def verify_file_integrity(self, file_path: Path) -> bool:
        """
        Verify that a downloaded file has valid gzip integrity.
        
        Args:
            file_path: Path to the file to verify
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                # Read the file in chunks to verify gzip integrity
                async for chunk in self._read_file_chunks(f):
                    # Try to decompress each chunk to verify integrity
                    try:
                        gzip.decompress(chunk)
                    except gzip.BadGzipFile:
                        # If we can't decompress, try reading as a stream
                        break
                        
            # Final verification: try to open the entire file
            with gzip.open(file_path, 'rb') as gz_file:
                # Read in chunks to avoid memory issues
                while gz_file.read(CHUNK_SIZE):
                    pass
                    
            logger.debug(f"File integrity verification passed for {file_path}")
            return True
            
        except Exception as e:
            logger.warning(f"File integrity verification failed for {file_path}: {e}")
            return False
            
    async def _read_file_chunks(self, file_handle, chunk_size: int = CHUNK_SIZE) -> AsyncGenerator[bytes, None]:
        """Read file in chunks asynchronously."""
        while True:
            chunk = await file_handle.read(chunk_size)
            if not chunk:
                break
            yield chunk
            
    async def download_file_with_progress(
        self,
        client: aioftp.Client,
        remote_file: str,
        local_file: Path,
        file_index: int = 0,
        total_files: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """
        Download a single file with progress tracking and resume capability.
        
        Args:
            client: FTP client connection
            remote_file: Name of the remote file
            local_file: Local path to save the file
            file_index: Current file index for progress display
            total_files: Total number of files for progress display
            
        Returns:
            Tuple of (success, checksum)
        """
        try:
            # Get file size for progress bar
            file_info = await client.stat(remote_file)
            # aioftp returns a dict, not an object
            expected_size = file_info.get('size') if isinstance(file_info, dict) else getattr(file_info, 'size', None)
            if expected_size is None:
                raise ValueError(f"Could not determine file size for {remote_file}")
            
            # Check if we can resume an existing partial download
            resume_pos = 0
            if local_file.exists():
                current_size = local_file.stat().st_size
                if current_size < expected_size:
                    resume_pos = current_size
                    logger.info(f"Resuming download of {remote_file} from byte {resume_pos}")
                elif current_size == expected_size:
                    # File might be complete, verify integrity
                    if await self.verify_file_integrity(local_file):
                        logger.info(f"File {remote_file} already complete and valid")
                        return True, None
                    else:
                        logger.info(f"File {remote_file} exists but is corrupt, redownloading")
                        resume_pos = 0
                        local_file.unlink()
                else:
                    # File is larger than expected, start over
                    logger.warning(f"Local file {local_file} is larger than expected, redownloading")
                    local_file.unlink()
                    resume_pos = 0
                    
            # Create progress bar
            file_desc = f"File {file_index}/{total_files}: {remote_file}"
            progress_bar = tqdm(
                total=expected_size,
                unit='B',
                unit_scale=True,
                desc=file_desc,
                ncols=100,
                initial=resume_pos
            )
            
            try:
                # Open file for writing (append if resuming)
                mode = 'ab' if resume_pos > 0 else 'wb'
                async with aiofiles.open(local_file, mode) as local_fp:
                    downloaded_bytes = resume_pos
                    
                    # Download the file
                    async with client.download_stream(remote_file, offset=resume_pos) as stream:
                        async for chunk in stream.iter_by_block(CHUNK_SIZE):
                            if not chunk:
                                break
                                
                            await local_fp.write(chunk)
                            chunk_size = len(chunk)
                            downloaded_bytes += chunk_size
                            progress_bar.update(chunk_size)
                            
                            # Stop if we've downloaded the expected amount
                            if downloaded_bytes >= expected_size:
                                break
                                
            finally:
                progress_bar.close()
                
            # Verify the download was successful
            if local_file.exists():
                actual_size = local_file.stat().st_size
                if actual_size == expected_size:
                    # Verify file integrity
                    if await self.verify_file_integrity(local_file):
                        logger.debug(f"Download completed successfully: {remote_file} ({actual_size} bytes)")
                        
                        # Try to download and verify MD5 checksum
                        checksum = await self._download_and_verify_md5(client, remote_file, local_file)
                        return True, checksum
                    else:
                        logger.warning(f"Downloaded file {remote_file} failed integrity check")
                        return False, None
                else:
                    logger.warning(f"Downloaded file size mismatch: expected {expected_size}, got {actual_size}")
                    return False, None
            else:
                logger.error(f"Downloaded file does not exist: {local_file}")
                return False, None
                
        except Exception as e:
            logger.error(f"Error downloading {remote_file}: {type(e).__name__}: {e}")
            return False, None
            
    async def _download_and_verify_md5(
        self,
        client: aioftp.Client,
        remote_file: str,
        local_file: Path
    ) -> Optional[str]:
        """
        Download MD5 file and verify checksum if available.
        
        Args:
            client: FTP client connection
            remote_file: Name of the remote XML file
            local_file: Path to the local XML file
            
        Returns:
            MD5 checksum if verification successful, None otherwise
        """
        md5_file = remote_file + '.md5'
        local_md5_file = local_file.with_suffix(local_file.suffix + '.md5')
        
        try:
            # Try to download MD5 file
            await client.download(md5_file, local_md5_file)
            logger.debug(f"Downloaded MD5 file for {remote_file}")
            
            # Verify MD5 checksum
            is_valid, checksum, error = await self._verify_md5_async(local_file)
            if is_valid:
                logger.debug(f"✓ MD5 verification passed for {remote_file}")
                return checksum
            else:
                logger.warning(f"✗ MD5 verification failed for {remote_file}: {error}")
                return None
                
        except Exception as md5_error:
            logger.debug(f"Could not download/verify MD5 for {remote_file}: {md5_error}")
            return None
            
    async def _verify_md5_async(self, file_path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verify a file's MD5 checksum against its corresponding .md5 file asynchronously.
        
        Args:
            file_path: Path to the file to verify
            
        Returns:
            Tuple of (is_valid, checksum_value, error_message)
        """
        md5_file_path = file_path.with_suffix(file_path.suffix + '.md5')
        
        if not md5_file_path.exists():
            return False, None, "MD5 file not found"
            
        try:
            # Calculate MD5 hash for the file
            md5_hash = hashlib.md5()
            async with aiofiles.open(file_path, 'rb') as f:
                async for chunk in self._read_file_chunks(f):
                    md5_hash.update(chunk)
            calculated_hash = md5_hash.hexdigest()
            
            # Read expected hash from .md5 file
            async with aiofiles.open(md5_file_path, 'r') as f:
                md5_content = await f.read()
                md5_content = md5_content.strip()
                
                # NCBI's MD5 files have format: MD5(filename)= hash
                if '=' in md5_content:
                    expected_hash = md5_content.split('=', 1)[1].strip()
                elif ' ' in md5_content:
                    expected_hash = md5_content.split()[0]
                else:
                    expected_hash = md5_content
                    
                expected_hash = expected_hash.strip().strip('"').strip("'")
                
            if not expected_hash:
                return False, calculated_hash, "Empty or invalid MD5 in checksum file"
                
            # Compare the hashes (case-insensitive)
            is_valid = calculated_hash.lower() == expected_hash.lower()
            
            if not is_valid:
                return False, calculated_hash, f"Checksum mismatch: expected {expected_hash}, got {calculated_hash}"
                
            return True, calculated_hash, None
            
        except Exception as e:
            return False, None, f"Error verifying MD5: {e}"

    async def download_single_file_with_retry(
        self,
        remote_file: str,
        local_file: Path,
        file_type: str = 'baseline',
        file_index: int = 0,
        total_files: int = 0,
        max_retries: int = MAX_RETRIES
    ) -> Tuple[bool, Optional[str]]:
        """
        Download a single file with retry logic and connection management.

        Args:
            remote_file: Name of the remote file
            local_file: Local path to save the file
            file_type: 'baseline' or 'update'
            file_index: Current file index for progress display
            total_files: Total number of files for progress display
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (success, checksum)
        """
        async with self.semaphore:  # Limit concurrent downloads
            for attempt in range(max_retries):
                client = None
                try:
                    # Create new FTP connection for each attempt
                    client = await self.create_ftp_client()

                    # Navigate to the appropriate directory
                    if file_type == 'baseline':
                        await client.change_directory('/pubmed/baseline')
                    else:  # update
                        await client.change_directory('/pubmed/updatefiles')

                    # Attempt the download
                    success, checksum = await self.download_file_with_progress(
                        client, remote_file, local_file, file_index, total_files
                    )

                    if success:
                        logger.info(f"✓ Successfully downloaded {remote_file}")
                        return True, checksum
                    else:
                        logger.warning(f"Download failed for {remote_file}, attempt {attempt + 1}/{max_retries}")

                except Exception as e:
                    logger.warning(f"Error during download attempt {attempt + 1}/{max_retries} for {remote_file}: {e}")

                finally:
                    # Always close the client connection
                    if client:
                        try:
                            await client.quit()
                        except:
                            pass

                # If not the last attempt, wait before retrying
                if attempt < max_retries - 1:
                    # Clean up partial file if it exists
                    if local_file.exists():
                        try:
                            file_size = local_file.stat().st_size
                            logger.info(f"Removing partial file ({file_size} bytes) before retry")
                            local_file.unlink()
                        except:
                            pass

                    await asyncio.sleep(RETRY_DELAY)

            logger.error(f"Failed to download {remote_file} after {max_retries} attempts")
            return False, None

    async def download_pubmed_baseline(
        self,
        baseline_dir: str = '~/knowledgebase/pubmed_data/baseline',
        tracker: Optional[PubMedDownloadTracker] = None,
        from_highest_seq: bool = False,
        from_highest_processed_seq: bool = False
    ) -> None:
        """
        Download the complete PubMed baseline dataset asynchronously.

        Args:
            baseline_dir: Directory to store baseline files
            tracker: Database tracker for downloaded files
            from_highest_seq: Start from highest sequence number in database
            from_highest_processed_seq: Start from highest processed sequence number
        """
        # Ensure the path is fully expanded
        baseline_path = Path(baseline_dir).expanduser().resolve()
        baseline_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting async PubMed baseline download to {baseline_path}")

        # Determine starting point
        last_downloaded_file = None
        if tracker and (from_highest_seq or from_highest_processed_seq):
            highest_seq = tracker.get_highest_sequence_number(processed_only=from_highest_processed_seq)
            if highest_seq > 0:
                last_downloaded_file = f"pubmed25n{highest_seq}.xml.gz"
                logger.info(f"Starting download from sequence number {highest_seq}")

        # Get list of files to download
        client = await self.create_ftp_client()
        try:
            await client.change_directory('/pubmed/baseline')
            files = []
            async for path, info in client.list():
                if path.name.endswith('.xml.gz'):
                    files.append(path.name)
            files.sort()

            # Skip files if we have a checkpoint
            if last_downloaded_file and last_downloaded_file in files:
                start_index = files.index(last_downloaded_file) + 1
                files = files[start_index:]
                logger.info(f"Resuming from file after {last_downloaded_file}")

        finally:
            await client.quit()

        total_files = len(files)
        logger.info(f"Found {total_files} PubMed baseline files to download")

        # Download files
        for i, xml_file in enumerate(files, 1):
            local_file = baseline_path / xml_file

            # Check if file already exists and is valid
            if await self._should_skip_file(xml_file, local_file, tracker, 'baseline'):
                logger.info(f"Skipping existing valid file {xml_file} ({i}/{total_files})")
                continue

            # Download the file
            success, checksum = await self.download_single_file_with_retry(
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

        logger.info("Async PubMed baseline download completed")

    async def _should_skip_file(
        self,
        xml_file: str,
        local_file: Path,
        tracker: Optional[PubMedDownloadTracker],
        file_type: str
    ) -> bool:
        """
        Check if a file should be skipped (already downloaded and valid).

        Args:
            xml_file: Name of the XML file
            local_file: Local file path
            tracker: Database tracker
            file_type: 'baseline' or 'update'

        Returns:
            True if file should be skipped, False otherwise
        """
        # Check database first if tracker available
        if tracker:
            if file_type == 'update' and tracker.is_file_processed(xml_file):
                return True
            if tracker.is_file_downloaded(xml_file):
                # Verify file still exists and is valid
                if local_file.exists() and await self.verify_file_integrity(local_file):
                    return True

        # Check local file
        if local_file.exists():
            if await self.verify_file_integrity(local_file):
                # Log to database if tracker available and not already logged
                if tracker and not tracker.is_file_downloaded(xml_file):
                    try:
                        file_size = local_file.stat().st_size
                        tracker.log_download(xml_file, file_type, file_size)
                    except Exception as e:
                        logger.error(f"Error logging existing file to database: {e}")
                return True

        return False

    async def download_pubmed_updates(
        self,
        updates_dir: str = '~/knowledgebase/pubmed_data/updates',
        tracker: Optional[PubMedDownloadTracker] = None,
        from_highest_seq: bool = False,
        from_highest_processed_seq: bool = False
    ) -> None:
        """
        Download PubMed update files asynchronously.

        Args:
            updates_dir: Directory to store update files
            tracker: Database tracker for downloaded files
            from_highest_seq: Start from highest sequence number in database
            from_highest_processed_seq: Start from highest processed sequence number
        """
        # Ensure the path is fully expanded
        updates_path = Path(updates_dir).expanduser().resolve()
        updates_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting async PubMed updates download to {updates_path}")

        # Determine starting point
        last_downloaded_file = None
        if tracker and (from_highest_seq or from_highest_processed_seq):
            highest_seq = tracker.get_highest_sequence_number(processed_only=from_highest_processed_seq)
            if highest_seq > 0:
                last_downloaded_file = f"pubmed25n{highest_seq}.xml.gz"
                logger.info(f"Starting download from sequence number {highest_seq}")

        # Get list of files to download
        client = await self.create_ftp_client()
        try:
            await client.change_directory('/pubmed/updatefiles')
            files = []
            async for path, info in client.list():
                if path.name.endswith('.xml.gz'):
                    files.append(path.name)
            files.sort()

            # Skip files if we have a checkpoint
            if last_downloaded_file and last_downloaded_file in files:
                start_index = files.index(last_downloaded_file) + 1
                files = files[start_index:]
                logger.info(f"Resuming from file after {last_downloaded_file}")

        finally:
            await client.quit()

        total_files = len(files)
        logger.info(f"Found {total_files} PubMed update files to download")

        # Download files
        for i, xml_file in enumerate(files, 1):
            local_file = updates_path / xml_file

            # Check if file already exists and is valid
            if await self._should_skip_file(xml_file, local_file, tracker, 'update'):
                logger.info(f"Skipping existing valid file {xml_file} ({i}/{total_files})")
                continue

            # Download the file
            success, checksum = await self.download_single_file_with_retry(
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

        logger.info("Async PubMed updates download completed")


# Convenience functions for easy usage
async def download_pubmed_baseline_async(
    baseline_dir: str = '~/knowledgebase/pubmed_data/baseline',
    tracker: Optional[PubMedDownloadTracker] = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False,
    max_concurrent_downloads: int = 3
) -> None:
    """
    Convenience function to download PubMed baseline files asynchronously.

    Args:
        baseline_dir: Directory to store baseline files
        tracker: Database tracker for downloaded files
        from_highest_seq: Start from highest sequence number in database
        from_highest_processed_seq: Start from highest processed sequence number
        max_concurrent_downloads: Maximum number of concurrent downloads
    """
    downloader = AsyncPubMedDownloader(max_concurrent_downloads)
    await downloader.download_pubmed_baseline(
        baseline_dir, tracker, from_highest_seq, from_highest_processed_seq
    )


async def download_pubmed_updates_async(
    updates_dir: str = '~/knowledgebase/pubmed_data/updates',
    tracker: Optional[PubMedDownloadTracker] = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False,
    max_concurrent_downloads: int = 3
) -> None:
    """
    Convenience function to download PubMed update files asynchronously.

    Args:
        updates_dir: Directory to store update files
        tracker: Database tracker for downloaded files
        from_highest_seq: Start from highest sequence number in database
        from_highest_processed_seq: Start from highest processed sequence number
        max_concurrent_downloads: Maximum number of concurrent downloads
    """
    downloader = AsyncPubMedDownloader(max_concurrent_downloads)
    await downloader.download_pubmed_updates(
        updates_dir, tracker, from_highest_seq, from_highest_processed_seq
    )


def run_async_baseline_download(
    baseline_dir: str = '~/knowledgebase/pubmed_data/baseline',
    tracker: Optional[PubMedDownloadTracker] = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False,
    max_concurrent_downloads: int = 3
) -> None:
    """
    Synchronous wrapper to run async baseline download.

    Args:
        baseline_dir: Directory to store baseline files
        tracker: Database tracker for downloaded files
        from_highest_seq: Start from highest sequence number in database
        from_highest_processed_seq: Start from highest processed sequence number
        max_concurrent_downloads: Maximum number of concurrent downloads
    """
    asyncio.run(download_pubmed_baseline_async(
        baseline_dir, tracker, from_highest_seq, from_highest_processed_seq, max_concurrent_downloads
    ))


def run_async_updates_download(
    updates_dir: str = '~/knowledgebase/pubmed_data/updates',
    tracker: Optional[PubMedDownloadTracker] = None,
    from_highest_seq: bool = False,
    from_highest_processed_seq: bool = False,
    max_concurrent_downloads: int = 3
) -> None:
    """
    Synchronous wrapper to run async updates download.

    Args:
        updates_dir: Directory to store update files
        tracker: Database tracker for downloaded files
        from_highest_seq: Start from highest sequence number in database
        from_highest_processed_seq: Start from highest processed sequence number
        max_concurrent_downloads: Maximum number of concurrent downloads
    """
    asyncio.run(download_pubmed_updates_async(
        updates_dir, tracker, from_highest_seq, from_highest_processed_seq, max_concurrent_downloads
    ))
