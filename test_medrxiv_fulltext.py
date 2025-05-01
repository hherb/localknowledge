#!/usr/bin/env python
"""
Test script for the MedRxiv fetcher with plain text support
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('medrxiv_test')

# Import the MedRxivFetcher from the local file
sys.path.append('/Users/hherb/Library/Mobile Documents/com~apple~CloudDocs/src/localpubmed/localknowledge')
from localknowledge.medrxiv.medrxiv_fetcher import MedRxivFetcher

def test_doi(doi):
    """Test retrieving a specific DOI"""
    print(f"\nTesting DOI: {doi}")
    
    fetcher = MedRxivFetcher(output_dir="./output")
    
    # Try to get plain text
    text_url = fetcher._try_direct_text_url(doi)
    if text_url:
        print(f"Found plain text URL: {text_url}")
        try:
            response = fetcher.session.get(text_url, timeout=10)
            response.raise_for_status()
            print(f"Successfully downloaded plain text ({len(response.text)} characters)")
            print(f"Sample: {response.text[:200]}...")
            return True
        except Exception as e:
            print(f"Error downloading plain text: {e}")
    else:
        print("Plain text not found")
    
    # Try to get XML
    xml_url = fetcher._try_direct_xml_url(doi)
    if xml_url:
        print(f"Found XML URL: {xml_url}")
        try:
            response = fetcher.session.get(xml_url, timeout=10)
            response.raise_for_status()
            print(f"Successfully downloaded XML ({len(response.text)} characters)")
            return True
        except Exception as e:
            print(f"Error downloading XML: {e}")
    else:
        print("XML not found")
    
    return False

if __name__ == "__main__":
    # Test DOIs
    dois = [
        "10.1101/2024.12.23.24319533",  # Should have plain text
        "10.1101/2025.03.07.25323558",  # Should have plain text
        "10.1101/2021.08.25.21262601"   # Should have XML with date variation
    ]
    
    for doi in dois:
        success = test_doi(doi)
        print(f"Result: {'Success' if success else 'Failure'}")
