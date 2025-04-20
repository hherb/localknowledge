#!/usr/bin/env python3
"""
MedRxiv to Markdown Converter

Fetches a medRxiv preprint by DOI, converts HTML to Markdown,
and downloads all images to a local directory.

Note: When processing XML, actual images cannot be downloaded since the XML only
contains references to images, not the actual image data or direct URLs.
For XML papers, the script will include figure captions but not the images themselves.
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
from localknowledge.medrxiv.medrxiv_fetcher import MedRxivFetcher

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('medrxiv_markdown')

# Check if lxml is installed, if not, display a helpful message
try:
    import lxml
except ImportError:
    logger.error("The lxml library is required for XML parsing. Please install it using: pip install lxml")
    logger.error("If you see 'Failed to convert XML to HTML' errors, this is likely the cause.")


class MedRxivMarkdownConverter:
    """Class to convert medRxiv preprints to Markdown with local images."""
    
    def __init__(self, output_dir="./output", image_dir="assets", save_files=True):
        """
        Initialize the converter.
        
        Args:
            output_dir (str): Directory to save markdown files (if save_files is True)
            image_dir (str): Directory to save images (relative to output_dir)
            save_files (bool): Whether to save files to disk or just return content
        """
        self.output_dir = output_dir
        self.image_dir = image_dir
        self.save_files = save_files
        self.fetcher = MedRxivFetcher(output_dir=output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })
        
        # Create output directory if it doesn't exist and we're saving files
        if save_files and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def xml_to_html(self, xml_content):
        """
        Convert XML to HTML for easier markdown conversion.
        
        Args:
            xml_content (str): XML content
            
        Returns:
            str: HTML content
        """
        try:
            # Parse XML with lxml parser explicitly
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Create a new HTML document
            html = BeautifulSoup('', 'html.parser')
            
            # Create the basic structure
            html_body = html.new_tag('body')
            html.append(html_body)
            
            # Extract title
            title_elem = soup.find('article-title')
            if title_elem:
                title_tag = html.new_tag('h1')
                title_tag.string = title_elem.get_text()
                html_body.append(title_tag)
            
            # Extract authors
            authors = []
            for contrib in soup.find_all('contrib'):
                if contrib.get('contrib-type') == 'author':
                    surname = contrib.find('surname')
                    given_names = contrib.find('given-names')
                    if surname and given_names:
                        authors.append(f"{given_names.get_text()} {surname.get_text()}")
            
            if authors:
                authors_p = html.new_tag('p')
                authors_p.string = "Authors: " + ", ".join(authors)
                html_body.append(authors_p)
            
            # Extract abstract
            abstract = soup.find('abstract')
            if abstract:
                abstract_div = html.new_tag('div')
                abstract_div['class'] = 'abstract'
                
                abstract_title = html.new_tag('h2')
                abstract_title.string = "Abstract"
                abstract_div.append(abstract_title)
                
                for p in abstract.find_all('p'):
                    p_tag = html.new_tag('p')
                    p_tag.string = p.get_text()
                    abstract_div.append(p_tag)
                
                html_body.append(abstract_div)
            
            # Extract sections
            body = soup.find('body')
            if body:
                for sec in body.find_all('sec'):
                    section_div = html.new_tag('div')
                    section_div['class'] = 'section'
                    
                    # Section title
                    title = sec.find('title')
                    if title:
                        h2 = html.new_tag('h2')
                        h2.string = title.get_text()
                        section_div.append(h2)
                    
                    # Section paragraphs
                    for p in sec.find_all('p'):
                        p_tag = html.new_tag('p')
                        p_tag.string = p.get_text()
                        section_div.append(p_tag)
                    
                    # Tables
                    for table in sec.find_all('table-wrap'):
                        table_tag = html.new_tag('table')
                        table_tag['border'] = '1'
                        
                        # Table caption
                        caption = table.find('caption')
                        if caption:
                            caption_tag = html.new_tag('caption')
                            caption_tag.string = caption.get_text()
                            table_tag.append(caption_tag)
                        
                        # Table body
                        tbody_tag = html.new_tag('tbody')
                        
                        for row in table.find_all('tr'):
                            tr_tag = html.new_tag('tr')
                            
                            for cell in row.find_all(['th', 'td']):
                                cell_tag = html.new_tag(cell.name)
                                cell_tag.string = cell.get_text()
                                tr_tag.append(cell_tag)
                            
                            tbody_tag.append(tr_tag)
                        
                        table_tag.append(tbody_tag)
                        section_div.append(table_tag)
                    
                    # Figures
                    for fig in sec.find_all('fig'):
                        fig_div = html.new_tag('div')
                        fig_div['class'] = 'figure'
                        
                        # Figure label
                        label = fig.find('label')
                        if label:
                            fig_label = html.new_tag('p')
                            fig_label['class'] = 'figure-label'
                            fig_label.string = label.get_text()
                            fig_div.append(fig_label)
                        
                        # Figure caption
                        caption = fig.find('caption')
                        if caption:
                            fig_caption = html.new_tag('p')
                            fig_caption['class'] = 'figure-caption'
                            fig_caption.string = caption.get_text()
                            fig_div.append(fig_caption)
                        
                        # Figure graphics - We'll add a placeholder since we can't directly access the image
                        # We just note that there was a figure, but don't try to include the actual image
                        # since XML doesn't contain the actual image data, just references
                        fig_notice = html.new_tag('p')
                        fig_notice['class'] = 'figure-placeholder'
                        fig_notice.string = "[Figure described in caption above]"
                        fig_div.append(fig_notice)
                        
                        section_div.append(fig_div)
                    
                    html_body.append(section_div)
            
            # References
            ref_list = soup.find('ref-list')
            if ref_list:
                refs_div = html.new_tag('div')
                refs_div['class'] = 'references'
                
                refs_title = html.new_tag('h2')
                refs_title.string = "References"
                refs_div.append(refs_title)
                
                refs_ol = html.new_tag('ol')
                
                for ref in ref_list.find_all('ref'):
                    ref_li = html.new_tag('li')
                    ref_li.string = ref.get_text().strip()
                    refs_ol.append(ref_li)
                
                refs_div.append(refs_ol)
                html_body.append(refs_div)
            
            return str(html)
            
        except Exception as e:
            logger.error(f"Error converting XML to HTML: {e}")
            # Return a simple HTML with error message
            return f"<html><body><h1>Error</h1><p>Failed to convert XML to HTML: {e}</p></body></html>"
    
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
        Download an image and return its local path or URL.
        
        Args:
            img_url (str): URL of the image
            base_url (str): Base URL for resolving relative paths
            image_directory (str): Directory to save images
            
        Returns:
            str: Local path to the saved image or the original URL if not saving
        """
        # Handle relative URLs
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(base_url, img_url)
            
        # If we're not saving files, just return the URL
        if not self.save_files:
            return img_url
        
        # Make sure the image directory exists
        if not os.path.exists(image_directory):
            os.makedirs(image_directory)
        
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
            
            #logger.info(f"Downloaded image: {filepath}")
            return filepath
            
        except requests.RequestException as e:
            logger.error(f"Error downloading image {img_url}: {e}")
            return img_url  # Return original URL if download fails
    
    def html_to_markdown_with_local_images(self, html_content, base_url, article_name):
        """
        Convert HTML to Markdown and process images.
        
        Args:
            html_content (str): HTML content
            base_url (str): Base URL for resolving relative paths
            article_name (str): Name of the article (for image directory)
            
        Returns:
            tuple: (Markdown content with image references, has_images boolean)
        """
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check if there are any images to process
        images = soup.find_all('img')
        has_images = len(images) > 0
        
        # Process images
        if has_images:
            # Create article image directory path (whether we use it or not)
            article_image_dir = os.path.join(self.output_dir, self.image_dir, article_name)
            
            # Create the directory only if we're saving files
            if self.save_files and not os.path.exists(article_image_dir):
                os.makedirs(article_image_dir)
            
            # Process all images
            for img in images:
                if img.get('src'):
                    # Download or get URL for the image
                    result_path = self.download_image(img['src'], base_url, article_image_dir)
                    
                    if result_path:
                        # If saving files, update src to relative path
                        if self.save_files:
                            relative_path = os.path.relpath(result_path, self.output_dir)
                            img['src'] = relative_path
                        else:
                            # Otherwise just use the full URL
                            img['src'] = result_path
        
        # Convert to markdown
        markdown_content = md(str(soup), heading_style="ATX")
        
        return markdown_content, has_images
    
    def convert_doi_to_markdown(self, doi):
        """
        Convert a medRxiv preprint to Markdown.
        
        Args:
            doi (str): DOI of the preprint
            
        Returns:
            dict: Dictionary containing {
                'markdown': markdown content, 
                'filepath': markdown file path (if saved),
                'has_images': boolean indicating if images were processed,
                'image_dir': path to image directory (if images were saved)
            }
        """
        # Clean the DOI format
        doi = self.fetcher._clean_doi(doi)
        
        # Check format availability
        availability = self.fetcher.check_format_availability(doi)
        
        # Create article name from DOI
        article_name = self._sanitize_filename(doi.replace('10.1101/', ''))
        
        # Get base URL
        base_url = f"https://www.medrxiv.org/content/{doi}"
        
        has_images = False
        markdown_content = None
        markdown_path = None
        
        # Try HTML first, then XML if HTML is not available
        if availability['html']:
            #logger.info(f"HTML format available for DOI: {doi}, downloading...")
            download_result = self.fetcher.download_preprint(doi, formats=['html'])
            
            if 'html' in download_result:
                html_path = download_result['html']
                
                # Read HTML content
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Convert HTML to Markdown with local images
                markdown_content, has_images = self.html_to_markdown_with_local_images(
                    html_content, base_url, article_name
                )
            else:
                logger.info(f"Failed to download HTML for DOI: {doi}")
                
        elif availability['xml']:
            #logger.info(f"HTML not available but XML is available for DOI: {doi}, downloading XML...")
            download_result = self.fetcher.download_preprint(doi, formats=['xml'])
            
            if 'xml' in download_result:
                xml_path = download_result['xml']
                
                # Read XML content
                with open(xml_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Convert XML to HTML
                #logger.info("Converting XML to HTML...")
                html_content = self.xml_to_html(xml_content)
                
                # Convert HTML to Markdown with local images
                markdown_content, has_images = self.html_to_markdown_with_local_images(
                    html_content, base_url, article_name
                )
            else:
                logger.error(f"Failed to download XML for DOI: {doi}")
                
        else:
            logger.error(f"Neither HTML nor XML format available for DOI: {doi}")
            return None
        
        # Only save markdown to file if save_files is True
        if markdown_content and self.save_files:
            markdown_path = os.path.join(self.output_dir, f"{article_name}.md")
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            #logger.info(f"Saved markdown to: {markdown_path}")
        
        # Create result dictionary
        result = {
            'markdown': markdown_content,
            'filepath': markdown_path,
            'has_images': has_images
        }
        
        # Add image directory path only if we have images and we're saving files
        if has_images and self.save_files:
            image_dir_path = os.path.join(self.output_dir, self.image_dir, article_name)
            result['image_dir'] = image_dir_path
            
        return result

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Convert medRxiv preprint to Markdown with local images.')
    parser.add_argument('doi', help='DOI of the medRxiv preprint (e.g., 10.1101/2023.01.15.23284593)')
    parser.add_argument('--output-dir', '-o', default='./output', help='Output directory')
    parser.add_argument('--image-dir', '-i', default='assets', help='Image directory (relative to output dir)')
    parser.add_argument('--no-save', action='store_true', help='Do not save files, just print markdown to stdout')
    
    args = parser.parse_args()
    
    # Check for required dependencies
    try:
        import lxml
    except ImportError:
        logger.error("The lxml library is required for XML parsing.")
        logger.error("Please install the required dependencies using:")
        logger.error("pip install requests beautifulsoup4 markdownify lxml")
        sys.exit(1)
        
    converter = MedRxivMarkdownConverter(
        output_dir=args.output_dir, 
        image_dir=args.image_dir, 
        save_files=not args.no_save
    )
    
    doi = args.doi
    
    result = converter.convert_doi_to_markdown(doi)
    
    if result and result['markdown']:
        if args.no_save:
            # Print markdown content to stdout if not saving to file
            print(result['markdown'])
        else:
            print(f"Successfully converted {doi} to Markdown.")
            print(f"Markdown file saved to: {result['filepath']}")
            
            if result['has_images'] and 'image_dir' in result:
                print(f"Images saved to: {result['image_dir']}")
            elif result['has_images']:
                print("Images were processed but not saved locally.")
            else:
                print("No images were found in the document.")
    else:
        print(f"Failed to convert {doi} to Markdown.")
        sys.exit(1)

if __name__ == "__main__":
    main()
