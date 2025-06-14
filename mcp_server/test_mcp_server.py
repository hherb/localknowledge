#!/usr/bin/env python3
"""
Test script for the LocalKnowledge MCP Server

This script tests the basic functionality of the MCP server
by calling the database functions directly.
"""

import sys
import os

# Add the parent directory to the path so we can import localknowledge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localknowledge_mcp_server import search_pubmed_by_keywords, get_document_details, get_full_text

def test_search():
    """Test the search functionality"""
    print("Testing search functionality...")
    
    # Test basic search
    results = search_pubmed_by_keywords("covid vaccine")
    if results:
        print(f"Found {len(results)} results for 'covid vaccine'")
        for i, result in enumerate(results[:3]):  # Show first 3 results
            print(f"  {i+1}. ID: {result.document_id}, DOI: {result.doi}")
            print(f"     Title: {result.title[:100]}...")
    else:
        print("No results found for 'covid vaccine'")
    
    # Test boolean search
    results = search_pubmed_by_keywords("(covid | coronavirus) & vaccine")
    if results:
        print(f"Found {len(results)} results for boolean search")
    else:
        print("No results found for boolean search")

def test_document_details():
    """Test getting document details"""
    print("\nTesting document details functionality...")
    
    # First get a document ID from search
    results = search_pubmed_by_keywords("covid")
    if results and len(results) > 0:
        doc_id = results[0].document_id
        print(f"Testing with document ID: {doc_id}")
        
        details = get_document_details(doc_id)
        if details:
            print(f"  Title: {details.title}")
            print(f"  DOI: {details.doi}")
            print(f"  PMID: {details.pmid}")
            print(f"  Authors: {details.authors}")
            print(f"  Journal: {details.journal}")
            print(f"  Publication Date: {details.publication_date}")
        else:
            print(f"No details found for document ID: {doc_id}")
    else:
        print("No documents found to test details with")

def test_full_text():
    """Test getting full text"""
    print("\nTesting full text functionality...")
    
    # First get a document ID from search
    results = search_pubmed_by_keywords("covid")
    if results and len(results) > 0:
        doc_id = results[0].document_id
        print(f"Testing with document ID: {doc_id}")
        
        full_text = get_full_text(doc_id)
        if full_text:
            print(f"  Markdown length: {len(full_text.markdown)} characters")
            print(f"  PDF URL: {full_text.pdf_url}")
            print(f"  PDF Path: {full_text.pdf_path}")
            if full_text.markdown:
                print(f"  First 200 chars: {full_text.markdown[:200]}...")
        else:
            print(f"No full text found for document ID: {doc_id}")
    else:
        print("No documents found to test full text with")

if __name__ == "__main__":
    print("LocalKnowledge MCP Server Test")
    print("=" * 40)
    
    try:
        test_search()
        test_document_details()
        test_full_text()
        print("\nTest completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
