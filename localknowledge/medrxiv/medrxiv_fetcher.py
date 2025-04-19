"""
MedRxiv Preprint Fetcher

A module to fetch preprints from medRxiv in different formats (PDF, HTML, XML).
Designed for medical researchers and data scientists working with medical literature.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('medrxiv_fetcher')

# Check if lxml is installed, if not, display a helpful message
try:
    import lxml
except ImportError:
    logger.error("The lxml library is required for XML parsing. Please install it using: pip install lxml")
    logger.error("If you see 'Failed to fetch XML' errors, this is likely the cause.")


class MedRxivFetcher:
    """Class to fetch preprints from medRxiv in different formats."""
    
    BASE_URL = "https://www.medrxiv.org"
    
    def __init__(self, output_dir="./downloads", delay_between_requests=1):
        """
        Initialize the MedRxiv fetcher.
        
        Args:
            output_dir (str): Directory to save downloaded files
            delay_between_requests (float): Time in seconds to wait between requests
        """
        self.output_dir = output_dir
        self.delay = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _clean_doi(self, doi):
        """
        Clean and normalize DOI format.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            str: Cleaned DOI
        """
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
            
        return doi#!/usr/bin/env python3
            
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filenames."""
        return re.sub(r'[\\/*?:"<>|]', "_", filename)
    
    def _wait(self):
        """Wait between requests to avoid overloading the server."""
        time.sleep(self.delay)
    
    def search(self, query, max_results=10):
        """
        Search for preprints matching the query.
        
        Args:
            query (str): Search terms
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of dictionaries containing preprint information
        """
        search_url = f"{self.BASE_URL}/search/resultjson?page=1&size={max_results}&term={query}&type=revised-article"
        
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            results = response.json()
            
            preprints = []
            for item in results.get('hits', {}).get('hits', []):
                source = item.get('_source', {})
                preprint = {
                    'title': source.get('title', ''),
                    'authors': source.get('authors', ''),
                    'doi': source.get('doi', ''),
                    'abstract': source.get('abstract', ''),
                    'url': urljoin(self.BASE_URL, f"/content/{source.get('doi')}")
                }
                preprints.append(preprint)
                
            return preprints
            
        except requests.RequestException as e:
            logger.error(f"Error searching medRxiv: {e}")
            return []
    
    def _get_format_urls(self, preprint_url):
        """
        Extract URLs for different formats (PDF, HTML, XML) from the preprint page.
        
        Args:
            preprint_url (str): URL of the preprint
            
        Returns:
            dict: URLs for different formats
        """
        format_urls = {'pdf': None, 'html': None, 'xml': None}
        
        # Extract DOI from URL if possible
        doi_match = re.search(r'10\.1101/([^/]+)', preprint_url)
        doi = doi_match.group(0) if doi_match else None
        
        # If we have a DOI, try to get metadata from API first
        if doi:
            metadata = self._get_metadata_from_api(doi)
            if 'jatsxml' in metadata and metadata['jatsxml']:
                format_urls['xml'] = metadata['jatsxml']
                #logger.info(f"Found XML URL from API: {format_urls['xml']}")
        
        # If we couldn't get XML from API or don't have a DOI, fall back to scraping
        try:
            response = self.session.get(preprint_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find PDF link - usually in the download section
            pdf_link = soup.select_one('a[href*=".full.pdf"]')
            if pdf_link:
                format_urls['pdf'] = urljoin(self.BASE_URL, pdf_link['href'])
            
            # Find HTML link - usually there's a "Full Text" link
            html_link = soup.select_one('a[href*=".full.html"]')
            if html_link:
                format_urls['html'] = urljoin(self.BASE_URL, html_link['href'])
            
            # Find XML link - may be labeled as "XML" or in a metadata section
            # Only look for XML if we didn't already find it via API
            if not format_urls['xml']:
                xml_link = soup.select_one('a[href*=".full.xml"], a[href*=".xml"]')
                if xml_link:
                    format_urls['xml'] = urljoin(self.BASE_URL, xml_link['href'])
            
            return format_urls
            
        except requests.RequestException as e:
            logger.error(f"Error extracting format URLs: {e}")
            return format_urls
    
    def _get_metadata_from_api(self, doi):
        """
        Get metadata including XML URL from medRxiv API.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            dict: Metadata including jatsxml URL if available
        """
        # Clean and normalize the DOI
        cleaned_doi = self._clean_doi(doi)
        
        # Construct API URL
        api_url = f"https://api.medrxiv.org/details/medrxiv/{cleaned_doi}"
        
        try:
            #logger.info(f"Fetching metadata from API: {api_url}")
            response = self.session.get(api_url)
            response.raise_for_status()
            
            data = response.json()
            
            if 'collection' in data and len(data['collection']) > 0:
                paper_metadata = data['collection'][0]  # Get the first (or only) paper
                
                # Extract relevant metadata
                metadata = {
                    'doi': paper_metadata.get('doi', '').replace('\\/', '/'),
                    'title': paper_metadata.get('title', ''),
                    'authors': paper_metadata.get('authors', ''),
                    'abstract': paper_metadata.get('abstract', ''),
                    'date': paper_metadata.get('date', ''),
                    'version': paper_metadata.get('version', ''),
                    'jatsxml': paper_metadata.get('jatsxml', '').replace('\\/', '/')
                }
                
                #logger.info(f"Found metadata for DOI {cleaned_doi}")
                return metadata
            else:
                logger.warning(f"No metadata found for DOI {cleaned_doi}")
                
                # Try an alternative approach - some DOIs might need to be formatted differently
                if '/' in cleaned_doi.split('10.1101/')[-1]:
                    # Try without the second slash
                    alt_doi = '10.1101/' + cleaned_doi.split('10.1101/')[-1].replace('/', '')
                    #logger.info(f"Trying alternative DOI format: {alt_doi}")
                    return self._get_metadata_from_api_direct(alt_doi)
                
                return {}
                
        except requests.RequestException as e:
            logger.error(f"Error fetching metadata from API: {e}")
            return {}
        except ValueError as e:
            logger.error(f"Error parsing API response: {e}")
            return {}
            
    def _get_metadata_from_api_direct(self, doi):
        """
        Alternative method to get metadata directly, used for retry with different format.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            dict: Metadata including jatsxml URL if available
        """
        # Construct API URL
        api_url = f"https://api.medrxiv.org/details/medrxiv/{doi}"
        
        try:
            #logger.info(f"Fetching metadata with alternative format: {api_url}")
            response = self.session.get(api_url)
            response.raise_for_status()
            
            data = response.json()
            
            if 'collection' in data and len(data['collection']) > 0:
                paper_metadata = data['collection'][0]
                
                metadata = {
                    'doi': paper_metadata.get('doi', '').replace('\\/', '/'),
                    'title': paper_metadata.get('title', ''),
                    'authors': paper_metadata.get('authors', ''),
                    'abstract': paper_metadata.get('abstract', ''),
                    'date': paper_metadata.get('date', ''),
                    'version': paper_metadata.get('version', ''),
                    'jatsxml': paper_metadata.get('jatsxml', '').replace('\\/', '/')
                }
                
                #logger.info(f"Found metadata with alternative format for DOI {doi}")
                return metadata
            else:
                # If API doesn't work, try constructing URL manually as fallback
                logger.warning(f"No metadata found with alternative format for DOI {doi}")
                
                # Try to construct XML URL manually for fallback
                try:
                    # Extract the document ID part
                    doc_id = doi.split('/')[-1]
                    
                    # Attempt to get the year and month from the ID
                    if doc_id.startswith('20') and len(doc_id) > 12 and doc_id.count('.') >= 2:
                        year = doc_id.split('.')[0]
                        month = doc_id.split('.')[1]
                        day = doc_id.split('.')[2][:2]
                        
                        xml_url = f"https://www.medrxiv.org/content/medrxiv/early/{year}/{month}/{day}/{doc_id}.source.xml"
                        
                        # Verify the URL works
                        check_response = self.session.head(xml_url)
                        if check_response.status_code == 200:
                            #logger.info(f"Manually constructed XML URL works: {xml_url}")
                            return {'jatsxml': xml_url}
                    
                except Exception as e:
                    logger.error(f"Error constructing fallback XML URL: {e}")
                
                return {}
                
        except requests.RequestException as e:
            logger.error(f"Error fetching alternative metadata from API: {e}")
            return {}
        except ValueError as e:
            logger.error(f"Error parsing alternative API response: {e}")
            return {}

    def download_preprint(self, doi_or_url, formats=None, filename_prefix=None):
        """
        Download a preprint in specified formats.
        
        Args:
            doi_or_url (str): DOI or URL of the preprint
            formats (list): List of formats to download ('pdf', 'html', 'xml')
            filename_prefix (str): Optional prefix for saved files
            
        Returns:
            dict: Paths to downloaded files
        """
        if formats is None:
            formats = ['pdf', 'html', 'xml']
            
        # Handle both DOI and full URL
        if not doi_or_url.startswith('http'):
            if doi_or_url.startswith('10.1101/'):
                preprint_url = f"{self.BASE_URL}/content/{doi_or_url}"
                doc_id = doi_or_url
            else:
                preprint_url = f"{self.BASE_URL}/content/10.1101/{doi_or_url}"
                doc_id = f"10.1101/{doi_or_url}"
        else:
            preprint_url = doi_or_url
            # Try to extract DOI from URL
            match = re.search(r'10\.1101/([^/]+)', preprint_url)
            doc_id = match.group(0) if match else None
            
        #logger.info(f"Fetching preprint: {preprint_url}")
        
        # Get URLs for different formats
        format_urls = self._get_format_urls(preprint_url)
        
        # Special handling for XML - try direct URL if not found via page links
        if 'xml' in formats and (not format_urls['xml'] or format_urls['xml'] is None) and doc_id:
            direct_xml_url = self._try_direct_xml_url(doc_id)
            if direct_xml_url:
                format_urls['xml'] = direct_xml_url
                #logger.info(f"Found XML using direct URL pattern: {direct_xml_url}")
        
        downloaded_files = {}
        
        # Extract DOI for filename if not provided
        if not filename_prefix:
            doi_match = re.search(r'10\.1101/([^/]+)', preprint_url)
            filename_prefix = doi_match.group(1) if doi_match else 'preprint'
        
        # Download each requested format
        for fmt in formats:
            if fmt in format_urls and format_urls[fmt]:
                try:
                    self._wait()  # Respect rate limits
                    #logger.info(f"Downloading {fmt} format...")
                    
                    response = self.session.get(format_urls[fmt], stream=True)
                    response.raise_for_status()
                    
                    filename = self._sanitize_filename(f"{filename_prefix}.{fmt}")
                    filepath = os.path.join(self.output_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                
                    downloaded_files[fmt] = filepath
                    #logger.info(f"Successfully downloaded {fmt} to {filepath}")
                    
                except requests.RequestException as e:
                    logger.error(f"Error downloading {fmt} format: {e}")
                    
            else:
                logger.warning(f"{fmt} format not available for this preprint")
                
        return downloaded_files
    
    def batch_download(self, dois_or_urls, formats=None):
        """
        Download multiple preprints.
        
        Args:
            dois_or_urls (list): List of DOIs or URLs
            formats (list): List of formats to download
            
        Returns:
            dict: Results of download attempts
        """
        results = {}
        
        for item in dois_or_urls:
            #logger.info(f"Processing item: {item}")
            results[item] = self.download_preprint(item, formats)
            self._wait()  # Add delay between preprints
            
        return results
    
    def check_format_availability(self, doi_or_url):
        """
        Check which formats are available for a preprint.
        
        Args:
            doi_or_url (str): DOI or URL of the preprint
            
        Returns:
            dict: Available formats with True/False values
        """
        # Handle both DOI and full URL
        if not doi_or_url.startswith('http'):
            if doi_or_url.startswith('10.1101/'):
                preprint_url = f"{self.BASE_URL}/content/{doi_or_url}"
                doc_id = doi_or_url
            else:
                preprint_url = f"{self.BASE_URL}/content/10.1101/{doi_or_url}"
                doc_id = f"10.1101/{doi_or_url}"
        else:
            preprint_url = doi_or_url
            # Try to extract DOI from URL
            match = re.search(r'10\.1101/([^/]+)', preprint_url)
            doc_id = match.group(0) if match else None
            
        format_urls = self._get_format_urls(preprint_url)
        
        # Check for direct XML URL if not found via page links
        if (not format_urls['xml'] or format_urls['xml'] is None) and doc_id:
            direct_xml_url = self._try_direct_xml_url(doc_id)
            if direct_xml_url:
                format_urls['xml'] = direct_xml_url
                #logger.info(f"Found XML using direct URL pattern: {direct_xml_url}")
        
        availability = {
            'pdf': format_urls['pdf'] is not None,
            'html': format_urls['html'] is not None,
            'xml': format_urls['xml'] is not None
        }
        
        return availability


# Example usage
if __name__ == "__main__":
    # Initialize the fetcher
    fetcher = MedRxivFetcher(output_dir="./medrxiv_papers")
    
    # Search for preprints
    preprints = fetcher.search("covid machine learning", max_results=5)
    print(f"Found {len(preprints)} preprints")
    
    # Check and download the first result
    if preprints:
        first_preprint = preprints[0]
        print(f"Checking formats for: {first_preprint['title']}")
        
        available_formats = fetcher.check_format_availability(first_preprint['url'])
        print(f"Available formats: {available_formats}")
        
        # Download available formats
        formats_to_download = [fmt for fmt, available in available_formats.items() if available]
        if formats_to_download:
            downloaded = fetcher.download_preprint(
                first_preprint['url'], 
                formats=formats_to_download
            )
            print(f"Downloaded files: {downloaded}")
        else:
            print("No formats available for download.")
