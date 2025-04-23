#!/usr/bin/env python3
"""
Script to run pending database migrations.

This script checks for pending migrations and runs them in sequence.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.migrations_system import MigrationsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run pending migrations."""
    parser = argparse.ArgumentParser(description='Run pending database migrations')
    parser.add_argument('--gui', action='store_true', help='Use GUI progress bar')
    parser.add_argument('--check', action='store_true', help='Check for pending migrations without running them')
    args = parser.parse_args()
    
    # Create a migrations manager
    migrations_manager = MigrationsManager()
    
    # Get current version
    current_version = migrations_manager.get_current_version()
    print(f"Current database version: {current_version}")
    
    # Get pending migrations
    pending_migrations = migrations_manager.get_pending_migrations()
    
    if not pending_migrations:
        print("No pending migrations")
        return 0
    
    print(f"Found {len(pending_migrations)} pending migrations:")
    for version, path in pending_migrations:
        print(f"  {version}: {path.name}")
    
    if args.check:
        # Just checking, don't run migrations
        return 0
    
    # Confirm before running migrations
    if not args.gui:  # Only prompt if not using GUI
        confirm = input("Run these migrations? [y/N] ")
        if confirm.lower() != 'y':
            print("Migrations cancelled")
            return 0
    
    # Run migrations
    success = migrations_manager.run_pending_migrations(use_gui_tqdm=args.gui)
    
    if success:
        new_version = migrations_manager.get_current_version()
        print(f"Migrations completed successfully. New database version: {new_version}")
        return 0
    else:
        print("Migration process failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
