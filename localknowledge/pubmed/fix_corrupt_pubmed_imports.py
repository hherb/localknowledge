#!/usr/bin/env python3
"""
Fix Corrupt PubMed Imports Module

This module identifies and fixes PubMed records that were corrupted during import
due to the abstract truncation bug. It re-processes XML files, compares with
existing database records, updates corrupted records, re-chunks abstracts,
and re-embeds the chunks.

The process:
1. Re-process XML files using the fixed import_downloads.process_article function
2. Compare with existing database records to identify differences
3. Update corrupted records in the database
4. Delete old chunks and embeddings for updated records
5. Re-chunk updated abstracts
6. Re-embed the new chunks

Usage:
    python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml/files
"""

import os
import sys
import gzip
import xml.etree.ElementTree as ET
import logging
import argparse
import time
from typing import Dict, Any, List, Optional, Tuple, Set, Generator
from datetime import datetime
from tqdm import tqdm
import json

# Add the parent directory to the path to import localknowledge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from localknowledge.pubmed.import_downloads import process_article, get_element_text
from localknowledge.db.pubmed import PubMedDatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkerDatabaseManager
from localknowledge.db.embeddings import EmbeddingsDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fix_corrupt_imports.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CorruptImportFixer:
    """
    Main class for fixing corrupt PubMed imports.
    """

    def __init__(self, xml_dir: str, batch_size: int = 1000):
        """
        Initialize the corrupt import fixer.

        Args:
            xml_dir: Directory containing PubMed XML files
            batch_size: Number of records to process in each batch
        """
        self.xml_dir = xml_dir
        self.batch_size = batch_size

        # Initialize database managers
        self.pubmed_db = PubMedDatabaseManager()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkerDatabaseManager()
        self.embeddings_db = EmbeddingsDatabaseManager()

        # Statistics
        self.stats = {
            'files_processed': 0,
            'articles_reprocessed': 0,
            'corrupted_found': 0,
            'records_updated': 0,
            'chunks_deleted': 0,
            'chunks_created': 0,
            'embeddings_deleted': 0,
            'embeddings_created': 0,
            'errors': 0
        }

        logger.info(f"Initialized CorruptImportFixer with XML directory: {xml_dir}")

    def get_xml_files(self) -> Generator[str, None, None]:
        """
        Get XML files to process as a generator.

        Yields:
            str: XML file paths
        """
        if not os.path.exists(self.xml_dir):
            logger.error(f"XML directory does not exist: {self.xml_dir}")
            return

        # Get all XML files and sort them
        xml_files = []
        for filename in os.listdir(self.xml_dir):
            if filename.endswith('.xml.gz'):
                xml_files.append(os.path.join(self.xml_dir, filename))

        xml_files.sort()
        logger.info(f"Found {len(xml_files)} XML files to process")

        # Yield files one by one
        for xml_file in xml_files:
            yield xml_file

    def process_xml_file(self, xml_file_path: str) -> List[Dict[str, Any]]:
        """
        Re-process a PubMed XML file using the fixed import function.

        Args:
            xml_file_path: Path to the XML file

        Returns:
            List of article data dictionaries
        """
        articles = []

        try:
            with gzip.open(xml_file_path, 'rb') as f:
                # Use iterparse to avoid loading entire file into memory
                context = ET.iterparse(f, events=('end',))

                for _, elem in context:
                    if elem.tag == 'PubmedArticle':
                        article_data = process_article(elem)
                        if article_data:
                            articles.append(article_data)

                        # Clear element to free up memory
                        elem.clear()

        except Exception as e:
            logger.error(f"Error processing XML file {xml_file_path}: {e}")
            self.stats['errors'] += 1

        return articles

    def compare_articles(self, new_article: Dict[str, Any], existing_article: Dict[str, Any]) -> Dict[str, bool]:
        """
        Compare new article data with existing database record.

        Args:
            new_article: Newly processed article data
            existing_article: Existing database record

        Returns:
            Dictionary indicating which fields differ
        """
        differences = {}

        # Fields to compare
        fields_to_compare = ['title', 'abstract', 'authors', 'journal', 'mesh_terms', 'keywords', 'doi']

        for field in fields_to_compare:
            new_value = new_article.get(field, '')

            # Handle different field names in database
            if field == 'journal':
                existing_value = existing_article.get('publication', '')
            elif field == 'authors':
                # Convert array back to string for comparison
                existing_authors = existing_article.get('authors', [])
                existing_value = ', '.join(existing_authors) if existing_authors else ''
            elif field == 'mesh_terms':
                # Convert array back to string for comparison
                existing_mesh = existing_article.get('mesh_terms', [])
                existing_value = ', '.join(existing_mesh) if existing_mesh else ''
            elif field == 'keywords':
                # Convert array back to string for comparison
                existing_keywords = existing_article.get('keywords', [])
                existing_value = ', '.join(existing_keywords) if existing_keywords else ''
            else:
                existing_value = existing_article.get(field, '')

            # Compare values (normalize whitespace)
            new_normalized = ' '.join(str(new_value).split()) if new_value else ''
            existing_normalized = ' '.join(str(existing_value).split()) if existing_value else ''

            differences[field] = new_normalized != existing_normalized

        return differences

    def update_corrupted_record(self, pmid: str, new_article: Dict[str, Any],
                               differences: Dict[str, bool]) -> bool:
        """
        Update a corrupted record in the database.

        Args:
            pmid: PubMed ID
            new_article: Corrected article data
            differences: Fields that need updating

        Returns:
            True if update was successful
        """
        try:
            # Get the document ID
            existing_doc = self.document_db.get_document_by_external_id('pubmed', pmid)
            if not existing_doc:
                logger.error(f"Could not find document for PMID {pmid}")
                return False

            document_id = existing_doc['id']

            # Build update query dynamically based on differences
            update_fields = []
            params = []

            if differences.get('title'):
                update_fields.append('title = %s')
                params.append(new_article.get('title', ''))

            if differences.get('abstract'):
                update_fields.append('abstract = %s')
                params.append(new_article.get('abstract', ''))

            if differences.get('authors'):
                update_fields.append('authors = %s')
                authors_str = new_article.get('authors', '')
                authors_array = authors_str.split(', ') if authors_str else []
                params.append(authors_array)

            if differences.get('journal'):
                update_fields.append('publication = %s')
                params.append(new_article.get('journal', ''))

            if differences.get('mesh_terms'):
                update_fields.append('mesh_terms = %s')
                mesh_str = new_article.get('mesh_terms', '')
                mesh_array = mesh_str.split(', ') if mesh_str else []
                params.append(mesh_array)

            if differences.get('keywords'):
                update_fields.append('keywords = %s')
                keywords_str = new_article.get('keywords', '')
                keywords_array = keywords_str.split(', ') if keywords_str else []
                params.append(keywords_array)

            if differences.get('doi'):
                update_fields.append('doi = %s')
                params.append(new_article.get('doi', ''))

            if not update_fields:
                logger.warning(f"No fields to update for PMID {pmid}")
                return True

            # Add updated timestamp
            update_fields.append('updated_date = CURRENT_TIMESTAMP')

            # Build and execute update query
            query = f"""
            UPDATE document
            SET {', '.join(update_fields)}
            WHERE id = %s
            """
            params.append(document_id)

            result = self.document_db.execute(query, params, commit=True)

            if result is not None:  # execute returns None on error, empty list on success
                logger.info(f"Updated corrupted record for PMID {pmid}")
                self.stats['records_updated'] += 1
                return True
            else:
                logger.error(f"Failed to update record for PMID {pmid}")
                return False

        except Exception as e:
            logger.error(f"Error updating record for PMID {pmid}: {e}")
            self.stats['errors'] += 1
            return False

    def delete_old_chunks_and_embeddings(self, document_id: int) -> Tuple[int, int]:
        """
        Delete old chunks and embeddings for a document.

        Args:
            document_id: Document ID

        Returns:
            Tuple of (chunks_deleted, embeddings_deleted)
        """
        chunks_deleted = 0
        embeddings_deleted = 0

        try:
            # Get existing chunks for this document
            chunks = list(self.chunker_db.get_chunks_for_document(document_id))

            for chunk in chunks:
                chunk_id = chunk.id

                # Delete embeddings for this chunk
                deleted_emb = self.delete_embeddings_for_chunk(chunk_id)
                embeddings_deleted += deleted_emb

                # Delete the chunk
                if self.delete_chunk(chunk_id):
                    chunks_deleted += 1

            self.stats['chunks_deleted'] += chunks_deleted
            self.stats['embeddings_deleted'] += embeddings_deleted

            logger.debug(f"Deleted {chunks_deleted} chunks and {embeddings_deleted} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error deleting chunks/embeddings for document {document_id}: {e}")
            self.stats['errors'] += 1

        return chunks_deleted, embeddings_deleted

    def delete_embeddings_for_chunk(self, chunk_id: int) -> int:
        """
        Delete embeddings for a specific chunk.

        Args:
            chunk_id: Chunk ID

        Returns:
            Number of embeddings deleted
        """
        try:
            # Delete from all embedding tables (emb_768, emb_1024, etc.)
            # Use the base table which will cascade to inherited tables
            query = "DELETE FROM embedding_base WHERE chunk_id = %s"
            result = self.embeddings_db.execute(query, (chunk_id,), commit=True)

            # Count deleted rows (PostgreSQL DELETE doesn't return count directly)
            # We'll assume 1 embedding per chunk for now
            return 1 if result is not None else 0

        except Exception as e:
            logger.error(f"Error deleting embeddings for chunk {chunk_id}: {e}")
            return 0

    def delete_chunk(self, chunk_id: int) -> bool:
        """
        Delete a specific chunk.

        Args:
            chunk_id: Chunk ID

        Returns:
            True if successful
        """
        try:
            query = "DELETE FROM chunks WHERE id = %s"
            result = self.chunker_db.execute(query, (chunk_id,), commit=True)
            return result is not None

        except Exception as e:
            logger.error(f"Error deleting chunk {chunk_id}: {e}")
            return False

    def store_chunk_embedding(self, chunk_id: int, model_id: int, embedding: List[float]) -> bool:
        """
        Store an embedding for a chunk.

        Args:
            chunk_id: Chunk ID
            model_id: Model ID
            embedding: Embedding vector

        Returns:
            True if successful
        """
        try:
            # Use the existing add_embedding method
            result = self.embeddings_db.add_embedding(chunk_id, model_id, embedding)
            return result > 0

        except Exception as e:
            logger.error(f"Error storing embedding for chunk {chunk_id}: {e}")
            return False

    def rechunk_abstract(self, document_id: int, title: str, abstract: str) -> int:
        """
        Re-chunk an updated abstract.

        Args:
            document_id: Document ID
            title: Document title
            abstract: Updated abstract text

        Returns:
            Number of chunks created
        """
        chunks_created = 0

        try:
            # Use the adaptive chunker similar to the existing chunking process
            from embeddingexperiments.chunk_abstracts import AdaptiveTextChunker

            chunker = AdaptiveTextChunker(
                single_chunk_threshold=2000,
                max_chunk_size=384,
                overlap=128,
                min_chunk_size=50
            )

            # Create chunks
            chunk_data = chunker.chunk_text(abstract, title)

            # Store chunks in database
            for i, (chunk_text, metadata) in enumerate(chunk_data):
                try:
                    # Create chunk object
                    from localknowledge.db.chunker import Chunk

                    chunk = Chunk(
                        document_id=document_id,
                        chunking_strategy_id=1,  # adaptive_splitter strategy
                        chunktype_id=1,  # abstract type
                        text=chunk_text,
                        document_title=title,
                        chunklength=len(chunk_text),
                        chunk_no=i,
                        page_start=0,
                        page_end=0,
                        metadata=metadata
                    )

                    chunk_id = self.chunker_db.create_chunk(chunk)
                    if chunk_id:
                        chunks_created += 1
                        logger.debug(f"Created chunk {i} for document {document_id}")

                except Exception as e:
                    logger.error(f"Error creating chunk {i} for document {document_id}: {e}")
                    self.stats['errors'] += 1

            self.stats['chunks_created'] += chunks_created
            logger.debug(f"Created {chunks_created} chunks for document {document_id}")

        except Exception as e:
            logger.error(f"Error re-chunking abstract for document {document_id}: {e}")
            self.stats['errors'] += 1

        return chunks_created

    def reembed_chunks(self, document_id: int) -> int:
        """
        Re-embed chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of embeddings created
        """
        embeddings_created = 0

        try:
            # Get chunks for this document
            chunks = list(self.chunker_db.get_chunks_for_document(document_id))

            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return 0

            # Use PubMedBERT for embedding (model_id=3)
            from embeddingexperiments.pubmedbert import PubMedBERT

            bert_model = PubMedBERT()

            # Process chunks in batches
            chunk_batch = []
            chunk_ids = []

            for chunk in chunks:
                chunk_batch.append(chunk.text)
                chunk_ids.append(chunk.id)

                # Process batch when it reaches a reasonable size
                if len(chunk_batch) >= 10:
                    embeddings = bert_model.embed_batch(chunk_batch)

                    # Store embeddings
                    for chunk_id, embedding in zip(chunk_ids, embeddings):
                        if len(embedding) > 0:
                            success = self.store_chunk_embedding(
                                chunk_id=chunk_id,
                                model_id=3,  # PubMedBERT model ID
                                embedding=embedding
                            )
                            if success:
                                embeddings_created += 1

                    # Reset batch
                    chunk_batch = []
                    chunk_ids = []

            # Process remaining chunks
            if chunk_batch:
                embeddings = bert_model.embed_batch(chunk_batch)

                for chunk_id, embedding in zip(chunk_ids, embeddings):
                    if len(embedding) > 0:
                        success = self.store_chunk_embedding(
                            chunk_id=chunk_id,
                            model_id=3,  # PubMedBERT model ID
                            embedding=embedding
                        )
                        if success:
                            embeddings_created += 1

            self.stats['embeddings_created'] += embeddings_created
            logger.debug(f"Created {embeddings_created} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error re-embedding chunks for document {document_id}: {e}")
            self.stats['errors'] += 1

        return embeddings_created

    def process_batch(self, articles: List[Dict[str, Any]]) -> None:
        """
        Process a batch of articles to identify and fix corruption.

        Args:
            articles: List of re-processed article data
        """
        for article in articles:
            pmid = article.get('pmid')
            if not pmid:
                continue

            try:
                # Get existing record from database
                existing_article = self.pubmed_db.get_article_by_pmid(pmid)

                if not existing_article:
                    logger.warning(f"PMID {pmid} not found in database")
                    continue

                # Compare articles
                differences = self.compare_articles(article, existing_article)

                # Check if any fields are different
                if any(differences.values()):
                    logger.info(f"Found corruption in PMID {pmid}: {[k for k, v in differences.items() if v]}")
                    self.stats['corrupted_found'] += 1

                    # Update the record
                    if self.update_corrupted_record(pmid, article, differences):
                        document_id = existing_article['id']

                        # If abstract was updated, re-chunk and re-embed
                        if differences.get('abstract'):
                            logger.info(f"Re-processing chunks and embeddings for PMID {pmid}")

                            # Delete old chunks and embeddings
                            self.delete_old_chunks_and_embeddings(document_id)

                            # Re-chunk the abstract
                            chunks_created = self.rechunk_abstract(
                                document_id,
                                article.get('title', ''),
                                article.get('abstract', '')
                            )

                            # Re-embed the chunks
                            if chunks_created > 0:
                                self.reembed_chunks(document_id)

                self.stats['articles_reprocessed'] += 1

            except Exception as e:
                logger.error(f"Error processing article with PMID {pmid}: {e}")
                self.stats['errors'] += 1

    def run_fix(self, max_files: Optional[int] = None, dry_run: bool = False) -> None:
        """
        Run the corruption fix process.

        Args:
            max_files: Maximum number of files to process (None for all)
            dry_run: If True, only identify corruption without fixing
        """
        logger.info("Starting corrupt PubMed import fix process")
        logger.info(f"XML directory: {self.xml_dir}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Dry run: {dry_run}")

        # Get XML files to process
        xml_files_generator = self.get_xml_files()

        # Process files with progress bar
        start_time = time.time()
        files_processed_count = 0

        # Use tqdm without total since we don't know the count in advance
        with tqdm(desc="Processing XML files", unit="file") as pbar:
            for xml_file in xml_files_generator:
                # Check max_files limit
                if max_files and files_processed_count >= max_files:
                    logger.info(f"Reached max_files limit of {max_files}")
                    break
                try:
                    logger.info(f"Processing file: {os.path.basename(xml_file)}")

                    # Re-process the XML file
                    articles = self.process_xml_file(xml_file)

                    if not articles:
                        logger.warning(f"No articles found in {xml_file}")
                        files_processed_count += 1
                        self.stats['files_processed'] += 1
                        pbar.update(1)
                        continue

                    # Process articles in batches
                    for i in range(0, len(articles), self.batch_size):
                        batch = articles[i:i + self.batch_size]

                        if not dry_run:
                            self.process_batch(batch)
                        else:
                            # In dry run mode, just identify corruption
                            for article in batch:
                                pmid = article.get('pmid')
                                if pmid:
                                    existing_article = self.pubmed_db.get_article_by_pmid(pmid)
                                    if existing_article:
                                        differences = self.compare_articles(article, existing_article)
                                        if any(differences.values()):
                                            logger.info(f"[DRY RUN] Would fix corruption in PMID {pmid}: {[k for k, v in differences.items() if v]}")
                                            self.stats['corrupted_found'] += 1
                                    self.stats['articles_reprocessed'] += 1

                    files_processed_count += 1
                    self.stats['files_processed'] += 1
                    pbar.update(1)

                    # Log progress every 10 files
                    if self.stats['files_processed'] % 10 == 0:
                        self.log_progress()

                except Exception as e:
                    logger.error(f"Error processing file {xml_file}: {e}")
                    files_processed_count += 1
                    self.stats['errors'] += 1
                    pbar.update(1)

        # Final statistics
        end_time = time.time()
        duration = end_time - start_time

        logger.info("=" * 60)
        logger.info("CORRUPTION FIX COMPLETED")
        logger.info("=" * 60)
        self.log_final_stats(duration, dry_run)

    def log_progress(self) -> None:
        """Log current progress statistics."""
        logger.info(f"Progress: {self.stats['files_processed']} files, "
                   f"{self.stats['articles_reprocessed']} articles, "
                   f"{self.stats['corrupted_found']} corrupted found, "
                   f"{self.stats['records_updated']} updated")

    def log_final_stats(self, duration: float, dry_run: bool) -> None:
        """
        Log final statistics.

        Args:
            duration: Total processing time in seconds
            dry_run: Whether this was a dry run
        """
        mode = "DRY RUN" if dry_run else "ACTUAL FIX"

        logger.info(f"Mode: {mode}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Articles reprocessed: {self.stats['articles_reprocessed']}")
        logger.info(f"Corrupted records found: {self.stats['corrupted_found']}")

        if not dry_run:
            logger.info(f"Records updated: {self.stats['records_updated']}")
            logger.info(f"Chunks deleted: {self.stats['chunks_deleted']}")
            logger.info(f"Chunks created: {self.stats['chunks_created']}")
            logger.info(f"Embeddings deleted: {self.stats['embeddings_deleted']}")
            logger.info(f"Embeddings created: {self.stats['embeddings_created']}")

        logger.info(f"Errors: {self.stats['errors']}")

        if self.stats['corrupted_found'] > 0:
            corruption_rate = (self.stats['corrupted_found'] / self.stats['articles_reprocessed']) * 100
            logger.info(f"Corruption rate: {corruption_rate:.2f}%")

    def close(self) -> None:
        """Close database connections."""
        try:
            self.pubmed_db.close()
            self.document_db.close()
            self.chunker_db.close()
            self.embeddings_db.close()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Fix corrupt PubMed imports due to abstract truncation bug",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # RECOMMENDED: Test first with the test module
  python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml

  # Dry run to identify corruption
  python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --dry-run

  # Fix corruption in first 10 files
  python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --max-files 10

  # Fix all corruption with larger batch size
  python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --batch-size 2000

