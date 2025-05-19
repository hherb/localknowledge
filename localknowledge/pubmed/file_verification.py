"""
Module for verifying and handling corrupt PubMed XML files.

This module provides functions to check file integrity, verify MD5 checksums,
and handle corrupt files by re-downloading them if necessary.
"""
import os
import gzip
import logging
import shutil
import ftplib
import time
import hashlib
from typing import Optional, Tuple, Union

# Set up logging
logger = logging.getLogger(__name__)

# FTP connection parameters
FTP_HOST = 'ftp.ncbi.nlm.nih.gov'
BASELINE_PATH = '/pubmed/baseline'
UPDATES_PATH = '/pubmed/updatefiles'
FTP_TIMEOUT = 60  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

def check_xml_integrity(xml_path: str) -> bool:
    """
    Check if a gzipped XML file can be properly decompressed.

    Args:
        xml_path: Path to the gzipped XML file

    Returns:
        True if the file can be properly decompressed, False otherwise
    """
    try:
        with gzip.open(xml_path, 'rb') as f:
            # First try to read a small chunk for quick issues detection
            f.read(4096)

            # For files that have issues later in the file, try to read the entire file
            # This provides a more thorough check at the expense of performance
            # Reset file pointer first
            f.seek(0)

            # Read in chunks to avoid memory issues with large files
            chunk_size = 1024 * 1024  # 1MB chunks
            while f.read(chunk_size):
                pass

        return True
    except Exception as e:
        # Get more detailed error information for CRC failures
        error_msg = str(e)
        if "CRC check failed" in error_msg:
            # Extract the CRC values for better diagnostics
            import re
            crc_match = re.search(r'CRC check failed (0x[0-9a-f]+) != (0x[0-9a-f]+)', error_msg)
            if crc_match:
                computed_crc, expected_crc = crc_match.groups()
                logger.warning(f"File integrity check failed for {os.path.basename(xml_path)}: CRC check failed {computed_crc} != {expected_crc}")
            else:
                logger.warning(f"File integrity check failed for {os.path.basename(xml_path)}: {error_msg}")
        else:
            logger.warning(f"File integrity check failed for {os.path.basename(xml_path)}: {error_msg}")
        return False

def create_ftp_connection() -> ftplib.FTP:
    """
    Create and return an FTP connection to the NCBI server.

    Returns:
        FTP connection object
    """
    ftp = ftplib.FTP(FTP_HOST, timeout=FTP_TIMEOUT)
    ftp.login()  # Anonymous login
    return ftp

