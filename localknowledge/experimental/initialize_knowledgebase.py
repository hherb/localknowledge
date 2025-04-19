import os
import requests
import gzip
import sqlite3
import xml.etree.ElementTree as ET
import concurrent.futures
import time
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
#import PyPDF2
import shutil
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medknowledge_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Base directories
BASE_DIR = os.path.expanduser('~/medical_knowledge_base')
PUBMED_DIR = os.path.join(BASE_DIR, 'pubmed')
MEDRXIV_DIR = os.path.join(BASE_DIR, 'medrxiv')
PDF_DIR = os.path.join(BASE_DIR, 'pdfs')

# Create directories
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(PUBMED_DIR, exist_ok=True)
os.makedirs(os.path.join(PUBMED_DIR, 'baseline'), exist_ok=True)
os.makedirs(os.path.join(PUBMED_DIR, 'updates'), exist_ok=True)
os.makedirs(MEDRXIV_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(os.path.join(PDF_DIR, 'pubmed'), exist_ok=True)
os.makedirs(os.path.join(PDF_DIR, 'medrxiv'), exist_ok=True)

# Database setup
def setup_databases():
    """Create SQLite databases for both PubMed and medRxiv"""
    # PubMed database
    pubmed_conn = sqlite3.connect(os.path.join(BASE_DIR, 'pubmed.db'))
    pubmed_cursor = pubmed_conn.cursor()
    
    pubmed_cursor.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        pmid TEXT PRIMARY KEY,
        title TEXT,
        abstract TEXT,
        authors TEXT,
        publication_year TEXT,
        journal TEXT,
        mesh_terms TEXT,
        keywords TEXT,
        doi TEXT,
        pdf_path TEXT
    )
    ''')
    
    # Create full-text search virtual table
    pubmed_cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        pmid, title, abstract, authors, mesh_terms, keywords,
        content='articles', content_rowid='rowid'
    )
    ''')
    
    # Create trigger to keep FTS table updated
    pubmed_cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts(pmid, title, abstract, authors, mesh_terms, keywords)
        VALUES (new.pmid, new.title, new.abstract, new.authors, new.mesh_terms, new.keywords);
    END;
    ''')
    
    pubmed_conn.commit()
    
    # medRxiv database
    medrxiv_conn = sqlite3.connect(os.path.join(BASE_DIR, 'medrxiv.db'))
    medrxiv_cursor = medrxiv_conn.cursor()
    
    medrxiv_cursor.execute('''
    CREATE TABLE IF NOT EXISTS preprints (
        doi TEXT PRIMARY KEY,
        title TEXT,
        abstract TEXT,
        authors TEXT,
        date_posted TEXT,
        category TEXT,
        version INTEGER,
        pdf_url TEXT,
        pdf_path TEXT,
        full_text TEXT
    )
    ''')
    
    # Create full-text search virtual table for medRxiv
    medrxiv_cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS preprints_fts USING fts5(
        doi, title, abstract, authors, category, full_text,
        content='preprints', content_rowid='rowid'
    )
    ''')
    
    # Create trigger to keep FTS table updated
    medrxiv_cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS preprints_ai AFTER INSERT ON preprints BEGIN
        INSERT INTO preprints_fts(doi, title, abstract, authors, category, full_text)
        VALUES (new.doi, new.title, new.abstract, new.authors, new.category, new.full_text);
    END;
    ''')
    
    medrxiv_conn.commit()
    
    return pubmed_conn, medrxiv_conn

# PubMed download functions
def download_pubmed_baseline():
    """Download the complete PubMed baseline dataset"""
    logger.info("Starting PubMed baseline download")
    
    try:
        from ftplib import FTP
        ftp = FTP('ftp.ncbi.nlm.nih.gov')
        ftp.login()
        ftp.cwd('/pubmed/baseline')
        
        files = ftp.nlst()
        xml_files = [f for f in files if f.endswith('.xml.gz')]
        total_files = len(xml_files)
        
        logger.info(f"Found {total_files} PubMed baseline files to download")
        
        for i, xml_file in enumerate(xml_files, 1):
            local_file = os.path.join(PUBMED_DIR, 'baseline', xml_file)
            
            if not os.path.exists(local_file):
                with open(local_file, 'wb') as fp:
                    ftp.retrbinary(f'RETR {xml_file}', fp.write)
                logger.info(f"Downloaded {xml_file} ({i}/{total_files})")
            else:
                logger.info(f"Skipped existing file {xml_file} ({i}/{total_files})")
        
        ftp.quit()
        logger.info("PubMed baseline download completed")
        
    except Exception as e:
        logger.error(f"Error downloading PubMed baseline: {e}")

def download_pubmed_updates():
    """Download PubMed update files"""
    logger.info("Starting PubMed updates download")
    
    try:
        from ftplib import FTP
        ftp = FTP('ftp.ncbi.nlm.nih.gov')
        ftp.login()
        ftp.cwd('/pubmed/updatefiles')
        
        files = ftp.nlst()
        xml_files = [f for f in files if f.endswith('.xml.gz')]
        
        logger.info(f"Found {len(xml_files)} PubMed update files to download")
        
        for i, xml_file in enumerate(xml_files, 1):
            local_file = os.path.join(PUBMED_DIR, 'updates', xml_file)
            
            if not os.path.exists(local_file):
                with open(local_file, 'wb') as fp:
                    ftp.retrbinary(f'RETR {xml_file}', fp.write)
                logger.info(f"Downloaded update {xml_file} ({i}/{len(xml_files)})")
            else:
                logger.info(f"Skipped existing update file {xml_file} ({i}/{len(xml_files)})")
        
        ftp.quit()
        logger.info("PubMed updates download completed")
        
    except Exception as e:
        logger.error(f"Error downloading PubMed updates: {e}")

def process_pubmed_file(xml_file_path, db_conn):
    """Process PubMed XML file and store in database"""
    cursor = db_conn.cursor()
    
    try:
        with gzip.open(xml_file_path, 'rb') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            
            articles_processed = 0
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    # Extract PMID
                    pmid = article.find('.//PMID').text
                    
                    # Extract title
                    title_element = article.find('.//ArticleTitle')
                    title = title_element.text if title_element is not None and title_element.text else ""
                    
                    # Extract abstract
                    abstract_texts = article.findall('.//AbstractText')
                    abstract = " ".join([t.text for t in abstract_texts if t is not None and t.text is not None])
                    
                    # Extract authors
                    author_elements = article.findall('.//Author')
                    authors = []
                    for author in author_elements:
                        last_name = author.find('.//LastName')
                        first_name = author.find('.//ForeName')
                        
                        author_name = ""
                        if last_name is not None and last_name.text:
                            author_name += last_name.text
                        if first_name is not None and first_name.text:
                            author_name += f" {first_name.text}" if author_name else first_name.text
                            
                        if author_name:
                            authors.append(author_name)
                    
                    author_string = ", ".join(authors)
                    
                    # Extract publication year
                    year_element = article.find('.//PubDate/Year')
                    if year_element is None:
                        # Try alternate locations
                        year_element = article.find('.//PubMedPubDate[@PubStatus="pubmed"]/Year')
                    
                    year = year_element.text if year_element is not None and year_element.text else ""
                    
                    # Extract journal
                    journal_element = article.find('.//Journal/Title')
                    journal = journal_element.text if journal_element is not None and journal_element.text else ""
                    
                    # Extract MeSH terms
                    mesh_elements = article.findall('.//MeshHeading/DescriptorName')
                    mesh_terms = ", ".join([m.text for m in mesh_elements if m is not None and m.text is not None])
                    
                    # Extract keywords
                    keyword_elements = article.findall('.//Keyword')
                    keywords = ", ".join([k.text for k in keyword_elements if k is not None and k.text is not None])
                    
                    # Extract DOI
                    doi_element = article.find('.//ArticleId[@IdType="doi"]')
                    doi = doi_element.text if doi_element is not None and doi_element.text else ""
                    
                    # Insert into database
                    cursor.execute(
                        """INSERT OR REPLACE INTO articles 
                           (pmid, title, abstract, authors, publication_year, journal, mesh_terms, keywords, doi, pdf_path) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (pmid, title, abstract, author_string, year, journal, mesh_terms, keywords, doi, "")
                    )
                    
                    articles_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing article: {e}")
                    continue
            
            db_conn.commit()
            logger.info(f"Processed {articles_processed} articles from {os.path.basename(xml_file_path)}")
            
    except Exception as e:
        logger.error(f"Error processing file {xml_file_path}: {e}")

# medRxiv download functions
def fetch_medrxiv_metadata(start_date="2019-06-06", end_date=None, batch_size=100):
    """Fetch all medRxiv metadata using their API"""
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    base_url = "https://api.biorxiv.org/details/medrxiv"
    
    all_papers = []
    cursor = 0
    total_fetched = 0
    
    while True:
        url = f"{base_url}/{start_date}/{end_date}/{cursor}"
        try:
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"Error fetching data: {response.status_code}")
                break
            
            data = response.json()
            collection = data.get('collection', [])
            
            if not collection:
                break
                
            all_papers.extend(collection)
            total_fetched += len(collection)
            logger.info(f"Fetched {total_fetched} papers so far...")
            
            # Update cursor for next batch
            cursor += batch_size
            
            # Check if we've reached the end
            if len(collection) < batch_size:
                break
                
            # Be nice to the API
            time.sleep(1)
        
        except Exception as e:
            logger.error(f"Error in API request: {e}")
            time.sleep(5)  # Wait longer on error
    
    logger.info(f"Total medRxiv papers fetched: {len(all_papers)}")
    return all_papers

def download_medrxiv_pdf(paper):
    """Download the PDF for a medRxiv paper"""
    doi = paper.get('doi', '')
    version = paper.get('version', '1')
    
    if not doi:
        return None
    
    # Create safe filename from DOI
    safe_filename = doi.replace('/', '_') + f'_v{version}.pdf'
    local_path = os.path.join(PDF_DIR, 'medrxiv', safe_filename)
    
    # Skip if already downloaded
    if os.path.exists(local_path):
        logger.info(f"Skipping existing PDF: {safe_filename}")
        return local_path
    
    # Construct PDF URL
    pdf_url = f"https://www.medrxiv.org/content/{doi}v{version}.full.pdf"
    
    try:
        response = requests.get(pdf_url, stream=True)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            logger.info(f"Downloaded PDF: {safe_filename}")
            return local_path
        else:
            logger.error(f"Failed to download {pdf_url}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error downloading {pdf_url}: {e}")
        return None

def process_medrxiv_papers(papers, db_conn):
    """Process medRxiv papers and store in database"""
    cursor = db_conn.cursor()
    
    for i, paper in enumerate(papers, 1):
        try:
            doi = paper.get('doi', '')
            title = paper.get('title', '')
            abstract = paper.get('abstract', '')
            authors = ', '.join([a.get('author', '') for a in paper.get('authors', [])])
            date_posted = paper.get('date', '')
            category = paper.get('category', '')
            version = paper.get('version', 1)
            
            # PDF URL
            pdf_url = f"https://www.medrxiv.org/content/{doi}v{version}.full.pdf"
            
            # Download PDF
            pdf_path = download_medrxiv_pdf(paper)
            
            # Extract full text if PDF available
            # full_text = ""
            # if pdf_path and os.path.exists(pdf_path):
            #     try:
            #         with open(pdf_path, 'rb') as pdf_file:
            #             reader = PyPDF2.PdfReader(pdf_file)
            #             for page_num in range(len(reader.pages)):
            #                 full_text += reader.pages[page_num].extract_text() + "\n"
            #     except Exception as e:
            #         logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            
            # Insert into database
            cursor.execute(
                """INSERT OR REPLACE INTO preprints 
                   (doi, title, abstract, authors, date_posted, category, version, pdf_url, pdf_path, full_text) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doi, title, abstract, authors, date_posted, category, version, pdf_url, pdf_path, "")
            )
            
            if i % 100 == 0:
                db_conn.commit()
                logger.info(f"Processed {i}/{len(papers)} medRxiv papers")
                
        except Exception as e:
            logger.error(f"Error processing paper {paper.get('doi', 'unknown')}: {e}")
    
    db_conn.commit()
    logger.info(f"Completed processing {len(papers)} medRxiv papers")

# Main functions
def download_pubmed_complete():
    """Download and process the complete PubMed database"""
    # Download baseline files
    download_pubmed_baseline()
    
    # Download update files
    download_pubmed_updates()
    
    # Process all files
    pubmed_conn, _ = setup_databases()
    
    xml_files = []
    # Collect baseline files
    for file in os.listdir(os.path.join(PUBMED_DIR, 'baseline')):
        if file.endswith('.xml.gz'):
            xml_files.append(os.path.join(PUBMED_DIR, 'baseline', file))
    
    # Collect update files
    for file in os.listdir(os.path.join(PUBMED_DIR, 'updates')):
        if file.endswith('.xml.gz'):
            xml_files.append(os.path.join(PUBMED_DIR, 'updates', file))
    
    logger.info(f"Processing {len(xml_files)} PubMed XML files")
    
    # Process files in parallel
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        for xml_file in xml_files:
            executor.submit(process_pubmed_file, xml_file, pubmed_conn)
    
    pubmed_conn.close()
    logger.info("PubMed processing complete")

def download_medrxiv_complete():
    """Download and process the complete medRxiv database"""
    # Fetch all papers
    papers = fetch_medrxiv_metadata()
    
    # Process papers and download PDFs
    _, medrxiv_conn = setup_databases()
    process_medrxiv_papers(papers, medrxiv_conn)
    
    medrxiv_conn.close()
    logger.info("medRxiv processing complete")

def main():
    """Main function to download both PubMed and medRxiv"""
    logger.info("Starting medical knowledge base download")
    
    # Create database connections
    pubmed_conn, medrxiv_conn = setup_databases()
    
    # Download PubMed
    download_pubmed_complete()
    
    # Download medRxiv
    download_medrxiv_complete()
    
    # Close connections
    pubmed_conn.close()
    medrxiv_conn.close()
    
    logger.info("Medical knowledge base download complete")

if __name__ == "__main__":
    main()