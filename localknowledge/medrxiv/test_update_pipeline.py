#!/usr/bin/env python3
"""
Test script for the medRxiv update pipeline.

This script provides basic tests to verify that the pipeline functions
can be imported and called without errors.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging for testing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all functions can be imported successfully."""
    try:
        from localknowledge.medrxiv.medrxiv_update_pipeline import (
            fetch_medrxiv_updates,
            fetch_missing_pdfs,
            fetch_missing_fulltext,
            update_document_database,
            create_embeddings,
            run_full_pipeline
        )
        logger.info("✓ All functions imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False

def test_function_signatures():
    """Test that functions have the expected signatures."""
    try:
        from localknowledge.medrxiv.medrxiv_update_pipeline import (
            fetch_medrxiv_updates,
            fetch_missing_pdfs,
            fetch_missing_fulltext,
            update_document_database,
            create_embeddings,
            run_full_pipeline
        )
        
        # Test that functions can be called with default parameters
        # Note: We're not actually calling them to avoid side effects
        
        # Check function signatures by inspecting their __annotations__
        import inspect
        
        # Test fetch_medrxiv_updates signature
        sig = inspect.signature(fetch_medrxiv_updates)
        assert 'download_pdfs' in sig.parameters
        assert 'max_retries' in sig.parameters
        logger.info("✓ fetch_medrxiv_updates signature is correct")
        
        # Test fetch_missing_pdfs signature
        sig = inspect.signature(fetch_missing_pdfs)
        assert 'max_retries' in sig.parameters
        assert 'limit' in sig.parameters
        logger.info("✓ fetch_missing_pdfs signature is correct")
        
        # Test fetch_missing_fulltext signature
        sig = inspect.signature(fetch_missing_fulltext)
        assert 'limit' in sig.parameters
        assert 'batch_size' in sig.parameters
        logger.info("✓ fetch_missing_fulltext signature is correct")
        
        # Test create_embeddings signature
        sig = inspect.signature(create_embeddings)
        assert 'limit' in sig.parameters
        assert 'model_name' in sig.parameters
        logger.info("✓ create_embeddings signature is correct")
        
        # Test run_full_pipeline signature
        sig = inspect.signature(run_full_pipeline)
        assert 'download_pdfs' in sig.parameters
        assert 'pdf_limit' in sig.parameters
        logger.info("✓ run_full_pipeline signature is correct")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Function signature test failed: {e}")
        return False

def test_docstrings():
    """Test that all functions have proper docstrings."""
    try:
        from localknowledge.medrxiv.medrxiv_update_pipeline import (
            fetch_medrxiv_updates,
            fetch_missing_pdfs,
            fetch_missing_fulltext,
            update_document_database,
            create_embeddings,
            run_full_pipeline
        )
        
        functions = [
            fetch_medrxiv_updates,
            fetch_missing_pdfs,
            fetch_missing_fulltext,
            update_document_database,
            create_embeddings,
            run_full_pipeline
        ]
        
        for func in functions:
            assert func.__doc__ is not None and len(func.__doc__.strip()) > 0, f"{func.__name__} missing docstring"
            logger.info(f"✓ {func.__name__} has docstring")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Docstring test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting medRxiv update pipeline tests...")
    
    tests = [
        ("Import test", test_imports),
        ("Function signature test", test_function_signatures),
        ("Docstring test", test_docstrings),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning {test_name}...")
        try:
            if test_func():
                passed += 1
                logger.info(f"✓ {test_name} PASSED")
            else:
                logger.error(f"✗ {test_name} FAILED")
        except Exception as e:
            logger.error(f"✗ {test_name} FAILED with exception: {e}")
    
    logger.info(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
