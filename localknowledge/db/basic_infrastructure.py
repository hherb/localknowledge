"""
Basic database infrastructure module for the LocalKnowledge library.

This module provides functionality to check and ensure that the basic database
infrastructure is in place, including:
- Database connection
- Required PostgreSQL extensions
- Database version

It performs these checks only once at startup and provides clear error messages
when infrastructure requirements are not met.
"""

import os
import logging
import psycopg2
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track whether environment variables have been loaded
_env_loaded = False
_env_file_path = None


class DatabaseInfrastructureError(Exception):
    """Base exception for database infrastructure errors."""
    pass


class DatabaseConnectionError(DatabaseInfrastructureError):
    """Exception raised when database connection fails."""
    pass


class DatabaseExtensionError(DatabaseInfrastructureError):
    """Exception raised when required database extensions are missing."""
    pass


class DatabaseVersionError(DatabaseInfrastructureError):
    """Exception raised when database version is incorrect."""
    pass


def load_environment(dotenv_path: Optional[str] = None, override: bool = True) -> str:
    """
    Load environment variables from .env file.

    This is the central function for loading environment variables in the application.
    All other modules should use this function instead of directly using dotenv.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'
        override: Whether to override existing environment variables

    Returns:
        str: Path to the loaded .env file
    """
    global _env_loaded, _env_file_path

    # If environment variables have already been loaded and we're not forcing an override,
    # return the path to the previously loaded .env file
    if _env_loaded and not override and _env_file_path:
        logger.debug(f"Environment variables already loaded from {_env_file_path}")
        return _env_file_path

    # Determine the .env file path
    if dotenv_path is None:
        # Check if DOTENV_FILE environment variable is set
        dotenv_path = os.environ.get('DOTENV_FILE')

        # If not, default to '.env'
        if dotenv_path is None:
            dotenv_path = '.env'

    # Check if the .env file exists
    if not os.path.exists(dotenv_path):
        logger.warning(f"Environment file {dotenv_path} not found")
        if dotenv_path != '.env' and os.path.exists('.env'):
            logger.info(f"Falling back to default .env file")
            dotenv_path = '.env'

    # Load environment variables
    if os.path.exists(dotenv_path):
        logger.info(f"Loading environment variables from {dotenv_path}")
        load_dotenv(dotenv_path, override=override)
        _env_loaded = True
        _env_file_path = dotenv_path
    else:
        logger.warning(f"No environment file found. Using existing environment variables.")

    return dotenv_path


@lru_cache(maxsize=1)
def get_db_connection_params(dotenv_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get database connection parameters from environment variables.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        Dict[str, Any]: Dictionary of connection parameters

    Raises:
        DatabaseConnectionError: If required environment variables are missing
    """
    # Load environment variables if needed
    if dotenv_path is not None:
        load_environment(dotenv_path=dotenv_path)
    elif not _env_loaded:
        load_environment()

    dbname = os.environ.get('POSTGRES_DB')
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    if not dbname:
        raise DatabaseConnectionError("POSTGRES_DB environment variable must be set")

    return {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }


@lru_cache(maxsize=1)
def check_database_connection(dotenv_path: Optional[str] = None) -> bool:
    """
    Check if the database connection is working.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        bool: True if connection is successful

    Raises:
        DatabaseConnectionError: If connection fails
    """
    connection_params = get_db_connection_params(dotenv_path=dotenv_path)

    try:
        # Try to connect to the database
        connection = psycopg2.connect(**connection_params)
        connection.close()
        logger.info(f"Successfully connected to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
        return True
    except psycopg2.Error as e:
        error_message = f"Failed to connect to PostgreSQL database: {e}"
        logger.error(error_message)
        raise DatabaseConnectionError(error_message)


@lru_cache(maxsize=1)
def check_required_extensions(dotenv_path: Optional[str] = None) -> bool:
    """
    Check if required PostgreSQL extensions are installed.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        bool: True if all required extensions are installed

    Raises:
        DatabaseExtensionError: If any required extension is missing
    """
    connection_params = get_db_connection_params(dotenv_path=dotenv_path)

    # List of required extensions
    required_extensions = ['vector']

    try:
        # Connect to the database
        connection = psycopg2.connect(**connection_params)
        cursor = connection.cursor()

        # Check each required extension
        missing_extensions = []
        for extension in required_extensions:
            cursor.execute(f"SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = '{extension}')")
            exists = cursor.fetchone()[0]
            if not exists:
                missing_extensions.append(extension)

        cursor.close()
        connection.close()

        if missing_extensions:
            error_message = f"Required PostgreSQL extensions are missing: {', '.join(missing_extensions)}"
            logger.error(error_message)
            raise DatabaseExtensionError(error_message)

        logger.info(f"All required PostgreSQL extensions are installed: {', '.join(required_extensions)}")
        return True
    except psycopg2.Error as e:
        error_message = f"Error checking PostgreSQL extensions: {e}"
        logger.error(error_message)
        raise DatabaseExtensionError(error_message)


@lru_cache(maxsize=1)
def check_database_version(dotenv_path: Optional[str] = None) -> Tuple[bool, int]:
    """
    Check the database version.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        Tuple[bool, int]: (is_initialized, current_version)

    Raises:
        DatabaseVersionError: If version check fails
    """
    connection_params = get_db_connection_params(dotenv_path=dotenv_path)

    try:
        # Connect to the database
        connection = psycopg2.connect(**connection_params)
        cursor = connection.cursor()

        # Check if version table exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'version'
        )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            cursor.close()
            connection.close()
            logger.warning("Database version table does not exist. Database may not be initialized.")
            return False, 0

        # Get current version
        cursor.execute("""
        SELECT MAX(version) as current_version
        FROM version
        WHERE migration_success = TRUE
        """)
        result = cursor.fetchone()
        current_version = result[0] if result[0] is not None else 0

        cursor.close()
        connection.close()

        logger.info(f"Current database version: {current_version}")
        return True, current_version
    except psycopg2.Error as e:
        error_message = f"Error checking database version: {e}"
        logger.error(error_message)
        raise DatabaseVersionError(error_message)


def check_database_infrastructure(dotenv_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Check all database infrastructure requirements.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        # Load environment variables if needed
        if dotenv_path is not None:
            load_environment(dotenv_path=dotenv_path)
        elif not _env_loaded:
            load_environment()

        # Check database connection
        check_database_connection(dotenv_path=dotenv_path)

        # Check required extensions
        check_required_extensions(dotenv_path=dotenv_path)

        # Check database version
        is_initialized, current_version = check_database_version(dotenv_path=dotenv_path)

        if not is_initialized:
            logger.warning("Database is not initialized. Run create_baseline_db.py to initialize it.")
            return False, "Database is not initialized. Run create_baseline_db.py to initialize it."

        return True, None
    except DatabaseInfrastructureError as e:
        return False, str(e)


def ensure_database_infrastructure(dotenv_path: Optional[str] = None) -> None:
    """
    Ensure all database infrastructure requirements are met.

    Args:
        dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'

    Raises:
        DatabaseInfrastructureError: If any infrastructure requirement is not met
    """
    is_valid, error_message = check_database_infrastructure(dotenv_path=dotenv_path)

    if not is_valid:
        raise DatabaseInfrastructureError(error_message)
