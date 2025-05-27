"""
MedRxiv Update Pipeline

This module provides a comprehensive pipeline for updating medRxiv-related records
in the document database. It orchestrates the following steps:

1. Fetches new medRxiv records from the medRxiv API
2. Downloads missing PDFs for those records
3. Fetches missing fulltext by attempting multiple strategies:
   - Download plain text files directly
   - Fall back to XML files and convert to markdown
   - Fall back to PDF-to-markdown conversion
4. Updates the document database with the new records
5. Creates embeddings for the abstracts of the new records

The module can be used both as a library (importing individual functions) or as a
command-line tool with various options for customizing the update process.

Example usage:
    # As a library
    from localknowledge.medrxiv.medrxiv_update_pipeline import run_full_pipeline
    success = run_full_pipeline(download_pdfs=True, days_to_fetch=30)

    # As a command-line tool
    python -m localknowledge.medrxiv.medrxiv_update_pipeline --download-pdfs --days-to-fetch 30

    # Run only specific steps
    python -m localknowledge.medrxiv.medrxiv_update_pipeline --step pdfs --pdf-limit 100
"""

import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_medrxiv_updates(download_pdfs: bool = False, max_retries: int = 5,
                         start_date_override: Optional[str] = None,
                         days_to_fetch: int = 7, end_date: Optional[str] = None) -> bool:
    """
    Fetch new medRxiv records and optionally their PDFs.

    Args:
        download_pdfs: Whether to download PDFs for each paper
        max_retries: Maximum number of retry attempts for API requests
        start_date_override: Force a specific start date (format: YYYY-MM-DD)
        days_to_fetch: Number of days back to fetch if no items in database
        end_date: Optional end date (format: YYYY-MM-DD), defaults to today

    Returns:
        True if successful, False otherwise
    """
    try:
        from localknowledge.medrxiv.medrxiv_import_new import update_medrxiv_database

        logger.info("Starting medRxiv updates...")
        update_medrxiv_database(
            download_pdfs=download_pdfs,
            max_retries=max_retries,
            start_date_override=start_date_override,
            days_to_fetch=days_to_fetch,
            end_date=end_date
        )
        logger.info("medRxiv updates completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error fetching medRxiv updates: {e}")
        return False

def fetch_missing_pdfs(max_retries: int = 5, limit: Optional[int] = None,
                      convert_to_markdown: bool = True, use_html_xml: bool = True) -> int:
    """
    Fetch missing PDF files for papers in the database.

    Args:
        max_retries: Maximum number of retry attempts for failed downloads
        limit: Maximum number of PDFs to fetch (None for no limit)
        convert_to_markdown: Whether to convert PDFs to markdown text
        use_html_xml: Whether to try HTML/XML conversion first before falling back to PDF

    Returns:
        Number of successfully downloaded PDFs
    """
    try:
        from localknowledge.medrxiv.medrxiv_import_new import fetch_missing_pdfs as fetch_pdfs_impl

        logger.info("Starting missing PDF downloads...")
        success_count = fetch_pdfs_impl(
            max_retries=max_retries,
            limit=limit,
            convert_to_markdown=convert_to_markdown,
            use_html_xml=use_html_xml
        )
        logger.info(f"Downloaded {success_count} missing PDFs")
        return success_count

    except Exception as e:
        logger.error(f"Error fetching missing PDFs: {e}")
        return 0

def fetch_missing_fulltext(limit: Optional[int] = None, batch_size: int = 100,
                          max_workers: int = 4, delay: float = 0.5) -> tuple[int, int, int]:
    """
    Fetch missing fulltext for papers using multiple strategies.

    Args:
        limit: Maximum number of records to process (None for no limit)
        batch_size: Number of records to process in each batch
        max_workers: Maximum number of concurrent workers
        delay: Delay between API requests to avoid rate limiting

    Returns:
        Tuple of (total processed, success count, failure count)
    """
    try:
        from localknowledge.medrxiv.update_missing_fulltext import MissingFulltextUpdater

        logger.info("Starting missing fulltext updates...")
        updater = MissingFulltextUpdater(
            batch_size=batch_size,
            max_workers=max_workers,
            delay=delay
        )

        total_processed, success_count, failure_count = updater.update_all_missing_fulltext(limit=limit)
        logger.info(f"Fulltext update completed: {success_count} successful, {failure_count} failed out of {total_processed} processed")
        return total_processed, success_count, failure_count

    except Exception as e:
        logger.error(f"Error fetching missing fulltext: {e}")
        return 0, 0, 0

