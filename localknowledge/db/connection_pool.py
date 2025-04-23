"""
Connection pool for database connections in the LocalKnowledge library.

This module provides a connection pool for database connections using psycopg2's
connection pool implementation. It also provides a context manager for database
connections.
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor

# Configure logging
logger = logging.getLogger(__name__)

# Global connection pool
_pool = None


def get_connection_params(dotenv_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get database connection parameters from environment variables.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        Dictionary of connection parameters
    """
    try:
        # Try to use the centralized environment loading
        from localknowledge.db.basic_infrastructure import get_db_connection_params
        return get_db_connection_params(dotenv_path=dotenv_path)
    except ImportError:
        # Fallback to direct environment variable access
        dbname = os.environ.get('POSTGRES_DB')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')

        if not dbname:
            raise ValueError("POSTGRES_DB environment variable must be set")

        return {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }


def initialize_pool(min_connections: int = 1, max_connections: int = 10, dotenv_path: Optional[str] = None) -> None:
    """
    Initialize the connection pool.

    Args:
        min_connections: Minimum number of connections in the pool
        max_connections: Maximum number of connections in the pool
        dotenv_path: Path to the .env file
    """
    global _pool
    if _pool is not None:
        logger.warning("Connection pool already initialized")
        return

    connection_params = get_connection_params(dotenv_path)
    try:
        _pool = ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            **connection_params
        )
        logger.info(f"Connection pool initialized with {min_connections}-{max_connections} connections")
    except psycopg2.Error as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise ConnectionError(f"Failed to initialize connection pool: {e}")


def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Connection pool closed")


@contextmanager
def get_connection():
    """
    Get a connection from the pool.

    Yields:
        A database connection from the pool

    Raises:
        ConnectionError: If the pool is not initialized or a connection cannot be obtained
    """
    global _pool
    if _pool is None:
        initialize_pool()

    conn = None
    try:
        conn = _pool.getconn()
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Error getting connection from pool: {e}")
        raise ConnectionError(f"Error getting connection from pool: {e}")
    finally:
        if conn is not None:
            _pool.putconn(conn)


@contextmanager
def get_cursor(commit: bool = False):
    """
    Get a cursor from a pooled connection.

    Args:
        commit: Whether to commit the transaction when the cursor is closed

    Yields:
        A database cursor

    Raises:
        ConnectionError: If the pool is not initialized or a connection cannot be obtained
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
