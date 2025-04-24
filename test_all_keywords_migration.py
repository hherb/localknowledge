#!/usr/bin/env python3
"""
Test script for the all_keywords migration.
This script tests the migration in a dry run mode without actually applying it.
"""

import sys
import logging
from pathlib import Path
from typing import Callable, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from localknowledge.db.migrations_system.manager import MigrationsManager
from localknowledge.db.base import DatabaseManager

def progress_callback(current: int, total: int, message: str) -> None:
    """
    Handle progress updates.

    Args:
        current: Current progress value
        total: Total progress value
        message: Progress message
    """
    print(f"Progress: {current}/{total} - {message}")

def test_migration():
    """Test the migration in dry run mode."""
    print("\n" + "="*80)
    print("Testing migration 002_add_all_keywords_column.py")
    print("="*80)

    # Create a database manager for testing
    db_manager = DatabaseManager()

    # Check if the all_keywords column already exists
    result = db_manager.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'document' AND column_name = 'all_keywords';
    """)

    if result:
        print(f"Column all_keywords already exists in document table.")
    else:
        print(f"Column all_keywords does not exist in document table.")

    # Check if the trigger function already exists
    result = db_manager.execute("""
    SELECT proname
    FROM pg_proc
    WHERE proname = 'update_all_keywords_trigger';
    """)

    if result:
        print(f"Trigger function update_all_keywords_trigger already exists.")
    else:
        print(f"Trigger function update_all_keywords_trigger does not exist.")

    # Check if the trigger already exists
    result = db_manager.execute("""
    SELECT tgname
    FROM pg_trigger
    WHERE tgname = 'update_all_keywords_before_ins_upd';
    """)

    if result:
        print(f"Trigger update_all_keywords_before_ins_upd already exists.")
    else:
        print(f"Trigger update_all_keywords_before_ins_upd does not exist.")

    # Check if the GIN index already exists
    result = db_manager.execute("""
    SELECT indexname
    FROM pg_indexes
    WHERE indexname = 'idx_document_all_keywords_gin';
    """)

    if result:
        print(f"GIN index idx_document_all_keywords_gin already exists.")
    else:
        print(f"GIN index idx_document_all_keywords_gin does not exist.")

    # Check the current database version
    migrations_manager = MigrationsManager(progress_callback=progress_callback)
    current_version = migrations_manager.get_current_version()
    print(f"Current database version: {current_version}")

    # Check for pending migrations
    pending_migrations = migrations_manager.get_pending_migrations()
    if pending_migrations:
        print(f"Pending migrations: {pending_migrations}")
    else:
        print("No pending migrations.")

    # Close the database connection
    db_manager.close()

def test_search_with_all_keywords():
    """Test searching with the all_keywords column."""
    print("\n" + "="*80)
    print("Testing search with all_keywords column")
    print("="*80)

    # Import the document database manager
    from localknowledge.db.document import DocumentDatabaseManager

    # Create a document database manager
    db_manager = DocumentDatabaseManager()

    # Test a simple search
    search_term = "covid"
    print(f"Searching for '{search_term}'...")

    results = db_manager.search_documents(
        search_text=search_term,
        limit=5
    )

    print(f"Found {len(results)} results")

    # Print the first few results
    if results:
        print("\nFirst few results:")
        for i, result in enumerate(results[:3]):
            print(f"\n--- Result {i+1} ---")
            print(f"Title: {result.get('title', 'No title')}")
            print(f"Source: {result.get('source_name', 'Unknown')}")
            print(f"DOI: {result.get('doi', 'No DOI')}")
            if 'all_keywords' in result:
                print(f"All Keywords: {result['all_keywords']}")
            if 'keywords' in result:
                print(f"Keywords: {result['keywords']}")
            if 'mesh_terms' in result:
                print(f"Mesh Terms: {result['mesh_terms']}")

    # Test a search with exclusion terms
    search_term = "covid"
    exclude_terms = ["children"]
    print(f"\nSearching for '{search_term}' excluding '{exclude_terms}'...")

    results = db_manager.search_documents(
        search_text=search_term,
        limit=5,
        exclude_terms=exclude_terms
    )

    print(f"Found {len(results)} results")

    # Close the database connection
    db_manager.close()

if __name__ == "__main__":
    test_migration()

    # Uncomment to test search after migration is applied
    # test_search_with_all_keywords()
