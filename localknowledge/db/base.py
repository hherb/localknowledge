"""
Base database functionality for the LocalKnowledge library.

This module provides a base class for database connections and operations
that can be extended for different data sources.
"""
import os
import logging
import psycopg2
from psycopg2.extras import DictCursor, Json
from psycopg2.extensions import register_adapter
from typing import List, Dict, Any, Optional, Tuple, Union
from functools import lru_cache
import time

# Register adapter for Python dict to PostgreSQL JSONB
register_adapter(dict, Json)

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
                dbname = os.environ.get('POSTGRES_DB','Postgres DB name not found in env')
                user = os.environ.get('POSTGRES_USER','Postgres user not found in env')
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

    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False, timeout: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query with a timeout.

        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit the transaction
            timeout: Query timeout in seconds (default: 30)

        Returns:
            Query results as a list of dictionaries, or None for non-SELECT queries
        """
        import threading
        import time

        # TODO: Consider refactoring to use a connection context manager for better
        # resource management and automatic cleanup. Current implementation handles
        # connection state manually but could benefit from structured cleanup.

        if not self.connection:
            self.connect()

        # Check if connection is closed and reconnect if needed
        if self.connection.closed:
            logger.warning("Database connection was closed. Reconnecting...")
            self.connect()

        # Set statement timeout to prevent queries from running too long
        with self.connection.cursor() as timeout_cursor:
            timeout_cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # Convert to milliseconds

        cursor = self.connection.cursor(cursor_factory=DictCursor)

        # Create a flag for timeout detection
        query_completed = threading.Event()
        query_error = [None]
        query_result = [None]

        def execute_query():
            try:
                # Log the query and parameters for debugging
                logger.debug(f"Executing SQL: {query}")
                logger.debug(f"With parameters: {params}")

                start_time = time.time()
                cursor.execute(query, params or ())
                execution_time = time.time() - start_time
                logger.debug(f"Query executed in {execution_time:.2f} seconds")

                if commit:
                    self.connection.commit()
                    if cursor.rowcount > 0:
                        logger.debug(f"Query affected {cursor.rowcount} rows")
                    if cursor.description and query.strip().upper().startswith(('INSERT', 'UPDATE')) and 'RETURNING' in query.upper():
                        # This is an INSERT or UPDATE query with RETURNING clause
                        result = [dict(row) for row in cursor.fetchall()]
                        logger.debug(f"Query returned: {result}")
                        query_result[0] = result
                    else:
                        query_result[0] = None
                elif cursor.description:  # This is a SELECT query
                    result = [dict(row) for row in cursor.fetchall()]
                    logger.debug(f"Query returned {len(result)} rows")
                    query_result[0] = result
                else:
                    query_result[0] = None

            except Exception as e:
                logger.error(f"SQL Error: {e}")
                query_error[0] = e
            finally:
                query_completed.set()

        try:
            # Execute the query in a separate thread
            query_thread = threading.Thread(target=execute_query)
            query_thread.daemon = True
            query_thread.start()

            # Wait for the query to complete or timeout
            if not query_completed.wait(timeout):
                logger.error(f"Query timed out after {timeout} seconds: {query}")
                # Try to cancel the query
                try:
                    self.connection.cancel()
                    logger.info("Query cancelled successfully")
                except Exception as cancel_error:
                    logger.error(f"Failed to cancel query: {cancel_error}")

                # Close and reopen the connection to ensure clean state
                try:
                    self.close()
                    self.connect()
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect after timeout: {reconnect_error}")

                raise TimeoutError(f"Query execution timed out after {timeout} seconds")

            # If there was an error in the query thread, raise it
            if query_error[0]:
                self.connection.rollback()
                raise query_error[0]

            return query_result[0]

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"SQL Error: {e}")
            raise e
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()

    def execute_many(self, query: str, params_list: List[Tuple], commit: bool = True, timeout: int = 60) -> None:
        """
        Execute a SQL query with multiple parameter sets and a timeout.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            commit: Whether to commit the transaction
            timeout: Query timeout in seconds (default: 60)
        """
        import threading
        import time

        # TODO: Consider refactoring to use a connection context manager for better
        # resource management and automatic cleanup.

        if not self.connection:
            self.connect()

        # Check if connection is closed and reconnect if needed
        if self.connection.closed:
            logger.warning("Database connection was closed. Reconnecting...")
            self.connect()

        # Set statement timeout to prevent queries from running too long
        with self.connection.cursor() as timeout_cursor:
            timeout_cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # Convert to milliseconds

        cursor = self.connection.cursor()

        # Create a flag for timeout detection
        query_completed = threading.Event()
        query_error = [None]

        def execute_query():
            try:
                # Log the query for debugging
                logger.debug(f"Executing SQL (multiple): {query}")
                logger.debug(f"With {len(params_list)} parameter sets")

                start_time = time.time()
                cursor.executemany(query, params_list)
                execution_time = time.time() - start_time
                logger.debug(f"Query executed in {execution_time:.2f} seconds")

                if commit:
                    self.connection.commit()
                    if cursor.rowcount > 0:
                        logger.debug(f"Query affected {cursor.rowcount} rows")

            except Exception as e:
                logger.error(f"SQL Error: {e}")
                query_error[0] = e
            finally:
                query_completed.set()

        try:
            # Execute the query in a separate thread
            query_thread = threading.Thread(target=execute_query)
            query_thread.daemon = True
            query_thread.start()

            # Wait for the query to complete or timeout
            if not query_completed.wait(timeout):
                logger.error(f"Query timed out after {timeout} seconds: {query}")
                # Try to cancel the query
                try:
                    self.connection.cancel()
                    logger.info("Query cancelled successfully")
                except Exception as cancel_error:
                    logger.error(f"Failed to cancel query: {cancel_error}")

                # Close and reopen the connection to ensure clean state
                try:
                    self.close()
                    self.connect()
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect after timeout: {reconnect_error}")

                raise TimeoutError(f"Query execution timed out after {timeout} seconds")

            # If there was an error in the query thread, raise it
            if query_error[0]:
                self.connection.rollback()
                raise query_error[0]

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"SQL Error: {e}")
            raise e
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()

    def _check_infrastructure(self) -> None:
        """
        Check database infrastructure. Use sparingly only once at boot-up time

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



    def execute_without_timeout(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query without any timeout.

        This method is specifically for long-running operations like migrations.
        It disables the statement timeout at the PostgreSQL level and doesn't use
        the threading-based timeout mechanism.

        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit the transaction

        Returns:
            Query results or None
        """

        # FIXME
        # TODO: implement with context manager (with connection/cursor ...)

        if not self.connection:
            self.connect()

        # Check if connection is closed and reconnect if needed
        if self.connection.closed:
            logger.warning("Database connection was closed. Reconnecting...")
            self.connect()

        # Disable statement timeout for this connection
        with self.connection.cursor() as timeout_cursor:
            timeout_cursor.execute("SET statement_timeout = 0;")  # 0 means no timeout
            self.connection.commit()

        cursor = self.connection.cursor(cursor_factory=DictCursor)

        try:
            # Log the query and parameters for debugging
            logger.debug(f"Executing SQL without timeout: {query}")
            logger.debug(f"With parameters: {params}")

            start_time = time.time()
            cursor.execute(query, params or ())
            execution_time = time.time() - start_time
            logger.debug(f"Query executed in {execution_time:.2f} seconds")

            if commit:
                self.connection.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Query affected {cursor.rowcount} rows")
                if cursor.description and query.strip().upper().startswith(('INSERT', 'UPDATE')) and 'RETURNING' in query.upper():
                    # This is an INSERT or UPDATE query with RETURNING clause
                    result = [dict(row) for row in cursor.fetchall()]
                    logger.debug(f"Query returned: {result}")
                    return result
                else:
                    return None
            elif cursor.description:  # This is a SELECT query
                result = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Query returned {len(result)} rows")
                return result
            else:
                return None

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"SQL Error: {e}")
            raise e
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()

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
