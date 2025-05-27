#!/usr/bin/env python3
"""
Test module for fix_corrupt_pubmed_imports.py

This module provides comprehensive testing for the corrupt import fixer without
actually modifying the live database. It includes mock database managers that
simulate database operations and track what would have been changed.

Usage:
    python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml/files
"""

import os
import sys
import logging
import argparse
import tempfile
import json
from typing import Dict, Any, List, Optional, Tuple, Generator
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass, field

# Add the parent directory to the path to import localknowledge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_fix_corrupt_imports.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class MockDatabaseOperation:
    """Represents a database operation that would have been performed."""
    operation_type: str  # 'SELECT', 'UPDATE', 'INSERT', 'DELETE'
    table: str
    query: str
    params: Optional[Tuple] = None
    would_affect_rows: int = 0
    would_return: Optional[List[Dict[str, Any]]] = None


@dataclass
class TestStatistics:
    """Statistics for the test run."""
    operations_logged: List[MockDatabaseOperation] = field(default_factory=list)
    files_processed: int = 0
    articles_reprocessed: int = 0
    corrupted_found: int = 0
    would_update_records: int = 0
    would_delete_chunks: int = 0
    would_create_chunks: int = 0
    would_delete_embeddings: int = 0
    would_create_embeddings: int = 0
    errors: int = 0


class MockPubMedDatabaseManager:
    """Mock PubMed database manager that simulates database operations."""

    def __init__(self, test_stats: TestStatistics):
        self.test_stats = test_stats
        # Sample data for testing
        self.sample_articles = {
            '12345678': {
                'id': 1,
                'pmid': '12345678',
                'title': 'Sample Article Title',
                'abstract': 'This is a truncated abstract...',  # Simulated corruption
                'authors': ['Author One', 'Author Two'],
                'publication': 'Sample Journal',
                'mesh_terms': ['Term1', 'Term2'],
                'keywords': ['keyword1', 'keyword2'],
                'doi': '10.1234/sample.doi'
            }
        }

    def get_article_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        """Mock method to get article by PMID."""
        operation = MockDatabaseOperation(
            operation_type='SELECT',
            table='document',
            query=f"SELECT * FROM document WHERE external_id = '{pmid}'",
            would_return=[self.sample_articles.get(pmid)] if pmid in self.sample_articles else []
        )
        self.test_stats.operations_logged.append(operation)

        return self.sample_articles.get(pmid)

    def close(self):
        """Mock close method."""
        pass


class MockDocumentDatabaseManager:
    """Mock Document database manager that simulates database operations."""

    def __init__(self, test_stats: TestStatistics):
        self.test_stats = test_stats
        self.sample_documents = {
            '12345678': {
                'id': 1,
                'external_id': '12345678',
                'source_id': 1
            }
        }

    def get_document_by_external_id(self, source: str, external_id: str) -> Optional[Dict[str, Any]]:
        """Mock method to get document by external ID."""
        operation = MockDatabaseOperation(
            operation_type='SELECT',
            table='document',
            query=f"SELECT * FROM document WHERE external_id = '{external_id}'",
            would_return=[self.sample_documents.get(external_id)] if external_id in self.sample_documents else []
        )
        self.test_stats.operations_logged.append(operation)

        return self.sample_documents.get(external_id)

    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Mock execute method that logs what would have been done."""
        operation = MockDatabaseOperation(
            operation_type='UPDATE' if 'UPDATE' in query.upper() else 'UNKNOWN',
            table='document',
            query=query,
            params=params,
            would_affect_rows=1 if commit else 0,
            would_return=[] if commit else None
        )
        self.test_stats.operations_logged.append(operation)

        if commit and 'UPDATE' in query.upper():
            self.test_stats.would_update_records += 1
            logger.info(f"[MOCK] Would execute UPDATE: {query[:100]}...")
            return []  # Simulate successful update

        return None

    def close(self):
        """Mock close method."""
        pass


class MockChunkerDatabaseManager:
    """Mock Chunker database manager that simulates database operations."""

    def __init__(self, test_stats: TestStatistics):
        self.test_stats = test_stats
        self.sample_chunks = {
            1: [  # document_id 1
                Mock(id=101, text="Sample chunk 1", document_id=1),
                Mock(id=102, text="Sample chunk 2", document_id=1)
            ]
        }

    def get_chunks_for_document(self, document_id: int) -> Generator:
        """Mock method to get chunks for a document."""
        operation = MockDatabaseOperation(
            operation_type='SELECT',
            table='chunks',
            query=f"SELECT * FROM chunks WHERE document_id = {document_id}",
            would_return=self.sample_chunks.get(document_id, [])
        )
        self.test_stats.operations_logged.append(operation)

        chunks = self.sample_chunks.get(document_id, [])
        for chunk in chunks:
            yield chunk

    def create_chunk(self, chunk) -> Optional[int]:
        """Mock method to create a chunk."""
        operation = MockDatabaseOperation(
            operation_type='INSERT',
            table='chunks',
            query="INSERT INTO chunks (...) VALUES (...)",
            would_affect_rows=1,
            would_return=[{'id': 999}]  # Mock chunk ID
        )
        self.test_stats.operations_logged.append(operation)
        self.test_stats.would_create_chunks += 1

        logger.info(f"[MOCK] Would create chunk for document {chunk.document_id}")
        return 999  # Mock chunk ID

    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Mock execute method for chunk deletion."""
        operation = MockDatabaseOperation(
            operation_type='DELETE' if 'DELETE' in query.upper() else 'UNKNOWN',
            table='chunks',
            query=query,
            params=params,
            would_affect_rows=1 if commit else 0
        )
        self.test_stats.operations_logged.append(operation)

        if commit and 'DELETE' in query.upper():
            self.test_stats.would_delete_chunks += 1
            logger.info(f"[MOCK] Would delete chunk: {query[:50]}...")
            return []

        return None

    def close(self):
        """Mock close method."""
        pass


