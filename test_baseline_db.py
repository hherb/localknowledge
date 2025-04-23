#!/usr/bin/env python3
"""
Test script to verify baseline database creation.

This script tests the create_baseline_db.py script to ensure it properly
creates the database schema.
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


def test_baseline_db_creation(force=False):
    """
    Test baseline database creation.

    Args:
        force: Whether to force recreation of tables
    """
    try:
        logger.info("Importing BaselineDBCreator")
        from localknowledge.db.create_baseline_db import BaselineDBCreator

        # Set environment variable for test database
        os.environ['DOTENV_FILE'] = test_env_file

        logger.info(f"Creating baseline database (force={force})")
        creator = BaselineDBCreator(force=force)

        logger.info("Checking if tables exist")
        tables_exist = creator.check_if_tables_exist()
        logger.info(f"Tables exist: {tables_exist}")

        if tables_exist and not force:
            logger.warning("Tables already exist. Use --force to recreate them.")
            return

        logger.info("Creating baseline database")
        creator.create_baseline_database()

        logger.info("Closing connection")
        creator.close()

        logger.info("Baseline database created successfully")
    except Exception as e:
        logger.error(f"Error creating baseline database: {e}")
        raise


def test_migrations():
    """Test migrations system."""
    try:
        logger.info("Importing migrations manager")
        from localknowledge.db.migrations_system import MigrationsManager

        # Set environment variable for test database
        os.environ['DOTENV_FILE'] = test_env_file

        logger.info("Creating migrations manager")
        manager = MigrationsManager()

        logger.info("Getting current version")
        current_version = manager.get_current_version()
        logger.info(f"Current database version: {current_version}")

        logger.info("Getting available migrations")
        available_migrations = manager.get_available_migrations()
        logger.info(f"Available migrations: {available_migrations}")

        logger.info("Getting pending migrations")
        pending_migrations = manager.get_pending_migrations()
        logger.info(f"Pending migrations: {pending_migrations}")

        if pending_migrations:
            logger.info("Running pending migrations")
            success = manager.run_pending_migrations()
            logger.info(f"Migrations completed successfully: {success}")

            logger.info("Getting new current version")
            new_version = manager.get_current_version()
            logger.info(f"New database version: {new_version}")
        else:
            logger.info("No pending migrations")

        logger.info("Migrations test completed successfully")
    except Exception as e:
        logger.error(f"Error testing migrations: {e}")
        raise


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test baseline database creation')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables')
    parser.add_argument('--skip-baseline', action='store_true', help='Skip baseline database creation')
    parser.add_argument('--skip-migrations', action='store_true', help='Skip migrations test')
    args = parser.parse_args()

    try:
        if not args.skip_baseline:
            test_baseline_db_creation(force=args.force)

        if not args.skip_migrations:
            test_migrations()

        logger.info("All tests completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
