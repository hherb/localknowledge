"""
Base database functionality for the LocalKnowledge library.

This module provides a base class for database connections and operations
that can be extended for different data sources.
"""
import os
import logging
import psycopg2
from psycopg2.extras import DictCursor
from typing import List, Dict, Any, Optional, Tuple, Union
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import infrastructure check functions
try:
    from localknowledge.db.basic_infrastructure import (
        check_database_infrastructure,
        DatabaseInfrastructureError,
        get_db_connection_params
    )
    INFRASTRUCTURE_CHECK_AVAILABLE = True
except ImportError:
    logger.warning("Basic infrastructure module not available. Skipping infrastructure checks.")
    INFRASTRUCTURE_CHECK_AVAILABLE = False

# Track whether infrastructure has been checked
_infrastructure_checked = False

# Debug counter for infrastructure checks
_check_counter = 0


class DatabaseManager:
    """Base class for database operations."""

    def __init__(self, check_infrastructure: bool = True, dotenv_path: Optional[str] = None):
        """
        Initialize the database manager.

        Uses environment variables for connection parameters:
        - POSTGRES_DB: Database name
        - POSTGRES_USER: Database user
        - POSTGRES_PASSWORD: Database password
        - POSTGRES_HOST: Database host
        - POSTGRES_PORT: Database port

        Args:
            check_infrastructure: Whether to check database infrastructure on initialization
            dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'
        """
        self.connection = None
        self.dotenv_path = dotenv_path

        # Check infrastructure if requested and not already checked
        global _infrastructure_checked
        if check_infrastructure and INFRASTRUCTURE_CHECK_AVAILABLE and not _infrastructure_checked:
            self._check_infrastructure()
            _infrastructure_checked = True

        self.connect()

    def connect(self):
        """Connect to the database using environment variables."""
        try:
            # Get database connection parameters using the basic_infrastructure module
            if INFRASTRUCTURE_CHECK_AVAILABLE:
                # Use the centralized environment loading
                connection_params = get_db_connection_params(dotenv_path=self.dotenv_path)

                self.connection = psycopg2.connect(**connection_params)
            else:
                # Fallback to direct environment variable access if basic_infrastructure is not available
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
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL database: {e}")

    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit the transaction

        Returns:
            Query results as a list of dictionaries, or None for non-SELECT queries
        """
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor(cursor_factory=DictCursor)
        try:
            # Log the query and parameters for debugging
            logger.debug(f"Executing SQL: {query}")
            logger.debug(f"With parameters: {params}")

            cursor.execute(query, params or ())

            if commit:
                self.connection.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Query affected {cursor.rowcount} rows")
                if cursor.description and query.strip().upper().startswith(('INSERT', 'UPDATE')) and 'RETURNING' in query.upper():
                    # This is an INSERT or UPDATE query with RETURNING clause
                    result = [dict(row) for row in cursor.fetchall()]
                    logger.debug(f"Query returned: {result}")
                    return result
                return None

            if cursor.description:  # This is a SELECT query
                result = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Query returned {len(result)} rows")
                return result
            return None

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"SQL Error: {e}")
            raise e
        finally:
            cursor.close()

    def execute_many(self, query: str, params_list: List[Tuple], commit: bool = True) -> None:
        """
        Execute a SQL query with multiple parameter sets.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            commit: Whether to commit the transaction
        """
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.executemany(query, params_list)
            if commit:
                self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def _check_infrastructure(self) -> None:
        """
        Check database infrastructure.

        Raises:
            DatabaseInfrastructureError: If infrastructure check fails
        """
        global _check_counter
        _check_counter += 1

        logger.info(f"Checking database infrastructure (check #{_check_counter})")
        is_valid, error_message = check_database_infrastructure(dotenv_path=self.dotenv_path)

        if not is_valid:
            logger.error(f"Database infrastructure check failed: {error_message}")
            raise DatabaseInfrastructureError(error_message)

        logger.info(f"Database infrastructure check #{_check_counter} passed")

    def create_tables(self) -> None:
        """
        Create database tables if they do not exist.

        This method is deprecated. Tables should be created using create_baseline_db.py
        and updated using migrations.
        """
        logger.warning(
            "The create_tables() method is deprecated. "
            "Tables should be created using create_baseline_db.py and updated using migrations."
        )
        raise NotImplementedError(
            "Subclasses should not implement create_tables(). "
            "Use create_baseline_db.py and migrations instead."
        )

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        """Enable context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection when exiting context."""
        self.close()
