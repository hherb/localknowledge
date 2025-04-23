#!/usr/bin/env python3
"""
Script to compare the tables in the test database with the tables in the production database.

This script connects to both the test and production databases, retrieves the list of tables,
and compares them to ensure that the test database structure matches the production database.
"""

import os
import sys
import logging
import psycopg2
from typing import Dict, List, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the basic_infrastructure module if available
try:
    from localknowledge.db.basic_infrastructure import load_environment
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv


def get_db_connection_params(dotenv_path: str = None) -> Dict[str, str]:
    """
    Get database connection parameters from environment variables.

    Args:
        dotenv_path: Path to the .env file

    Returns:
        Dict[str, str]: Dictionary of connection parameters
    """
    # Load environment variables
    if BASIC_INFRASTRUCTURE_AVAILABLE:
        load_environment(dotenv_path=dotenv_path)
    elif dotenv_path and os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        load_dotenv()

    # Get database connection parameters
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


def get_tables(connection_params: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Get the list of tables in a database.

    Args:
        connection_params: Database connection parameters

    Returns:
        List[Dict[str, str]]: List of tables with their details
    """
    try:
        # Connect to the database
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()

        # Get the list of tables
        query = """
        SELECT
            table_name,
            table_schema
        FROM
            information_schema.tables
        WHERE
            table_schema = 'public'
            AND table_type = 'BASE TABLE'
        ORDER BY
            table_name
        """
        cursor.execute(query)

        # Convert to list of dictionaries
        tables = []
        for row in cursor.fetchall():
            tables.append({
                'table_name': row[0],
                'table_schema': row[1]
            })

        cursor.close()
        conn.close()

        return tables
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
        return []


def get_table_columns(connection_params: Dict[str, str], table_name: str) -> List[Dict[str, str]]:
    """
    Get the columns of a table.

    Args:
        connection_params: Database connection parameters
        table_name: Name of the table

    Returns:
        List[Dict[str, str]]: List of columns with their details
    """
    try:
        # Connect to the database
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()

        # Get the columns of the table
        query = """
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable
        FROM
            information_schema.columns
        WHERE
            table_schema = 'public'
            AND table_name = %s
        ORDER BY
            ordinal_position
        """
        cursor.execute(query, (table_name,))

        # Convert to list of dictionaries
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'column_name': row[0],
                'data_type': row[1],
                'character_maximum_length': row[2],
                'is_nullable': row[3]
            })

        cursor.close()
        conn.close()

        return columns
    except Exception as e:
        logger.error(f"Error getting columns for table {table_name}: {e}")
        return []


def compare_databases(prod_params: Dict[str, str], test_params: Dict[str, str]) -> Tuple[bool, List[str]]:
    """
    Compare the tables in the production and test databases.

    Args:
        prod_params: Production database connection parameters
        test_params: Test database connection parameters

    Returns:
        Tuple[bool, List[str]]: (is_match, differences)
    """
    # Get the tables in both databases
    prod_tables = get_tables(prod_params)
    test_tables = get_tables(test_params)

    # Get the table names as sets for comparison
    prod_table_names = {table['table_name'] for table in prod_tables}
    test_table_names = {table['table_name'] for table in test_tables}

    # Find tables that are in production but not in test
    missing_tables = prod_table_names - test_table_names

    # Find tables that are in test but not in production
    extra_tables = test_table_names - prod_table_names

    # Find tables that are in both databases
    common_tables = prod_table_names.intersection(test_table_names)

    # Compare the columns of common tables
    column_differences = []
    for table_name in common_tables:
        prod_columns = get_table_columns(prod_params, table_name)
        test_columns = get_table_columns(test_params, table_name)

        # Compare columns
        if prod_columns != test_columns:
            # Find the differences
            prod_column_names = {col['column_name'] for col in prod_columns}
            test_column_names = {col['column_name'] for col in test_columns}

            # Find columns that are in production but not in test
            missing_columns = prod_column_names - test_column_names

            # Find columns that are in test but not in production
            extra_columns = test_column_names - prod_column_names

            # Find columns that have different definitions
            common_column_names = prod_column_names.intersection(test_column_names)
            different_columns = []

            for col_name in common_column_names:
                prod_col = next(col for col in prod_columns if col['column_name'] == col_name)
                test_col = next(col for col in test_columns if col['column_name'] == col_name)

                if prod_col != test_col:
                    different_columns.append(col_name)

            column_differences.append({
                'table_name': table_name,
                'missing_columns': missing_columns,
                'extra_columns': extra_columns,
                'different_columns': different_columns
            })

    # Compile the differences
    differences = []

    if missing_tables:
        differences.append(f"Tables in production but not in test: {', '.join(missing_tables)}")

    if extra_tables:
        differences.append(f"Tables in test but not in production: {', '.join(extra_tables)}")

    for diff in column_differences:
        table_name = diff['table_name']

        if diff['missing_columns']:
            differences.append(f"Table {table_name} is missing columns: {', '.join(diff['missing_columns'])}")

        if diff['extra_columns']:
            differences.append(f"Table {table_name} has extra columns: {', '.join(diff['extra_columns'])}")

        if diff['different_columns']:
            differences.append(f"Table {table_name} has different column definitions: {', '.join(diff['different_columns'])}")

    # Determine if the databases match
    is_match = not (missing_tables or extra_tables or column_differences)

    return is_match, differences


def main():
    """Main function."""
    # Load production database parameters
    logger.info("Loading production database parameters")
    prod_params = get_db_connection_params()

    # Create test database parameters
    logger.info("Creating test database parameters")
    test_params = prod_params.copy()
    test_params['dbname'] = 'test_rwb'

    # Print database names
    logger.info(f"Production database: {prod_params['dbname']}")
    logger.info(f"Test database: {test_params['dbname']}")

    # Compare the databases
    logger.info("Comparing databases")
    is_match, differences = compare_databases(prod_params, test_params)

    if is_match:
        logger.info("The databases match!")
        return 0
    else:
        logger.warning("The databases do not match")
        logger.warning("Differences:")
        for diff in differences:
            logger.warning(f"  {diff}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