IMPORTANT: Always test first using test_fix_corrupt_pubmed_imports.py before running
the actual fix to avoid unintended database modifications.
        """
    )

    parser.add_argument(
        '--xml-dir',
        required=True,
        help='Directory containing PubMed XML files'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of records to process in each batch (default: 1000)'
    )

    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of XML files to process (default: all)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only identify corruption without fixing (default: False)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Safety check - require confirmation for non-dry-run operations
    if not args.dry_run:
        print("\n" + "="*60)
        print("WARNING: This will modify the live database!")
        print("="*60)
        print("This operation will:")
        print("- Update corrupted records in the database")
        print("- Delete and recreate chunks and embeddings")
        print("- Make permanent changes to your data")
        print("\nRECOMMENDED: Run the test module first:")
        print("python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir", args.xml_dir)
        print("\nOr run with --dry-run to see what would be changed without making changes.")
        print("="*60)

        confirmation = input("\nAre you sure you want to proceed with live database modifications? (yes/no): ")
        if confirmation.lower() not in ['yes', 'y']:
            print("Operation cancelled.")
            return

    # Create and run the fixer
    fixer = CorruptImportFixer(
        xml_dir=args.xml_dir,
        batch_size=args.batch_size
    )

    try:
        fixer.run_fix(
            max_files=args.max_files,
            dry_run=args.dry_run
        )
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        fixer.close()


if __name__ == "__main__":
    main()
