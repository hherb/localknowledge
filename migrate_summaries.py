#!/usr/bin/env python3
"""
Script to migrate summaries table to use document_id foreign key.

This script adds a document_id column to the summaries table and
populates it by matching records based on publication_id.
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


def migrate_summaries(dotenv_path=None, dry_run=False):
    """
    Migrate summaries table to use document_id foreign key.

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
        # Step 1: Check if summaries table exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'summaries'
        )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            logger.error("summaries table does not exist")
            return False

        # Step 2: Check if document_id column already exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'summaries'
            AND column_name = 'document_id'
        )
        """)
        column_exists = cursor.fetchone()[0]

        # Step 3: Add document_id column if it doesn't exist
        if not column_exists:
            logger.info("Adding document_id column to summaries table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE summaries
                ADD COLUMN document_id INTEGER REFERENCES document(id) ON DELETE CASCADE
                """)
        else:
            logger.info("document_id column already exists in summaries table")

        # Step 4: Create an index on the new column
        if not dry_run:
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summaries_document_id
            ON summaries(document_id)
            """)

        # Step 5: Get source ID for medrxiv
        cursor.execute("SELECT id FROM sources WHERE name = 'medrxiv'")
        result = cursor.fetchone()

        if not result:
            logger.warning("medrxiv source not found in sources table")
            return False

        medrxiv_source_id = result[0]

        # Step 6: Count records that need updating
        if column_exists:
            cursor.execute("""
            SELECT COUNT(*) FROM summaries WHERE document_id IS NULL
            """)
            records_to_update = cursor.fetchone()[0]
            logger.info(f"Found {records_to_update} summaries that need updating")
        else:
            # If column doesn't exist yet, all records need updating
            cursor.execute("SELECT COUNT(*) FROM summaries")
            records_to_update = cursor.fetchone()[0]
            logger.info(f"Found {records_to_update} summaries that need updating (all records)")

        if records_to_update > 0:
            # Step 7: Update summaries records
            if column_exists:
                update_query = """
                UPDATE summaries s
                SET document_id = d.id
                FROM document d
                WHERE s.publication_id = d.external_id
                  AND d.source_id = %s
                  AND s.document_id IS NULL
                """
            else:
                update_query = """
                UPDATE summaries s
                SET document_id = d.id
                FROM document d
                WHERE s.publication_id = d.external_id
                  AND d.source_id = %s
                """

            if not dry_run:
                cursor.execute(update_query, (medrxiv_source_id,))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} summaries")
            else:
                logger.info(f"Would update summaries")

        # Step 8: Check for unmatched records
        if column_exists or not dry_run:  # Only check if column exists or we've created it
            cursor.execute("""
            SELECT COUNT(*) FROM summaries WHERE document_id IS NULL
            """)
            unmatched_count = cursor.fetchone()[0]
            logger.info(f"Unmatched summaries after migration: {unmatched_count}")

            if unmatched_count > 0:
                # Get sample of unmatched records
                cursor.execute("""
                SELECT publication_id
                FROM summaries
                WHERE document_id IS NULL
                LIMIT 10
                """)
                unmatched_samples = cursor.fetchall()

                logger.warning("Sample of unmatched records:")
                for sample in unmatched_samples:
                    logger.warning(f"publication_id: {sample[0]}")

                # Check if these publication_ids exist in the preprints table
                for sample in unmatched_samples:
                    cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM preprints WHERE doi = %s
                    )
                    """, (sample[0],))
                    exists_in_preprints = cursor.fetchone()[0]

                    cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM document WHERE external_id = %s AND source_id = %s
                    )
                    """, (sample[0], medrxiv_source_id))
                    exists_in_document = cursor.fetchone()[0]

                    logger.warning(f"publication_id: {sample[0]}, exists in preprints: {exists_in_preprints}, exists in document: {exists_in_document}")

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
        logger.error(f"Error migrating summaries: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Migrate summaries table to use document_id foreign key')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    args = parser.parse_args()

    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')

    try:
        if migrate_summaries(dotenv_path=dotenv_path, dry_run=args.dry_run):
            logger.info("Summaries migration completed successfully")
            return 0
        else:
            logger.error("Failed to migrate summaries")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
