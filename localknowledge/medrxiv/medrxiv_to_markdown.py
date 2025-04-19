#!/usr/bin/env python3
"""
MedRxiv to Markdown Converter

Fetches a medRxiv preprint by DOI, converts HTML to Markdown,
and downloads all images to a local directory.
"""

import os
import sys
import re
import argparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin, urlparse
import logging
import uuid

# Import the MedRxivFetcher class
from medrxiv_fetcher import MedRxivFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('medrxiv_markdown')

class MedRxivMarkdownConverter:
    """Class to convert medRxiv preprints to Markdown with local images."""
    
    def __init__(self, output_dir="./output", image_dir="assets"):
        """
        Initialize the converter.
        
        Args:
            output_dir (str): Directory to save markdown files
            image_dir (str): Directory to save images (relative to output_dir)
        """
        self.output_dir = output_dir
        self.image_dir = image_dir
        self.fetcher = MedRxivFetcher(output_dir=output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filenames."""
        return re.sub(r'[\\/*?:"<>|]', "_", filename)
    
    def _get_safe_filename(self, url):
        """Create a safe filename from URL."""
        parsed = urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        
        # If no extension or filename is weird, generate one
        if not filename or '.' not in filename:
            ext = self._guess_extension_from_url(url)
            filename = f"{str(uuid.uuid4())[:8]}{ext}"
        
        return self._sanitize_filename(filename)
    
    def _guess_extension_from_url(self, url):
        """Guess file extension from URL or default to .jpg."""
        if 'png' in url.lower():
            return '.png'
        elif 'gif' in url.lower():
            return '.gif'
        elif 'svg' in url.lower():
            return '.svg'
        else:
            return '.jpg'  # Default to jpg
    
    def download_image(self, img_url, base_url, image_directory):
        """
        Download an image and return its local path.
        
        Args:
            img_url (str): URL of the image
            base_url (str): Base URL for resolving relative paths
            image_directory (str): Directory to save images
            
        Returns:
            str: Local path to the saved image
        """
        # Make sure the image directory exists
        if not os.path.exists(image_directory):
            os.makedirs(image_directory)
        
        # Handle relative URLs
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(base_url, img_url)
        
        try:
            response = self.session.get(img_url, stream=True, timeout=10)
            response.raise_for_status()
            
            # Create a safe filename
            filename = self._get_safe_filename(img_url)
            filepath = os.path.join(image_directory, filename)
            
            # Save the image
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Downloaded image: {filepath}")
            return filepath
            
        except requests.RequestException as e:
            logger.error(f"Error downloading image {img_url}: {e}")
            return None
    
    def html_to_markdown_with_local_images(self, html_content, base_url, article_name):
        """
        Convert HTML to Markdown and download images.
        
        Args:
            html_content (str): HTML content
            base_url (str): Base URL for resolving relative paths
            article_name (str): Name of the article (for image directory)
            
        Returns:
            str: Markdown content with local image references
        """
        # Create a specific image directory for this article
        article_image_dir = os.path.join(self.output_dir, self.image_dir, article_name)
        if not os.path.exists(article_image_dir):
            os.makedirs(article_image_dir)
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Process all images
        for img in soup.find_all('img'):
            if img.get('src'):
                # Download the image
                local_path = self.download_image(img['src'], base_url, article_image_dir)
                
                if local_path:
                    # Update the src to point to the local file
                    relative_path = os.path.relpath(local_path, self.output_dir)
                    img['src'] = relative_path
        
        # Convert to markdown
        markdown_content = md(str(soup), heading_style="ATX")
        
        return markdown_content
    
    def convert_doi_to_markdown(self, doi):
        """
        Convert a medRxiv preprint to Markdown.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            tuple: (markdown content, markdown file path)
        """
        # Check format availability
        availability = self.fetcher.check_format_availability(doi)
        
        if not availability['html']:
            logger.error(f"HTML format not available for DOI: {doi}")
            return None, None
        
        # Download HTML
        download_result = self.fetcher.download_preprint(doi, formats=['html'])
        
        if 'html' not in download_result:
            logger.error(f"Failed to download HTML for DOI: {doi}")
            return None, None
        
        html_path = download_result['html']
        
        # Read HTML content
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Create article name from DOI
        article_name = self._sanitize_filename(doi.replace('10.1101/', ''))
        
        # Get base URL
        base_url = f"https://www.medrxiv.org/content/{doi}"
        
        # Convert HTML to Markdown with local images
        markdown_content = self.html_to_markdown_with_local_images(
            html_content, base_url, article_name
        )
        
        # Save markdown to file
        markdown_path = os.path.join(self.output_dir, f"{article_name}.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"Saved markdown to: {markdown_path}")
        
        return markdown_content, markdown_path

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Convert medRxiv preprint to Markdown with local images.')
    parser.add_argument('doi', help='DOI of the medRxiv preprint (e.g., 10.1101/2023.01.15.23284593)')
    parser.add_argument('--output-dir', '-o', default='./output', help='Output directory')
    parser.add_argument('--image-dir', '-i', default='assets', help='Image directory (relative to output dir)')
    
    args = parser.parse_args()
    
    converter = MedRxivMarkdownConverter(output_dir=args.output_dir, image_dir=args.image_dir)
    
    doi = args.doi
    if not doi.startswith('10.1101/'):
        doi = f"10.1101/{doi}"
    
    markdown_content, markdown_path = converter.convert_doi_to_markdown(doi)
    
    if markdown_content:
        print(f"Successfully converted {doi} to Markdown.")
        print(f"Markdown file saved to: {markdown_path}")
        print(f"Images saved to: {os.path.join(args.output_dir, args.image_dir)}")
    else:
        print(f"Failed to convert {doi} to Markdown.")
        sys.exit(1)

if __name__ == "__main__":
    main()
