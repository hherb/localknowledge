#!/usr/bin/env python3
"""
Script to examine the structure of database tables.

This script connects to the database and examines the structure of tables
to help understand how to migrate data.
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


def examine_table(table_name, dotenv_path=None):
    """
    Examine the structure of a table.
    
    Args:
        table_name: Name of the table to examine
        dotenv_path: Path to the .env file
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
    conn = psycopg2.connect(**connection_params)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
        """, (table_name,))
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error(f"Table {table_name} does not exist")
            return False
        
        # Get table columns
        cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        logger.info(f"Table {table_name} has {len(columns)} columns:")
        for column in columns:
            logger.info(f"  {column[0]}: {column[1]}, nullable: {column[2]}")
        
        # Get primary key
        cursor.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (table_name,))
        
        primary_key = cursor.fetchall()
        
        if primary_key:
            logger.info(f"Primary key: {', '.join([pk[0] for pk in primary_key])}")
        else:
            logger.info("No primary key defined")
        
        # Get foreign keys
        cursor.execute("""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
        """, (table_name,))
        
        foreign_keys = cursor.fetchall()
        
        if foreign_keys:
            logger.info("Foreign keys:")
            for fk in foreign_keys:
                logger.info(f"  {fk[0]} references {fk[1]}.{fk[2]}")
        else:
            logger.info("No foreign keys defined")
        
        # Get sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        sample_data = cursor.fetchall()
        
        if sample_data:
            logger.info("Sample data:")
            for i, row in enumerate(sample_data):
                logger.info(f"  Row {i+1}: {row}")
        else:
            logger.info("No data in table")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        logger.info(f"Total rows: {row_count}")
        
        return True
    except Exception as e:
        logger.error(f"Error examining table {table_name}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def examine_reading_records_content_ids(dotenv_path=None):
    """
    Examine the content_id values in the reading_records table.
    
    Args:
        dotenv_path: Path to the .env file
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
    conn = psycopg2.connect(**connection_params)
    cursor = conn.cursor()
    
    try:
        # Get distinct source_types
        cursor.execute("""
        SELECT DISTINCT source_type FROM reading_records
        """)
        
        source_types = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Distinct source_types: {source_types}")
        
        # For each source_type, get sample content_ids
        for source_type in source_types:
            cursor.execute("""
            SELECT content_id FROM reading_records WHERE source_type = %s LIMIT 10
            """, (source_type,))
            
            content_ids = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Sample content_ids for source_type '{source_type}': {content_ids}")
            
            # If content_ids are numeric, try to find what they reference
            if all(content_id.isdigit() for content_id in content_ids):
                logger.info(f"All content_ids for source_type '{source_type}' are numeric")
                
                # Check if they reference preprints.doi
                if source_type == 'medrxiv':
                    # Get a sample content_id
                    sample_id = content_ids[0]
                    
                    # Check if it's a row number in preprints
                    cursor.execute("""
                    SELECT doi FROM preprints OFFSET %s LIMIT 1
                    """, (int(sample_id) - 1,))  # OFFSET is 0-based, so subtract 1
                    
                    result = cursor.fetchone()
                    
                    if result:
                        logger.info(f"content_id {sample_id} might reference row number in preprints, corresponding to doi: {result[0]}")
                        
                        # Check if this DOI exists in document table
                        cursor.execute("""
                        SELECT id FROM document WHERE external_id = %s
                        """, (result[0],))
                        
                        doc_result = cursor.fetchone()
                        
                        if doc_result:
                            logger.info(f"DOI {result[0]} exists in document table with id: {doc_result[0]}")
                        else:
                            logger.info(f"DOI {result[0]} does not exist in document table")
        
        return True
    except Exception as e:
        logger.error(f"Error examining reading_records content_ids: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Examine database tables')
    parser.add_argument('--table', help='Name of the table to examine')
    parser.add_argument('--reading-records', action='store_true', help='Examine reading_records content_ids')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    args = parser.parse_args()
    
    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')
    
    try:
        if args.table:
            if examine_table(args.table, dotenv_path=dotenv_path):
                logger.info(f"Successfully examined table {args.table}")
                return 0
            else:
                logger.error(f"Failed to examine table {args.table}")
                return 1
        elif args.reading_records:
            if examine_reading_records_content_ids(dotenv_path=dotenv_path):
                logger.info("Successfully examined reading_records content_ids")
                return 0
            else:
                logger.error("Failed to examine reading_records content_ids")
                return 1
        else:
            logger.error("No action specified. Use --table or --reading-records")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
