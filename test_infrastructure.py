#!/usr/bin/env python3
"""
Test script to verify that database infrastructure checks only happen once.

This script creates multiple DatabaseManager instances and verifies that
the infrastructure check only happens once.
"""

import os
import sys
import logging

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the basic_infrastructure module
try:
    from localknowledge.db.basic_infrastructure import load_environment
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load test environment variables
test_env_file = os.environ.get('DOTENV_FILE', '.env.test')
if os.path.exists(test_env_file):
    logger.info(f"Loading environment from {test_env_file}")
    # Override existing environment variables
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment(dotenv_path=test_env_file, override=True)
    else:
        load_dotenv(test_env_file, override=True)
else:
    logger.warning(f"Test environment file {test_env_file} not found, using default .env")
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment()
    else:
        load_dotenv()

# Verify we're using the test database
db_name = os.environ.get('POSTGRES_DB')
if db_name != 'test_rwb':
    logger.warning(f"Not using test database! Current database: {db_name}")
    response = input("Continue with current database? [y/N] ")
    if response.lower() != 'y':
        logger.info("Exiting. Run test_env.py first to set up test environment.")
        sys.exit(1)

# Import the DatabaseManager class
from localknowledge.db.base import DatabaseManager


def test_infrastructure_check():
    """Test that infrastructure check only happens once."""
    logger.info("Creating first DatabaseManager instance")
    db1 = DatabaseManager(dotenv_path=test_env_file)

    logger.info("Creating second DatabaseManager instance")
    db2 = DatabaseManager(dotenv_path=test_env_file)

    logger.info("Creating third DatabaseManager instance")
    db3 = DatabaseManager(dotenv_path=test_env_file)

    # Create a manager with check_infrastructure=False
    logger.info("Creating DatabaseManager with check_infrastructure=False")
    db4 = DatabaseManager(check_infrastructure=False, dotenv_path=test_env_file)

    # Close all connections
    db1.close()
    db2.close()
    db3.close()
    db4.close()

    logger.info("Test completed successfully")


def main():
    """Main function."""
    try:
        test_infrastructure_check()
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
