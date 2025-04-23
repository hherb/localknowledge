#!/usr/bin/env python3
"""
Database manager for unified multiembeddings.

This module provides a database manager for the unified_multiembeddings table,
which stores embeddings from multiple sources and models, referencing the document table.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

from localknowledge.db.base import DatabaseManager
from localknowledge.db.embedding_source import get_embedding_source_db
from localknowledge.db.document import DocumentDatabaseManager

logger = logging.getLogger(__name__)


class UnifiedMultiEmbeddingsDatabaseManager(DatabaseManager):
    """Database manager for unified multiembeddings."""

    def __init__(self):
        """Initialize the unified multiembeddings database manager."""
        super().__init__()
        self.embedding_source_db = get_embedding_source_db()
        self.document_db = DocumentDatabaseManager()
        self.create_tables()

    def create_tables(self):
        """Create the unified_multiembeddings table if it doesn't exist."""
        # First, ensure the embedding_source table exists
        self.embedding_source_db.create_tables()

        # Assuming pgvector is installed
        logger.info("Creating unified_multiembeddings table with vector type")
        # Create the unified_multiembeddings table with vector type
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
        logger.info("Created unified_multiembeddings table")

        # Create indices
        self._create_indices()

    def _create_indices(self):
        """Create indices for the unified_multiembeddings table."""
        # Basic indices
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
                logger.error(f"Error creating index: {e}")

        # Create vector index
        try:
            vector_index_query = """
            CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_embedding
            ON unified_multiembeddings USING ivfflat (embedding vector_cosine_ops)
            """
            self.execute(vector_index_query, commit=True)
            logger.info("Created vector index for unified_multiembeddings table")
        except Exception as e:
            logger.error(f"Error creating vector index: {e}")

        logger.info("Created indices for unified_multiembeddings table")

    def add_embedding(self, document_id: int, embed_source: str, chunk_no: int,
                     text: str, embedding: List[float], model_name: str,
                     page_no: Optional[int] = None, keywords: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add a new embedding.

        Args:
            document_id: ID of the document
            embed_source: Name of the embedding source (e.g., 'abstract', 'full_text')
            chunk_no: Chunk number
            text: Text that was embedded
            embedding: Embedding vector
            model_name: Name of the model used to generate the embedding
            page_no: Page number (optional)
            keywords: List of keywords (optional)
            metadata: Additional metadata (optional)

        Returns:
            ID of the new embedding or -1 if failed

        Raises:
            Exception: If there's an error adding the embedding
        """
        try:
            # Get or create the embedding source
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

            if not embed_source_record:
                embed_source_id = self.embedding_source_db.add_embedding_source(
                    embed_source, f"Embeddings from {embed_source}")
            else:
                embed_source_id = embed_source_record['id']

            # Validate document_id
            if not isinstance(document_id, int) or document_id <= 0:
                raise ValueError(f"Invalid document_id: {document_id}")

            # For pgvector, the embedding can be in various formats
            # PostgreSQL will handle the conversion to the vector type
            # We just need to ensure it's not None
            if embedding is None:
                raise ValueError("Embedding cannot be None")

            # Truncate text if it's too long (PostgreSQL has a limit on text size)
            if text and len(text) > 1000000:  # 1MB limit
                text = text[:1000000]
                logger.warning(f"Text truncated for document {document_id}, chunk {chunk_no} (too long)")

            # Convert metadata to JSON
            try:
                metadata_json = json.dumps(metadata) if metadata else None
            except Exception as e:
                logger.warning(f"Error converting metadata to JSON: {e}. Using None instead.")
                metadata_json = None

            query = """
            INSERT INTO unified_multiembeddings (
                document_id, embed_source_id, chunk_no, page_no, text, keywords, embedding, model_name, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id, embed_source_id, chunk_no, page_no, model_name)
            DO UPDATE SET
                text = EXCLUDED.text,
                keywords = EXCLUDED.keywords,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                created_at = CURRENT_TIMESTAMP
            RETURNING id;
            """

            result = self.execute(
                query,
                (document_id, embed_source_id, chunk_no, page_no, text, keywords, embedding, model_name, metadata_json),
                commit=True
            )

            if result:
                embedding_id = result[0]['id']
                logger.info(f"Added embedding for document {document_id}, source {embed_source}, chunk {chunk_no}")
                return embedding_id

            # Check if the embedding already exists
            check_query = """
            SELECT id FROM unified_multiembeddings
            WHERE document_id = %s AND embed_source_id = %s AND chunk_no = %s AND page_no = %s AND model_name = %s
            """

            check_result = self.execute(check_query, (document_id, embed_source_id, chunk_no, page_no, model_name))

            if check_result:
                embedding_id = check_result[0]['id']
                logger.info(f"Embedding already exists for document {document_id}, source {embed_source}, chunk {chunk_no}")
                return embedding_id

            # Log at debug level instead of error level
            logger.debug(f"Failed to add embedding for document {document_id}, source {embed_source}, chunk {chunk_no}")
            return -1
        except Exception as e:
            logger.error(f"Error adding embedding for document {document_id}, source {embed_source}, chunk {chunk_no}: {e}")
            raise

    def get_embedding(self, embedding_id: int) -> Optional[Dict[str, Any]]:
        """Get an embedding by ID.

        Args:
            embedding_id: ID of the embedding

        Returns:
            Embedding record or None if not found
        """
        query = """
        SELECT e.*, s.name as embed_source
        FROM unified_multiembeddings e
        JOIN embedding_source s ON e.embed_source_id = s.id
        WHERE e.id = %s
        """

        result = self.execute(query, (embedding_id,))

        if result:
            return result[0]

        return None

    def get_embeddings_by_document(self, document_id: int,
                                  embed_source: Optional[str] = None,
                                  model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get embeddings for a document.

        Args:
            document_id: ID of the document
            embed_source: Name of the embedding source (optional)
            model_name: Name of the model (optional)

        Returns:
            List of embedding records
        """
        query = """
        SELECT e.*, s.name as embed_source
        FROM unified_multiembeddings e
        JOIN embedding_source s ON e.embed_source_id = s.id
        WHERE e.document_id = %s
        """

        params = [document_id]

        if embed_source:
            query += " AND s.name = %s"
            params.append(embed_source)

        if model_name:
            query += " AND e.model_name = %s"
            params.append(model_name)

        query += " ORDER BY e.chunk_no, e.page_no"

        result = self.execute(query, tuple(params))

        return result or []

    def search_similar(self, embedding: List[float], embed_source: str,
                      model_name: str, limit: int = 10,
                      threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar embeddings.

        Args:
            embedding: Query embedding vector
            embed_source: Name of the embedding source
            model_name: Name of the model
            limit: Maximum number of results
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar embedding records with similarity scores
        """
        # Get the embedding source ID
        embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

        if not embed_source_record:
            logger.error(f"Embedding source not found: {embed_source}")
            return []

        embed_source_id = embed_source_record['id']

        # Check if pgvector extension is installed
        check_query = "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        result = self.execute(check_query)

        if not result or not result[0]['exists']:
            logger.warning("pgvector extension is not installed. Vector search is not available.")
            # Return empty results if pgvector is not installed
            return []

        # Check if the embedding column is of type vector
        column_query = """
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'unified_multiembeddings' AND column_name = 'embedding'
        """
        column_result = self.execute(column_query)

        if not column_result:
            logger.warning("Could not determine embedding column type. Vector search is not available.")
            return []

        # PostgreSQL reports the vector type as 'USER-DEFINED'
        if column_result[0]['data_type'] != 'USER-DEFINED':
            logger.warning(f"Embedding column is of type {column_result[0]['data_type']}, not vector. Vector search is not available.")
            return []

        try:
            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(embedding)

            query = """
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.title, d.abstract
            FROM unified_multiembeddings e
            JOIN embedding_source s ON e.embed_source_id = s.id
            JOIN document d ON e.document_id = d.id
            WHERE e.embed_source_id = %s
            AND e.model_name = %s
            AND 1 - (e.embedding <=> vector(%s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
            """

            result = self.execute(
                query,
                (embedding_str, embedding_str, embed_source_id, model_name, embedding_str, threshold, limit)
            )

            return result or []
        except Exception as e:
            logger.error(f"Error searching for similar embeddings: {e}")
            return []

    def delete_embeddings_by_document(self, document_id: int,
                                     embed_source: Optional[str] = None,
                                     model_name: Optional[str] = None) -> int:
        """Delete embeddings for a document.

        Args:
            document_id: ID of the document
            embed_source: Name of the embedding source (optional)
            model_name: Name of the model (optional)

        Returns:
            Number of embeddings deleted
        """
        query = "DELETE FROM unified_multiembeddings WHERE document_id = %s"
        params = [document_id]

        if embed_source:
            # Get the embedding source ID
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

            if embed_source_record:
                query += " AND embed_source_id = %s"
                params.append(embed_source_record['id'])

        if model_name:
            query += " AND model_name = %s"
            params.append(model_name)

        self.execute(query, tuple(params), commit=True)

        logger.info(f"Deleted embeddings for document {document_id}")

        return 1  # In a real implementation, you would return the actual count

    def migrate_from_legacy_embeddings(self, batch_size: int = 1000) -> int:
        """Migrate embeddings from the legacy embeddings table.

        Args:
            batch_size: Number of embeddings to process in each batch

        Returns:
            Number of embeddings migrated
        """
        # Check if the legacy embeddings table exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'embeddings'
        );
        """
        result = self.execute(check_query)

        if not result or not result[0]['exists']:
            logger.info("Legacy embeddings table does not exist, skipping migration")
            return 0

        # Count total embeddings to migrate
        count_query = """
        SELECT COUNT(*) as count FROM embeddings
        WHERE document_ref_id IS NOT NULL
        """
        result = self.execute(count_query)
        total_embeddings = result[0]['count'] if result else 0

        if total_embeddings == 0:
            logger.info("No legacy embeddings to migrate")
            return 0

        logger.info(f"Migrating {total_embeddings} legacy embeddings")

        # Get the abstract embedding source ID
        abstract_source = self.embedding_source_db.get_embedding_source_by_name('abstract')
        if not abstract_source:
            abstract_source_id = self.embedding_source_db.add_embedding_source(
                'abstract', 'Embeddings generated from document abstracts')
        else:
            abstract_source_id = abstract_source['id']

        # Process in batches
        offset = 0
        migrated_count = 0

        while True:
            # Get a batch of embeddings
            query = f"""
            SELECT e.*, d.id as document_id
            FROM embeddings e
            JOIN document d ON e.document_ref_id = d.id
            ORDER BY e.id
            LIMIT {batch_size} OFFSET {offset}
            """

            embeddings = self.execute(query)

            if not embeddings:
                break

            # Process each embedding
            for embedding in embeddings:
                try:
                    # Add to unified_multiembeddings
                    self.add_embedding(
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

                    migrated_count += 1

                    if migrated_count % 100 == 0:
                        logger.info(f"Migrated {migrated_count}/{total_embeddings} embeddings")

                except Exception as e:
                    logger.error(f"Error migrating embedding {embedding['id']}: {e}")

            offset += batch_size

            if len(embeddings) < batch_size:
                break

        logger.info(f"Migrated {migrated_count} legacy embeddings")

        return migrated_count

    def migrate_from_legacy_qaembeddings(self, batch_size: int = 1000) -> int:
        """Migrate QA embeddings from the legacy qaembeddings table.

        Args:
            batch_size: Number of embeddings to process in each batch

        Returns:
            Number of embeddings migrated
        """
        # Check if the legacy qaembeddings table exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'qaembeddings'
        );
        """
        result = self.execute(check_query)

        if not result or not result[0]['exists']:
            logger.info("Legacy qaembeddings table does not exist, skipping migration")
            return 0

        # Count total qaembeddings to migrate
        count_query = """
        SELECT COUNT(*) as count FROM qaembeddings
        WHERE document_ref_id IS NOT NULL
        """
        result = self.execute(count_query)
        total_embeddings = result[0]['count'] if result else 0

        if total_embeddings == 0:
            logger.info("No legacy QA embeddings to migrate")
            return 0

        logger.info(f"Migrating {total_embeddings} legacy QA embeddings")

        # Get the qa_pairs embedding source ID
        qa_source = self.embedding_source_db.get_embedding_source_by_name('qa_pairs')
        if not qa_source:
            qa_source_id = self.embedding_source_db.add_embedding_source(
                'qa_pairs', 'Embeddings generated from question-answer pairs')
        else:
            qa_source_id = qa_source['id']

        # Process in batches
        offset = 0
        migrated_count = 0

        while True:
            # Get a batch of qaembeddings
            query = f"""
            SELECT e.*, d.id as document_id
            FROM qaembeddings e
            JOIN document d ON e.document_ref_id = d.id
            ORDER BY e.id
            LIMIT {batch_size} OFFSET {offset}
            """

            qaembeddings = self.execute(query)

            if not qaembeddings:
                break

            # Process each qaembedding
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

                    # Add to unified_multiembeddings
                    self.add_embedding(
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

                    migrated_count += 1

                    if migrated_count % 100 == 0:
                        logger.info(f"Migrated {migrated_count}/{total_embeddings} QA embeddings")

                except Exception as e:
                    logger.error(f"Error migrating QA embedding {qaembedding['id']}: {e}")

            offset += batch_size

            if len(qaembeddings) < batch_size:
                break

        logger.info(f"Migrated {migrated_count} legacy QA embeddings")

        return migrated_count

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about the embeddings.

        Returns:
            Dictionary with statistics
        """
        stats = {}

        # Count total embeddings
        query = "SELECT COUNT(*) as count FROM unified_multiembeddings"
        result = self.execute(query)
        stats['total_embeddings'] = result[0]['count'] if result else 0

        # Count embeddings by source
        query = """
        SELECT s.name, COUNT(*) as count
        FROM unified_multiembeddings e
        JOIN embedding_source s ON e.embed_source_id = s.id
        GROUP BY s.name
        ORDER BY count DESC
        """
        result = self.execute(query)
        stats['embeddings_by_source'] = result or []

        # Count embeddings by model
        query = """
        SELECT model_name, COUNT(*) as count
        FROM unified_multiembeddings
        GROUP BY model_name
        ORDER BY count DESC
        """
        result = self.execute(query)
        stats['embeddings_by_model'] = result or []

        # Count documents with embeddings
        query = "SELECT COUNT(DISTINCT document_id) as count FROM unified_multiembeddings"
        result = self.execute(query)
        stats['documents_with_embeddings'] = result[0]['count'] if result else 0

        return stats


# Singleton instance
_instance = None

def get_unified_multiembeddings_db():
    """Get the singleton instance of the unified multiembeddings database manager."""
    global _instance
    if _instance is None:
        _instance = UnifiedMultiEmbeddingsDatabaseManager()
    return _instance
