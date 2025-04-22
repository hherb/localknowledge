#!/usr/bin/env python3
"""
Script to monitor the progress of the document migration.

This script:
1. Periodically checks the document table count
2. Calculates the insertion rate
3. Estimates time to completion
4. Monitors system resources

Usage:
    python monitor_migration_progress.py --interval 60 --total 38000000
"""

import argparse
import logging
import sys
import os
import time
import psutil
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.db.base import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationMonitor(DatabaseManager):
    """Monitor the progress of the document migration."""

    def __init__(self, interval=60, total_records=38000000):
        """Initialize the monitor.

        Args:
            interval: Check interval in seconds
            total_records: Total number of records to migrate
        """
        super().__init__()
        self.interval = interval
        self.total_records = total_records

    def get_document_count(self):
        """Get the current count of documents in the document table."""
        query = "SELECT COUNT(*) as count FROM document"
        result = self.execute(query)
        return result[0]['count'] if result else 0

    def get_system_stats(self):
        """Get system resource statistics."""
        stats = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_io': psutil.disk_io_counters(),
            'disk_usage': psutil.disk_usage('/').percent
        }
        return stats

    def monitor(self):
        """Monitor migration progress."""
        logger.info(f"Starting migration monitor (interval: {self.interval}s, total records: {self.total_records:,})")

        prev_count = 0
        prev_time = time.time()
        start_time = time.time()

        try:
            while True:
                # Get current document count
                current_count = self.get_document_count()
                current_time = time.time()

                # Calculate statistics
                elapsed_total = current_time - start_time
                elapsed_interval = current_time - prev_time

                if prev_count > 0 and elapsed_interval > 0:
                    # Records inserted in this interval
                    interval_records = current_count - prev_count

                    # Calculate rates
                    overall_rate = current_count / (elapsed_total / 60)  # Records per minute
                    interval_rate = interval_records / (elapsed_interval / 60)  # Records per minute

                    # Estimate completion
                    remaining_records = self.total_records - current_count
                    eta_minutes = 0
                    eta_str = "Unknown"

                    if interval_rate > 0 and remaining_records > 0:
                        eta_minutes = remaining_records / interval_rate
                        eta_time = datetime.now() + timedelta(minutes=eta_minutes)
                        eta_str = eta_time.strftime('%Y-%m-%d %H:%M:%S')

                    # Get system stats
                    stats = self.get_system_stats()

                    # Print progress
                    print("\n" + "=" * 80)
                    print(f"MIGRATION PROGRESS REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("=" * 80)
                    print(f"Documents migrated:    {current_count:,} / {self.total_records:,} ({current_count/self.total_records*100:.2f}% or {current_count/38616116*100:.2f}% of total)")
                    print(f"Elapsed time:          {timedelta(seconds=int(elapsed_total))}")
                    print(f"Overall rate:          {overall_rate:.1f} records/minute")
                    print(f"Current rate:          {interval_rate:.1f} records/minute")

                    if remaining_records > 0:
                        print(f"ETA:                   {eta_str} (in {timedelta(minutes=int(eta_minutes))})")
                    else:
                        print(f"ETA:                   Preprints completed, now migrating PubMed articles")

                    print("-" * 80)
                    print(f"CPU usage:             {stats['cpu_percent']:.1f}%")
                    print(f"Memory usage:          {stats['memory_percent']:.1f}%")
                    print(f"Disk usage:            {stats['disk_usage']:.1f}%")
                    print(f"Disk reads:            {stats['disk_io'].read_count:,}")
                    print(f"Disk writes:           {stats['disk_io'].write_count:,}")
                    print("=" * 80)
                else:
                    print(f"Initial count: {current_count:,} documents")

                # Update previous values
                prev_count = current_count
                prev_time = current_time

                # Sleep until next check
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.close()


def main():
    """Run the monitor."""
    parser = argparse.ArgumentParser(description='Monitor document migration progress')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds (default: 60)')
    parser.add_argument('--total', type=int, default=38000000, help='Total number of records to migrate (default: 38,000,000)')
    args = parser.parse_args()

    monitor = MigrationMonitor(interval=args.interval, total_records=args.total)
    monitor.monitor()

    return 0


if __name__ == "__main__":
    sys.exit(main())
