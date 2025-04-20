#!/usr/bin/env python3
"""
Script to directly fix a corrupt PubMed XML file by downloading a fresh copy.
This bypasses the normal import process to focus on repairing specific files.
"""

import os
import sys
import logging
import gzip
from localknowledge.pubmed.file_verification import check_xml_integrity, verify_and_handle_corrupt_file

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def fix_corrupt_file(file_path):
    """
    Fix a corrupt PubMed XML file by downloading a fresh copy.
    
    Args:
        file_path: Path to the corrupt XML file
    """
    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return False
    
    logger.info(f"Checking file integrity: {file_path}")
    
    # Check if file is corrupt by trying to fully decompress it
    try:
        # Perform a more thorough integrity check by actually reading the whole file
        with gzip.open(file_path, 'rb') as f:
            # Try to read the entire file, which will verify full decompression
            content = f.read()
            if len(content) > 0:
                logger.info(f"File passes integrity check, no need to fix: {file_path}")
                return True
            else:
                logger.warning(f"File appears to be empty: {file_path}")
    except Exception as e:
        logger.warning(f"File is definitely corrupt: {file_path} - Error: {str(e)}")

    logger.warning(f"File appears to be corrupt: {file_path}")
    
    # Get directory type (baseline or updates) from path
    if "baseline" in file_path.lower():
        baseline_dir = os.path.dirname(file_path)
        updates_dir = None
    elif "updates" in file_path.lower() or "update" in file_path.lower():
        baseline_dir = None
        updates_dir = os.path.dirname(file_path)
    else:
        # If can't determine, set both to the parent directory
        parent_dir = os.path.dirname(file_path)
        baseline_dir = parent_dir
        updates_dir = parent_dir
    
    # Try to repair the file
    is_fixed = verify_and_handle_corrupt_file(
        file_path,
        baseline_dir=baseline_dir,
        updates_dir=updates_dir
    )
    
    if is_fixed:
        logger.info(f"Successfully fixed corrupt file: {file_path}")
    else:
        logger.error(f"Failed to fix corrupt file: {file_path}")
    
    return is_fixed

if __name__ == "__main__":
    # Get file path from command line argument or use default
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        target_file = "/Users/hherb/knowledgebase/pubmed_data/updates/pubmed25n1282.xml.gz"
    
    # Make sure file path is absolute
    target_file = os.path.abspath(os.path.expanduser(target_file))
    
    logger.info(f"Starting repair process for: {target_file}")
    result = fix_corrupt_file(target_file)
    
    # Exit with appropriate status code
    sys.exit(0 if result else 1)
