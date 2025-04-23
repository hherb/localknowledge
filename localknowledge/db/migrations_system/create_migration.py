#!/usr/bin/env python3
"""
Script to create a new migration file.

This script creates a new migration file with a template.
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
    """Create a new migration file."""
    parser = argparse.ArgumentParser(description='Create a new migration file')
    parser.add_argument('name', help='Name for the migration (will be used in filename)')
    args = parser.parse_args()
    
    # Create a migrations manager
    migrations_manager = MigrationsManager()
    
    # Create a migration file
    migration_path = migrations_manager.create_migration_template(args.name)
    
    print(f"Created migration file: {migration_path}")
    print(f"Edit this file to implement your migration logic.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
