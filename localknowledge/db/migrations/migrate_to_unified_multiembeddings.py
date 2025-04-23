#!/usr/bin/env python3
"""
Migration script to migrate embeddings to the unified multiembeddings system.

This script will:
1. Create the embedding_source table if it doesn't exist
2. Create the unified_multiembeddings table if it doesn't exist
3. Migrate embeddings from the legacy embeddings table
4. Migrate QA embeddings from the legacy qaembeddings table

IMPORTANT: This script should be run after the main document migration is complete
and after the embeddings and qaembeddings tables have been updated to reference the document table.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import tqdm
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from localknowledge.db.base import DatabaseManager
from localknowledge.db.embedding_source import get_embedding_source_db
from localknowledge.db.unified_multiembeddings import get_unified_multiembeddings_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('unified_multiembeddings_migration.log')
    ]
)
logger = logging.getLogger(__name__)


# Global variable to store command-line arguments
args = None

class UnifiedMultiEmbeddingsMigration(DatabaseManager):
    """Migration to migrate embeddings to the unified multiembeddings system."""

    def __init__(self, dry_run=True, batch_size=1000, continue_on_error=False):
        """Initialize the migration.

        Args:
            dry_run: If True, only print what would be done without making changes
            batch_size: Number of records to process in each batch
        """
        print("Initializing UnifiedMultiEmbeddingsMigration...")
        print(f"Dry run: {dry_run}, Batch size: {batch_size}")

        try:
            print("Calling super().__init__()...")
            super().__init__()
            print("super().__init__() completed")

            self.dry_run = dry_run
            self.batch_size = batch_size
            self.continue_on_error = continue_on_error

            print("Getting embedding_source_db...")
            self.embedding_source_db = get_embedding_source_db()
            print("embedding_source_db initialized")

            print("Getting unified_multiembeddings_db...")
            self.unified_multiembeddings_db = get_unified_multiembeddings_db()
            print("unified_multiembeddings_db initialized")

            logger.info(f"Unified multiembeddings migration initialized in {'dry run' if dry_run else 'execution'} mode")
            logger.info(f"Using batch size of {batch_size}")
            print("UnifiedMultiEmbeddingsMigration initialization complete")
        except Exception as e:
            print(f"Error initializing UnifiedMultiEmbeddingsMigration: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    def setup_tables(self):
        """Create the necessary tables if they don't exist."""
        logger.info("Setting up tables")
        print("Setting up tables...")

        if not self.dry_run:
            try:
                # Create embedding_source table
                print("Creating embedding_source table...")
                self.embedding_source_db.create_tables()
                print("Embedding source table created")

                # Create unified_multiembeddings table directly with SQL
                # instead of using the manager to avoid potential circular dependencies
                print("Creating unified_multiembeddings table directly...")

                # Create the unified_multiembeddings table
                query = """
                CREATE TABLE IF NOT EXISTS unified_multiembeddings (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
                    embed_source_id INTEGER REFERENCES embedding_source(id) ON DELETE CASCADE,
                    chunk_no INTEGER,
                    page_no INTEGER,
                    text TEXT,
                    keywords TEXT[],
                    embedding VECTOR(1024),
                    model_name TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (document_id, embed_source_id, chunk_no, page_no, model_name)
                );
                """
                self.execute(query, commit=True)
                print("Unified multiembeddings table created")

                # Create basic indices
                print("Creating basic indices...")
                indices = [
                    "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_document_id ON unified_multiembeddings(document_id)",
                    "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_embed_source_id ON unified_multiembeddings(embed_source_id)",
                    "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_model_name ON unified_multiembeddings(model_name)",
                    "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_created_at ON unified_multiembeddings(created_at)"
                ]

                for index_query in indices:
                    try:
                        self.execute(index_query, commit=True)
                    except Exception as e:
                        print(f"Warning: Error creating index: {e}")

                # Create vector index
                print("Creating vector index...")
                try:
                    vector_index_query = """
                    CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_embedding
                    ON unified_multiembeddings USING ivfflat (embedding vector_cosine_ops)
                    """
                    self.execute(vector_index_query, commit=True)
                    print("Vector index created")
                except Exception as e:
                    print(f"Warning: Error creating vector index: {e}")

                logger.info("Tables created")
                print("All tables created successfully")
            except Exception as e:
                logger.error(f"Error creating tables: {e}")
                print(f"Error creating tables: {e}")
                raise
        else:
            logger.info("Dry run: Would create tables")
            print("Dry run: Would create tables")

    def count_legacy_embeddings(self, start_document_id: int = 0, end_document_id: int = 0) -> int:
        """Count the number of legacy embeddings to migrate.

        Args:
            start_document_id: Start from this document ID (inclusive)
            end_document_id: End at this document ID (inclusive, 0 means no limit)

        Returns:
            Number of legacy embeddings
        """
        print("Counting legacy embeddings...")

        # First check if the table exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'embeddings'
        );
        """
        check_result = self.execute(check_query)

        if not check_result or not check_result[0]['exists']:
            print("Legacy embeddings table does not exist")
            return 0

        # Check if document_ref_id column exists
        column_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'embeddings'
            AND column_name = 'document_ref_id'
        );
        """
        column_result = self.execute(column_query)

        if not column_result or not column_result[0]['exists']:
            print("document_ref_id column does not exist in embeddings table")
            return 0

        # Build the query with document ID filters
        where_clauses = ["e.document_ref_id IS NOT NULL"]
        params = []

        if start_document_id > 0:
            where_clauses.append("d.id >= %s")
            params.append(start_document_id)

        if end_document_id > 0:
            where_clauses.append("d.id <= %s")
            params.append(end_document_id)

        where_clause = " AND ".join(where_clauses)

        # Count embeddings with document_ref_id and optional document ID filters
        query = f"""
        SELECT COUNT(*) as count
        FROM embeddings e
        JOIN document d ON e.document_ref_id = d.id
        WHERE {where_clause}
        """

        result = self.execute(query, tuple(params))
        count = result[0]['count'] if result else 0

        filter_info = ""
        if start_document_id > 0 and end_document_id > 0:
            filter_info = f" (filtered by document IDs {start_document_id}-{end_document_id})"
        elif start_document_id > 0:
            filter_info = f" (filtered by document IDs >= {start_document_id})"
        elif end_document_id > 0:
            filter_info = f" (filtered by document IDs <= {end_document_id})"

        print(f"Found {count} legacy embeddings with document_ref_id{filter_info}")
        return count

    def count_legacy_qaembeddings(self, start_document_id: int = 0, end_document_id: int = 0) -> int:
        """Count the number of legacy QA embeddings to migrate.

        Args:
            start_document_id: Start from this document ID (inclusive)
            end_document_id: End at this document ID (inclusive, 0 means no limit)

        Returns:
            Number of legacy QA embeddings
        """
        print("Counting legacy QA embeddings...")

        # First check if the table exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'qaembeddings'
        );
        """
        check_result = self.execute(check_query)

        if not check_result or not check_result[0]['exists']:
            print("Legacy qaembeddings table does not exist")
            return 0

        # Check if document_ref_id column exists
        column_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'qaembeddings'
            AND column_name = 'document_ref_id'
        );
        """
        column_result = self.execute(column_query)

        if not column_result or not column_result[0]['exists']:
            print("document_ref_id column does not exist in qaembeddings table")
            return 0

        # Build the query with document ID filters
        where_clauses = ["e.document_ref_id IS NOT NULL"]
        params = []

        if start_document_id > 0:
            where_clauses.append("d.id >= %s")
            params.append(start_document_id)

        if end_document_id > 0:
            where_clauses.append("d.id <= %s")
            params.append(end_document_id)

        where_clause = " AND ".join(where_clauses)

        # Count qaembeddings with document_ref_id and optional document ID filters
        query = f"""
        SELECT COUNT(*) as count
        FROM qaembeddings e
        JOIN document d ON e.document_ref_id = d.id
        WHERE {where_clause}
        """

        result = self.execute(query, tuple(params))
        count = result[0]['count'] if result else 0

        filter_info = ""
        if start_document_id > 0 and end_document_id > 0:
            filter_info = f" (filtered by document IDs {start_document_id}-{end_document_id})"
        elif start_document_id > 0:
            filter_info = f" (filtered by document IDs >= {start_document_id})"
        elif end_document_id > 0:
            filter_info = f" (filtered by document IDs <= {end_document_id})"

        print(f"Found {count} legacy QA embeddings with document_ref_id{filter_info}")
        return count

    def get_legacy_embeddings_batch(self, offset: int, start_document_id: int = 0, end_document_id: int = 0) -> List[Dict[str, Any]]:
        """Get a batch of legacy embeddings to migrate.

        Args:
            offset: Offset for pagination
            start_document_id: Start from this document ID (inclusive)
            end_document_id: End at this document ID (inclusive, 0 means no limit)

        Returns:
            List of legacy embedding records
        """
        where_clauses = ["e.document_ref_id IS NOT NULL"]
        params = []

        if start_document_id > 0:
            where_clauses.append("d.id >= %s")
            params.append(start_document_id)

        if end_document_id > 0:
            where_clauses.append("d.id <= %s")
            params.append(end_document_id)

        where_clause = " AND ".join(where_clauses)

        query = f"""
        SELECT e.*, d.id as document_id
        FROM embeddings e
        JOIN document d ON e.document_ref_id = d.id
        WHERE {where_clause}
        ORDER BY d.id, e.chunk_no
        LIMIT {self.batch_size} OFFSET {offset}
        """

        return self.execute(query, tuple(params)) or []

    def get_legacy_qaembeddings_batch(self, offset: int, start_document_id: int = 0, end_document_id: int = 0) -> List[Dict[str, Any]]:
        """Get a batch of legacy QA embeddings to migrate.

        Args:
            offset: Offset for pagination
            start_document_id: Start from this document ID (inclusive)
            end_document_id: End at this document ID (inclusive, 0 means no limit)

        Returns:
            List of legacy QA embedding records
        """
        where_clauses = ["e.document_ref_id IS NOT NULL"]
        params = []

        if start_document_id > 0:
            where_clauses.append("d.id >= %s")
            params.append(start_document_id)

        if end_document_id > 0:
            where_clauses.append("d.id <= %s")
            params.append(end_document_id)

        where_clause = " AND ".join(where_clauses)

        query = f"""
        SELECT e.*, d.id as document_id
        FROM qaembeddings e
        JOIN document d ON e.document_ref_id = d.id
        WHERE {where_clause}
        ORDER BY d.id, e.chunk_no
        LIMIT {self.batch_size} OFFSET {offset}
        """

        return self.execute(query, tuple(params)) or []

    def migrate_legacy_embeddings(self):
        """Migrate legacy embeddings to the unified multiembeddings system."""
        logger.info("Migrating legacy embeddings")

        # Get start and end document IDs from command-line arguments
        start_document_id = args.start_document_id
        end_document_id = args.end_document_id

        # Count total legacy embeddings
        total_embeddings = self.count_legacy_embeddings(start_document_id, end_document_id)
        logger.info(f"Found {total_embeddings} legacy embeddings to migrate")

        if total_embeddings == 0:
            logger.info("No legacy embeddings to migrate")
            return

        # Get the abstract embedding source ID
        abstract_source = self.embedding_source_db.get_embedding_source_by_name('abstract')
        if not abstract_source:
            abstract_source_id = self.embedding_source_db.add_embedding_source(
                'abstract', 'Embeddings generated from document abstracts')
        else:
            abstract_source_id = abstract_source['id']

        # Check for checkpoint file
        checkpoint_file = 'embeddings_migration_checkpoint.txt'
        start_offset = 0

        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    start_offset = int(f.read().strip())
                    logger.info(f"Resuming from offset {start_offset}")
                    print(f"Resuming from offset {start_offset}")
            except Exception as e:
                logger.error(f"Error reading checkpoint file: {e}")
                print(f"Error reading checkpoint file: {e}")

        # Process in batches
        migrated_count = 0
        error_count = 0
        skipped_count = 0

        # Check if any embeddings have already been migrated
        if start_offset > 0:
            skipped_count = start_offset
            logger.info(f"Skipping {skipped_count} already processed embeddings")
            print(f"Skipping {skipped_count} already processed embeddings")

        with tqdm.tqdm(total=total_embeddings, desc="Migrating legacy embeddings", initial=skipped_count) as pbar:
            offset = start_offset

            try:


                while True:
                    embeddings = self.get_legacy_embeddings_batch(offset, start_document_id, end_document_id)

                    if not embeddings:
                        break

                    batch_success = 0
                    batch_errors = 0

                    for embedding in embeddings:
                        try:
                            if not self.dry_run:
                                # For pgvector, we need to ensure the embedding is in the correct format
                                # The embedding is already stored in the database in the correct format
                                # We don't need to convert it, as PostgreSQL will handle it correctly

                                # Check if the embedding already exists
                                check_query = """
                                SELECT id FROM unified_multiembeddings
                                WHERE document_id = %s AND embed_source_id = %s AND chunk_no = %s AND page_no = %s AND model_name = %s
                                """

                                # Get the embedding source ID
                                embed_source_record = self.embedding_source_db.get_embedding_source_by_name('abstract')
                                embed_source_id = embed_source_record['id']

                                check_result = self.execute(
                                    check_query,
                                    (embedding['document_id'], embed_source_id, embedding['chunk_no'], embedding['page_no'], embedding['model_name'] or 'unknown')
                                )

                                if check_result:
                                    # Embedding already exists, skip it
                                    logger.info(f"Embedding already exists for document {embedding['document_id']}, source abstract, chunk {embedding['chunk_no']}")
                                else:
                                    # Add to unified_multiembeddings
                                    self.unified_multiembeddings_db.add_embedding(
                                        document_id=embedding['document_id'],
                                        embed_source='abstract',
                                        chunk_no=embedding['chunk_no'],
                                        page_no=embedding['page_no'],
                                        text=embedding['text'],
                                        keywords=embedding['keywords'],
                                        embedding=embedding['embedding'],
                                        model_name=embedding['model_name'] or 'unknown',
                                        metadata={
                                            'source_id': embedding['source_id'],
                                            'document_id': embedding['document_id'],
                                            'legacy_id': embedding['id']
                                        }
                                    )

                            batch_success += 1
                            migrated_count += 1
                        except Exception as e:
                            # Get detailed information about the embedding that failed
                            doc_id = embedding.get('document_id')
                            source_id = embedding.get('source_id')
                            chunk_no = embedding.get('chunk_no')
                            page_no = embedding.get('page_no')
                            model_name = embedding.get('model_name')
                            embedding_id = embedding.get('id')

                            # Check embedding vector
                            embedding_vector = embedding.get('embedding')
                            vector_info = "None" if embedding_vector is None else f"Type: {type(embedding_vector)}, Length: {len(embedding_vector) if hasattr(embedding_vector, '__len__') else 'N/A'}"

                            # Check text
                            text = embedding.get('text')
                            text_info = "None" if text is None else f"Type: {type(text)}, Length: {len(text)}"

                            error_msg = f"\nERROR migrating embedding:\n"
                            error_msg += f"  Document ID: {doc_id}\n"
                            error_msg += f"  Source ID: {source_id}\n"
                            error_msg += f"  Embedding ID: {embedding_id}\n"
                            error_msg += f"  Chunk: {chunk_no}, Page: {page_no}\n"
                            error_msg += f"  Model: {model_name}\n"
                            error_msg += f"  Embedding vector: {vector_info}\n"
                            error_msg += f"  Text: {text_info}\n"
                            error_msg += f"  Error: {str(e)}\n"

                            # Get traceback
                            import traceback
                            tb = traceback.format_exc()
                            error_msg += f"\nTraceback:\n{tb}\n"

                            logger.error(error_msg)
                            print(error_msg)

                            # Save error details to file for later analysis
                            with open(f"embedding_error_{doc_id}_{chunk_no}.log", "w") as f:
                                f.write(error_msg)

                                # Include a sample of the text if available
                                if text and isinstance(text, str):
                                    f.write("\nText sample (first 500 chars):\n")
                                    f.write(text[:500])

                                # Include a sample of the embedding vector if available
                                if embedding_vector and hasattr(embedding_vector, '__iter__'):
                                    f.write("\nEmbedding vector sample (first 10 values):\n")
                                    try:
                                        f.write(str(list(embedding_vector)[:10]))
                                    except:
                                        f.write("Could not convert embedding vector to string")

                            batch_errors += 1
                            error_count += 1

                            # Always stop on first error to diagnose the issue
                            raise Exception(f"Migration stopped due to error with document {doc_id}, chunk {chunk_no}. Check the error log for details.")

                        pbar.update(1)

                    # Save checkpoint after each batch
                    if not self.dry_run:
                        new_offset = offset + len(embeddings)
                        with open(checkpoint_file, 'w') as f:
                            f.write(str(new_offset))

                    logger.info(f"Batch completed: {batch_success} succeeded, {batch_errors} failed")

                    offset += self.batch_size

                    # Break if we've processed all embeddings
                    if len(embeddings) < self.batch_size:
                        break
            except KeyboardInterrupt:
                logger.warning("Migration interrupted by user")
                print("\nMigration interrupted by user")
                print(f"Progress saved at offset {offset}")
                print(f"Run the script again to resume from this point")
                # Don't re-raise the exception, let the function complete normally

        logger.info(f"Migrated {migrated_count} legacy embeddings with {error_count} errors")
        print(f"Migrated {migrated_count} legacy embeddings with {error_count} errors")

        # Remove checkpoint file if migration completed successfully
        if not self.dry_run and migrated_count + error_count + skipped_count >= total_embeddings:
            try:
                if os.path.exists(checkpoint_file):
                    os.remove(checkpoint_file)
                    logger.info("Removed checkpoint file")
            except Exception as e:
                logger.error(f"Error removing checkpoint file: {e}")

    def migrate_legacy_qaembeddings(self):
        """Migrate legacy QA embeddings to the unified multiembeddings system."""
        logger.info("Migrating legacy QA embeddings")

        # Get start and end document IDs from command-line arguments
        start_document_id = args.start_document_id
        end_document_id = args.end_document_id

        # Count total legacy QA embeddings
        total_embeddings = self.count_legacy_qaembeddings(start_document_id, end_document_id)
        logger.info(f"Found {total_embeddings} legacy QA embeddings to migrate")

        if total_embeddings == 0:
            logger.info("No legacy QA embeddings to migrate")
            return

        # Get the qa_pairs embedding source ID
        qa_source = self.embedding_source_db.get_embedding_source_by_name('qa_pairs')
        if not qa_source:
            qa_source_id = self.embedding_source_db.add_embedding_source(
                'qa_pairs', 'Embeddings generated from question-answer pairs')
        else:
            qa_source_id = qa_source['id']

        # Check for checkpoint file
        checkpoint_file = 'qaembeddings_migration_checkpoint.txt'
        start_offset = 0

        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    start_offset = int(f.read().strip())
                    logger.info(f"Resuming from offset {start_offset}")
                    print(f"Resuming from offset {start_offset}")
            except Exception as e:
                logger.error(f"Error reading checkpoint file: {e}")
                print(f"Error reading checkpoint file: {e}")

        # Process in batches
        migrated_count = 0
        error_count = 0
        skipped_count = 0

        # Check if any QA embeddings have already been migrated
        if start_offset > 0:
            skipped_count = start_offset
            logger.info(f"Skipping {skipped_count} already processed QA embeddings")
            print(f"Skipping {skipped_count} already processed QA embeddings")

        with tqdm.tqdm(total=total_embeddings, desc="Migrating legacy QA embeddings", initial=skipped_count) as pbar:
            offset = start_offset

            try:


                while True:
                    qaembeddings = self.get_legacy_qaembeddings_batch(offset, start_document_id, end_document_id)

                    if not qaembeddings:
                        break

                    batch_success = 0
                    batch_errors = 0

                    for qaembedding in qaembeddings:
                        try:
                            # Extract text from qa_pairs
                            qa_pairs = qaembedding['qa_pairs']
                            text = ""

                            if isinstance(qa_pairs, list):
                                for qa in qa_pairs:
                                    if isinstance(qa, dict):
                                        q = qa.get('question', '')
                                        a = qa.get('answer', '')
                                        text += f"Q: {q}\nA: {a}\n\n"

                            if not self.dry_run:
                                # Check if the embedding already exists
                                check_query = """
                                SELECT id FROM unified_multiembeddings
                                WHERE document_id = %s AND embed_source_id = %s AND chunk_no = %s AND page_no = %s AND model_name = %s
                                """

                                # Get the embedding source ID
                                embed_source_record = self.embedding_source_db.get_embedding_source_by_name('qa_pairs')
                                embed_source_id = embed_source_record['id']

                                check_result = self.execute(
                                    check_query,
                                    (qaembedding['document_id'], embed_source_id, qaembedding['chunk_no'], qaembedding['page_no'], qaembedding['model_name'] or 'unknown')
                                )

                                if check_result:
                                    # Embedding already exists, skip it
                                    logger.info(f"QA embedding already exists for document {qaembedding['document_id']}, source qa_pairs, chunk {qaembedding['chunk_no']}")
                                else:
                                    # Add to unified_multiembeddings
                                    self.unified_multiembeddings_db.add_embedding(
                                        document_id=qaembedding['document_id'],
                                        embed_source='qa_pairs',
                                        chunk_no=qaembedding['chunk_no'],
                                        page_no=qaembedding['page_no'],
                                        text=text,
                                        keywords=None,
                                        embedding=qaembedding['embedding'],
                                        model_name=qaembedding['model_name'] or 'unknown',
                                        metadata={
                                            'source_id': qaembedding['source_id'],
                                            'document_id': qaembedding['document_id'],
                                            'legacy_id': qaembedding['id'],
                                            'qa_pairs': qa_pairs
                                        }
                                    )

                            batch_success += 1
                            migrated_count += 1
                        except Exception as e:
                            # Get detailed information about the QA embedding that failed
                            doc_id = qaembedding.get('document_id')
                            source_id = qaembedding.get('source_id')
                            chunk_no = qaembedding.get('chunk_no')
                            page_no = qaembedding.get('page_no')
                            model_name = qaembedding.get('model_name')
                            embedding_id = qaembedding.get('id')

                            # Check embedding vector
                            embedding_vector = qaembedding.get('embedding')
                            vector_info = "None" if embedding_vector is None else f"Type: {type(embedding_vector)}, Length: {len(embedding_vector) if hasattr(embedding_vector, '__len__') else 'N/A'}"

                            # Check qa_pairs
                            qa_pairs = qaembedding.get('qa_pairs')
                            qa_info = "None" if qa_pairs is None else f"Type: {type(qa_pairs)}, Length: {len(qa_pairs) if hasattr(qa_pairs, '__len__') else 'N/A'}"

                            error_msg = f"\nERROR migrating QA embedding:\n"
                            error_msg += f"  Document ID: {doc_id}\n"
                            error_msg += f"  Source ID: {source_id}\n"
                            error_msg += f"  Embedding ID: {embedding_id}\n"
                            error_msg += f"  Chunk: {chunk_no}, Page: {page_no}\n"
                            error_msg += f"  Model: {model_name}\n"
                            error_msg += f"  Embedding vector: {vector_info}\n"
                            error_msg += f"  QA pairs: {qa_info}\n"
                            error_msg += f"  Error: {str(e)}\n"

                            # Get traceback
                            import traceback
                            tb = traceback.format_exc()
                            error_msg += f"\nTraceback:\n{tb}\n"

                            logger.error(error_msg)
                            print(error_msg)

                            # Save error details to file for later analysis
                            with open(f"qa_embedding_error_{doc_id}_{chunk_no}.log", "w") as f:
                                f.write(error_msg)

                                # Include a sample of the text if available
                                if text and isinstance(text, str):
                                    f.write("\nText sample (first 500 chars):\n")
                                    f.write(text[:500])

                                # Include a sample of the embedding vector if available
                                if embedding_vector and hasattr(embedding_vector, '__iter__'):
                                    f.write("\nEmbedding vector sample (first 10 values):\n")
                                    try:
                                        f.write(str(list(embedding_vector)[:10]))
                                    except:
                                        f.write("Could not convert embedding vector to string")

                                # Include a sample of the QA pairs if available
                                if qa_pairs and hasattr(qa_pairs, '__iter__'):
                                    f.write("\nQA pairs sample (first 2 pairs):\n")
                                    try:
                                        import json
                                        f.write(json.dumps(qa_pairs[:2] if isinstance(qa_pairs, list) else qa_pairs, indent=2))
                                    except:
                                        f.write("Could not convert QA pairs to string")

                            batch_errors += 1
                            error_count += 1

                            # Always stop on first error to diagnose the issue
                            raise Exception(f"Migration stopped due to error with document {doc_id}, chunk {chunk_no}. Check the error log for details.")

                        pbar.update(1)

                    # Save checkpoint after each batch
                    if not self.dry_run:
                        new_offset = offset + len(qaembeddings)
                        with open(checkpoint_file, 'w') as f:
                            f.write(str(new_offset))

                    logger.info(f"Batch completed: {batch_success} succeeded, {batch_errors} failed")

                    offset += self.batch_size

                    # Break if we've processed all QA embeddings
                    if len(qaembeddings) < self.batch_size:
                        break
            except KeyboardInterrupt:
                logger.warning("Migration interrupted by user")
                print("\nMigration interrupted by user")
                print(f"Progress saved at offset {offset}")
                print(f"Run the script again to resume from this point")
                # Don't re-raise the exception, let the function complete normally

        logger.info(f"Migrated {migrated_count} legacy QA embeddings with {error_count} errors")
        print(f"Migrated {migrated_count} legacy QA embeddings with {error_count} errors")

        # Remove checkpoint file if migration completed successfully
        if not self.dry_run and migrated_count + error_count + skipped_count >= total_embeddings:
            try:
                if os.path.exists(checkpoint_file):
                    os.remove(checkpoint_file)
                    logger.info("Removed checkpoint file")
            except Exception as e:
                logger.error(f"Error removing checkpoint file: {e}")

    def create_indices(self):
        """Create indices for the unified_multiembeddings table."""
        logger.info("Creating indices")

        if not self.dry_run:
            # Create indices
            self.unified_multiembeddings_db._create_indices()

            logger.info("Indices created")
        else:
            logger.info("Dry run: Would create indices")


