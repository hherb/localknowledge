#!/usr/bin/env python3
"""
Test script for baseline database creation using schema.sql.

This script creates a test database, runs the baseline creation script with schema.sql,
and then drops the test database. It includes safety checks to ensure we're not
affecting the production database.

Usage:
    python test_baseline_creation.py
"""

import os
import sys
import logging
import psycopg2
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test database name
TEST_DB_NAME = 'test_rwb'

def get_connection_params():
    """Get database connection parameters from environment variables."""
    # Load environment variables
    dotenv_file = os.environ.get('DOTENV_FILE', '.env')
    if os.path.exists(dotenv_file):
        load_dotenv(dotenv_file)
    else:
        load_dotenv()

    # Get connection parameters
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    # Get production database name for safety check
    prod_db = os.environ.get('POSTGRES_DB')

    return {
        'user': user,
        'password': password,
        'host': host,
        'port': port,
        'prod_db': prod_db
    }

def create_test_database(connection_params):
    """Create a test database."""
    # Connect to default postgres database
    conn = psycopg2.connect(
        dbname='postgres',
        user=connection_params['user'],
        password=connection_params['password'],
        host=connection_params['host'],
        port=connection_params['port']
    )
    conn.autocommit = True
    cursor = conn.cursor()

    # Safety check: make sure test database name is not the same as production
    if connection_params['prod_db'] == TEST_DB_NAME:
        logger.error(f"Test database name '{TEST_DB_NAME}' is the same as production database. Aborting.")
        sys.exit(1)

    # Drop test database if it exists
    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        logger.info(f"Dropped existing test database '{TEST_DB_NAME}'")
    except psycopg2.Error as e:
        logger.error(f"Error dropping test database: {e}")
        conn.close()
        sys.exit(1)

    # Create test database
    try:
        cursor.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        logger.info(f"Created test database '{TEST_DB_NAME}'")
    except psycopg2.Error as e:
        logger.error(f"Error creating test database: {e}")
        conn.close()
        sys.exit(1)

    # Create vector extension in the test database
    try:
        # Connect to the test database
        test_conn = psycopg2.connect(
            dbname=TEST_DB_NAME,
            user=connection_params['user'],
            password=connection_params['password'],
            host=connection_params['host'],
            port=connection_params['port']
        )
        test_conn.autocommit = True
        test_cursor = test_conn.cursor()

        # Create vector extension
        test_cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.info("Created vector extension in test database")

        test_cursor.close()
        test_conn.close()
    except psycopg2.Error as e:
        logger.error(f"Error creating vector extension: {e}")
        conn.close()
        sys.exit(1)

    cursor.close()
    conn.close()

def drop_test_database(connection_params):
    """Drop the test database."""
    # Connect to default postgres database
    conn = psycopg2.connect(
        dbname='postgres',
        user=connection_params['user'],
        password=connection_params['password'],
        host=connection_params['host'],
        port=connection_params['port']
    )
    conn.autocommit = True
    cursor = conn.cursor()

    # Safety check: make sure test database name is not the same as production
    if connection_params['prod_db'] == TEST_DB_NAME:
        logger.error(f"Test database name '{TEST_DB_NAME}' is the same as production database. Aborting.")
        sys.exit(1)

    # Drop test database
    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        logger.info(f"Dropped test database '{TEST_DB_NAME}'")
    except psycopg2.Error as e:
        logger.error(f"Error dropping test database: {e}")

    cursor.close()
    conn.close()

def run_baseline_creation(connection_params):
    """Run the baseline creation script with the test database."""
    # Create a test environment file
    test_env_path = Path('test_env')
    logger.info(f"Using test environment file: {test_env_path}")

    # Find the schema.sql file
    schema_path = Path('schema.sql')
    if not schema_path.exists():
        logger.error(f"Schema file not found: {schema_path}")
        sys.exit(1)

    # Run the baseline creation script
    cmd = [sys.executable, '-m', 'localknowledge.db.create_baseline_db', '--schema', str(schema_path), '--dotenv', str(test_env_path)]
    logger.info(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("Baseline creation completed successfully")
        logger.info(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Baseline creation failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test baseline database creation')
    parser.add_argument('--keep-db', action='store_true', help='Keep the test database after the test')
    args = parser.parse_args()

    # Get connection parameters
    connection_params = get_connection_params()

    try:
        # Create test database
        create_test_database(connection_params)

        # Run baseline creation
        success = run_baseline_creation(connection_params)

        # Drop test database if not keeping it
        if not args.keep_db:
            drop_test_database(connection_params)
        else:
            logger.info(f"Keeping test database '{TEST_DB_NAME}' as requested")

        return 0 if success else 1
    except Exception as e:
        logger.error(f"Error: {e}")
        # Make sure to drop the test database in case of error
        if not args.keep_db:
            drop_test_database(connection_params)
        return 1

if __name__ == "__main__":
    sys.exit(main())
