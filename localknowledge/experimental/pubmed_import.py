import os
import gzip
import xml.etree.ElementTree as ET
import requests
from ftplib import FTP
import sqlite3
import concurrent.futures

def download_pubmed_baseline():
    """Download baseline PubMed XML files from NCBI FTP server"""
    ftp = FTP('ftp.ncbi.nlm.nih.gov')
    ftp.login()
    ftp.cwd('/pubmed/baseline')
    
    files = ftp.nlst()
    xml_files = [f for f in files if f.endswith('.xml.gz')]
    
    os.makedirs('pubmed_data/baseline', exist_ok=True)
    
    for xml_file in xml_files:
        local_file = os.path.join('pubmed_data/baseline', xml_file)
        if not os.path.exists(local_file):
            with open(local_file, 'wb') as fp:
                ftp.retrbinary(f'RETR {xml_file}', fp.write)
            print(f"Downloaded {xml_file}")
    
    ftp.quit()

def download_pubmed_updates():
    """Download incremental updates from NCBI FTP server"""
    ftp = FTP('ftp.ncbi.nlm.nih.gov')
    ftp.login()
    ftp.cwd('/pubmed/updatefiles')
    
    files = ftp.nlst()
    xml_files = [f for f in files if f.endswith('.xml.gz')]
    
    os.makedirs('pubmed_data/updates', exist_ok=True)
    
    for xml_file in xml_files:
        local_file = os.path.join('pubmed_data/updates', xml_file)
        if not os.path.exists(local_file):
            with open(local_file, 'wb') as fp:
                ftp.retrbinary(f'RETR {xml_file}', fp.write)
            print(f"Downloaded update {xml_file}")
    
    ftp.quit()

def process_xml_to_database(xml_file_path, db_conn):
    """Process PubMed XML and store in SQLite database"""
    cursor = db_conn.cursor()
    
    with gzip.open(xml_file_path, 'rb') as f:
        tree = ET.parse(f)
        root = tree.getroot()
        
        for article in root.findall('.//PubmedArticle'):
            try:
                # Extract PMID
                pmid = article.find('.//PMID').text
                
                # Extract title
                title_element = article.find('.//ArticleTitle')
                title = title_element.text if title_element is not None else ""
                
                # Extract abstract
                abstract_texts = article.findall('.//AbstractText')
                abstract = " ".join([t.text for t in abstract_texts if t.text is not None])
                
                # Extract authors
                author_elements = article.findall('.//Author')
                authors = []
                for author in author_elements:
                    last_name = author.find('.//LastName')
                    first_name = author.find('.//ForeName')
                    if last_name is not None and first_name is not None:
                        authors.append(f"{last_name.text} {first_name.text}")
                author_string = ", ".join(authors)
                
                # Extract publication year
                year_element = article.find('.//PubDate/Year')
                year = year_element.text if year_element is not None else ""
                
                # Insert into database
                cursor.execute(
                    "INSERT OR REPLACE INTO articles (pmid, title, abstract, authors, publication_year) VALUES (?, ?, ?, ?, ?)",
                    (pmid, title, abstract, author_string, year)
                )
                
            except Exception as e:
                print(f"Error processing article: {e}")
                continue
    
    db_conn.commit()

def setup_database():
    """Create SQLite database for PubMed articles"""
    conn = sqlite3.connect('pubmed_local.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        pmid TEXT PRIMARY KEY,
        title TEXT,
        abstract TEXT,
        authors TEXT,
        publication_year TEXT,
        mesh_terms TEXT,
        keywords TEXT
    )
    ''')
    
    # Create indexes for fast searching
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON articles(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_abstract ON articles(abstract)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON articles(publication_year)')
    
    conn.commit()
    return conn

def main():
    # Setup database
    conn = setup_database()
    
    # Download baseline data (only run this once)
    download_pubmed_baseline()
    
    # Process XML files in parallel
    xml_files = []
    for root, _, files in os.walk('pubmed_data'):
        for file in files:
            if file.endswith('.xml.gz'):
                xml_files.append(os.path.join(root, file))
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(process_xml_to_database, xml_file, conn) for xml_file in xml_files]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in processing: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()