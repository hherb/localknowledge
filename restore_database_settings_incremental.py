#!/usr/bin/env python3
"""
Script to restore database settings and recreate indices incrementally.

This script:
1. Restores pre-migration PostgreSQL settings
2. Recreates indices that were dropped during migration, one at a time
"""

import os
import sys
import logging
import psycopg2
import argparse
import time
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


def restore_postgresql_settings(dotenv_path=None, dry_run=False):
    """
    Restore PostgreSQL settings.
    
    Args:
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
    conn = psycopg2.connect(**connection_params)
    conn.autocommit = True  # Use autocommit for settings
    
    cursor = conn.cursor()
    
    try:
        logger.info("Restoring PostgreSQL settings")
        
        # Reset work_mem to default (4MB)
        if not dry_run:
            cursor.execute("SET work_mem TO DEFAULT")
            logger.info("Reset work_mem to default")
        else:
            logger.info("Would reset work_mem to default")
        
        # Reset maintenance_work_mem to default (64MB)
        if not dry_run:
            cursor.execute("SET maintenance_work_mem TO DEFAULT")
            logger.info("Reset maintenance_work_mem to default")
        else:
            logger.info("Would reset maintenance_work_mem to default")
        
        return True
    except Exception as e:
        logger.error(f"Error restoring PostgreSQL settings: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def create_index(index_query, dotenv_path=None, dry_run=False):
    """
    Create a single index.
    
    Args:
        index_query: SQL query to create the index
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    conn = psycopg2.connect(**connection_params)
    conn.autocommit = True  # Use autocommit for index creation
    
    cursor = conn.cursor()
    
    try:
        if not dry_run:
            start_time = time.time()
            cursor.execute(index_query)
            end_time = time.time()
            logger.info(f"Created index: {index_query} (took {end_time - start_time:.2f} seconds)")
        else:
            logger.info(f"Would create index: {index_query}")
        
        return True
    except Exception as e:
        logger.error(f"Error creating index: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def analyze_table(table_name, dotenv_path=None, dry_run=False):
    """
    Analyze a table to update statistics.
    
    Args:
        table_name: Name of the table to analyze
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
    """
    # Get connection parameters
    connection_params = get_connection_params(dotenv_path)
    
    # Connect to the database
    conn = psycopg2.connect(**connection_params)
    conn.autocommit = True  # Use autocommit for analyze
    
    cursor = conn.cursor()
    
    try:
        if not dry_run:
            start_time = time.time()
            cursor.execute(f"ANALYZE {table_name}")
            end_time = time.time()
            logger.info(f"Analyzed table: {table_name} (took {end_time - start_time:.2f} seconds)")
        else:
            logger.info(f"Would analyze table: {table_name}")
        
        return True
    except Exception as e:
        logger.error(f"Error analyzing table: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def restore_database_settings_incremental(dotenv_path=None, dry_run=False):
    """
    Restore database settings and recreate indices incrementally.
    
    Args:
        dotenv_path: Path to the .env file
        dry_run: If True, don't make any changes, just print what would be done
    """
    # Step 1: Restore PostgreSQL settings
    if not restore_postgresql_settings(dotenv_path, dry_run):
        return False
    
    # Step 2: Recreate indices
    logger.info("Recreating indices")
    
    # Define indices to recreate
    indices = [
        # Document table indices
        "CREATE INDEX IF NOT EXISTS idx_document_external_id ON document(external_id)",
        "CREATE INDEX IF NOT EXISTS idx_document_doi ON document(doi)",
        "CREATE INDEX IF NOT EXISTS idx_document_title ON document USING gin(to_tsvector('english', title))",
        "CREATE INDEX IF NOT EXISTS idx_document_abstract ON document USING gin(to_tsvector('english', abstract))",
        "CREATE INDEX IF NOT EXISTS idx_document_keywords ON document USING gin(keywords)",
        "CREATE INDEX IF NOT EXISTS idx_document_publication_date ON document(publication_date)",
        
        # Reading records indices
        "CREATE INDEX IF NOT EXISTS idx_reading_records_document_id ON reading_records(document_id)",
        "CREATE INDEX IF NOT EXISTS idx_reading_records_user_id ON reading_records(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_reading_records_timestamp ON reading_records(read_timestamp)",
        
        # Summaries indices
        "CREATE INDEX IF NOT EXISTS idx_summaries_document_id ON summaries(document_id)",
        
        # Embedding indices
        "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_document_id ON unified_multiembeddings(document_id)",
        "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_embed_source_id ON unified_multiembeddings(embed_source_id)",
        "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_model_name ON unified_multiembeddings(model_name)",
        "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_created_at ON unified_multiembeddings(created_at)",
        
        # Vector indices
        "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_vector ON unified_multiembeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    ]
    
    # Create each index in a separate transaction
    for index_query in indices:
        if not create_index(index_query, dotenv_path, dry_run):
            logger.warning(f"Failed to create index: {index_query}")
    
    # Step 3: Analyze tables to update statistics
    tables = [
        "document",
        "reading_records",
        "summaries",
        "unified_multiembeddings",
        "embedding_source"
    ]
    
    for table in tables:
        if not analyze_table(table, dotenv_path, dry_run):
            logger.warning(f"Failed to analyze table: {table}")
    
    logger.info("Database settings restored and indices recreated successfully")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Restore database settings and recreate indices incrementally')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    args = parser.parse_args()
    
    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')
    
    try:
        if restore_database_settings_incremental(dotenv_path=dotenv_path, dry_run=args.dry_run):
            logger.info("Database settings restored successfully")
            return 0
        else:
            logger.error("Failed to restore database settings")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
