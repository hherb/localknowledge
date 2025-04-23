#!/usr/bin/env python3
"""
Run all database infrastructure tests.

This script runs all the database infrastructure tests in sequence.
It first sets up the test environment, then runs the tests.
"""

import os
import sys
import logging
import subprocess
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(command):
    """Run a command and return the exit code."""
    logger.info(f"Running command: {command}")

    # Create a copy of the current environment
    env = os.environ.copy()

    # Ensure DOTENV_FILE is set to the test environment file
    env['DOTENV_FILE'] = '.env.test'

    # Run the command with the modified environment
    process = subprocess.run(command, shell=True, env=env)
    return process.returncode


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run database infrastructure tests')
    parser.add_argument('--skip-env', action='store_true', help='Skip environment setup')
    parser.add_argument('--skip-infrastructure', action='store_true', help='Skip infrastructure test')
    parser.add_argument('--skip-basic', action='store_true', help='Skip basic infrastructure test')
    parser.add_argument('--skip-baseline', action='store_true', help='Skip baseline database test')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables in baseline test')
    parser.add_argument('--cleanup', action='store_true', help='Clean up test environment after tests')
    parser.add_argument('--cleanup-only', action='store_true', help='Only clean up test environment, don\'t run tests')
    args = parser.parse_args()

    # Clean up only
    if args.cleanup_only:
        logger.info("Cleaning up test environment")
        exit_code = run_command("python test_env.py --cleanup")
        if exit_code != 0:
            logger.error("Failed to clean up test environment")
            return exit_code
        logger.info("Test environment cleaned up successfully")
        return 0

    # Set up test environment
    if not args.skip_env:
        # Check if .env.test already exists
        if os.path.exists('.env.test'):
            logger.info("Test environment already set up. Skipping environment setup.")
            # Make sure the test database exists
            exit_code = run_command("python create_test_db.py")
            if exit_code != 0:
                logger.error("Failed to ensure test database exists")
                return exit_code
        else:
            logger.info("Setting up test environment")
            exit_code = run_command("python test_env.py")
            if exit_code != 0:
                logger.error("Failed to set up test environment")
                return exit_code

    # Set environment variable for test environment
    os.environ['DOTENV_FILE'] = '.env.test'

    try:
        # Run infrastructure test
        if not args.skip_infrastructure:
            logger.info("Running infrastructure test")
            exit_code = run_command("python test_infrastructure.py")
            if exit_code != 0:
                logger.error("Infrastructure test failed")
                return exit_code

        # Run basic infrastructure test
        if not args.skip_basic:
            logger.info("Running basic infrastructure test")
            exit_code = run_command("python test_basic_infrastructure.py")
            if exit_code != 0:
                logger.error("Basic infrastructure test failed")
                return exit_code

        # Run baseline database test
        if not args.skip_baseline:
            logger.info("Running baseline database test")
            command = "python test_baseline_db.py"
            if args.force:
                command += " --force"
            exit_code = run_command(command)
            if exit_code != 0:
                logger.error("Baseline database test failed")
                return exit_code

        logger.info("All tests completed successfully")
        return 0
    finally:
        # Clean up test environment if requested
        if args.cleanup:
            logger.info("Cleaning up test environment")
            exit_code = run_command("python test_env.py --cleanup")
            if exit_code != 0:
                logger.error("Failed to clean up test environment")
                return exit_code
            logger.info("Test environment cleaned up successfully")


if __name__ == "__main__":
    sys.exit(main())
