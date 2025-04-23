#!/usr/bin/env python3
"""
Set up test environment for database tests.

This script sets up environment variables for testing the database infrastructure.
It creates a temporary .env.test file with test database settings.
"""

import os
import sys
import logging
import argparse

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the basic_infrastructure module
try:
    from localknowledge.db.basic_infrastructure import load_environment
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv, set_key

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test database settings
TEST_DB_NAME = "test_rwb"
TEST_ENV_FILE = ".env.test"


def setup_test_env():
    """Set up test environment variables."""
    # Load existing environment variables
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment()
    else:
        load_dotenv()

    # Get current database settings
    current_db = os.environ.get('POSTGRES_DB')
    current_user = os.environ.get('POSTGRES_USER')
    current_password = os.environ.get('POSTGRES_PASSWORD')
    current_host = os.environ.get('POSTGRES_HOST', 'localhost')
    current_port = os.environ.get('POSTGRES_PORT', '5432')

    logger.info(f"Current database: {current_db}")
    logger.info(f"Test database: {TEST_DB_NAME}")

    # SAFETY CHECK: Ensure test database is different from current database
    if current_db == TEST_DB_NAME:
        logger.error(f"SAFETY ERROR: Test database '{TEST_DB_NAME}' is the same as current database!")
        logger.error("This could lead to data loss in your current database.")
        logger.error("Please use a different name for the test database.")
        raise ValueError(f"Test database '{TEST_DB_NAME}' cannot be the same as current database '{current_db}'")

    # Create test .env file
    with open(TEST_ENV_FILE, 'w') as f:
        f.write(f"POSTGRES_DB={TEST_DB_NAME}\n")
        f.write(f"POSTGRES_USER={current_user}\n")
        f.write(f"POSTGRES_PASSWORD={current_password}\n")
        f.write(f"POSTGRES_HOST={current_host}\n")
        f.write(f"POSTGRES_PORT={current_port}\n")
        f.write(f"RWB_MIGRATION_DIR=./test_migrations\n")

    logger.info(f"Created test environment file: {TEST_ENV_FILE}")

    # Create test migrations directory
    os.makedirs("./test_migrations", exist_ok=True)
    logger.info("Created test migrations directory: ./test_migrations")

    # Return the test environment file path
    return TEST_ENV_FILE


def create_test_database():
    """Create test database if it doesn't exist."""
    import psycopg2

    # Load existing environment variables
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment()
    else:
        load_dotenv()

    # Get current database settings
    current_db = os.environ.get('POSTGRES_DB')
    user = os.environ.get('POSTGRES_USER')
    password = os.environ.get('POSTGRES_PASSWORD')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    # SAFETY CHECK: Ensure test database is different from current database
    if current_db == TEST_DB_NAME:
        logger.error(f"SAFETY ERROR: Test database '{TEST_DB_NAME}' is the same as current database!")
        logger.error("This could lead to data loss in your current database.")
        logger.error("Please use a different name for the test database.")
        return False

    # SAFETY CHECK: Ensure test database name follows a safe pattern
    if not TEST_DB_NAME.startswith('test_'):
        logger.error(f"SAFETY ERROR: Test database name '{TEST_DB_NAME}' must start with 'test_'")
        logger.error("This is a safety measure to prevent accidental use of production databases.")
        return False

    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if test database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'")
        exists = cursor.fetchone()

        if not exists:
            # Create test database
            logger.info(f"Creating test database: {TEST_DB_NAME}")
            cursor.execute(f"CREATE DATABASE {TEST_DB_NAME}")
            logger.info(f"Test database created: {TEST_DB_NAME}")
        else:
            logger.info(f"Test database already exists: {TEST_DB_NAME}")

        cursor.close()
        conn.close()

        # Connect to the test database to create extensions
        conn = psycopg2.connect(
            dbname=TEST_DB_NAME,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Create pgvector extension
        try:
            logger.info("Creating pgvector extension in test database")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("pgvector extension created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating pgvector extension: {e}")
            logger.warning("Some tests may fail due to missing pgvector extension")

        cursor.close()
        conn.close()

        return True
    except Exception as e:
        logger.error(f"Error creating test database: {e}")
        return False


def drop_test_database():
    """Drop the test database."""
    import psycopg2

    # Load existing environment variables
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment()
    else:
        load_dotenv()

    # Get current database settings
    user = os.environ.get('POSTGRES_USER')
    password = os.environ.get('POSTGRES_PASSWORD')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    # SAFETY CHECK: Ensure test database name follows a safe pattern
    if not TEST_DB_NAME.startswith('test_'):
        logger.error(f"SAFETY ERROR: Cannot drop database '{TEST_DB_NAME}' as it doesn't start with 'test_'")
        logger.error("This is a safety measure to prevent accidental dropping of production databases.")
        return False

    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if test database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'")
        exists = cursor.fetchone()

        if exists:
            # Terminate all connections to the test database
            cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
            AND pid <> pg_backend_pid()
            """)

            # Drop test database
            logger.info(f"Dropping test database: {TEST_DB_NAME}")
            cursor.execute(f"DROP DATABASE {TEST_DB_NAME}")
            logger.info(f"Test database dropped: {TEST_DB_NAME}")
        else:
            logger.info(f"Test database does not exist: {TEST_DB_NAME}")

        cursor.close()
        conn.close()

        return True
    except Exception as e:
        logger.error(f"Error dropping test database: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Set up test environment')
    parser.add_argument('--cleanup', action='store_true', help='Clean up test environment')
    args = parser.parse_args()

    if args.cleanup:
        try:
            # Drop test database
            if not drop_test_database():
                logger.error("Failed to drop test database")
                return 1

            # Remove test environment file
            if os.path.exists(TEST_ENV_FILE):
                os.remove(TEST_ENV_FILE)
                logger.info(f"Removed test environment file: {TEST_ENV_FILE}")

            logger.info("Test environment cleaned up successfully")
            return 0
        except Exception as e:
            logger.error(f"Error cleaning up test environment: {e}")
            return 1
    else:
        try:
            # Set up test environment
            test_env_file = setup_test_env()

            # Create test database
            if not create_test_database():
                logger.error("Failed to create test database")
                return 1

            logger.info("Test environment set up successfully")
            logger.info(f"To use the test environment, run: export DOTENV_FILE={test_env_file}")
            logger.info(f"To clean up the test environment, run: python {sys.argv[0]} --cleanup")

            return 0
        except Exception as e:
            logger.error(f"Error setting up test environment: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
