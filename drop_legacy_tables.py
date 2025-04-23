#!/usr/bin/env python3
"""
Script to drop legacy tables that are no longer needed.

This script drops the following legacy tables:
- preprints
- pubmed_articles
- embeddings
- qaembeddings

These tables have been replaced by the unified document structure.
"""

import os
import sys
import logging
import psycopg2
import argparse
from typing import Dict, Any, List

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


def check_table_references(cursor, table_name: str) -> List[Dict[str, str]]:
    """
    Check if a table is referenced by any foreign keys.
    
    Args:
        cursor: Database cursor
        table_name: Name of the table to check
        
    Returns:
        List of dictionaries with referencing table and constraint information
    """
    # Query to find all foreign keys that reference this table
    query = """
    SELECT
        tc.table_name AS referencing_table,
        tc.constraint_name AS constraint_name,
        kcu.column_name AS referencing_column,
        ccu.column_name AS referenced_column
    FROM
        information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = %s
    """
    
    cursor.execute(query, (table_name,))
    references = []
    
    for row in cursor.fetchall():
        references.append({
            'referencing_table': row[0],
            'constraint_name': row[1],
            'referencing_column': row[2],
            'referenced_column': row[3]
        })
    
    return references


def drop_legacy_tables(dotenv_path=None, dry_run=False, force=False):
    """
    Drop legacy tables that are no longer needed.
    
    Args:
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
        force: If True, drop tables even if they are referenced by other tables
    """
    # Legacy tables to drop
    legacy_tables = [
        'preprints',
        'pubmed_articles',
        'embeddings',
        'qaembeddings'
    ]
    
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
        # Check if each table exists and if it's referenced by other tables
        for table_name in legacy_tables:
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
                logger.info(f"Table {table_name} does not exist, skipping")
                continue
            
            # Check if table is referenced by other tables
            references = check_table_references(cursor, table_name)
            
            if references:
                logger.warning(f"Table {table_name} is referenced by other tables:")
                for ref in references:
                    logger.warning(f"  {ref['referencing_table']}.{ref['referencing_column']} -> {table_name}.{ref['referenced_column']} (constraint: {ref['constraint_name']})")
                
                if force:
                    logger.warning(f"Forcing drop of table {table_name} with CASCADE")
                    if not dry_run:
                        cursor.execute(f"DROP TABLE {table_name} CASCADE")
                        logger.info(f"Dropped table {table_name} CASCADE")
                    else:
                        logger.info(f"Would drop table {table_name} CASCADE")
                else:
                    logger.error(f"Cannot drop table {table_name} because it is referenced by other tables. Use --force to drop with CASCADE.")
                    continue
            else:
                # No references, safe to drop
                if not dry_run:
                    cursor.execute(f"DROP TABLE {table_name}")
                    logger.info(f"Dropped table {table_name}")
                else:
                    logger.info(f"Would drop table {table_name}")
        
        # Commit the transaction if not a dry run
        if not dry_run:
            conn.commit()
            logger.info("All specified legacy tables dropped successfully")
        else:
            logger.info("Dry run completed successfully")
        
        return True
    except Exception as e:
        # Rollback the transaction on error
        if not dry_run:
            conn.rollback()
        logger.error(f"Error dropping legacy tables: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Drop legacy tables that are no longer needed')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    parser.add_argument('--force', action='store_true', help='Force drop tables even if they are referenced by other tables')
    args = parser.parse_args()
    
    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')
    
    try:
        if drop_legacy_tables(dotenv_path=dotenv_path, dry_run=args.dry_run, force=args.force):
            logger.info("Legacy tables dropped successfully")
            return 0
        else:
            logger.error("Failed to drop legacy tables")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
