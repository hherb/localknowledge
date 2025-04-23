#!/usr/bin/env python3
"""
Script to set up the pgvector extension in the test database.

This script connects to the test database and creates the pgvector extension,
which is required before creating tables that use the vector data type.
"""

import os
import sys
import logging
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the basic_infrastructure module if available
try:
    from localknowledge.db.basic_infrastructure import load_environment, get_db_connection_params
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv

# Test database settings
TEST_ENV_FILE = ".env.test"


def setup_pgvector():
    """Set up the pgvector extension in the test database."""
    # Load environment variables from .env.test
    if os.path.exists(TEST_ENV_FILE):
        logger.info(f"Using environment file: {TEST_ENV_FILE}")
        if BASIC_INFRASTRUCTURE_AVAILABLE:
            load_environment(dotenv_path=TEST_ENV_FILE)
        else:
            from dotenv import load_dotenv
            load_dotenv(TEST_ENV_FILE)
    
    # Get database connection parameters
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        connection_params = get_db_connection_params(dotenv_path=TEST_ENV_FILE)
    else:
        dbname = os.environ.get('POSTGRES_DB')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        
        connection_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
    
    try:
        # Connect to the database
        logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
        conn = psycopg2.connect(**connection_params)
        conn.autocommit = True  # Important: autocommit must be True for creating extensions
        cursor = conn.cursor()
        
        # Try to set role to postgres (superuser) if possible
        try:
            logger.info("Attempting to set role to postgres for creating extension")
            cursor.execute("SET ROLE postgres")
            logger.info("Successfully set role to postgres")
        except psycopg2.Error as e:
            logger.warning(f"Could not set role to postgres: {e}")
            logger.warning("Continuing without superuser privileges. Extension creation may fail.")
        
        # Create pgvector extension
        logger.info("Creating pgvector extension")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.info("pgvector extension created successfully")
        
        # Reset role if we were able to set it
        try:
            cursor.execute("RESET ROLE")
            logger.info("Reset role after creating extension")
        except psycopg2.Error as e:
            logger.warning(f"Could not reset role: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info("pgvector extension setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up pgvector extension: {e}")
        return False


def main():
    """Main function."""
    try:
        if setup_pgvector():
            logger.info("pgvector extension setup completed successfully")
            return 0
        else:
            logger.error("Failed to set up pgvector extension")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