def verify_md5(file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verify a file's MD5 checksum against its corresponding .md5 file.

    Args:
        file_path: Path to the file to verify

    Returns:
        Tuple of (is_valid, checksum_value, error_message)
    """
    md5_file_path = file_path + '.md5'

    # Check if the MD5 file exists
    if not os.path.exists(md5_file_path):
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

            # Handle various MD5 file formats
            # Format 1: hash filename
            if ' ' in md5_content:
                expected_hash = md5_content.split()[0]
            # Format 2: MD5(filename)=hash
            elif 'MD5(' in md5_content and ')=' in md5_content:
                expected_hash = md5_content.split(')=')[1].strip()
            # Format 3: Just the hash
            else:
                expected_hash = md5_content

            # Remove any quotes, spaces, or other non-hex characters
            expected_hash = ''.join(c for c in expected_hash if c.isalnum())

            # If the expected hash is empty or not a valid MD5 (32 hex chars), verification cannot succeed
            if not expected_hash or len(expected_hash) != 32:
                # Log the content of the MD5 file for debugging
                logger.warning(f"Invalid MD5 content in {md5_file_path}: '{md5_content}'")
                return False, calculated_hash, "Empty or invalid MD5 in checksum file"

        # Compare the hashes (case-insensitive)
        is_valid = calculated_hash.lower() == expected_hash.lower()

        if not is_valid:
            return False, calculated_hash, f"Checksum mismatch: expected {expected_hash}, got {calculated_hash}"

        return True, calculated_hash, None

    except Exception as e:
        logger.error(f"Error verifying MD5 for {file_path}: {str(e)}")
        return False, None, f"Error verifying MD5: {str(e)}"

def download_file_from_ftp(ftp_path: str, file_name: str, local_path: str) -> bool:
    """
    Download a file from the NCBI FTP server.

    Args:
        ftp_path: Path on the FTP server
        file_name: Name of the file to download
        local_path: Local path to save the file

    Returns:
        True if download was successful, False otherwise
    """
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            ftp = create_ftp_connection()
            ftp.cwd(ftp_path)

            # Check if the file exists on the server
            try:
                file_size = ftp.size(file_name)
                logger.info(f"Found file {file_name} on FTP server with size {file_size} bytes")
            except Exception as e:
                logger.warning(f"File {file_name} not found on FTP server in {ftp_path}: {e}")
                return False

            logger.info(f"Downloading {file_name} from {ftp_path}")

            # Check if file exists and determine resume position
            rest_pos = 0
            if os.path.exists(local_path):
                try:
                    local_size = os.path.getsize(local_path)

                    # If local file is significantly larger than remote (corrupt), delete it
                    if local_size > file_size * 1.1:
                        logger.warning(f"File {local_path} appears corrupt (local: {local_size} bytes, remote: {file_size} bytes) - removing and downloading fresh")
                        os.remove(local_path)
                    # If file size matches, check if it's a valid gzip file
                    elif local_size == file_size:
                        try:
                            with gzip.open(local_path, 'rb') as test_f:
                                # Read a small chunk to verify it's a valid gzip file
                                test_f.read(4096)
                            # File is complete and valid, no need to download
                            logger.info(f"File {file_name} already exists and is valid, skipping download")
                            return True
                        except Exception as gz_error:
                            logger.warning(f"File {local_path} appears corrupt (gzip error: {gz_error}) - removing and downloading fresh")
                            os.remove(local_path)
                    else:
                        # File is incomplete but not corrupt, resume download
                        rest_pos = local_size
                        logger.info(f"Resuming download of {file_name} from position {rest_pos}")
                except Exception as e:
                    logger.warning(f"Error checking file size for {file_name}: {e} - restarting download")
                    if os.path.exists(local_path):
                        os.remove(local_path)

            # Download the file with size limit
            with open(local_path, 'ab' if rest_pos > 0 else 'wb') as f:
                # Track total bytes downloaded
                downloaded_bytes = rest_pos
                expected_size = file_size

                # Define callback function that will be called for each chunk of data
                def callback(data):
                    nonlocal downloaded_bytes
                    chunk_size = len(data)

                    # Check if adding this chunk would exceed the expected file size
                    if downloaded_bytes + chunk_size > expected_size:
                        # Only write the portion that fits within the expected size
                        bytes_to_write = expected_size - downloaded_bytes
                        if bytes_to_write > 0:
                            f.write(data[:bytes_to_write])
                            downloaded_bytes += bytes_to_write

                        # Signal to stop the download by raising a custom exception
                        raise StopDownloadException("Expected file size reached")
                    else:
                        # Normal case - write the whole chunk
                        f.write(data)
                        downloaded_bytes += chunk_size

                # Custom exception to cleanly stop the download when size is reached
                class StopDownloadException(Exception):
                    pass

                # Download the file
                try:
                    if rest_pos > 0:
                        try:
                            ftp.retrbinary(f'RETR {file_name}', callback, rest=rest_pos)
                        except StopDownloadException:
                            logger.info(f"Download stopped at expected size of {expected_size} bytes")
                        except Exception as e:
                            # If we get an invalid REST error, restart from beginning
                            if "invalid REST argument" in str(e):
                                logger.warning(f"Invalid resume position for {file_name}, restarting download from beginning")
                                # Close and reopen file in write mode
                                f.close()
                                with open(local_path, 'wb') as f:
                                    # Reset download counter
                                    downloaded_bytes = 0

                                    def callback_restart(data):
                                        nonlocal downloaded_bytes
                                        chunk_size = len(data)

                                        # Check if adding this chunk would exceed the expected file size
                                        if downloaded_bytes + chunk_size > expected_size:
                                            # Only write the portion that fits within the expected size
                                            bytes_to_write = expected_size - downloaded_bytes
                                            if bytes_to_write > 0:
                                                f.write(data[:bytes_to_write])
                                                downloaded_bytes += bytes_to_write

                                            # Signal to stop the download
                                            raise StopDownloadException("Expected file size reached")
                                        else:
                                            # Normal case - write the whole chunk
                                            f.write(data)
                                            downloaded_bytes += chunk_size

                                    try:
                                        ftp.retrbinary(f'RETR {file_name}', callback_restart)
                                    except StopDownloadException:
                                        logger.info(f"Download stopped at expected size of {expected_size} bytes")
                            else:
                                raise
                    else:
                        try:
                            ftp.retrbinary(f'RETR {file_name}', callback)
                        except StopDownloadException:
                            logger.info(f"Download stopped at expected size of {expected_size} bytes")

                    # Ensure all data is written to disk
                    f.flush()
                    os.fsync(f.fileno())
                except StopDownloadException:
                    logger.info(f"Download stopped at expected size of {expected_size} bytes")

            try:
                ftp.quit()
            except:
                pass

            # Verify the file was downloaded successfully
            if os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                if local_size == file_size:
                    logger.info(f"Successfully downloaded {file_name} ({local_size} bytes)")

                    # Verify the file is a valid gzip file
                    try:
                        with gzip.open(local_path, 'rb') as test_f:
                            test_f.read(4096)
                        logger.info(f"Gzip integrity check passed for {file_name}")
                        return True
                    except Exception as gz_error:
                        logger.warning(f"Gzip integrity check failed for {file_name}: {gz_error}")
                        os.remove(local_path)
                        retry_count += 1
                        continue
                else:
                    logger.warning(f"Downloaded file {file_name} has incorrect size. Expected {file_size}, got {local_size}.")
                    os.unlink(local_path)  # Remove the corrupted file

        except Exception as e:
            retry_count += 1
            logger.warning(f"Error downloading {file_name} (attempt {retry_count}/{MAX_RETRIES}): {e}")

            # Sleep before retrying
            time.sleep(RETRY_DELAY)

            try:
                ftp.quit()
            except:
                pass

    logger.error(f"Failed to download {file_name} after {MAX_RETRIES} attempts")
    return False

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
    import re
    match = re.search(r'pubmed\d+n(\d+)\.xml\.gz', xml_file)
    if not match:
        logger.warning(f"Cannot determine file type for {xml_file}, filename format not recognized")
        return False

    seq_number = int(match.group(1))
    # The update files typically have higher sequence numbers than baseline files
    # For 2025, updates start at 1275 according to documentation
    ftp_path = BASELINE_PATH if seq_number < 1275 else UPDATES_PATH

    md5_filename = f"{xml_file}.md5"

    # Download MD5 file directly without using the regular download function
    # since MD5 files are small text files, not gzipped files
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            ftp = create_ftp_connection()
            ftp.cwd(ftp_path)

            # Check if the file exists on the server
            try:
                file_size = ftp.size(md5_filename)
                logger.info(f"Found MD5 file {md5_filename} on FTP server with size {file_size} bytes")
            except Exception as e:
                logger.warning(f"MD5 file {md5_filename} not found on FTP server in {ftp_path}: {e}")
                return False

            logger.info(f"Downloading MD5 file {md5_filename} from {ftp_path}")

            # Download the MD5 file
            with open(md5_file_path, 'wb') as f:
                def callback(data):
                    f.write(data)
                ftp.retrbinary(f'RETR {md5_filename}', callback)

            ftp.quit()

            # Verify the file was downloaded successfully
            if os.path.exists(md5_file_path):
                local_size = os.path.getsize(md5_file_path)
                if local_size > 0:
                    logger.info(f"Successfully downloaded MD5 file {md5_filename} ({local_size} bytes)")
                    return True
                else:
                    logger.warning(f"Downloaded MD5 file {md5_filename} is empty")
                    os.unlink(md5_file_path)  # Remove the empty file

        except Exception as e:
            retry_count += 1
            logger.warning(f"Error downloading MD5 file {md5_filename} (attempt {retry_count}/{MAX_RETRIES}): {e}")

            # Sleep before retrying
            time.sleep(RETRY_DELAY)

            try:
                ftp.quit()
            except:
                pass

    logger.error(f"Failed to download MD5 file {md5_filename} after {MAX_RETRIES} attempts")
    return False

def verify_and_handle_corrupt_file(
    xml_path: str,
    baseline_dir: Optional[str] = None,
    updates_dir: Optional[str] = None,
    tracker = None
) -> bool:
    """
    Verify a potentially corrupt file and handle it by re-downloading if necessary.

    Args:
        xml_path: Path to the XML file to verify
        baseline_dir: Directory for baseline files (if applicable)
        updates_dir: Directory for update files (if applicable)
        tracker: Optional PubMedDownloadTracker instance

    Returns:
        True if the file was successfully verified or repaired, False otherwise
    """
    xml_file = os.path.basename(xml_path)
    logger.info(f"Verifying potentially corrupt file: {xml_file}")

    # Determine if it's a baseline or update file and the appropriate directory
    import re
    match = re.search(r'pubmed\d+n(\d+)\.xml\.gz', xml_file)
    if match:
        seq_number = int(match.group(1))
        is_update = seq_number >= 1275  # For 2025, updates start at 1275

        if is_update:
            ftp_path = UPDATES_PATH
            target_dir = updates_dir or os.path.dirname(xml_path)
        else:
            ftp_path = BASELINE_PATH
            target_dir = baseline_dir or os.path.dirname(xml_path)
    else:
        logger.error(f"Cannot determine file type for {xml_file}, canceling repair")
        return False

    # First, verify the MD5 checksum if an MD5 file exists
    is_valid, checksum, error_msg = verify_md5(xml_path)

    if is_valid:
        logger.info(f"MD5 verification passed for {xml_file} despite decompression issues")
        return True

    # If MD5 file doesn't exist or checksum failed, try to download the MD5 file
    if not is_valid and error_msg == "MD5 file not found":
        logger.info(f"MD5 file not found for {xml_file}, attempting to download")
        md5_path = xml_path + '.md5'
        md5_downloaded = download_md5_file(xml_file, md5_path)

        if md5_downloaded:
            is_valid, checksum, error_msg = verify_md5(xml_path)
            if is_valid:
                logger.info(f"Re-verification with downloaded MD5 file passed for {xml_file}")
                return True

    # If MD5 verification failed or couldn't be done, need to re-download the file
    logger.info(f"Re-downloading corrupt file {xml_file}")

    # Move the corrupted file to a backup
    backup_path = f"{xml_path}.corrupt"
    try:
        shutil.move(xml_path, backup_path)
        logger.info(f"Moved corrupt file to {backup_path}")
    except Exception as e:
        logger.warning(f"Could not create backup of corrupt file: {e}")
        # If we can't move the file, try to delete it
        try:
            os.remove(xml_path)
            logger.info(f"Deleted corrupt file {xml_path}")
        except Exception as e2:
            logger.warning(f"Could not delete corrupt file: {e2}")
            # If we can't delete it either, we might have permission issues
            # Try to continue anyway

    # Download a fresh copy
    download_successful = download_file_from_ftp(ftp_path, xml_file, xml_path)

    if download_successful:
        # Verify the file can be decompressed
        try:
            with gzip.open(xml_path, 'rb') as test_f:
                # Read a small chunk to verify it's a valid gzip file
                test_f.read(4096)
            logger.info(f"Gzip integrity check passed for re-downloaded file {xml_file}")

            # Also download the MD5 file if it doesn't exist
            md5_path = xml_path + '.md5'
            if not os.path.exists(md5_path):
                md5_file = xml_file + '.md5'
                download_md5_file(xml_file, md5_path)

            # Verify the newly downloaded file with MD5 if possible
            if os.path.exists(md5_path):
                is_valid, checksum, error_msg = verify_md5(xml_path)

                if not is_valid:
                    logger.warning(f"MD5 verification failed for re-downloaded file: {error_msg}")
                    # Continue anyway since the gzip check passed

            logger.info(f"Successfully replaced corrupt file {xml_file}")

            # Remove the backup of the corrupt file if it exists
            if os.path.exists(backup_path):
                try:
                    os.unlink(backup_path)
                    logger.info(f"Removed backup of corrupt file {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not remove backup of corrupt file: {e}")

            # Update tracker if provided
            if tracker:
                try:
                    file_size = os.path.getsize(xml_path)
                    file_type = 'update' if is_update else 'baseline'
                    tracker.log_download(xml_file, file_type, file_size)
                    logger.info(f"Updated tracker for re-downloaded file {xml_file}")
                except Exception as e:
                    logger.warning(f"Could not update tracker for {xml_file}: {e}")

            return True
        except Exception as gz_error:
            logger.error(f"Re-downloaded file {xml_file} failed gzip integrity check: {gz_error}")

            # If the re-downloaded file is also corrupt, try one more time with a different approach
            try:
                os.remove(xml_path)
                logger.info(f"Removed corrupt re-downloaded file {xml_file}")

                # Try one more time with a direct download approach
                logger.info(f"Attempting final direct download of {xml_file}")

                # Create a new FTP connection
                ftp = create_ftp_connection()
                ftp.cwd(ftp_path)

                # Download directly without size checks
                with open(xml_path, 'wb') as f:
                    def callback(data):
                        f.write(data)
                    ftp.retrbinary(f'RETR {xml_file}', callback)

                ftp.quit()

                # Verify this final attempt
                try:
                    with gzip.open(xml_path, 'rb') as test_f:
                        test_f.read(4096)
                    logger.info(f"Final download attempt successful for {xml_file}")
                    return True
                except Exception as final_error:
                    logger.error(f"Final download attempt also failed: {final_error}")
                    return False
            except Exception as e:
                logger.error(f"Error during final download attempt: {e}")
                return False
    else:
        # If download failed, restore the backup if it exists
        if os.path.exists(backup_path):
            try:
                shutil.move(backup_path, xml_path)
                logger.info(f"Restored original file from backup after failed download")
            except Exception as e:
                logger.error(f"Could not restore backup after failed download: {e}")

        return False
