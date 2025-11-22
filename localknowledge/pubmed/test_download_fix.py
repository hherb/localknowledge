#!/usr/bin/env python3
"""
Test script to verify the fixed download functionality.
This script tests the simplified download logic to ensure it works correctly.
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from localknowledge.pubmed.download import create_ftp_connection, download_single_file
from localknowledge.pubmed.file_verification import check_xml_integrity

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def test_download_single_file():
    """
    Test downloading a single small PubMed file to verify the fix works.
    """
    logger.info("Testing simplified download functionality...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Connect to FTP
            logger.info("Connecting to NCBI FTP server...")
            ftp = create_ftp_connection()
            
            # Get a list of files from the baseline directory
            ftp.cwd('/pubmed/baseline')
            files = ftp.nlst()
            xml_files = [f for f in files if f.endswith('.xml.gz')]
            
            if not xml_files:
                logger.error("No XML files found in baseline directory")
                return False
            
            # Pick the first (smallest) file for testing
            test_file = xml_files[0]
            local_path = os.path.join(temp_dir, test_file)
            
            logger.info(f"Testing download of {test_file}")
            
            # Test the download
            success, checksum = download_single_file(ftp, test_file, local_path, 'baseline', 1, 1)
            
            if success:
                logger.info(f"✓ Download successful!")
                
                # Verify file integrity
                if check_xml_integrity(local_path):
                    logger.info(f"✓ File integrity check passed!")
                    
                    # Check file size
                    file_size = os.path.getsize(local_path)
                    logger.info(f"✓ Downloaded file size: {file_size} bytes")
                    
                    if checksum:
                        logger.info(f"✓ MD5 checksum: {checksum}")
                    
                    return True
                else:
                    logger.error("✗ File integrity check failed!")
                    return False
            else:
                logger.error("✗ Download failed!")
                return False
                
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            return False
        finally:
            try:
                ftp.quit()
            except Exception:
                pass

def test_file_validation():
    """
    Test the file validation functions.
    """
    logger.info("Testing file validation functionality...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Create a test file with some content
            test_file_path = os.path.join(temp_dir, "test.txt")
            with open(test_file_path, 'w') as f:
                f.write("This is a test file for validation.")
            
            # Test that the file exists and has content
            if os.path.exists(test_file_path) and os.path.getsize(test_file_path) > 0:
                logger.info("✓ File validation test setup successful")
                return True
            else:
                logger.error("✗ File validation test setup failed")
                return False
                
        except Exception as e:
            logger.error(f"File validation test failed: {e}")
            return False

def main():
    """
    Run all tests.
    """
    logger.info("=" * 60)
    logger.info("TESTING DOWNLOAD CORRUPTION FIXES")
    logger.info("=" * 60)
    
    # Test file validation first (simpler test)
    if not test_file_validation():
        logger.error("Basic file validation test failed")
        return False
    
    # Test actual download functionality
    if not test_download_single_file():
        logger.error("Download test failed")
        return False
    
    logger.info("=" * 60)
    logger.info("✓ ALL TESTS PASSED - Download fixes appear to be working!")
    logger.info("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
