#!/usr/bin/env python3
"""
Test script for the MedRxiv fetcher with plain text support
Specifically testing the DOI 10.1101/2024.12.23.24319533
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('medrxiv_fetcher_test')

class MedRxivFetcherTest:
    """Simplified version of MedRxivFetcher for testing the plain text support"""
    
    BASE_URL = "https://www.medrxiv.org"
    
    def __init__(self):
        """Initialize the test fetcher"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })
    
    def _clean_doi(self, doi):
        """Clean and normalize DOI format."""
        # Remove any file extensions or query params
        doi = doi.split('?')[0].split('#')[0]
        
        # Replace underscores with forward slashes if they're used in place of the standard separator
        if '_' in doi and '/' not in doi.split('10.1101')[-1]:
            doi = doi.replace('_', '/')
        
        # Make sure we have the proper prefix
        if not doi.startswith('10.1101/'):
            if doi.startswith('10.1101'):
                # In case the slash is missing after the prefix
                doi = '10.1101/' + doi[8:]
            else:
                # If it's just the ID without the prefix
                doi = '10.1101/' + doi
                
        # Remove any duplicate prefix (in case someone entered 10.1101/10.1101/...)
        if doi.count('10.1101/') > 1:
            parts = doi.split('10.1101/')
            doi = '10.1101/' + parts[-1]
            
        return doi
    
    def try_direct_text_url(self, doi):
        """
        Try to construct a direct plain text URL based on DOI patterns.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            str: Direct plain text URL if successful, None otherwise
        """
        # Clean DOI to ensure proper format
        doi = self._clean_doi(doi)
        
        try:
            # Extract the document ID part
            doc_id = doi.split('/')[-1]
            
            # Common URL patterns for plain text files in medRxiv
            url_patterns = [
                # Standard pattern with version number
                lambda doc_id: f"{self.BASE_URL}/content/10.1101/{doc_id}v1.full.txt",
                # Alternative pattern without version number
                lambda doc_id: f"{self.BASE_URL}/content/10.1101/{doc_id}.full.txt"
            ]
            
            # Try each pattern
            for pattern_func in url_patterns:
                url = pattern_func(doc_id)
                if url:
                    # Test if URL is accessible
                    try:
                        logger.info(f"Trying URL: {url}")
                        head_response = self.session.head(url, timeout=5)
                        if head_response.status_code == 200:
                            logger.info(f"Found direct plain text URL: {url}")
                            return url
                    except requests.RequestException as e:
                        logger.info(f"Request failed for {url}: {e}")
                        # Continue to next pattern if this one fails
                        pass
            
            logger.info(f"Could not find direct plain text URL for DOI {doi}")
            return None
            
        except Exception as e:
            logger.error(f"Error constructing direct plain text URL: {e}")
            return None
    
    def get_text_content(self, url):
        """Get the content of a plain text URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching text content: {e}")
            return None

# Test with the specific DOI
if __name__ == "__main__":
    fetcher = MedRxivFetcherTest()
    test_doi = "10.1101/2024.12.23.24319533"
    print(f"Testing DOI: {test_doi}")
    
    # First, let's directly check the URL we know works
    known_url = "https://www.medrxiv.org/content/10.1101/2024.12.23.24319533v1.full.txt"
    try:
        head_response = fetcher.session.head(known_url, timeout=5)
        print(f"Direct check of known URL: {known_url}")
        print(f"Status code: {head_response.status_code}")
    except Exception as e:
        print(f"Error checking known URL: {e}")
    
    # Now let's test our algorithm
    text_url = fetcher.try_direct_text_url(test_doi)
    print(f"Result from algorithm: {text_url}")
    
    # Let's get a sample of the content
    if text_url:
        content = fetcher.get_text_content(text_url)
        if content:
            print("\nSample of content (first 500 characters):")
            print(content[:500])
        else:
            print("Failed to fetch content")
    else:
        print("No text URL found")
