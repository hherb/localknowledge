"""
Simplified async PubMed downloader using aioftp.

This is a simpler, more robust implementation that avoids some of the
complexity issues with the full async downloader.
"""

import asyncio
import os
import gzip
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import aiofiles
    import aioftp
    ASYNC_DEPS_AVAILABLE = True
except ImportError as e:
    ASYNC_DEPS_AVAILABLE = False
    missing_deps = str(e)
    logging.warning(f"Async dependencies not available: {missing_deps}")

# Import the download tracker
from localknowledge.pubmed.download_tracker import PubMedDownloadTracker

# Set up logging
logger = logging.getLogger(__name__)

# Constants
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
CHUNK_SIZE = 1024 * 1024  # 1MB chunks


class SimpleAsyncDownloader:
    """Simplified async PubMed downloader."""
    
    def __init__(self):
        """Initialize the downloader."""
        pass
        
    async def create_ftp_client(self) -> aioftp.Client:
        """Create and return a new FTP client connection."""
        client = aioftp.Client()
        await client.connect(FTP_HOST)
        await client.login()
        return client
        
    async def get_file_size(self, client: aioftp.Client, filename: str) -> int:
        """Get the size of a remote file."""
        try:
            # Try using SIZE command first
            response = await client.command("SIZE " + filename)
            if response.code == "213":
                return int(response.info[-1])
        except:
            pass
            
        # Fallback to stat
        try:
            stat_info = await client.stat(filename)
            if isinstance(stat_info, dict):
                return int(stat_info.get('size', 0))
            else:
                return int(getattr(stat_info, 'size', 0))
        except:
            return 0
            
    async def download_file_simple(
        self,
        remote_file: str,
        local_file: Path,
        file_type: str = 'update'
    ) -> Tuple[bool, Optional[str]]:
        """
        Download a single file with basic progress logging.
        
        Args:
            remote_file: Name of the remote file
            local_file: Local path to save the file
            file_type: 'baseline' or 'update'
            
        Returns:
            Tuple of (success, checksum)
        """
        client = None
        try:
            # Create FTP connection
            client = await self.create_ftp_client()
            
            # Navigate to appropriate directory
            if file_type == 'baseline':
                await client.change_directory('/pubmed/baseline')
            else:
                await client.change_directory('/pubmed/updatefiles')
                
            # Get file size
            expected_size = await self.get_file_size(client, remote_file)
            if expected_size == 0:
                logger.warning(f"Could not determine size for {remote_file}")
                
            logger.info(f"Starting download of {remote_file} ({expected_size} bytes)")
            
            # Check if we can resume
            resume_pos = 0
            if local_file.exists():
                current_size = local_file.stat().st_size
                if current_size < expected_size:
                    resume_pos = current_size
                    logger.info(f"Resuming download from byte {resume_pos}")
                elif current_size == expected_size:
                    # File might be complete
                    if await self._verify_file_integrity(local_file):
                        logger.info(f"File {remote_file} already complete and valid")
                        return True, None
                    else:
                        logger.info(f"File {remote_file} exists but is corrupt, redownloading")
                        local_file.unlink()
                        resume_pos = 0
                        
            # Download the file
            downloaded_bytes = resume_pos
            mode = 'ab' if resume_pos > 0 else 'wb'
            
            async with aiofiles.open(local_file, mode) as f:
                async with client.download_stream(remote_file, offset=resume_pos) as stream:
                    async for chunk in stream.iter_by_block(CHUNK_SIZE):
                        if not chunk:
                            break
                            
                        await f.write(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # Log progress every 10MB
                        if downloaded_bytes % (10 * 1024 * 1024) == 0:
                            if expected_size > 0:
                                percent = (downloaded_bytes / expected_size) * 100
                                logger.info(f"Downloaded {downloaded_bytes}/{expected_size} bytes ({percent:.1f}%)")
                            else:
                                logger.info(f"Downloaded {downloaded_bytes} bytes")
                                
                        # Stop if we've reached expected size
                        if expected_size > 0 and downloaded_bytes >= expected_size:
                            break
                            
            # Verify download
            if local_file.exists():
                actual_size = local_file.stat().st_size
                if expected_size > 0 and actual_size != expected_size:
                    logger.warning(f"Size mismatch: expected {expected_size}, got {actual_size}")
                    
                # Verify file integrity
                if await self._verify_file_integrity(local_file):
                    logger.info(f"✓ Successfully downloaded {remote_file} ({actual_size} bytes)")
                    
                    # Try to get MD5 checksum
                    checksum = await self._download_and_verify_md5(client, remote_file, local_file)
                    return True, checksum
                else:
                    logger.error(f"Downloaded file {remote_file} failed integrity check")
                    return False, None
            else:
                logger.error(f"Downloaded file does not exist: {local_file}")
                return False, None
                
        except Exception as e:
            logger.error(f"Error downloading {remote_file}: {type(e).__name__}: {e}")
            return False, None
            
        finally:
            if client:
                try:
                    await client.quit()
                except:
                    pass
                    
    async def _verify_file_integrity(self, file_path: Path) -> bool:
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
            
    async def _download_and_verify_md5(
        self,
        client: aioftp.Client,
        remote_file: str,
        local_file: Path
    ) -> Optional[str]:
        """Download and verify MD5 checksum if available."""
        md5_file = remote_file + '.md5'
        local_md5_file = local_file.with_suffix(local_file.suffix + '.md5')
        
        try:
            await client.download(md5_file, local_md5_file)
            
            # Calculate MD5 of downloaded file
            md5_hash = hashlib.md5()
            async with aiofiles.open(local_file, 'rb') as f:
                async for chunk in self._read_file_chunks(f):
                    md5_hash.update(chunk)
            calculated_hash = md5_hash.hexdigest()
            
            # Read expected hash
            async with aiofiles.open(local_md5_file, 'r') as f:
                md5_content = await f.read()
                md5_content = md5_content.strip()
                
                if '=' in md5_content:
                    expected_hash = md5_content.split('=', 1)[1].strip()
                elif ' ' in md5_content:
                    expected_hash = md5_content.split()[0]
                else:
                    expected_hash = md5_content
                    
                expected_hash = expected_hash.strip().strip('"').strip("'")
                
            # Compare hashes
            if calculated_hash.lower() == expected_hash.lower():
                logger.debug(f"✓ MD5 verification passed for {remote_file}")
                return calculated_hash
            else:
                logger.warning(f"✗ MD5 mismatch for {remote_file}: expected {expected_hash}, got {calculated_hash}")
                return None
                
        except Exception as e:
            logger.debug(f"Could not verify MD5 for {remote_file}: {e}")
            return None
            
    async def _read_file_chunks(self, file_handle, chunk_size: int = CHUNK_SIZE):
        """Read file in chunks asynchronously."""
        while True:
            chunk = await file_handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


# Convenience functions
async def download_single_file_async(
    remote_file: str,
    local_file: str,
    file_type: str = 'update'
) -> Tuple[bool, Optional[str]]:
    """
    Download a single PubMed file asynchronously.
    
    Args:
        remote_file: Name of the remote file
        local_file: Local path to save the file
        file_type: 'baseline' or 'update'
        
    Returns:
        Tuple of (success, checksum)
    """
    if not ASYNC_DEPS_AVAILABLE:
        raise ImportError("Async dependencies not available. Please install: pip install aioftp aiofiles")
        
    downloader = SimpleAsyncDownloader()
    return await downloader.download_file_simple(remote_file, Path(local_file), file_type)


def download_single_file_sync(
    remote_file: str,
    local_file: str,
    file_type: str = 'update'
) -> Tuple[bool, Optional[str]]:
    """
    Synchronous wrapper for downloading a single file.
    
    Args:
        remote_file: Name of the remote file
        local_file: Local path to save the file
        file_type: 'baseline' or 'update'
        
    Returns:
        Tuple of (success, checksum)
    """
    return asyncio.run(download_single_file_async(remote_file, local_file, file_type))