def main():
    """Run the migration."""
    global args

    parser = argparse.ArgumentParser(description='Migrate embeddings to the unified multiembeddings system')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry run)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--skip-tables', action='store_true', help='Skip table creation')
    parser.add_argument('--skip-embeddings', action='store_true', help='Skip embeddings migration')
    parser.add_argument('--skip-qaembeddings', action='store_true', help='Skip QA embeddings migration')
    parser.add_argument('--skip-indices', action='store_true', help='Skip indices creation')
    parser.add_argument('--continue-on-error', action='store_true', help='Continue migration even if individual embeddings fail')
    parser.add_argument('--start-document-id', type=int, default=0, help='Start migration from this document ID (default: 0)')
    parser.add_argument('--end-document-id', type=int, default=0, help='End migration at this document ID (default: 0 = no limit)')
    parser.add_argument('--timeout', type=int, default=30, help='Database operation timeout in seconds (default: 30)')
    args = parser.parse_args()

    # Set database timeout
    os.environ['PGCONNECT_TIMEOUT'] = str(args.timeout)
    os.environ['PGTIMEOUT'] = str(args.timeout)

    dry_run = not args.execute
    batch_size = args.batch_size

    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    if dry_run:
        logger.info("Running in DRY RUN mode. No changes will be made.")
        logger.info("Use --execute to actually perform the migration.")

    print("Starting unified multiembeddings migration...")
    print(f"Options: dry_run={dry_run}, batch_size={batch_size}, skip_tables={args.skip_tables}, "
          f"skip_embeddings={args.skip_embeddings}, skip_qaembeddings={args.skip_qaembeddings}, "
          f"skip_indices={args.skip_indices}, continue_on_error={args.continue_on_error}")

    try:
        # Initialize migration
        print("Initializing migration...")
        migration = UnifiedMultiEmbeddingsMigration(dry_run=dry_run, batch_size=batch_size, continue_on_error=args.continue_on_error)
        print("Migration initialized")

        # Setup tables
        if not args.skip_tables:
            print("Setting up tables...")
            migration.setup_tables()
            print("Tables setup complete")
        else:
            print("Skipping table creation")

        # Check if legacy tables exist
        print("Checking for legacy embeddings tables...")
        embeddings_exist = migration.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'embeddings')")
        qaembeddings_exist = migration.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'qaembeddings')")

        print(f"Legacy embeddings table exists: {embeddings_exist[0]['exists'] if embeddings_exist else False}")
        print(f"Legacy QA embeddings table exists: {qaembeddings_exist[0]['exists'] if qaembeddings_exist else False}")

        # Check for document_ref_id columns
        if embeddings_exist and embeddings_exist[0]['exists']:
            print("Checking for document_ref_id column in embeddings table...")
            column_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'embeddings'
                AND column_name = 'document_ref_id'
            );
            """
            column_result = migration.execute(column_query)
            print(f"document_ref_id column exists in embeddings table: {column_result[0]['exists'] if column_result else False}")

        if qaembeddings_exist and qaembeddings_exist[0]['exists']:
            print("Checking for document_ref_id column in qaembeddings table...")
            column_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'qaembeddings'
                AND column_name = 'document_ref_id'
            );
            """
            column_result = migration.execute(column_query)
            print(f"document_ref_id column exists in qaembeddings table: {column_result[0]['exists'] if column_result else False}")

        # Migrate legacy embeddings
        if not args.skip_embeddings:
            print("Starting migration of legacy embeddings...")
            migration.migrate_legacy_embeddings()
            print("Legacy embeddings migration complete")
        else:
            print("Skipping embeddings migration")

        # Migrate legacy QA embeddings
        if not args.skip_qaembeddings:
            print("Starting migration of legacy QA embeddings...")
            migration.migrate_legacy_qaembeddings()
            print("Legacy QA embeddings migration complete")
        else:
            print("Skipping QA embeddings migration")

        # Create indices
        if not args.skip_indices:
            print("Creating indices...")
            migration.create_indices()
            print("Indices created")
        else:
            print("Skipping indices creation")

        logger.info("Unified multiembeddings migration completed successfully")
        print("Unified multiembeddings migration completed successfully")
    except Exception as e:
        logger.error(f"Unified multiembeddings migration failed: {e}")
        print(f"ERROR: Unified multiembeddings migration failed: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        print(f"Error details:\n{error_trace}")
        return 1
    finally:
        if 'migration' in locals():
            print("Closing database connection...")
            migration.close()
            print("Database connection closed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
