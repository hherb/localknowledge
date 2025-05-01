#!/usr/bin/env python3
"""
Test script for the MedRxiv fetcher with date-based fallback mechanism
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
    """Simplified version of MedRxivFetcher for testing the fallback mechanism"""
    
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
    
    def try_direct_xml_url(self, doi):
        """
        Try to construct a direct XML URL based on DOI patterns.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            str: Direct XML URL if successful, None otherwise
        """
        # Clean DOI to ensure proper format
        doi = self._clean_doi(doi)
        
        try:
            # Extract the document ID part
            doc_id = doi.split('/')[-1]
            
            # Common URL patterns for XML files in medRxiv
            url_patterns = [
                # Standard pattern with year/month/day structure
                lambda doc_id: f"{self.BASE_URL}/content/10.1101/{doc_id}.full.xml",
                # Alternative pattern with 'early' prefix
                lambda doc_id: f"{self.BASE_URL}/content/10.1101/{doc_id}.source.xml",
                # Pattern with year/month/day folders if available in the ID
                lambda doc_id: f"{self.BASE_URL}/content/medrxiv/early/{doc_id[:4]}/{doc_id[5:7]}/{doc_id[8:10]}/{doc_id}.source.xml"
                if len(doc_id) > 10 and doc_id.count('.') >= 2 else None
            ]
            
            # Try each basic pattern first
            for pattern_func in url_patterns:
                url = pattern_func(doc_id)
                if url:
                    # Test if URL is accessible
                    try:
                        head_response = self.session.head(url, timeout=5)
                        if head_response.status_code == 200:
                            logger.info(f"Found direct XML URL: {url}")
                            return url
                    except requests.RequestException:
                        # Continue to next pattern if this one fails
                        pass
            
            # If basic patterns fail, try date-based patterns with date variations
            if len(doc_id) > 10 and doc_id.count('.') >= 2:
                try:
                    # Extract date components from the DOI
                    year = doc_id[:4]
                    month = doc_id.split('.')[1]
                    day = doc_id.split('.')[2][:2]
                    
                    # Create a base date from the DOI
                    try:
                        base_date = datetime(int(year), int(month), int(day))
                        
                        # Try the original date and up to 7 days after
                        for days_offset in range(8):  # 0 to 7 days
                            check_date = base_date + timedelta(days=days_offset)
                            date_str = f"{check_date.year}/{check_date.month:02d}/{check_date.day:02d}"
                            
                            # Construct URL with the date variation
                            url = f"{self.BASE_URL}/content/medrxiv/early/{date_str}/{doc_id}.source.xml"
                            
                            # Test if URL is accessible
                            try:
                                logger.info(f"Trying URL with date offset {days_offset}: {url}")
                                head_response = self.session.head(url, timeout=5)
                                if head_response.status_code == 200:
                                    logger.info(f"Found XML URL with date variation ({days_offset} days offset): {url}")
                                    return url
                            except requests.RequestException as e:
                                logger.info(f"Request failed for {url}: {e}")
                                # Continue to next date if this one fails
                                pass
                    except ValueError as e:
                        logger.error(f"Error parsing date from DOI: {e}")
                        # If date parsing fails, try the original pattern
                        url = f"{self.BASE_URL}/content/medrxiv/early/{year}/{month}/{day}/{doc_id}.source.xml"
                        try:
                            head_response = self.session.head(url, timeout=5)
                            if head_response.status_code == 200:
                                logger.info(f"Found direct XML URL with original date: {url}")
                                return url
                        except requests.RequestException:
                            pass
                except Exception as e:
                    logger.error(f"Error trying date variations: {e}")
            
            logger.warning(f"Could not find direct XML URL for DOI {doi}")
            return None
            
        except Exception as e:
            logger.error(f"Error constructing direct XML URL: {e}")
            return None

# Test with the example DOI
if __name__ == "__main__":
    fetcher = MedRxivFetcherTest()
    test_doi = "10.1101/2021.08.25.21262601"
    print(f"Testing DOI: {test_doi}")
    xml_url = fetcher.try_direct_xml_url(test_doi)
    print(f"Result: {xml_url}")
