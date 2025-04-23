#!/usr/bin/env python3
"""
Script to fix the summaries table schema.

This script:
1. Ensures all summaries have a valid document_id
2. Drops the foreign key constraint on publication_id
3. Drops the publication_id column
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


def fix_summaries_table(dotenv_path=None, dry_run=False):
    """
    Fix the summaries table schema.

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

        # Step 2: Check if document_id column exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'summaries'
            AND column_name = 'document_id'
        )
        """)
        document_id_exists = cursor.fetchone()[0]

        if not document_id_exists:
            logger.error("document_id column does not exist in summaries table")
            return False

        # Step 3: Check if all summaries have a valid document_id
        cursor.execute("""
        SELECT COUNT(*) FROM summaries WHERE document_id IS NULL
        """)
        null_document_ids = cursor.fetchone()[0]

        if null_document_ids > 0:
            logger.warning(f"Found {null_document_ids} summaries with NULL document_id")

            # Get sample of records with NULL document_id
            cursor.execute("""
            SELECT id, publication_id FROM summaries WHERE document_id IS NULL LIMIT 5
            """)
            null_samples = cursor.fetchall()

            logger.warning("Sample of summaries with NULL document_id:")
            for sample in null_samples:
                logger.warning(f"id: {sample[0]}, publication_id: {sample[1]}")

            # Try to fix these records
            if not dry_run:
                cursor.execute("""
                UPDATE summaries s
                SET document_id = d.id
                FROM document d
                JOIN preprints p ON p.doi = d.external_id
                WHERE s.publication_id = p.doi
                AND s.document_id IS NULL
                """)

                fixed_count = cursor.rowcount
                logger.info(f"Fixed {fixed_count} summaries with NULL document_id")

                # Check if any still have NULL document_id
                cursor.execute("""
                SELECT COUNT(*) FROM summaries WHERE document_id IS NULL
                """)
                remaining_null = cursor.fetchone()[0]

                if remaining_null > 0:
                    logger.warning(f"Still have {remaining_null} summaries with NULL document_id")
                    logger.warning("These records will be deleted if you proceed")

                    # Delete records with NULL document_id
                    cursor.execute("""
                    DELETE FROM summaries WHERE document_id IS NULL
                    """)

                    deleted_count = cursor.rowcount
                    logger.info(f"Deleted {deleted_count} summaries with NULL document_id")
            else:
                logger.info("Would try to fix summaries with NULL document_id")

        # Step 4: Get the foreign key constraint name for publication_id
        cursor.execute("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = 'summaries'
          AND kcu.column_name = 'publication_id'
        """)

        constraint_result = cursor.fetchone()

        if constraint_result:
            constraint_name = constraint_result[0]
            logger.info(f"Found foreign key constraint on publication_id: {constraint_name}")

            # Step 5: Drop the foreign key constraint
            if not dry_run:
                cursor.execute(f"""
                ALTER TABLE summaries
                DROP CONSTRAINT {constraint_name}
                """)
                logger.info(f"Dropped foreign key constraint: {constraint_name}")
            else:
                logger.info(f"Would drop foreign key constraint: {constraint_name}")
        else:
            logger.info("No foreign key constraint found on publication_id")

        # Step 6: Drop the publication_id column
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'summaries'
            AND column_name = 'publication_id'
        )
        """)
        publication_id_exists = cursor.fetchone()[0]

        if publication_id_exists:
            logger.info("Dropping publication_id column from summaries table")
            if not dry_run:
                cursor.execute("""
                ALTER TABLE summaries
                DROP COLUMN publication_id
                """)
            else:
                logger.info("Would drop publication_id column from summaries table")
        else:
            logger.info("publication_id column does not exist in summaries table")

        # Step 7: Make document_id NOT NULL
        if not dry_run:
            cursor.execute("""
            ALTER TABLE summaries
            ALTER COLUMN document_id SET NOT NULL
            """)
            logger.info("Set document_id column to NOT NULL")
        else:
            logger.info("Would set document_id column to NOT NULL")

        # Step 8: Add a unique constraint on (document_id, user_id) if user_id exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'summaries'
            AND column_name = 'user_id'
        )
        """)
        user_id_exists = cursor.fetchone()[0]

        if user_id_exists:
            if not dry_run:
                cursor.execute("""
                ALTER TABLE summaries
                ADD CONSTRAINT summaries_document_user_unique UNIQUE (document_id, user_id)
                """)
                logger.info("Added unique constraint on (document_id, user_id)")
            else:
                logger.info("Would add unique constraint on (document_id, user_id)")

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
        logger.error(f"Error fixing summaries table: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Fix summaries table schema')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t make any changes, just print what would be done')
    args = parser.parse_args()

    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')

    try:
        if fix_summaries_table(dotenv_path=dotenv_path, dry_run=args.dry_run):
            logger.info("Summaries table schema fix completed successfully")
            return 0
        else:
            logger.error("Failed to fix summaries table schema")
            return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
