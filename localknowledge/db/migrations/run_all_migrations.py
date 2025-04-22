#!/usr/bin/env python3
"""
Script to run all migrations in the correct order.

This script will:
1. Create the new document tables
2. Migrate data from the existing tables to the new document table
3. Update embeddings references to point to the new document structure
4. Update QA embeddings references to point to the new document structure

IMPORTANT: This script should be run with caution on a production database.
Always backup your database before running migrations.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('all_migrations.log')
    ]
)
logger = logging.getLogger(__name__)


def run_migration(script_name: str, execute: bool, batch_size: int) -> bool:
    """Run a migration script.
    
    Args:
        script_name: Name of the migration script
        execute: Whether to execute the migration or run in dry-run mode
        batch_size: Batch size for processing
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Running migration: {script_name}")
    
    # Get the path to the script
    script_path = Path(__file__).resolve().parent / script_name
    
    # Build the command
    cmd = [sys.executable, str(script_path)]
    if execute:
        cmd.append('--execute')
    cmd.extend(['--batch-size', str(batch_size)])
    
    # Run the script
    try:
        logger.info(f"Executing command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Migration {script_name} completed successfully")
        logger.info(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration {script_name} failed with exit code {e.returncode}")
        logger.error(f"Output: {e.stdout}")
        logger.error(f"Error: {e.stderr}")
        return False


def main():
    """Run all migrations in the correct order."""
    parser = argparse.ArgumentParser(description='Run all migrations in the correct order')
    parser.add_argument('--execute', action='store_true', help='Execute the migrations (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    args = parser.parse_args()

    execute = args.execute
    batch_size = args.batch_size

    if not execute:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migrations.")

    # List of migrations to run in order
    migrations = [
        'migrate_to_unified_document.py',
        'update_embeddings_references.py',
        'update_qaembeddings_references.py'
    ]

    # Run each migration
    start_time = time.time()
    success = True
    
    for migration in migrations:
        if not run_migration(migration, execute, batch_size):
            logger.error(f"Migration {migration} failed. Stopping.")
            success = False
            break
        
        # Add a small delay between migrations
        time.sleep(1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    if success:
        logger.info(f"All migrations completed successfully in {duration:.2f} seconds")
    else:
        logger.error(f"Migrations failed after {duration:.2f} seconds")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
