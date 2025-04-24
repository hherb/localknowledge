#!/usr/bin/env python3
"""
Script to run the all_keywords migration directly.
This script bypasses the migrations system entirely to avoid any timeouts.
"""

import logging
import sys
from localknowledge.migrations.002_add_all_keywords_column import migrate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def progress_callback(current, total, message):
    """
    Handle progress updates.
    
    Args:
        current: Current progress value
        total: Total progress value
        message: Progress message
    """
    print(f"Progress: {current}/{total} - {message}")

def main():
    """Run the migration directly."""
    print("\n" + "="*80)
    print("Running all_keywords migration directly")
    print("="*80)
    
    try:
        # Run the migration with a progress callback
        migrate(None, progress_callback)
        print("\nMigration completed successfully!")
    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
