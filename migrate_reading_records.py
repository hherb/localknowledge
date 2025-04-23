#!/usr/bin/env python3
"""
Script to migrate reading_records table to use document_id foreign key.

This script adds a document_id column to the reading_records table and
populates it by matching records based on source_type and content_id.
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


def migrate_reading_records(dotenv_path=None, dry_run=False):
    """
    Migrate reading_records table to use document_id foreign key.

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
        column_exists = cursor.fetchone()[0]

        # Step 3: Add document_id column if it doesn't exist
        if not column_exists:
            logger.info("Adding document_id column to reading_records table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE reading_records
                ADD COLUMN document_id INTEGER REFERENCES document(id) ON DELETE CASCADE
                """)
        else:
            logger.info("document_id column already exists in reading_records table")

        # Step 4: Create an index on the new column
        if not dry_run:
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reading_records_document_id
            ON reading_records(document_id)
            """)

        # Step 5: Get source IDs for medrxiv and pubmed
        cursor.execute("SELECT id, name FROM sources WHERE name IN ('medrxiv', 'pubmed')")
        source_ids = {row[1]: row[0] for row in cursor.fetchall()}

        if 'medrxiv' not in source_ids:
            logger.warning("medrxiv source not found in sources table")
        if 'pubmed' not in source_ids:
            logger.warning("pubmed source not found in sources table")

        # Step 6: Count records that need updating
        if column_exists:
            cursor.execute("""
            SELECT COUNT(*) FROM reading_records WHERE document_id IS NULL
            """)
            records_to_update = cursor.fetchone()[0]
            logger.info(f"Found {records_to_update} reading records that need updating")
        else:
            # If column doesn't exist yet, all records need updating
            cursor.execute("SELECT COUNT(*) FROM reading_records")
            records_to_update = cursor.fetchone()[0]
            logger.info(f"Found {records_to_update} reading records that need updating (all records)")

        # Step 7: Update medrxiv records
        if 'medrxiv' in source_ids:
            medrxiv_source_id = source_ids['medrxiv']

            # Count medrxiv records that need updating
            if column_exists:
                cursor.execute("""
                SELECT COUNT(*)
                FROM reading_records
                WHERE source_type = 'medrxiv' AND document_id IS NULL
                """)
                medrxiv_records = cursor.fetchone()[0]
            else:
                cursor.execute("""
                SELECT COUNT(*)
                FROM reading_records
                WHERE source_type = 'medrxiv'
                """)
                medrxiv_records = cursor.fetchone()[0]

            logger.info(f"Found {medrxiv_records} medrxiv reading records that need updating")

            if medrxiv_records > 0:
                # Update medrxiv records
                update_query = """
                UPDATE reading_records rr
                SET document_id = d.id
                FROM document d
                WHERE rr.source_type = 'medrxiv'
                  AND rr.content_id = d.external_id
                  AND d.source_id = %s
                  AND rr.document_id IS NULL
                """

                if not dry_run:
                    cursor.execute(update_query, (medrxiv_source_id,))
                    updated_count = cursor.rowcount
                    logger.info(f"Updated {updated_count} medrxiv reading records")
                else:
                    logger.info(f"Would update medrxiv reading records")

        # Step 8: Update pubmed records
        if 'pubmed' in source_ids:
            pubmed_source_id = source_ids['pubmed']

            # Count pubmed records that need updating
            if column_exists:
                cursor.execute("""
                SELECT COUNT(*)
                FROM reading_records
                WHERE source_type = 'pubmed' AND document_id IS NULL
                """)
                pubmed_records = cursor.fetchone()[0]
            else:
                cursor.execute("""
                SELECT COUNT(*)
                FROM reading_records
                WHERE source_type = 'pubmed'
                """)
                pubmed_records = cursor.fetchone()[0]

            logger.info(f"Found {pubmed_records} pubmed reading records that need updating")

            if pubmed_records > 0:
                # Update pubmed records
                update_query = """
                UPDATE reading_records rr
                SET document_id = d.id
                FROM document d
                WHERE rr.source_type = 'pubmed'
                  AND rr.content_id = d.external_id
                  AND d.source_id = %s
                  AND rr.document_id IS NULL
                """

                if not dry_run:
                    cursor.execute(update_query, (pubmed_source_id,))
                    updated_count = cursor.rowcount
                    logger.info(f"Updated {updated_count} pubmed reading records")
                else:
                    logger.info(f"Would update pubmed reading records")

        # Step 9: Check for unmatched records
        if column_exists or not dry_run:  # Only check if column exists or we've created it
            cursor.execute("""
            SELECT COUNT(*) FROM reading_records WHERE document_id IS NULL
            """)
            unmatched_count = cursor.fetchone()[0]
            logger.info(f"Unmatched reading records after migration: {unmatched_count}")

            if unmatched_count > 0:
                # Get sample of unmatched records
                cursor.execute("""
                SELECT source_type, content_id
                FROM reading_records
                WHERE document_id IS NULL
                LIMIT 10
                """)
                unmatched_samples = cursor.fetchall()

                logger.warning("Sample of unmatched records:")
                for sample in unmatched_samples:
                    logger.warning(f"source_type: {sample[0]}, content_id: {sample[1]}")

        # Commit the transaction if not a dry run
        if not dry_run:
            conn.commit()
            logger.info("Migration completed successfully")
        else:
            logger.info("Dry run completed successfully")

        return True
    except Exception as e:
        # Rollback the transaction on error
        if not dry_run:
            conn.rollback()
        logger.error(f"Error migrating reading_records: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Migrate reading_records table to use document_id foreign key')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    args = parser.parse_args()

    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')

    try:
        if migrate_reading_records(dotenv_path=dotenv_path, dry_run=args.dry_run):
            logger.info("Reading records migration completed successfully")
            return 0
        else:
            logger.error("Failed to migrate reading records")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
