#!/usr/bin/env python3
"""
Run all tests for LocalKnowledge.

This script discovers and runs tests using pytest across the project.
Tests are organized in:
- tests/                  - Main integration tests
- localknowledge/*/tests/ - Module-specific tests

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run only unit tests (fast)
    python run_tests.py --integration      # Run integration tests
    python run_tests.py -k "pattern"       # Run tests matching pattern
    python run_tests.py -v                 # Verbose output
    python run_tests.py --coverage         # Run with coverage report
"""

import os
import sys
import argparse
import subprocess


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run LocalKnowledge tests')
    parser.add_argument('--unit', action='store_true',
                        help='Run only unit tests (module-specific tests)')
    parser.add_argument('--integration', action='store_true',
                        help='Run integration tests (tests/ directory)')
    parser.add_argument('-k', '--keyword', type=str, default=None,
                        help='Run tests matching keyword expression')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose test output')
    parser.add_argument('--coverage', action='store_true',
                        help='Run with coverage report')
    parser.add_argument('--env-file', type=str, default=None,
                        help='Environment file to use (default: .env.test if exists, else .env)')
    parser.add_argument('-x', '--exitfirst', action='store_true',
                        help='Exit on first failure')
    parser.add_argument('--markers', action='store_true',
                        help='Show available test markers')
    parser.add_argument('remaining', nargs='*',
                        help='Additional arguments to pass to pytest')
    args = parser.parse_args()

    # Set up environment file
    if args.env_file:
        env_file = args.env_file
    elif os.path.exists('.env.test'):
        env_file = '.env.test'
    elif os.path.exists('.env'):
        env_file = '.env'
    else:
        env_file = None

    if env_file:
        os.environ['DOTENV_FILE'] = env_file
        print(f"Using environment file: {env_file}")

    # Build pytest command
    pytest_args = ['python', '-m', 'pytest']

    # Determine test paths
    test_paths = []
    if args.unit:
        # Module-specific tests only
        test_paths.extend([
            'localknowledge/db/tests/',
            'localknowledge/embeddings/tests/',
            'localknowledge/ui/tests/',
            'localknowledge/ai/tests/',
            'localknowledge/textprocessing/chunking/tests/',
            'localknowledge/textprocessing/keywords/tests/',
            'localknowledge/medrxiv/tests/',
        ])
    elif args.integration:
        # Integration tests only
        test_paths.append('tests/')
    else:
        # All tests
        test_paths.extend([
            'tests/',
            'localknowledge/',
        ])

    # Filter to existing paths
    test_paths = [p for p in test_paths if os.path.exists(p)]
    if not test_paths:
        print("No test directories found!")
        return 1

    pytest_args.extend(test_paths)

    # Add pytest options
    if args.verbose:
        pytest_args.append('-v')
    else:
        pytest_args.append('-q')

    if args.keyword:
        pytest_args.extend(['-k', args.keyword])

    if args.exitfirst:
        pytest_args.append('-x')

    if args.coverage:
        pytest_args.extend([
            '--cov=localknowledge',
            '--cov-report=term-missing',
            '--cov-report=html:coverage_html'
        ])

    if args.markers:
        pytest_args.append('--markers')

    # Add any remaining arguments
    pytest_args.extend(args.remaining)

    # Print command
    print(f"Running: {' '.join(pytest_args)}")
    print("-" * 60)

    # Run pytest
    result = subprocess.run(pytest_args)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
