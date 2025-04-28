#!/usr/bin/env python3
"""
PubMedBERT Experiment

This module provides an experimental implementation for working with PubMedBERT embeddings
and PostgreSQL database. It's separate from the main codebase.
"""

import os
import logging
from typing import Optional, Dict, Any, ContextManager
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to environment file
ENV_FILE = ".env_embedtest"


def load_environment(env_file: str = ENV_FILE) -> Dict[str, Any]:
    """
    Load environment variables from the specified .env file.
    
    Args:
        env_file: Path to the .env file
        
    Returns:
        Dictionary of connection parameters
    """
    # Load environment variables
    load_dotenv(env_file)
    
    # Get database connection parameters
    dbname = os.environ.get('POSTGRES_DB')
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')
    
    if not dbname:
        raise ValueError(f"POSTGRES_DB environment variable must be set in {env_file}")
    
    logger.info(f"Loaded database configuration from {env_file}: {dbname}@{host}:{port}")
    
    return {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }


@contextmanager
def get_connection(connection_params: Optional[Dict[str, Any]] = None):
    """
    Get a database connection as a context manager.
    
    Args:
        connection_params: Optional dictionary of connection parameters.
                          If None, loads from environment.
    
    Yields:
        A database connection
    """
    if connection_params is None:
        connection_params = load_environment()
    
    conn = None
    try:
        conn = psycopg2.connect(**connection_params)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.debug("Database connection closed")


@contextmanager
def get_cursor(commit: bool = False, connection_params: Optional[Dict[str, Any]] = None):
    """
    Get a database cursor as a context manager.
    
    Args:
        commit: Whether to commit the transaction when the cursor is closed
        connection_params: Optional dictionary of connection parameters.
                          If None, loads from environment.
    
    Yields:
        A database cursor
    """
    with get_connection(connection_params) as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
                logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            cursor.close()


def test_connection():
    """Test the database connection and print version information."""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            logger.info(f"Successfully connected to PostgreSQL: {version}")
            return True
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting PubMedBERT experiment")
    
    # Test database connection
    if test_connection():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed")
        exit(1)
    
    # TODO: Add PubMedBERT implementation
    logger.info("PubMedBERT experiment setup complete")
