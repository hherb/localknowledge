#!/usr/bin/env python3
"""
Run all tests for the embeddings module.
"""

import unittest
import sys
import os
import argparse

# Add the parent directory to the path so we can import the localknowledge package
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the test modules
from localknowledge.embeddings.tests.test_embedding_manager import TestEmbeddingManager
from localknowledge.embeddings.tests.test_embedding_database import TestEmbeddingDatabaseManager
from localknowledge.embeddings.tests.test_embedding_integration import TestEmbeddingIntegration


def run_tests(include_integration=False):
    """Run all tests for the embeddings module.

    Args:
        include_integration: Whether to include integration tests that make actual Ollama calls

    Returns:
        Test result object
    """
    # Create a test suite
    test_suite = unittest.TestSuite()

    # Add the test cases
    loader = unittest.TestLoader()
    test_suite.addTest(loader.loadTestsFromTestCase(TestEmbeddingManager))
    test_suite.addTest(loader.loadTestsFromTestCase(TestEmbeddingDatabaseManager))

    # Add integration tests if requested
    if include_integration:
        test_suite.addTest(loader.loadTestsFromTestCase(TestEmbeddingIntegration))

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Return the result
    return result


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run tests for the embeddings module')
    parser.add_argument('--integration', action='store_true', help='Include integration tests with actual Ollama calls')
    args = parser.parse_args()

    # Run the tests
    result = run_tests(include_integration=args.integration)
    sys.exit(not result.wasSuccessful())
