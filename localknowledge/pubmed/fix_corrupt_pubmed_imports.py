#!/usr/bin/env python3
"""
Fix Corrupt PubMed Imports Module

This module identifies and fixes PubMed records that were corrupted during import
due to the abstract truncation bug. It intelligently distinguishes between legitimate
article updates and data corruption using revision dates and other metadata.

The process:
1. Re-process XML files using the fixed import_downloads.process_article function
2. Compare with existing database records using intelligent update detection:
   - Check revision dates to identify legitimate updates vs corruption
   - For legitimate updates: Accept XML version regardless of length
   - For suspected corruption: Use length-based detection with user confirmation
3. Update corrupted/revised records in the database
4. Delete old chunks and embeddings for updated records
5. Re-chunk updated abstracts
6. Re-embed the new chunks

Key improvements:
- Uses date_revised from XML to detect legitimate article updates
- Distinguishes between article revisions and data corruption
- Provides better user prompts with context about update vs corruption
- Automatically accepts longer versions as corruption fixes
- Special handling for MeSH terms (always keeps longer version)

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
from typing import Dict, Any, List, Optional, Tuple, Generator
from tqdm import tqdm

# Add the parent directory to the path to import localknowledge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from localknowledge.pubmed.import_downloads import process_article
from localknowledge.db.pubmed import PubMedDatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.db.embeddings import EmbeddingsDatabaseManager
from localknowledge.db.import_tracker import ImportTracker

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

    def __init__(self, xml_dir: str, batch_size: int = 1000, force_all_files: bool = False):
        """
        Initialize the corrupt import fixer.

        Args:
            xml_dir: Directory containing PubMed XML files
            batch_size: Number of records to process in each batch
            force_all_files: If True, process all XML files regardless of import tracker status
        """
        self.xml_dir = xml_dir
        self.batch_size = batch_size
        self.force_all_files = force_all_files

        # Initialize database managers
        self.pubmed_db = PubMedDatabaseManager()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkingDatabaseManager()
        self.embeddings_db = EmbeddingsDatabaseManager()
        self.import_tracker = ImportTracker()

        # Get available embedding models
        self.embedding_models = self._get_embedding_models()

        # Initialize embedders once at startup for efficiency
        self.embedders = {}
        self._initialize_embedders()

        # Statistics
        self.stats = {
            'files_processed': 0,
            'total_files': 0,
            'articles_reprocessed': 0,
            'corrupted_found': 0,
            'records_updated': 0,
            'chunks_deleted': 0,
            'chunks_created': 0,
            'embeddings_deleted': 0,
            'embeddings_created': 0,
            'errors': 0,
            'titles_updated': 0,
            'abstracts_updated': 0,
            'mesh_updated': 0,
            'dois_updated': 0,
            'authors_updated': 0,
            'journals_updated': 0,
            'keywords_updated': 0
        }

        logger.info(f"Initialized CorruptImportFixer with XML directory: {xml_dir}")
        logger.info(f"Available embedding models: {self.embedding_models}")
        logger.info(f"Initialized embedders: {list(self.embedders.keys())}")

    def _get_embedding_models(self) -> List[Dict[str, Any]]:
        """
        Get available embedding models from the database.

        Returns:
            List of embedding model dictionaries with id and model_name
        """
        try:
            # Get models that have embeddings in the database
            models_dict = self.embeddings_db.get_models_with_embeddings()

            # Convert to list format expected by the rest of the code
            models_list = []
            for model_id, model_name in models_dict.items():
                models_list.append({'id': model_id, 'model_name': model_name})

            if not models_list:
                logger.warning("No embedding models found in database, using defaults")
                # Fallback to known models
                models_list = [
                    {'id': 1, 'model_name': 'snowflake-arctic-embed2:latest'},
                    {'id': 2, 'model_name': 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext'}
                ]

            return models_list

        except Exception as e:
            logger.error(f"Error getting embedding models: {e}")
            # Fallback to known models
            return [
                {'id': 1, 'model_name': 'snowflake-arctic-embed2:latest'},
                {'id': 2, 'model_name': 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext'}
            ]

    def _initialize_embedders(self) -> None:
        """
        Initialize all embedders once at startup for efficiency.
        This prevents re-initializing models (especially PubMedBERT) multiple times.
        """
        logger.info("Initializing embedders for all available models...")

        for model_info in self.embedding_models:
            model_name = model_info['model_name']
            logger.info(f"Initializing embedder for model: {model_name}")

            try:
                embedder = self._create_embedder_for_model(model_name)
                if embedder:
                    self.embedders[model_name] = embedder
                    logger.info(f"Successfully initialized embedder for {model_name}")
                else:
                    logger.warning(f"Failed to initialize embedder for {model_name}")

            except Exception as e:
                logger.error(f"Error initializing embedder for {model_name}: {e}")

        logger.info(f"Embedder initialization complete. Available embedders: {list(self.embedders.keys())}")

    def _create_embedder_for_model(self, model_name: str):
        """
        Create the appropriate embedder instance for a model.

        Args:
            model_name: Name of the embedding model

        Returns:
            Embedder instance or None if not supported
        """
        try:
            if 'snowflake-arctic-embed' in model_name.lower() or 'ollama' in model_name.lower():
                # Use Ollama embedder for snowflake and other Ollama models
                from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
                logger.info(f"Creating OllamaEmbedder for model: {model_name}")
                return OllamaEmbedder(model_name=model_name)

            elif 'pubmedbert' in model_name.lower() or 'biomedbert' in model_name.lower():
                # Use PubMedBERT embedder for biomedical models
                from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder
                logger.info(f"Creating PubMedBERTEmbedder for model: {model_name}")
                return PubMedBERTEmbedder()

            else:
                logger.warning(f"No embedder available for model: {model_name}")
                return None

        except Exception as e:
            logger.error(f"Error creating embedder for model {model_name}: {e}")
            return None

    def _get_embedder_for_model(self, model_name: str):
        """
        Get the cached embedder instance for a model.

        Args:
            model_name: Name of the embedding model

        Returns:
            Cached embedder instance or None if not available
        """
        embedder = self.embedders.get(model_name)
        if not embedder:
            logger.warning(f"No cached embedder found for model: {model_name}")
        return embedder

    def _select_latest_version(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the latest version from multiple articles with the same PMID.

        Uses DOI version number to determine the latest version.

        Args:
            articles: List of articles with the same PMID

        Returns:
            The article with the highest version number
        """
        if len(articles) == 1:
            return articles[0]

        # Sort by DOI version number (extract version from DOI like "10.12688/f1000research.6085.2")
        def get_version_number(article):
            doi = article.get('doi', '')
            if not doi:
                return 0

            # Try to extract version number from DOI
            try:
                # Look for pattern like ".1", ".2", etc. at the end of DOI
                parts = doi.split('.')
                if len(parts) >= 2:
                    # Try to parse the last part as a version number
                    last_part = parts[-1]
                    if last_part.isdigit():
                        return int(last_part)
            except (AttributeError, IndexError, ValueError):
                pass

            return 0

        # Sort articles by version number (highest first)
        sorted_articles = sorted(articles, key=get_version_number, reverse=True)
        latest = sorted_articles[0]

        logger.debug(f"Selected version with DOI: {latest.get('doi', '')} from {len(articles)} versions")
        return latest

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

        # Determine which files to process
        if self.force_all_files:
            # Process all XML files regardless of import tracker status
            files_to_process = xml_files
            self.stats['total_files'] = len(files_to_process)
            logger.info(f"Found {len(xml_files)} XML files total, processing ALL files (force_all_files=True)")
        else:
            # Filter to only include files that have been imported (since we're fixing imports)
            imported_files = []
            for xml_file in xml_files:
                filename = os.path.basename(xml_file)
                if self.import_tracker.is_file_imported(filename):
                    imported_files.append(xml_file)

            files_to_process = imported_files
            self.stats['total_files'] = len(imported_files)
            logger.info(f"Found {len(xml_files)} XML files total, {len(imported_files)} have been imported and will be processed for corruption fixes")

            # If no files are marked as imported, provide helpful debugging information
            if len(imported_files) == 0 and len(xml_files) > 0:
                logger.warning("No XML files are marked as imported in the import tracker!")
                logger.info("This could mean:")
                logger.info("1. Files were imported before the import tracker system was implemented")
                logger.info("2. The import tracker table is missing entries for these files")
                logger.info("3. The files haven't actually been imported yet")

                # Show import tracker statistics
                stats = self.import_tracker.get_processing_stats()
                logger.info(f"Import tracker statistics: {stats}")

                # Show a few example filenames for debugging
                example_files = [os.path.basename(f) for f in xml_files[:5]]
                logger.info(f"Example XML filenames: {example_files}")

                # Check if any of these files exist in the import tracker at all
                for filename in example_files:
                    try:
                        results = self.import_tracker.execute(
                            "SELECT filename, imported, chunked, embedded FROM import_tracker WHERE filename = %s",
                            (filename,)
                        )
                        if results:
                            logger.info(f"File {filename} in tracker: {results[0]}")
                        else:
                            logger.info(f"File {filename} NOT found in import tracker")
                    except Exception as e:
                        logger.error(f"Error checking {filename} in tracker: {e}")

                logger.info("To fix this, you may need to:")
                logger.info("1. Run the import process first to populate the import tracker")
                logger.info("2. Or manually mark files as imported if they were imported before the tracker existed")
                logger.info("3. Or use --force-all-files flag to process all files regardless of tracker status")

        # Yield files one by one
        for xml_file in files_to_process:
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

    def compare_articles(self, new_article: Dict[str, Any], existing_article: Dict[str, Any]) -> Tuple[Dict[str, bool], Dict[str, str]]:
        """
        Compare new article data with existing database record.
        Uses revision date and intelligent heuristics to distinguish between legitimate updates and corruption.

        Logic:
        1. Check if XML has a revision date newer than database record - indicates legitimate update
        2. For legitimate updates: Accept XML version regardless of length
        3. For potential corruption: Use length-based detection with user confirmation for shorter versions
        4. Special handling for MeSH terms: Always keep longer version without confirmation

        Args:
            new_article: Newly processed article data
            existing_article: Existing database record

        Returns:
            Tuple of (differences dict, user_decisions dict)
            - differences: Dictionary indicating which fields differ and should be updated
            - user_decisions: Dictionary of user decisions for ambiguous cases
        """
        differences = {}
        user_decisions = {}

        # Check if this is a legitimate update based on revision dates
        is_legitimate_update = self._is_legitimate_update(new_article, existing_article)
        pmid = new_article.get('pmid', 'unknown')

        if is_legitimate_update:
            logger.info(f"PMID {pmid}: Detected legitimate update based on revision date")
        else:
            logger.debug(f"PMID {pmid}: No clear update indication, using corruption detection logic")

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
                # Note: Database stores as array split by '; ' but process_article returns comma-separated
                existing_mesh = existing_article.get('mesh_terms', [])
                existing_value = ', '.join(existing_mesh) if existing_mesh else ''
            elif field == 'keywords':
                # Convert array back to string for comparison
                # Note: Database stores as array split by '; ' but process_article returns comma-separated
                existing_keywords = existing_article.get('keywords', [])
                existing_value = ', '.join(existing_keywords) if existing_keywords else ''
            else:
                existing_value = existing_article.get(field, '')

            # Compare values (normalize whitespace and handle empty values)
            new_normalized = ' '.join(str(new_value).split()) if new_value else ''
            existing_normalized = ' '.join(str(existing_value).split()) if existing_value else ''

            # Special handling for mesh_terms and keywords to account for separator differences
            if field in ['mesh_terms', 'keywords']:
                # Normalize separators: convert both to comma-separated and compare
                if new_normalized:
                    # Split by various separators and rejoin with comma-space
                    new_parts = [part.strip() for part in new_normalized.replace(';', ',').split(',') if part.strip()]
                    new_normalized = ', '.join(new_parts)
                if existing_normalized:
                    # Split by various separators and rejoin with comma-space
                    existing_parts = [part.strip() for part in existing_normalized.replace(';', ',').split(',') if part.strip()]
                    existing_normalized = ', '.join(existing_parts)

            # Check if values are different
            if new_normalized != existing_normalized:
                new_len = len(new_normalized)
                existing_len = len(existing_normalized)

                if is_legitimate_update:
                    # For legitimate updates, accept XML version regardless of length
                    differences[field] = True
                    logger.info(f"Field '{field}' updated in legitimate revision: XML ({new_len} chars) vs DB ({existing_len} chars)")
                else:
                    # Use corruption detection logic
                    if new_len > existing_len:
                        # New version is longer - likely corruption fix
                        differences[field] = True
                        logger.info(f"Field '{field}' corruption detected: XML version is longer ({new_len} vs {existing_len} chars)")
                    elif new_len < existing_len:
                        # New version is shorter - suspicious, could be corruption or legitimate update
                        if field == 'mesh_terms':
                            # For MeSH terms, always keep the longer version without asking
                            differences[field] = False  # Keep existing (longer) version
                            logger.info(f"Field '{field}': Keeping existing longer version ({existing_len} vs {new_len} chars) - MeSH terms auto-decision")
                        else:
                            # For other fields, ask user for confirmation
                            decision = self._ask_user_for_replacement_decision(
                                pmid, field, new_normalized, existing_normalized, is_legitimate_update
                            )
                            user_decisions[field] = decision
                            differences[field] = (decision == 'accept')
                    else:
                        # Same length but different content - assume new is correct
                        differences[field] = True
                        logger.info(f"Field '{field}' content differs (same length {new_len} chars)")
            else:
                differences[field] = False

        return differences, user_decisions

    def _is_legitimate_update(self, new_article: Dict[str, Any], existing_article: Dict[str, Any]) -> bool:
        """
        Determine if the XML article represents a legitimate update vs potential corruption.

        Uses revision dates and other metadata to make this determination.

        Args:
            new_article: Newly processed article data from XML
            existing_article: Existing database record

        Returns:
            True if this appears to be a legitimate update, False otherwise
        """
        try:
            # Get revision dates
            xml_date_revised = new_article.get('date_revised')

            # If XML has no revision date, we can't determine if it's an update
            if not xml_date_revised:
                return False

            # Get the database record's updated_date (when it was last modified)
            # This is the best proxy we have for when the record was last updated from XML
            db_updated_date = existing_article.get('updated_date')

            if not db_updated_date:
                # If no database update date, assume XML might be newer
                logger.debug(f"No database update date available, cannot determine update status")
                return False

            # Convert dates to comparable format
            from datetime import datetime

            try:
                # Parse XML revision date (format: YYYY-MM-DD)
                xml_date = datetime.strptime(xml_date_revised, '%Y-%m-%d').date()

                # Parse database updated date (could be datetime or date)
                if isinstance(db_updated_date, str):
                    # Try to parse string date
                    if 'T' in db_updated_date or ' ' in db_updated_date:
                        # Datetime format
                        db_date = datetime.fromisoformat(db_updated_date.replace('T', ' ').split('.')[0]).date()
                    else:
                        # Date format
                        db_date = datetime.strptime(db_updated_date, '%Y-%m-%d').date()
                else:
                    # Assume it's already a date or datetime object
                    db_date = db_updated_date.date() if hasattr(db_updated_date, 'date') else db_updated_date

                # If XML revision date is newer than database update date, it's likely a legitimate update
                is_update = xml_date > db_date

                if is_update:
                    logger.info(f"Legitimate update detected: XML revised {xml_date} > DB updated {db_date}")
                else:
                    logger.debug(f"No update detected: XML revised {xml_date} <= DB updated {db_date}")

                return is_update

            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing dates for update detection: {e}")
                logger.debug(f"XML date_revised: '{xml_date_revised}', DB updated_date: '{db_updated_date}'")
                return False

        except Exception as e:
            logger.error(f"Error in update detection: {e}")
            return False

    def _ask_user_for_replacement_decision(self, pmid: str, field: str,
                                         new_value: str, existing_value: str,
                                         is_legitimate_update: bool = False) -> str:
        """
        Ask user whether to accept a replacement when XML version is shorter.

        Args:
            pmid: PubMed ID
            field: Field name
            new_value: New (shorter) value from XML
            existing_value: Existing (longer) value from database
            is_legitimate_update: Whether this appears to be a legitimate update

        Returns:
            'accept' or 'reject'
        """
        print("\n" + "="*80)
        if is_legitimate_update:
            print(f"📝 LEGITIMATE UPDATE with SHORTER CONTENT for PMID {pmid}")
            print("="*80)
            print("This appears to be a legitimate article update based on revision dates,")
            print("but the XML version is shorter than the database version.")
            print("This could be:")
            print("  • Legitimate content revision (author shortened abstract/title)")
            print("  • Correction or retraction")
            print("  • Data corruption during processing")
        else:
            print(f"⚠️  SUSPICIOUS REPLACEMENT DETECTED for PMID {pmid}")
            print("="*80)
            print("No clear update indication found, and XML version is shorter.")
            print("This is likely data corruption, but could be a legitimate change.")

        print("="*80)
        print(f"Field: {field}")
        print(f"XML version is SHORTER than database version:")
        print(f"  XML length: {len(new_value)} characters")
        print(f"  DB length:  {len(existing_value)} characters")
        print()

        # Show truncated versions for readability
        max_display_len = 200

        print("XML version:")
        if len(new_value) <= max_display_len:
            print(f"  '{new_value}'")
        else:
            print(f"  '{new_value[:max_display_len]}...' (truncated)")
        print()

        print("Database version:")
        if len(existing_value) <= max_display_len:
            print(f"  '{existing_value}'")
        else:
            print(f"  '{existing_value[:max_display_len]}...' (truncated)")
        print()

        print("Options:")
        print("  (a)ccept - Replace database with XML version")
        if is_legitimate_update:
            print("  (r)eject - Keep database version (consider carefully for legitimate updates)")
        else:
            print("  (r)eject - Keep database version (default, recommended for suspected corruption)")
        print("="*80)

        while True:
            try:
                choice = input("Your choice [a/R]: ").strip().lower()
                if choice in ['a', 'accept']:
                    print(f"✓ Accepting XML version for {field}")
                    return 'accept'
                elif choice in ['r', 'reject', '']:
                    print(f"✓ Rejecting XML version for {field}")
                    return 'reject'
                else:
                    print("Please enter 'a' for accept or 'r' for reject")
            except (EOFError, KeyboardInterrupt):
                print("\n✓ Defaulting to reject")
                return 'reject'

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
                self.stats['titles_updated'] += 1

            if differences.get('abstract'):
                update_fields.append('abstract = %s')
                params.append(new_article.get('abstract', ''))
                self.stats['abstracts_updated'] += 1

            if differences.get('authors'):
                update_fields.append('authors = %s')
                authors_str = new_article.get('authors', '')
                authors_array = authors_str.split(', ') if authors_str else []
                params.append(authors_array)
                self.stats['authors_updated'] += 1

            if differences.get('journal'):
                update_fields.append('publication = %s')
                params.append(new_article.get('journal', ''))
                self.stats['journals_updated'] += 1

            if differences.get('mesh_terms'):
                update_fields.append('mesh_terms = %s')
                mesh_str = new_article.get('mesh_terms', '')
                mesh_array = mesh_str.split(', ') if mesh_str else []
                params.append(mesh_array)
                self.stats['mesh_updated'] += 1

            if differences.get('keywords'):
                update_fields.append('keywords = %s')
                keywords_str = new_article.get('keywords', '')
                keywords_array = keywords_str.split(', ') if keywords_str else []
                params.append(keywords_array)
                self.stats['keywords_updated'] += 1

            if differences.get('doi'):
                update_fields.append('doi = %s')
                new_doi_value = new_article.get('doi', '')
                params.append(new_doi_value)
                self.stats['dois_updated'] += 1
                logger.debug(f"Will update DOI for PMID {pmid} to: '{new_doi_value}'")

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

            logger.debug(f"Executing update query for PMID {pmid}: {query}")
            logger.debug(f"Update parameters: {params}")

            # Execute the update query
            # Note: For UPDATE queries without RETURNING clause, execute() returns None on success
            # and raises an exception on error
            self.document_db.execute(query, params, commit=True)

            logger.info(f"Updated corrupted record for PMID {pmid}")
            self.stats['records_updated'] += 1
            return True

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
            chunks = list(self.chunker_db.get_chunks_by_document(document_id))

            for chunk in chunks:
                chunk_id = chunk.chunk_id

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
            self.embeddings_db.execute(query, (chunk_id,), commit=True)

            # For DELETE queries without RETURNING clause, execute() returns None on success
            # We'll assume 1 embedding per chunk for now
            return 1

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
            self.chunker_db.execute(query, (chunk_id,), commit=True)
            # For DELETE queries without RETURNING clause, execute() returns None on success
            return True

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
            from localknowledge.textprocessing.chunking import AdaptiveTextChunker

            chunker = AdaptiveTextChunker(
                max_chunk_size=384,
                overlap=128,
                min_chunk_size=50
            )

            # Create chunks with metadata
            metadata = {'title': title}
            chunk_data = chunker.chunk(abstract, metadata=metadata)

            # Convert to database chunks
            db_chunks = []
            for i, chunk in enumerate(chunk_data):
                try:
                    # Create chunk object
                    from localknowledge.db.chunker import Chunk

                    db_chunk = Chunk(
                        chunk_id=0,  # Will be set by database
                        document_id=document_id,
                        chunking_strategy_id=1,  # adaptive_splitter strategy
                        chunktype_id=1,  # abstract type
                        text=chunk.text,
                        document_title=title,
                        chunklength=len(chunk.text),
                        chunk_no=i,
                        page_start=0,
                        page_end=0,
                        metadata=chunk.metadata
                    )
                    db_chunks.append(db_chunk)

                except Exception as e:
                    logger.error(f"Error creating chunk {i} for document {document_id}: {e}")
                    self.stats['errors'] += 1

            # Store chunks in database using batch insert for better performance
            if db_chunks:
                try:
                    chunk_ids = self.chunker_db.batch_insert_chunks(db_chunks)
                    chunks_created = len(chunk_ids)
                    logger.debug(f"Created {chunks_created} chunks for document {document_id}")
                except Exception as e:
                    logger.error(f"Error batch inserting chunks for document {document_id}: {e}")
                    self.stats['errors'] += 1

            self.stats['chunks_created'] += chunks_created
            logger.debug(f"Created {chunks_created} chunks for document {document_id}")

        except Exception as e:
            logger.error(f"Error re-chunking abstract for document {document_id}: {e}")
            self.stats['errors'] += 1

        return chunks_created

    def reembed_chunks(self, document_id: int) -> int:
        """
        Re-embed chunks for a document using all available embedding models.

        Args:
            document_id: Document ID

        Returns:
            Number of embeddings created
        """
        embeddings_created = 0

        try:
            # Get chunks for this document
            chunks = list(self.chunker_db.get_chunks_by_document(document_id))

            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return 0

            logger.info(f"Re-embedding {len(chunks)} chunks for document {document_id}")

            # Process each embedding model
            for model_info in self.embedding_models:
                model_id = model_info['id']
                model_name = model_info['model_name']

                logger.info(f"Creating embeddings with model {model_name} (ID: {model_id}) for {len(chunks)} chunks")

                try:
                    # Get the cached embedder instance
                    embedder = self._get_embedder_for_model(model_name)
                    if not embedder:
                        logger.warning(f"No cached embedder available for model {model_name}")
                        continue

                    # Process chunks in batches with progress tracking
                    chunk_batch = []
                    chunk_ids = []
                    model_embeddings_created = 0
                    batch_size = 10

                    for i, chunk in enumerate(chunks):
                        chunk_batch.append(chunk.text)
                        chunk_ids.append(chunk.chunk_id)

                        # Process batch when it reaches the specified size
                        if len(chunk_batch) >= batch_size:
                            logger.debug(f"Processing batch {i//batch_size + 1} for model {model_name}")
                            embeddings = embedder.embed_batch(chunk_batch)

                            # Store embeddings
                            for chunk_id, embedding in zip(chunk_ids, embeddings):
                                if len(embedding) > 0:
                                    success = self.store_chunk_embedding(
                                        chunk_id=chunk_id,
                                        model_id=model_id,
                                        embedding=embedding
                                    )
                                    if success:
                                        embeddings_created += 1
                                        model_embeddings_created += 1

                            # Reset batch
                            chunk_batch = []
                            chunk_ids = []

                    # Process remaining chunks
                    if chunk_batch:
                        logger.debug(f"Processing final batch for model {model_name}")
                        embeddings = embedder.embed_batch(chunk_batch)

                        for chunk_id, embedding in zip(chunk_ids, embeddings):
                            if len(embedding) > 0:
                                success = self.store_chunk_embedding(
                                    chunk_id=chunk_id,
                                    model_id=model_id,
                                    embedding=embedding
                                )
                                if success:
                                    embeddings_created += 1
                                    model_embeddings_created += 1

                    logger.info(f"Completed embeddings for model {model_name}: {model_embeddings_created} embeddings created")

                except Exception as e:
                    logger.error(f"Error creating embeddings with model {model_name}: {e}")
                    self.stats['errors'] += 1
                    continue

            self.stats['embeddings_created'] += embeddings_created
            logger.debug(f"Created {embeddings_created} total embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error re-embedding chunks for document {document_id}: {e}")
            self.stats['errors'] += 1

        return embeddings_created

    def process_batch(self, articles: List[Dict[str, Any]], xml_filename: str = None) -> None:
        """
        Process a batch of articles to identify and fix corruption.

        Handles duplicate PMIDs by only processing the latest version of each article.

        Args:
            articles: List of re-processed article data
            xml_filename: Optional filename for tracking purposes
        """
        # Group articles by PMID to handle duplicates
        articles_by_pmid = {}
        for article in articles:
            pmid = article.get('pmid')
            if not pmid:
                continue

            if pmid not in articles_by_pmid:
                articles_by_pmid[pmid] = []
            articles_by_pmid[pmid].append(article)

        # Process each unique PMID
        for pmid, pmid_articles in articles_by_pmid.items():
            try:
                # If multiple versions exist, choose the one with the highest DOI version number
                if len(pmid_articles) > 1:
                    dois = [a.get('doi', 'no DOI') for a in pmid_articles]
                    logger.info(f"Found {len(pmid_articles)} versions of PMID {pmid} with DOIs: {dois}")
                    article = self._select_latest_version(pmid_articles)
                    logger.info(f"Selected version with DOI: {article.get('doi', 'no DOI')}")
                else:
                    article = pmid_articles[0]

                # Get existing record from database
                existing_article = self.pubmed_db.get_article_by_pmid(pmid)

                if not existing_article:
                    logger.warning(f"PMID {pmid} not found in database")
                    continue

                # Compare articles
                differences, user_decisions = self.compare_articles(article, existing_article)

                # Check if any fields are different
                if any(differences.values()):
                    corrupted_fields = [k for k, v in differences.items() if v]
                    logger.info(f"Found corruption in PMID {pmid}: {corrupted_fields}")

                    # Log user decisions if any were made
                    if user_decisions:
                        for field, decision in user_decisions.items():
                            logger.info(f"User decision for {field}: {decision}")

                    # Add debug logging for DOI field specifically
                    if 'doi' in corrupted_fields:
                        new_doi = article.get('doi', '')
                        existing_doi = existing_article.get('doi', '')
                        logger.debug(f"DOI comparison for PMID {pmid}:")
                        logger.debug(f"  New DOI: '{new_doi}' (type: {type(new_doi)})")
                        logger.debug(f"  Existing DOI: '{existing_doi}' (type: {type(existing_doi)})")
                        logger.debug(f"  Normalized new: '{' '.join(str(new_doi).split()) if new_doi else ''}'")
                        logger.debug(f"  Normalized existing: '{' '.join(str(existing_doi).split()) if existing_doi else ''}'")

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
                                embeddings_created = self.reembed_chunks(document_id)

                                # Mark file as chunked and embedded in import tracker
                                if xml_filename:
                                    self.import_tracker.mark_file_chunked(xml_filename)
                                    if embeddings_created > 0:
                                        self.import_tracker.mark_file_embedded(xml_filename)

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

        # Use tqdm with total files count for better progress tracking
        with tqdm(total=self.stats['total_files'],
                 desc="Processing XML files",
                 unit="file",
                 bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} files [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
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
                            self.process_batch(batch, os.path.basename(xml_file))
                        else:
                            # In dry run mode, just identify corruption
                            for article in batch:
                                pmid = article.get('pmid')
                                if pmid:
                                    existing_article = self.pubmed_db.get_article_by_pmid(pmid)
                                    if existing_article:
                                        differences, _ = self.compare_articles(article, existing_article)
                                        if any(differences.values()):
                                            logger.info(f"[DRY RUN] Would fix corruption in PMID {pmid}: {[k for k, v in differences.items() if v]}")
                                            self.stats['corrupted_found'] += 1
                                    self.stats['articles_reprocessed'] += 1

                    files_processed_count += 1
                    self.stats['files_processed'] += 1
                    pbar.update(1)

                    # Update progress bar description with current stats
                    pbar.set_postfix({
                        'docs': self.stats['articles_reprocessed'],
                        'corrupt': self.stats['corrupted_found'],
                        'updated': self.stats['records_updated'],
                        'abs': self.stats['abstracts_updated'],
                        'titles': self.stats['titles_updated'],
                        'mesh': self.stats['mesh_updated'],
                        'dois': self.stats['dois_updated']
                    })

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
        logger.info(f"Progress: {self.stats['files_processed']}/{self.stats['total_files']} files, "
                   f"{self.stats['articles_reprocessed']} articles, "
                   f"{self.stats['corrupted_found']} corrupted found, "
                   f"{self.stats['records_updated']} updated")
        logger.info(f"Field updates: abstracts={self.stats['abstracts_updated']}, "
                   f"titles={self.stats['titles_updated']}, "
                   f"mesh={self.stats['mesh_updated']}, "
                   f"dois={self.stats['dois_updated']}, "
                   f"authors={self.stats['authors_updated']}, "
                   f"journals={self.stats['journals_updated']}, "
                   f"keywords={self.stats['keywords_updated']}")

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
            logger.info(f"Field updates breakdown:")
            logger.info(f"  - Abstracts: {self.stats['abstracts_updated']}")
            logger.info(f"  - Titles: {self.stats['titles_updated']}")
            logger.info(f"  - MeSH terms: {self.stats['mesh_updated']}")
            logger.info(f"  - DOIs: {self.stats['dois_updated']}")
            logger.info(f"  - Authors: {self.stats['authors_updated']}")
            logger.info(f"  - Journals: {self.stats['journals_updated']}")
            logger.info(f"  - Keywords: {self.stats['keywords_updated']}")
            logger.info(f"Chunks deleted: {self.stats['chunks_deleted']}")
            logger.info(f"Chunks created: {self.stats['chunks_created']}")
            logger.info(f"Embeddings deleted: {self.stats['embeddings_deleted']}")
            logger.info(f"Embeddings created: {self.stats['embeddings_created']}")

        logger.info(f"Errors: {self.stats['errors']}")

        if self.stats['corrupted_found'] > 0:
            corruption_rate = (self.stats['corrupted_found'] / self.stats['articles_reprocessed']) * 100
            logger.info(f"Corruption rate: {corruption_rate:.2f}%")

    def close(self) -> None:
        """Close database connections and clean up embedders."""
        try:
            # Clean up embedders
            for model_name, embedder in self.embedders.items():
                try:
                    # Some embedders might have cleanup methods
                    if hasattr(embedder, 'close'):
                        embedder.close()
                except Exception as e:
                    logger.warning(f"Error closing embedder for {model_name}: {e}")

            self.embedders.clear()

            # Close database connections
            self.pubmed_db.close()
            self.document_db.close()
            self.chunker_db.close()
            self.embeddings_db.close()
            self.import_tracker.close()
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

  # Force processing all files (useful if files were imported before import tracker existed)
  python -m localknowledge.pubmed.fix_corrupt_pubmed_imports --xml-dir /path/to/xml --force-all-files

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
        '--force-all-files',
        action='store_true',
        help='Process all XML files regardless of import tracker status (default: False)'
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
        batch_size=args.batch_size,
        force_all_files=args.force_all_files
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
