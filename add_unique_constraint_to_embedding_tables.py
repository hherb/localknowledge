#!/usr/bin/env python3
"""
Add unique constraint to embedding tables.

This script adds a unique constraint on (chunk_id, model_id) to all existing embedding tables.
This enables more efficient upsert operations using ON CONFLICT.
"""

import argparse
import logging
import sys
import time
import os
import psycopg2
from psycopg2.extras import DictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get a database connection using environment variables."""
    dbname = os.environ.get('POSTGRES_DB')
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    if not dbname:
        # Try to load from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
            dbname = os.environ.get('POSTGRES_DB')
        except ImportError:
            pass

    if not dbname:
        raise ValueError("POSTGRES_DB environment variable must be set")

    return psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )


def get_embedding_tables(conn) -> list:
    """Get all embedding tables that inherit from embedding_base.

    Args:
        conn: Database connection

    Returns:
        List of embedding table names
    """
    query = """
    SELECT c.relname as table_name
    FROM pg_inherits i
    JOIN pg_class c ON i.inhrelid = c.oid
    JOIN pg_class p ON i.inhparent = p.oid
    WHERE p.relname = 'embedding_base'
    AND c.relname LIKE 'emb_%'
    """

    with conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        return [row['table_name'] for row in result] if result else []


def add_unique_constraint(conn, table_name: str, dry_run: bool = False) -> bool:
    """Add unique constraint to an embedding table.

    Args:
        conn: Database connection
        table_name: Name of the table
        dry_run: If True, don't actually modify the database

    Returns:
        True if successful, False otherwise
    """
    constraint_name = f"{table_name}_chunk_model_unique"

    # Check if constraint already exists
    check_query = """
    SELECT COUNT(*) as count
    FROM pg_constraint
    WHERE conname = %s
    """

    with conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(check_query, (constraint_name,))
        result = cursor.fetchone()
        if result and result['count'] > 0:
            logger.info(f"Constraint {constraint_name} already exists on table {table_name}")
            return True

    # Check for duplicate rows that would violate the constraint
    check_duplicates_query = f"""
    SELECT chunk_id, model_id, COUNT(*) as count
    FROM {table_name}
    GROUP BY chunk_id, model_id
    HAVING COUNT(*) > 1
    """

    with conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(check_duplicates_query)
        duplicates = cursor.fetchall()
        if duplicates:
            logger.warning(f"Found {len(duplicates)} duplicate entries in {table_name} that would violate the constraint")
            for dup in duplicates:
                logger.warning(f"  chunk_id={dup['chunk_id']}, model_id={dup['model_id']}, count={dup['count']}")

            if not dry_run:
                # Remove duplicates, keeping the most recent one
                for dup in duplicates:
                    chunk_id = dup['chunk_id']
                    model_id = dup['model_id']

                    # Get all IDs for this combination
                    get_ids_query = f"""
                    SELECT id
                    FROM {table_name}
                    WHERE chunk_id = %s AND model_id = %s
                    ORDER BY id DESC
                    """

                    cursor.execute(get_ids_query, (chunk_id, model_id))
                    ids = cursor.fetchall()
                    if ids and len(ids) > 1:
                        # Keep the first one (highest ID), delete the rest
                        keep_id = ids[0]['id']
                        delete_ids = [row['id'] for row in ids[1:]]

                        delete_query = f"""
                        DELETE FROM {table_name}
                        WHERE id IN ({','.join(['%s'] * len(delete_ids))})
                        """

                        logger.info(f"Removing {len(delete_ids)} duplicates for chunk_id={chunk_id}, model_id={model_id}, keeping id={keep_id}")
                        cursor.execute(delete_query, tuple(delete_ids))
                        conn.commit()

    if dry_run:
        logger.info(f"DRY RUN: Would add constraint {constraint_name} to table {table_name}")
        return True

    # Add the constraint
    try:
        add_constraint_query = f"""
        ALTER TABLE {table_name}
        ADD CONSTRAINT {constraint_name} UNIQUE (chunk_id, model_id)
        """

        with conn.cursor() as cursor:
            cursor.execute(add_constraint_query)
            conn.commit()
            logger.info(f"Added constraint {constraint_name} to table {table_name}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding constraint to {table_name}: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Add unique constraint to embedding tables.')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without modifying the database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information')
    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    try:
        # Get database connection
        conn = get_db_connection()

        # Get all embedding tables
        tables = get_embedding_tables(conn)
        logger.info(f"Found {len(tables)} embedding tables: {', '.join(tables)}")

        if not tables:
            logger.info("No embedding tables found")
            return

        # Add unique constraint to each table
        success_count = 0
        for table in tables:
            if add_unique_constraint(conn, table, args.dry_run):
                success_count += 1

        logger.info(f"Successfully added unique constraint to {success_count}/{len(tables)} tables")

        if args.dry_run:
            logger.info("Dry run completed. No changes were made to the database.")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        # Close the connection
        if 'conn' in locals() and conn:
            conn.close()


if __name__ == "__main__":
    main()
