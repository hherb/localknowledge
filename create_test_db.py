#!/usr/bin/env python3
"""
Script to create a minimal test database.

This script creates a minimal test database with just the version table
for testing the migrations system.
"""

import os
import sys
import logging
import psycopg2
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test database settings
TEST_DB_NAME = "test_rwb"
TEST_ENV_FILE = ".env.test"


def create_minimal_test_db():
    """Create a minimal test database with just the version table."""
    # Load environment variables from .env.test
    if os.path.exists(TEST_ENV_FILE):
        logger.info(f"Using environment file: {TEST_ENV_FILE}")
        os.environ['DOTENV_FILE'] = TEST_ENV_FILE
    
    # Get database connection parameters
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')
    
    try:
        # Connect to the test database
        conn = psycopg2.connect(
            dbname=TEST_DB_NAME,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create version table
        logger.info("Creating version table")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS version (
            version INTEGER UNIQUE NOT NULL,
            migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            migration_success BOOLEAN NOT NULL
        )
        """)
        
        # Insert initial version record
        logger.info("Inserting initial version record")
        cursor.execute("""
        INSERT INTO version (version, migrated, migration_success)
        VALUES (1, %s, TRUE)
        ON CONFLICT (version) DO NOTHING
        """, (datetime.now(),))
        
        # Create a simple document table for testing
        logger.info("Creating document table")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document (
            id SERIAL PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            added_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create a simple embedding_source table
        logger.info("Creating embedding_source table")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS embedding_source (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Insert default embedding sources
        logger.info("Inserting default embedding sources")
        cursor.execute("""
        INSERT INTO embedding_source (name, description)
        VALUES 
            ('abstract', 'Document abstract'),
            ('full_text', 'Full document text'),
            ('chunk', 'Document text chunk'),
            ('qa_pair', 'Question-answer pair')
        ON CONFLICT (name) DO NOTHING
        """)
        
        # Create a simple unified_multiembeddings table
        logger.info("Creating unified_multiembeddings table")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS unified_multiembeddings (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            embed_source_id INTEGER REFERENCES embedding_source(id),
            chunk_no INTEGER,
            text TEXT NOT NULL,
            embedding vector(1024),
            model_name TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cursor.close()
        conn.close()
        
        logger.info("Minimal test database created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating minimal test database: {e}")
        return False


def main():
    """Main function."""
    try:
        if create_minimal_test_db():
            logger.info("Test database setup completed successfully")
            return 0
        else:
            logger.error("Failed to set up test database")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
