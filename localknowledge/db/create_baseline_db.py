#!/usr/bin/env python3
"""
Monolithic database initialization script for the LocalKnowledge library.

This script creates all database tables, indices, and extensions in a single
transaction. It should be run only once to initialize a new database. After
the initial setup, all schema changes should be done through migrations.

Usage:
    python -m localknowledge.db.create_baseline_db [--force] [--schema SCHEMA_FILE]

Options:
    --force    Force recreation of tables (WARNING: This will delete all data)
    --schema   Path to a SQL schema file to use for baseline creation (default: schema.sql)
"""

import os
import sys
import argparse
import logging
import psycopg2
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the basic_infrastructure module
try:
    from localknowledge.db.basic_infrastructure import load_environment, get_db_connection_params
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    logger.warning("Basic infrastructure module not available. Using direct environment access.")
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv


class BaselineDBCreator:
    """Class to create the baseline database schema using a SQL schema file."""

    def __init__(self, force: bool = False, dotenv_path: Optional[str] = None, schema_file: Optional[str] = None):
        """
        Initialize the baseline database creator.

        Args:
            force: Whether to force recreation of tables (WARNING: This will delete all data)
            dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'
            schema_file: Path to a SQL schema file to use for baseline creation
        """
        self.force = force
        self.dotenv_path = dotenv_path
        self.schema_file = schema_file or 'schema.sql'
        self.connection = None

        # Load environment variables
        if BASIC_INFRASTRUCTURE_AVAILABLE:
            load_environment(dotenv_path=self.dotenv_path)
        else:
            # Fallback to direct environment variable access
            dotenv_file = os.environ.get('DOTENV_FILE', '.env')
            if os.path.exists(dotenv_file):
                load_dotenv(dotenv_file)
            else:
                load_dotenv()

        self.connect()

    def connect(self) -> None:
        """Connect to the database using environment variables."""
        try:
            if BASIC_INFRASTRUCTURE_AVAILABLE:
                # Use the centralized environment loading
                connection_params = get_db_connection_params(dotenv_path=self.dotenv_path)

                self.connection = psycopg2.connect(**connection_params)
                logger.info(f"Connected to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
            else:
                # Fallback to direct environment variable access
                dbname = os.environ.get('POSTGRES_DB')
                user = os.environ.get('POSTGRES_USER', 'postgres')
                password = os.environ.get('POSTGRES_PASSWORD', '')
                host = os.environ.get('POSTGRES_HOST', 'localhost')
                port = os.environ.get('POSTGRES_PORT', '5432')

                if not dbname:
                    raise ValueError("POSTGRES_DB environment variable must be set")

                self.connection = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                logger.info(f"Connected to database {dbname} at {host}:{port}")
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL database: {e}")

    def execute(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Query results as a list of dictionaries, or None for non-SELECT queries
        """
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params or ())

            if cursor.description:  # This is a SELECT query
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return None

        except psycopg2.Error as e:
            logger.error(f"Error executing query: {e}")
            raise
        finally:
            cursor.close()

    def check_if_tables_exist(self) -> bool:
        """
        Check if any tables already exist in the database.

        Returns:
            bool: True if tables exist, False otherwise
        """
        query = """
        SELECT COUNT(*) as table_count
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
        result = self.execute(query)

        if result and result[0]['table_count'] > 0:
            return True
        return False



    def drop_all_tables(self) -> None:
        """Drop all tables in the database."""
        if not self.force:
            logger.error("Cannot drop tables without --force flag")
            return

        logger.warning("Dropping all tables in the database")

        # Get all tables
        query = """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        """
        result = self.execute(query)

        if not result:
            logger.info("No tables to drop")
            return

        # Drop all tables
        for row in result:
            table_name = row['tablename']
            logger.info(f"Dropping table {table_name}")
            self.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        logger.info("All tables dropped")

    def execute_sql_file(self, file_path: Union[str, Path]) -> None:
        """Execute SQL statements from a file.

        Args:
            file_path: Path to the SQL file

        Raises:
            FileNotFoundError: If the file does not exist
            psycopg2.Error: If there is an error executing the SQL
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        logger.info(f"Executing SQL from file: {file_path}")
        with open(file_path, 'r') as f:
            sql = f.read()

        # Execute the SQL
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            logger.info(f"Successfully executed SQL from file: {file_path}")
        except psycopg2.Error as e:
            logger.error(f"Error executing SQL from file {file_path}: {e}")
            raise
        finally:
            cursor.close()

    def create_baseline_database(self) -> None:
        """Create the baseline database schema using the schema.sql file."""
        # Check if tables already exist
        if self.check_if_tables_exist():
            if self.force:
                logger.warning("Tables already exist, but --force flag is set. Dropping all tables.")
                self.drop_all_tables()
            else:
                logger.error("Tables already exist. Use --force to drop and recreate them.")
                return

        # Set autocommit to True for the entire operation
        self.connection.autocommit = True

        try:
            # Execute the schema file
            schema_path = Path(self.schema_file)
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_path}")

            logger.info(f"Creating baseline database using schema file: {schema_path}")
            self.execute_sql_file(schema_path)

            # Insert initial version record if not already present
            query = """
            INSERT INTO version (version, migrated, migration_success)
            VALUES (1, CURRENT_TIMESTAMP, TRUE)
            ON CONFLICT (version) DO NOTHING
            """
            self.execute(query)

            logger.info("Baseline database created successfully")
        except Exception as e:
            logger.error(f"Error creating baseline database: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None


def main():
    """Main function to execute when run as a script."""
    parser = argparse.ArgumentParser(description='Create baseline database schema')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables (WARNING: This will delete all data)')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    parser.add_argument('--schema', help='Path to a SQL schema file to use for baseline creation')
    args = parser.parse_args()

    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')

    try:
        creator = BaselineDBCreator(force=args.force, dotenv_path=dotenv_path, schema_file=args.schema)
        creator.create_baseline_database()
        creator.close()
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
