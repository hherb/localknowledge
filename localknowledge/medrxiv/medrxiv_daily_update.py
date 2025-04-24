#!/usr/bin/env python3
"""
MedRxiv Daily Update Script

This script is designed to run periodically (e.g., via cron) to fetch and update the
database with new medRxiv papers published since the last fetch up until yesterday.
It also generates AI summaries for newly fetched papers.

Usage:
- Run this script directly (after activating virtual environment): python medrxiv_daily_update.py
- To run with summarization: python medrxiv_daily_update.py --summarize
- Or set it up as a cron job to run automatically (see below)

Example cron entry (runs daily at 2:00 AM):
0 2 * * * cd /Users/hherb/Library/Mobile Documents/com~apple~CloudDocs/src/localpubmed/localknowledge && source .venv/bin/activate && python localknowledge/experimental/medrxiv_daily_update.py --summarize >> /tmp/medrxiv_update.log 2>&1
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser('~/medrxiv_daily_update.log'))
    ]
)
logger = logging.getLogger('medrxiv_daily_update')

# Fix import path issue - we need to add appropriate paths
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)  # For importing from this directory
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)  # For importing from parent directory

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file if it exists

# Import required modules
try:
    from localknowledge.medrxiv.medrxiv_import_new import update_medrxiv_database, fetch_and_convert_to_markdown
    from localknowledge.medrxiv.medrxiv_to_markdown import MedRxivMarkdownConverter
    from localknowledge.db.medrxiv import MedRxivDatabaseManager
    from localknowledge.ai.summarizer import summarize_interesting_text
    logger.info("Successfully imported required modules")
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    sys.exit(1)

# Define interests for summarization
INTERESTS = [
    'emergency medicine', 
    'rural and remote medicine', 
    'AI use in medicine', 
    'machine learning'
]

def generate_summaries(limit: int = 100) -> int:
    """
    Generate AI summaries for papers that don't have summaries yet.
    
    Args:
        limit: Maximum number of papers to summarize
        
    Returns:
        Number of papers successfully summarized
    """
    try:
        logger.info(f"Starting AI summarization for up to {limit} papers")
        
        # Connect to the database
        db_manager = MedRxivDatabaseManager()
        
        # Get papers without summaries
        papers = db_manager.get_preprints_without_summaries(limit=limit)
        if not papers:
            logger.info("No papers found that need summarization")
            db_manager.close()
            return 0
            
        logger.info(f"Found {len(papers)} papers that need summarization")
        success_count = 0
        
        # Generate summaries for each paper
        for i, paper in enumerate(papers):
            try:
                # Use title + abstract for summarization
                text_to_summarize = f"{paper['title']}\n\n{paper['abstract']}"
                
                # Generate the summary using the AI model
                logger.info(f"Generating summary for paper {i+1}/{len(papers)}: {paper['doi']}")
                summary_result = summarize_interesting_text(text_to_summarize, INTERESTS)
                
                # Store the summary in the database
                summary_id = db_manager.store_summary(paper['doi'], summary_result)
                
                if summary_id:
                    success_count += 1
                    if success_count % 10 == 0:
                        logger.info(f"Processed {success_count} summaries")
                
                # Avoid overwhelming the AI service with requests
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error summarizing paper {paper['doi']}: {e}")
                continue
        
        logger.info(f"Successfully generated {success_count} summaries")
        db_manager.close()
        return success_count
        
    except Exception as e:
        logger.error(f"Error during summarization process: {e}")
        return 0

def fetch_markdown_for_recent_papers(days_back: int = 7, limit: int = 100) -> int:
    """
    Fetch markdown versions of recently added papers that don't have full text yet.
    
    This function retrieves papers from the database that were added within the 
    specified timeframe and don't have full-text content. It then attempts to 
    convert them to markdown using HTML/XML sources, which typically produces 
    better results than PDF extraction.
    
    Args:
        days_back: Number of days to look back for papers
        limit: Maximum number of papers to process
        
    Returns:
        Number of papers successfully converted to markdown
    """
    try:
        logger.info(f"Starting markdown conversion for papers from the last {days_back} days")
        
        # Connect to the database
        db_manager = MedRxivDatabaseManager()
        
        # Get recent papers without full text
        papers = db_manager.get_recent_preprints_without_fulltext(days_back=days_back, limit=limit)
        
        if not papers:
            logger.info("No recent papers found that need markdown conversion")
            db_manager.close()
            return 0
            
        logger.info(f"Found {len(papers)} recent papers that need markdown conversion")
        success_count = 0
        
        # Process each paper
        for i, paper in enumerate(papers):
            try:
                doi = paper['doi']
                logger.info(f"Converting paper {i+1}/{len(papers)}: {doi}")
                
                # Try to convert to markdown using HTML/XML
                markdown_text = fetch_and_convert_to_markdown(doi, save_files=False)
                
                if markdown_text:
                    # Update the database with the markdown text
                    db_manager.update_full_text(doi, markdown_text)
                    success_count += 1
                    logger.info(f"Successfully converted {doi} to markdown")
                else:
                    logger.warning(f"Failed to convert {doi} to markdown")
                
                # Avoid hammering the server
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error converting paper {paper['doi']} to markdown: {e}")
                continue
        
        logger.info(f"Successfully converted {success_count} papers to markdown")
        db_manager.close()
        return success_count
        
    except Exception as e:
        logger.error(f"Error during markdown conversion process: {e}")
        return 0

def run_daily_update(summarize: bool = False, summary_limit: int = 250, convert_to_markdown: bool = True, markdown_limit: int = 250):
    """
    Run the daily update process to fetch papers from the last fetch date until yesterday
    
    Args:
        summarize: Whether to generate AI summaries for newly fetched papers
        summary_limit: Maximum number of papers to summarize
        convert_to_markdown: Whether to convert papers to markdown using HTML/XML
        markdown_limit: Maximum number of papers to convert to markdown
    """
    try:
        logger.info("Starting daily medRxiv update process")
        
        # Calculate yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Start the update process
        # We don't provide a start_date_override because the update_medrxiv_database function 
        # will automatically determine the last fetch date from the database
        # We'll use the end_date parameter to set yesterday as the end date
        logger.info(f"Fetching papers until {yesterday}")
        
        # Run the update with our custom end date
        update_medrxiv_database(
            download_pdfs=False,  # Change to True if you want to download PDFs
            max_retries=5,
            start_date_override=None,  # Let it auto-determine from database
            days_to_fetch=30,  # Fallback in case database is empty
            end_date=yesterday
        )
        
        logger.info("Daily update of papers completed successfully")
        
        # Convert papers to markdown if requested
        if convert_to_markdown:
            logger.info("Starting markdown conversion process")
            markdown_count = fetch_markdown_for_recent_papers(days_back=7, limit=markdown_limit)
            logger.info(f"Markdown conversion completed: {markdown_count} papers converted")
        
        # Generate summaries if requested
        if summarize:
            logger.info("Starting summarization process")
            summary_count = generate_summaries(limit=summary_limit)
            logger.info(f"Summarization completed: {summary_count} papers summarized")
        
        return True
    except Exception as e:
        logger.error(f"Error during daily update: {e}")
        return False

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Update medRxiv database and generate summaries")
    parser.add_argument("--summarize", action="store_true", 
                      help="Generate AI summaries for papers without summaries")
    parser.add_argument("--markdown", action="store_true",
                      help="Convert papers to markdown using HTML/XML sources")
    parser.add_argument("--summary-limit", type=int, default=100,
                      help="Maximum number of papers to summarize")
    parser.add_argument("--markdown-limit", type=int, default=100,
                      help="Maximum number of papers to convert to markdown")
    args = parser.parse_args()
    
    start_time = time.time()
    success = run_daily_update(
        summarize=args.summarize, 
        summary_limit=args.summary_limit,
        convert_to_markdown=args.markdown,
        markdown_limit=args.markdown_limit
    )
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    
    if success:
        logger.info(f"Update completed in {duration} seconds")
    else:
        logger.error(f"Update failed after {duration} seconds")
        sys.exit(1)
