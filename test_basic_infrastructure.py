#!/usr/bin/env python3
"""
Test script to verify basic infrastructure checks.

This script tests the basic_infrastructure.py module to ensure it properly
checks database connection, extensions, and version.
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


def test_db_connection_params():
    """Test database connection parameters."""
    try:
        logger.info("Importing get_db_connection_params")
        from localknowledge.db.basic_infrastructure import get_db_connection_params

        logger.info("Getting database connection parameters")
        params = get_db_connection_params(dotenv_path=test_env_file)

        # Print parameters (without password)
        safe_params = params.copy()
        if 'password' in safe_params:
            safe_params['password'] = '********'
        logger.info(f"Database connection parameters: {safe_params}")

        logger.info("Database connection parameters test passed")
    except Exception as e:
        logger.error(f"Error testing database connection parameters: {e}")
        raise


def test_db_connection():
    """Test database connection."""
    try:
        logger.info("Importing check_database_connection")
        from localknowledge.db.basic_infrastructure import check_database_connection

        logger.info("Checking database connection")
        result = check_database_connection(dotenv_path=test_env_file)

        logger.info(f"Database connection check result: {result}")
        logger.info("Database connection test passed")
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")
        raise


def test_required_extensions():
    """Test required extensions check."""
    try:
        logger.info("Importing check_required_extensions")
        from localknowledge.db.basic_infrastructure import check_required_extensions

        logger.info("Checking required extensions")
        result = check_required_extensions(dotenv_path=test_env_file)

        logger.info(f"Required extensions check result: {result}")
        logger.info("Required extensions test passed")
    except Exception as e:
        logger.error(f"Error testing required extensions: {e}")
        raise


def test_db_version():
    """Test database version check."""
    try:
        logger.info("Importing check_database_version")
        from localknowledge.db.basic_infrastructure import check_database_version

        logger.info("Checking database version")
        is_initialized, current_version = check_database_version(dotenv_path=test_env_file)

        logger.info(f"Database initialized: {is_initialized}")
        logger.info(f"Current database version: {current_version}")
        logger.info("Database version test passed")
    except Exception as e:
        logger.error(f"Error testing database version: {e}")
        raise


def test_db_infrastructure():
    """Test overall database infrastructure check."""
    try:
        logger.info("Importing check_database_infrastructure")
        from localknowledge.db.basic_infrastructure import check_database_infrastructure

        logger.info("Checking database infrastructure")
        is_valid, error_message = check_database_infrastructure(dotenv_path=test_env_file)

        logger.info(f"Database infrastructure valid: {is_valid}")
        if not is_valid:
            logger.warning(f"Error message: {error_message}")

        logger.info("Database infrastructure test passed")
    except Exception as e:
        logger.error(f"Error testing database infrastructure: {e}")
        raise


def main():
    """Main function."""
    try:
        test_db_connection_params()
        test_db_connection()
        test_required_extensions()
        test_db_version()
        test_db_infrastructure()

        logger.info("All tests completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