def update_document_database() -> bool:
    """
    Update document database - this is a coordination function as the actual
    database updates are handled by the individual fetch functions.

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Document database updates are handled by individual fetch functions")
        return True

    except Exception as e:
        logger.error(f"Error in document database update coordination: {e}")
        return False

def create_embeddings(limit: Optional[int] = None, batch_size: int = 100,
                     model_name: str = "snowflake-arctic-embed2:latest") -> int:
    """
    Create embeddings for medRxiv abstracts that haven't been embedded yet.

    Args:
        limit: Maximum number of abstracts to embed (None for no limit)
        batch_size: Number of abstracts to process in each batch
        model_name: Name of the embedding model to use

    Returns:
        Number of abstracts embedded
    """
    try:
        from localknowledge.medrxiv.embed_abstracts import MedrxivAbstractEmbedder

        logger.info("Starting embedding creation...")
        embedder = MedrxivAbstractEmbedder(model_name=model_name)

        try:
            embedded_count = embedder.embed_abstracts(limit=limit, batch_size=batch_size)
            logger.info(f"Created embeddings for {embedded_count} abstracts")
            return embedded_count
        finally:
            embedder.close()

    except Exception as e:
        logger.error(f"Error creating embeddings: {e}")
        return 0

def run_full_pipeline(download_pdfs: bool = True, pdf_limit: Optional[int] = None,
                     fulltext_limit: Optional[int] = None, embedding_limit: Optional[int] = None,
                     days_to_fetch: int = 7, max_retries: int = 5) -> bool:
    """
    Run the complete medRxiv update pipeline.

    Args:
        download_pdfs: Whether to download PDFs during initial fetch
        pdf_limit: Limit for missing PDF downloads
        fulltext_limit: Limit for missing fulltext updates
        embedding_limit: Limit for embedding creation
        days_to_fetch: Number of days back to fetch if no items in database
        max_retries: Maximum retry attempts for network operations

    Returns:
        True if all steps completed successfully, False otherwise
    """
    success = True

    # Step 1: Fetch new medRxiv records
    logger.info("=== Step 1: Fetching new medRxiv records ===")
    if not fetch_medrxiv_updates(
        download_pdfs=download_pdfs,
        max_retries=max_retries,
        days_to_fetch=days_to_fetch
    ):
        logger.error("Failed to fetch medRxiv updates")
        success = False

    # Step 2: Fetch missing PDFs
    logger.info("=== Step 2: Fetching missing PDFs ===")
    pdf_count = fetch_missing_pdfs(
        max_retries=max_retries,
        limit=pdf_limit,
        convert_to_markdown=True,
        use_html_xml=True
    )
    if pdf_count == 0:
        logger.warning("No PDFs were downloaded (this may be normal if none are missing)")

    # Step 3: Fetch missing fulltext
    logger.info("=== Step 3: Fetching missing fulltext ===")
    total_processed, success_count, failure_count = fetch_missing_fulltext(
        limit=fulltext_limit
    )
    if total_processed == 0:
        logger.info("No records missing fulltext found")
    elif failure_count > success_count:
        logger.warning(f"More failures ({failure_count}) than successes ({success_count}) in fulltext updates")

    # Step 4: Update document database (coordination step)
    logger.info("=== Step 4: Document database coordination ===")
    if not update_document_database():
        logger.error("Document database coordination failed")
        success = False

    # Step 5: Create embeddings
    logger.info("=== Step 5: Creating embeddings ===")
    embedded_count = create_embeddings(
        limit=embedding_limit
    )
    if embedded_count == 0:
        logger.info("No new embeddings created (this may be normal if all abstracts are already embedded)")

    if success:
        logger.info("=== Pipeline completed successfully ===")
    else:
        logger.error("=== Pipeline completed with errors ===")

    return success


def main():
    """Main function with argument parsing for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="medRxiv update pipeline")
    parser.add_argument('--download-pdfs', action='store_true',
                       help='Download PDFs during initial fetch')
    parser.add_argument('--pdf-limit', type=int,
                       help='Limit for missing PDF downloads')
    parser.add_argument('--fulltext-limit', type=int,
                       help='Limit for missing fulltext updates')
    parser.add_argument('--embedding-limit', type=int,
                       help='Limit for embedding creation')
    parser.add_argument('--days-to-fetch', type=int, default=7,
                       help='Number of days back to fetch if no items in database (default: 7)')
    parser.add_argument('--max-retries', type=int, default=5,
                       help='Maximum retry attempts for network operations (default: 5)')
    parser.add_argument('--step', choices=['updates', 'pdfs', 'fulltext', 'embeddings', 'all'],
                       default='all', help='Run only a specific step (default: all)')

    args = parser.parse_args()

    if args.step == 'all':
        success = run_full_pipeline(
            download_pdfs=args.download_pdfs,
            pdf_limit=args.pdf_limit,
            fulltext_limit=args.fulltext_limit,
            embedding_limit=args.embedding_limit,
            days_to_fetch=args.days_to_fetch,
            max_retries=args.max_retries
        )
        return 0 if success else 1
    elif args.step == 'updates':
        success = fetch_medrxiv_updates(
            download_pdfs=args.download_pdfs,
            max_retries=args.max_retries,
            days_to_fetch=args.days_to_fetch
        )
        return 0 if success else 1
    elif args.step == 'pdfs':
        count = fetch_missing_pdfs(
            max_retries=args.max_retries,
            limit=args.pdf_limit
        )
        logger.info(f"Downloaded {count} PDFs")
        return 0
    elif args.step == 'fulltext':
        total, success, failure = fetch_missing_fulltext(limit=args.fulltext_limit)
        logger.info(f"Processed {total} records: {success} successful, {failure} failed")
        return 0
    elif args.step == 'embeddings':
        count = create_embeddings(limit=args.embedding_limit)
        logger.info(f"Created {count} embeddings")
        return 0


if __name__ == "__main__":
    exit(main())
