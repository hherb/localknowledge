#!/usr/bin/env python3
"""
Update PDF paths in the database.

This script checks for existing PDFs that aren't recorded in the database
and updates the database accordingly.

Usage:
    python -m localknowledge.medrxiv.update_pdf_paths [--extract] [--batch-size BATCH_SIZE]

Options:
    --extract           Extract text from found PDFs
    --batch-size BATCH_SIZE   Number of records to process in each batch (default: 1000)
"""
import os
import sys
import argparse
from tqdm import tqdm

# Fix import path issue
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)

# Now import our custom modules
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.medrxiv.medrxiv_import_new import get_pdf_base_dir, extract_full_text, remove_sequential_line_numbers

def update_pdf_paths(extract_text=False, batch_size=1000):
    """
    Check for existing PDFs that aren't recorded in the database and update the database.
    
    Parameters:
    - extract_text: Whether to extract text from found PDFs
    - batch_size: Number of records to process in each batch
    
    Returns:
    - Number of PDFs found and updated in the database
    """
    # Create database manager
    db_manager = MedRxivDatabaseManager()
    
    # Get PDF directory
    pdf_base_dir = get_pdf_base_dir()
    print(f"Using PDF directory: {pdf_base_dir}")
    
    # Count total records in database
    total_records = db_manager.execute("SELECT COUNT(*) FROM preprints")[0]['count']
    print(f"Total records in database: {total_records}")
    
    # Count records with PDF paths
    records_with_pdfs = db_manager.execute("SELECT COUNT(*) FROM preprints WHERE local_pdf_path IS NOT NULL AND local_pdf_path != ''")[0]['count']
    print(f"Records with PDF paths: {records_with_pdfs}")
    
    # Count records without PDF paths
    records_without_pdfs = db_manager.execute("SELECT COUNT(*) FROM preprints WHERE local_pdf_path IS NULL OR local_pdf_path = ''")[0]['count']
    print(f"Records without PDF paths: {records_without_pdfs}")
    
    # Count PDF files in the directory
    if os.path.exists(pdf_base_dir):
        pdf_files = [f for f in os.listdir(pdf_base_dir) if f.endswith('.pdf')]
        print(f"PDF files in directory: {len(pdf_files)}")
    else:
        print(f"WARNING: PDF directory {pdf_base_dir} does not exist!")
        pdf_files = []
    
    # Process records in batches
    offset = 0
    total_found = 0
    
    while offset < records_without_pdfs:
        # Get a batch of records
        query = """
        SELECT doi, title, date_posted, category, pdf_url
        FROM preprints
        WHERE (local_pdf_path = '' OR local_pdf_path IS NULL)
        ORDER BY date_posted DESC
        LIMIT %s OFFSET %s
        """
        records = db_manager.execute(query, (batch_size, offset))
        
        if not records:
            break
            
        print(f"Processing batch of {len(records)} records (offset: {offset})")
        
        # Process each record
        found_count = 0
        papers_pbar = tqdm(records, desc="Checking for existing PDFs", unit="paper")
        
        for record in papers_pbar:
            doi = record['doi']
            papers_pbar.set_description(f"Checking {doi}")
            
            # Create safe filename from DOI (new format with underscore)
            safe_filename = doi.replace('/', '_') + '.pdf'
            local_path = os.path.join(pdf_base_dir, safe_filename)
            
            # Also check old format with hyphen
            old_format_filename = doi.replace('/', '-') + '.pdf'
            old_format_path = os.path.join(pdf_base_dir, old_format_filename)
            
            # Check if the PDF exists locally in either format
            if os.path.exists(local_path):
                found_filename = safe_filename
            elif os.path.exists(old_format_path):
                found_filename = old_format_filename
                tqdm.write(f"Found PDF with old format filename: {old_format_filename}")
                # Optionally rename the file here if desired
            else:
                continue
            
            # If we found a file
            tqdm.write(f"Found existing PDF for {doi}: {found_filename}")
            
            # Extract text if requested
            full_text = ""
            if extract_text:
                tqdm.write(f"Extracting text from {found_filename}")
                full_text = extract_full_text(found_filename)
                if full_text:
                    full_text = remove_sequential_line_numbers(full_text)
            
            # Update the database
            db_manager.update_pdf_path(doi, found_filename, full_text)
            found_count += 1
        
        print(f"Found and updated {found_count} out of {len(records)} missing PDF paths in this batch")
        total_found += found_count
        
        # Update offset for next batch
        offset += batch_size
    
    print(f"Total PDFs found and updated: {total_found}")
    db_manager.close()
    return total_found

def main():
    """Main function that parses command line arguments and runs the update"""
    parser = argparse.ArgumentParser(description="Update PDF paths in the database")
    parser.add_argument('--extract', action='store_true',
                      help='Extract text from found PDFs')
    parser.add_argument('--batch-size', type=int, default=1000,
                      help='Number of records to process in each batch')
    
    args = parser.parse_args()
    
    update_pdf_paths(
        extract_text=args.extract,
        batch_size=args.batch_size
    )

if __name__ == "__main__":
    main()