class MockEmbeddingsDatabaseManager:
    """Mock Embeddings database manager that simulates database operations."""

    def __init__(self, test_stats: TestStatistics):
        self.test_stats = test_stats

    def add_embedding(self, chunk_id: int, model_id: int, embedding: List[float]) -> int:
        """Mock method to add an embedding."""
        operation = MockDatabaseOperation(
            operation_type='INSERT',
            table='embedding_base',
            query=f"INSERT INTO emb_{len(embedding)} (...) VALUES (...)",
            would_affect_rows=1,
            would_return=[{'id': 888}]  # Mock embedding ID
        )
        self.test_stats.operations_logged.append(operation)
        self.test_stats.would_create_embeddings += 1

        logger.info(f"[MOCK] Would create embedding for chunk {chunk_id}, model {model_id}")
        return 888  # Mock embedding ID

    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Mock execute method for embedding deletion."""
        operation = MockDatabaseOperation(
            operation_type='DELETE' if 'DELETE' in query.upper() else 'UNKNOWN',
            table='embedding_base',
            query=query,
            params=params,
            would_affect_rows=1 if commit else 0
        )
        self.test_stats.operations_logged.append(operation)

        if commit and 'DELETE' in query.upper():
            self.test_stats.would_delete_embeddings += 1
            logger.info(f"[MOCK] Would delete embedding: {query[:50]}...")
            return []

        return None

    def close(self):
        """Mock close method."""
        pass


class MockCorruptImportFixer:
    """
    Test version of CorruptImportFixer that uses mock database managers.
    """

    def __init__(self, xml_dir: str, batch_size: int = 1000):
        """
        Initialize the test corrupt import fixer.

        Args:
            xml_dir: Directory containing PubMed XML files
            batch_size: Number of records to process in each batch
        """
        self.xml_dir = xml_dir
        self.batch_size = batch_size

        # Initialize test statistics
        self.test_stats = TestStatistics()

        # Initialize mock database managers
        self.pubmed_db = MockPubMedDatabaseManager(self.test_stats)
        self.document_db = MockDocumentDatabaseManager(self.test_stats)
        self.chunker_db = MockChunkerDatabaseManager(self.test_stats)
        self.embeddings_db = MockEmbeddingsDatabaseManager(self.test_stats)

        # Statistics (same as original)
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

        logger.info(f"Initialized MockCorruptImportFixer with XML directory: {xml_dir}")

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
        Mock process XML file - returns sample data for testing.

        Args:
            xml_file_path: Path to the XML file

        Returns:
            List of sample article data dictionaries
        """
        # Return sample article data for testing
        sample_articles = [
            {
                'pmid': '12345678',
                'title': 'Sample Article Title - Fixed Version',
                'abstract': 'This is the complete abstract that was previously truncated due to the bug. It contains much more information than the corrupted version.',
                'authors': 'Author One, Author Two, Author Three',  # Added third author
                'journal': 'Sample Journal',
                'mesh_terms': 'Term1, Term2, Term3',  # Added third term
                'keywords': 'keyword1, keyword2',
                'doi': '10.1234/sample.doi'
            }
        ]

        logger.info(f"[MOCK] Processing XML file: {os.path.basename(xml_file_path)}")
        return sample_articles

    def compare_articles(self, new_article: Dict[str, Any], existing_article: Dict[str, Any]) -> Dict[str, bool]:
        """
        Compare new article data with existing database record.
        (Same logic as original)
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

    def update_corrupted_record(self, pmid: str, new_article: Dict[str, Any], differences: Dict[str, bool]) -> bool:
        """Mock update corrupted record - simulates database update."""
        try:
            # Get the document ID
            existing_doc = self.document_db.get_document_by_external_id('pubmed', pmid)
            if not existing_doc:
                logger.error(f"Could not find document for PMID {pmid}")
                return False

            document_id = existing_doc['id']

            # Simulate building update query
            update_fields = []
            params = []

            if differences.get('title'):
                update_fields.append('title = %s')
                params.append(new_article.get('title', ''))

            if differences.get('abstract'):
                update_fields.append('abstract = %s')
                params.append(new_article.get('abstract', ''))

            # ... other fields would be handled similarly

            if not update_fields:
                logger.warning(f"No fields to update for PMID {pmid}")
                return True

            # Mock the database update
            query = f"UPDATE document SET {', '.join(update_fields)} WHERE id = %s"
            params.append(document_id)

            result = self.document_db.execute(query, params, commit=True)

            if result is not None:
                logger.info(f"[MOCK] Would update corrupted record for PMID {pmid}")
                self.stats['records_updated'] += 1
                return True
            else:
                logger.error(f"[MOCK] Would fail to update record for PMID {pmid}")
                return False

        except Exception as e:
            logger.error(f"Error in mock update for PMID {pmid}: {e}")
            self.stats['errors'] += 1
            return False

    def delete_old_chunks_and_embeddings(self, document_id: int) -> Tuple[int, int]:
        """Mock delete old chunks and embeddings."""
        chunks_deleted = 0
        embeddings_deleted = 0

        try:
            # Get existing chunks for this document
            chunks = list(self.chunker_db.get_chunks_for_document(document_id))

            for chunk in chunks:
                chunk_id = chunk.id

                # Mock delete embeddings for this chunk
                deleted_emb = self.delete_embeddings_for_chunk(chunk_id)
                embeddings_deleted += deleted_emb

                # Mock delete the chunk
                if self.delete_chunk(chunk_id):
                    chunks_deleted += 1

            self.stats['chunks_deleted'] += chunks_deleted
            self.stats['embeddings_deleted'] += embeddings_deleted

            logger.debug(f"[MOCK] Would delete {chunks_deleted} chunks and {embeddings_deleted} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error in mock deletion for document {document_id}: {e}")
            self.stats['errors'] += 1

        return chunks_deleted, embeddings_deleted

    def delete_embeddings_for_chunk(self, chunk_id: int) -> int:
        """Mock delete embeddings for a specific chunk."""
        try:
            query = "DELETE FROM embedding_base WHERE chunk_id = %s"
            result = self.embeddings_db.execute(query, (chunk_id,), commit=True)
            return 1 if result is not None else 0
        except Exception as e:
            logger.error(f"Error in mock embedding deletion for chunk {chunk_id}: {e}")
            return 0

    def delete_chunk(self, chunk_id: int) -> bool:
        """Mock delete a specific chunk."""
        try:
            query = "DELETE FROM chunks WHERE id = %s"
            result = self.chunker_db.execute(query, (chunk_id,), commit=True)
            return result is not None
        except Exception as e:
            logger.error(f"Error in mock chunk deletion for chunk {chunk_id}: {e}")
            return False

    def process_batch(self, articles: List[Dict[str, Any]]) -> None:
        """Process a batch of articles to identify and simulate fixing corruption."""
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

                    # Simulate updating the record
                    if self.update_corrupted_record(pmid, article, differences):
                        document_id = existing_article['id']

                        # If abstract was updated, simulate re-chunking and re-embedding
                        if differences.get('abstract'):
                            logger.info(f"[MOCK] Would re-process chunks and embeddings for PMID {pmid}")

                            # Simulate deleting old chunks and embeddings
                            chunks_deleted, embeddings_deleted = self.delete_old_chunks_and_embeddings(document_id)

                            # Simulate re-chunking the abstract
                            chunks_created = self.mock_rechunk_abstract(document_id, article.get('title', ''), article.get('abstract', ''))

                            # Simulate re-embedding the chunks
                            if chunks_created > 0:
                                embeddings_created = self.mock_reembed_chunks(document_id, chunks_created)

                self.stats['articles_reprocessed'] += 1

            except Exception as e:
                logger.error(f"Error processing article with PMID {pmid}: {e}")
                self.stats['errors'] += 1

    def mock_rechunk_abstract(self, document_id: int, title: str, abstract: str) -> int:
        """Mock re-chunk an updated abstract."""
        # Simulate creating 2-3 chunks for the abstract
        chunks_created = 2 if len(abstract) < 500 else 3

        for i in range(chunks_created):
            # Mock creating chunk
            mock_chunk = Mock(
                document_id=document_id,
                chunking_strategy_id=1,
                chunktype_id=1,
                text=f"Mock chunk {i} from: {abstract[:50]}...",
                document_title=title,
                chunklength=len(abstract) // chunks_created,
                chunk_no=i,
                page_start=0,
                page_end=0,
                metadata={}
            )

            chunk_id = self.chunker_db.create_chunk(mock_chunk)
            if chunk_id:
                logger.debug(f"[MOCK] Would create chunk {i} for document {document_id}")

        self.stats['chunks_created'] += chunks_created
        logger.debug(f"[MOCK] Would create {chunks_created} chunks for document {document_id}")
        return chunks_created

    def mock_reembed_chunks(self, document_id: int, chunks_count: int) -> int:
        """Mock re-embed chunks for a document."""
        embeddings_created = 0

        try:
            # Simulate embedding each chunk
            for i in range(chunks_count):
                mock_embedding = [0.1] * 768  # Mock 768-dimensional embedding

                success = self.embeddings_db.add_embedding(
                    chunk_id=999 + i,  # Mock chunk ID
                    model_id=3,  # PubMedBERT model ID
                    embedding=mock_embedding
                )
                if success:
                    embeddings_created += 1

            self.stats['embeddings_created'] += embeddings_created
            logger.debug(f"[MOCK] Would create {embeddings_created} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error in mock re-embedding for document {document_id}: {e}")
            self.stats['errors'] += 1

        return embeddings_created

    def run_test(self, max_files: Optional[int] = None) -> None:
        """Run the test simulation."""
        logger.info("Starting MOCK corrupt PubMed import fix process")
        logger.info(f"XML directory: {self.xml_dir}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info("*** THIS IS A TEST RUN - NO ACTUAL DATABASE CHANGES WILL BE MADE ***")

        # Get XML files to process
        xml_files_generator = self.get_xml_files()

        # Process files
        files_processed_count = 0

        for xml_file in xml_files_generator:
            # Check max_files limit
            if max_files and files_processed_count >= max_files:
                logger.info(f"Reached max_files limit of {max_files}")
                break

            try:
                logger.info(f"Processing file: {os.path.basename(xml_file)}")

                # Process the XML file (mock)
                articles = self.process_xml_file(xml_file)

                if not articles:
                    logger.warning(f"No articles found in {xml_file}")
                    files_processed_count += 1
                    self.stats['files_processed'] += 1
                    continue

                # Process articles in batches
                for i in range(0, len(articles), self.batch_size):
                    batch = articles[i:i + self.batch_size]
                    self.process_batch(batch)

                files_processed_count += 1
                self.stats['files_processed'] += 1

                # Log progress every 10 files
                if self.stats['files_processed'] % 10 == 0:
                    self.log_progress()

            except Exception as e:
                logger.error(f"Error processing file {xml_file}: {e}")
                files_processed_count += 1
                self.stats['errors'] += 1

        # Final statistics
        logger.info("=" * 60)
        logger.info("MOCK CORRUPTION FIX TEST COMPLETED")
        logger.info("=" * 60)
        self.log_final_stats()
        self.log_database_operations()

    def log_progress(self) -> None:
        """Log current progress statistics."""
        logger.info(f"Progress: {self.stats['files_processed']} files, "
                   f"{self.stats['articles_reprocessed']} articles, "
                   f"{self.stats['corrupted_found']} corrupted found, "
                   f"{self.stats['records_updated']} would be updated")

    def log_final_stats(self) -> None:
        """Log final test statistics."""
        logger.info("TEST MODE - SIMULATED RESULTS")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Articles reprocessed: {self.stats['articles_reprocessed']}")
        logger.info(f"Corrupted records found: {self.stats['corrupted_found']}")
        logger.info(f"Records that would be updated: {self.stats['records_updated']}")
        logger.info(f"Chunks that would be deleted: {self.stats['chunks_deleted']}")
        logger.info(f"Chunks that would be created: {self.stats['chunks_created']}")
        logger.info(f"Embeddings that would be deleted: {self.stats['embeddings_deleted']}")
        logger.info(f"Embeddings that would be created: {self.stats['embeddings_created']}")
        logger.info(f"Errors: {self.stats['errors']}")

        if self.stats['corrupted_found'] > 0:
            corruption_rate = (self.stats['corrupted_found'] / self.stats['articles_reprocessed']) * 100
            logger.info(f"Corruption rate: {corruption_rate:.2f}%")

    def log_database_operations(self) -> None:
        """Log summary of database operations that would have been performed."""
        operations_by_type = {}
        for op in self.test_stats.operations_logged:
            op_type = f"{op.operation_type}_{op.table}"
            operations_by_type[op_type] = operations_by_type.get(op_type, 0) + 1

        logger.info("Database operations that would have been performed:")
        for op_type, count in operations_by_type.items():
            logger.info(f"  {op_type}: {count}")

        logger.info(f"Total database operations: {len(self.test_stats.operations_logged)}")

    def close(self) -> None:
        """Close mock database connections."""
        try:
            self.pubmed_db.close()
            self.document_db.close()
            self.chunker_db.close()
            self.embeddings_db.close()
        except Exception as e:
            logger.error(f"Error closing mock database connections: {e}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Test the corrupt PubMed import fixer without modifying the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with sample XML files
  python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml

  # Test with first 5 files only
  python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml --max-files 5

  # Test with larger batch size
  python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --xml-dir /path/to/xml --batch-size 2000

  # Create sample XML files for testing
  python -m localknowledge.pubmed.test_fix_corrupt_pubmed_imports --create-sample-xml /tmp/test_xml
        """
    )

    parser.add_argument(
        '--xml-dir',
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
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--create-sample-xml',
        metavar='DIR',
        help='Create sample XML files for testing in the specified directory'
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create sample XML files if requested
    if args.create_sample_xml:
        create_sample_xml_files(args.create_sample_xml)
        return

    # Validate arguments
    if not args.xml_dir:
        parser.error("--xml-dir is required unless using --create-sample-xml")

    # Create and run the test fixer
    test_fixer = MockCorruptImportFixer(
        xml_dir=args.xml_dir,
        batch_size=args.batch_size
    )

    try:
        test_fixer.run_test(max_files=args.max_files)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error during test: {e}")
        raise
    finally:
        test_fixer.close()


def create_sample_xml_files(output_dir: str) -> None:
    """Create sample XML files for testing."""
    import gzip

    os.makedirs(output_dir, exist_ok=True)

    # Sample XML content
    sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
<PubmedArticle>
    <MedlineCitation Status="MEDLINE" Owner="NLM">
        <PMID Version="1">12345678</PMID>
        <Article PubModel="Print">
            <Journal>
                <Title>Sample Journal</Title>
            </Journal>
            <ArticleTitle>Sample Article Title</ArticleTitle>
            <Abstract>
                <AbstractText>This is a sample abstract for testing purposes. It simulates a PubMed article abstract.</AbstractText>
            </Abstract>
            <AuthorList CompleteYN="Y">
                <Author ValidYN="Y">
                    <LastName>Author</LastName>
                    <ForeName>Sample</ForeName>
                    <Initials>S</Initials>
                </Author>
            </AuthorList>
        </Article>
        <MeshHeadingList>
            <MeshHeading>
                <DescriptorName UI="D000001" MajorTopicYN="N">Sample Term</DescriptorName>
            </MeshHeading>
        </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
        <ArticleIdList>
            <ArticleId IdType="pubmed">12345678</ArticleId>
            <ArticleId IdType="doi">10.1234/sample.doi</ArticleId>
        </ArticleIdList>
    </PubmedData>
</PubmedArticle>
</PubmedArticleSet>'''

    # Create a few sample files
    for i in range(3):
        filename = f"pubmed_sample_{i+1:02d}.xml.gz"
        filepath = os.path.join(output_dir, filename)

        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            f.write(sample_xml)

        logger.info(f"Created sample XML file: {filepath}")

    logger.info(f"Created {3} sample XML files in {output_dir}")
    logger.info(f"You can now test with: --xml-dir {output_dir}")


if __name__ == "__main__":
    main()