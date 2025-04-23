#!/usr/bin/env python3
"""
Script to update the reading_records table schema.

This script:
1. Ensures the document_id column exists
2. Drops the old-style document identification columns (source_type and content_id)
"""

import os
import sys
import logging
import psycopg2
import argparse
from typing import Dict, Any

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


def get_connection_params(dotenv_path=None):
    """Get database connection parameters."""
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        # Load environment variables
        if dotenv_path:
            load_environment(dotenv_path=dotenv_path)
        else:
            load_environment()
        
        # Get connection parameters
        return get_db_connection_params(dotenv_path=dotenv_path)
    else:
        # Load environment variables
        if dotenv_path and os.path.exists(dotenv_path):
            from dotenv import load_dotenv
            load_dotenv(dotenv_path)
        else:
            from dotenv import load_dotenv
            load_dotenv()
        
        # Get connection parameters
        dbname = os.environ.get('POSTGRES_DB')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        
        return {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }


def update_reading_records_schema(dotenv_path=None, dry_run=False):
    """
    Update the reading_records table schema.
    
    Args:
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
    conn = psycopg2.connect(**connection_params)
    
    if not dry_run:
        # We'll handle transactions manually
        conn.autocommit = False
    else:
        logger.info("DRY RUN MODE: No changes will be made to the database")
    
    cursor = conn.cursor()
    
    try:
        # Step 1: Check if reading_records table exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'reading_records'
        )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error("reading_records table does not exist")
            return False
        
        # Step 2: Check if document_id column already exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'reading_records' 
            AND column_name = 'document_id'
        )
        """)
        document_id_exists = cursor.fetchone()[0]
        
        # Step 3: Add document_id column if it doesn't exist
        if not document_id_exists:
            logger.info("Adding document_id column to reading_records table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE reading_records 
                ADD COLUMN document_id INTEGER REFERENCES document(id) ON DELETE CASCADE
                """)
        else:
            logger.info("document_id column already exists in reading_records table")
        
        # Step 4: Create an index on the document_id column
        if not dry_run:
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reading_records_document_id 
            ON reading_records(document_id)
            """)
        
        # Step 5: Check if source_type column exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'reading_records' 
            AND column_name = 'source_type'
        )
        """)
        source_type_exists = cursor.fetchone()[0]
        
        # Step 6: Check if content_id column exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'reading_records' 
            AND column_name = 'content_id'
        )
        """)
        content_id_exists = cursor.fetchone()[0]
        
        # Step 7: Drop source_type column if it exists
        if source_type_exists:
            logger.info("Dropping source_type column from reading_records table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE reading_records 
                DROP COLUMN source_type
                """)
        else:
            logger.info("source_type column does not exist in reading_records table")
        
        # Step 8: Drop content_id column if it exists
        if content_id_exists:
            logger.info("Dropping content_id column from reading_records table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE reading_records 
                DROP COLUMN content_id
                """)
        else:
            logger.info("content_id column does not exist in reading_records table")
        
        # Commit the transaction if not a dry run
        if not dry_run:
            conn.commit()
            logger.info("Schema update completed successfully")
        else:
            logger.info("Dry run completed successfully")
        
        return True
    except Exception as e:
        # Rollback the transaction on error
        if not dry_run:
            conn.rollback()
        logger.error(f"Error updating reading_records schema: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Update reading_records table schema')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    args = parser.parse_args()
    
    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')
    
    try:
        if update_reading_records_schema(dotenv_path=dotenv_path, dry_run=args.dry_run):
            logger.info("Reading records schema update completed successfully")
            return 0
        else:
            logger.error("Failed to update reading records schema")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
