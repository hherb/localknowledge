"""
Configuration module for the migrations system.

This module handles configuration for the migrations system, including
determining the directory for migration files.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


def get_migrations_dir() -> Path:
    """
    Get the directory for migration files.
    
    The directory is determined in the following order:
    1. From RWB_MIGRATION_DIR environment variable if set
    2. Default to ~/localknowledge/migrations if not set
    
    The directory will be created if it doesn't exist.
    
    Returns:
        Path: Path to the migrations directory
    """
    # Get migrations directory from environment variable or use default
    migrations_dir_str = os.environ.get('RWB_MIGRATION_DIR')
    
    if migrations_dir_str:
        migrations_dir = Path(migrations_dir_str).expanduser()
        logger.info(f"Using migrations directory from environment: {migrations_dir}")
    else:
        # Default to ~/localknowledge/migrations
        migrations_dir = Path.home() / "localknowledge" / "migrations"
        logger.info(f"Using default migrations directory: {migrations_dir}")
    
    # Create directory if it doesn't exist
    if not migrations_dir.exists():
        logger.info(f"Creating migrations directory: {migrations_dir}")
        migrations_dir.mkdir(parents=True, exist_ok=True)
    
    return migrations_dir
