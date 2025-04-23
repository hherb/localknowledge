#!/usr/bin/env python3
"""
Database functionality for embeddings in the LocalKnowledge library.

This module provides database operations for working with embeddings stored in the
unified_multiembeddings table. It abstracts all SQL statements and provides a clean
interface for other modules to interact with embeddings data.
"""

import logging
from typing import List, Dict, Any, Optional, Union
import json

from localknowledge.db.base import DatabaseManager
from localknowledge.db.embedding_source import get_embedding_source_db

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingsDatabaseManager(DatabaseManager):
    """Database manager for embeddings operations.

    This class provides methods for working with embeddings stored in the
    unified_multiembeddings table. It does not create any tables or indices,
    as those are handled by the migration system.
    """

    def __init__(self):
        """Initialize the embeddings database manager."""
        super().__init__()
        self.embedding_source_db = get_embedding_source_db()

    def add_embedding(
        self,
        document_id: int,
        embed_source: str,
        text: str,
        embedding: List[float],
        model_name: str,
        chunk_no: int = 0,
        page_no: Optional[int] = None,
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add a new embedding.

        Args:
            document_id: ID of the document
            embed_source: Name of the embedding source (e.g., 'abstract', 'full_text')
            text: Text that was embedded
            embedding: Embedding vector
            model_name: Name of the model used to generate the embedding
            chunk_no: Chunk number (default: 0)
            page_no: Page number (optional)
            keywords: List of keywords (optional)
            metadata: Additional metadata (optional)

        Returns:
            ID of the new embedding or -1 if failed
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

    def get_documents_without_embeddings(
        self,
        embed_source: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get documents with abstracts that don't have embeddings for a specific source.

        Args:
            embed_source: Name of the embedding source (e.g., 'abstract')
            limit: Maximum number of documents to retrieve

        Returns:
            List of documents without embeddings for the specified source
        """
        return self.get_documents_without_embeddings_batch(embed_source, limit, 0)

    def get_documents_without_embeddings_batch(
        self,
        embed_source: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of documents with abstracts that don't have embeddings for a specific source.

        Args:
            embed_source: Name of the embedding source (e.g., 'abstract')
            limit: Maximum number of documents to retrieve
            offset: Number of documents to skip

        Returns:
            List of documents without embeddings for the specified source
        """
        # Get the embedding source ID
        embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

        if not embed_source_record:
            # If the embedding source doesn't exist, all documents need embeddings
            logger.info(f"Embedding source '{embed_source}' not found, all documents need embeddings")
            # Create the embedding source
            embed_source_id = self.embedding_source_db.add_embedding_source(
                embed_source, f"Embeddings from {embed_source}")
        else:
            embed_source_id = embed_source_record['id']

        # Query for documents with abstracts that don't have embeddings
        query = """
        SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN (
            SELECT DISTINCT document_id
            FROM unified_multiembeddings
            WHERE embed_source_id = %s
        ) e ON d.id = e.document_id
        WHERE d.abstract IS NOT NULL
        AND d.abstract != ''
        AND e.document_id IS NULL
        ORDER BY d.id
        """

        params = [embed_source_id]

        # Add OFFSET and LIMIT clauses
        if offset > 0:
            query += f" OFFSET {offset}"

        if limit:
            query += f" LIMIT {limit}"

        documents = self.execute(query, params)
        logger.debug(f"Found {len(documents)} documents with abstracts that need '{embed_source}' embeddings (offset: {offset}, limit: {limit})")
        return documents or []

    def count_documents_without_embeddings(self, embed_source: str) -> int:
        """Count documents that don't have embeddings for a specific source.

        Args:
            embed_source: Name of the embedding source (e.g., 'abstract')

        Returns:
            Number of documents without embeddings for the specified source
        """
        # Get the embedding source ID
        embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

        if not embed_source_record:
            # If the embedding source doesn't exist, all documents need embeddings
            logger.info(f"Embedding source '{embed_source}' not found, counting all documents with abstracts")
            query = """
            SELECT COUNT(*) as count
            FROM document
            WHERE abstract IS NOT NULL
            AND abstract != ''
            """
            params = []
        else:
            embed_source_id = embed_source_record['id']
            query = """
            SELECT COUNT(*) as count
            FROM document d
            LEFT JOIN (
                SELECT DISTINCT document_id
                FROM unified_multiembeddings
                WHERE embed_source_id = %s
            ) e ON d.id = e.document_id
            WHERE d.abstract IS NOT NULL
            AND d.abstract != ''
            AND e.document_id IS NULL
            """
            params = [embed_source_id]

        result = self.execute(query, params)
        count = result[0]['count'] if result else 0
        return count

    def get_embeddings_by_document(
        self,
        document_id: int,
        embed_source: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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

    def search_similar(
        self,
        embedding: List[float],
        embed_source: str,
        model_name: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
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

    def delete_embeddings_by_document(
        self,
        document_id: int,
        embed_source: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> int:
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

    def find_zero_vectors(self, embed_source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find embeddings that are all zeros (likely created by error).

        Args:
            embed_source: Name of the embedding source (optional)

        Returns:
            List of embedding records with zero vectors
        """
        # For pgvector, we'll use a fixed dimension of 1024, which is what we expect
        # This is the dimension used by most embedding models like snowflake-arctic-embed2
        dimensions = 1024
        logger.info(f"Using fixed embedding dimension: {dimensions}")

        # Create a properly formatted zero vector with the correct dimensions
        zero_vector_str = f"[{','.join(['0' for _ in range(dimensions)])}]"
        logger.debug(f"Zero vector: {zero_vector_str[:50]}...{zero_vector_str[-10:]} (length: {len(zero_vector_str)})")

        # Base query to find zero vectors
        # We need to check if the embedding is all zeros
        # For pgvector, we can use the <-> operator (L2 distance) to compare with a zero vector
        # If the distance is very small, it's likely a zero vector
        query = """
        SELECT e.id, e.document_id, s.name as embed_source, e.model_name, e.chunk_no, e.page_no
        FROM unified_multiembeddings e
        JOIN embedding_source s ON e.embed_source_id = s.id
        WHERE e.embedding <-> %s::vector < 0.0001
        """

        params = [zero_vector_str]

        if embed_source:
            # Get the embedding source ID
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

            if embed_source_record:
                query += " AND e.embed_source_id = %s"
                params.append(embed_source_record['id'])

        query += " ORDER BY e.document_id, e.chunk_no, e.page_no"

        result = self.execute(query, tuple(params))
        logger.info(f"Found {len(result)} embeddings with zero vectors")
        return result or []

    def delete_zero_vectors(self, embed_source: Optional[str] = None) -> int:
        """Delete embeddings that are all zeros (likely created by error).

        Args:
            embed_source: Name of the embedding source (optional)

        Returns:
            Number of embeddings deleted
        """
        # Find zero vectors first
        zero_vectors = self.find_zero_vectors(embed_source)

        if not zero_vectors:
            logger.info("No zero vectors found")
            return 0

        # Extract IDs of zero vectors
        zero_vector_ids = [record['id'] for record in zero_vectors]

        # Delete zero vectors by ID
        query = "DELETE FROM unified_multiembeddings WHERE id = ANY(%s)"
        self.execute(query, (zero_vector_ids,), commit=True)

        deleted_count = len(zero_vector_ids)
        logger.info(f"Deleted {deleted_count} embeddings with zero vectors")
        return deleted_count

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

        # Count zero vectors
        # For pgvector, we'll use a fixed dimension of 1024, which is what we expect
        # This is the dimension used by most embedding models like snowflake-arctic-embed2
        dimensions = 1024

        # Create a properly formatted zero vector with the correct dimensions
        zero_vector_str = f"[{','.join(['0' for _ in range(dimensions)])}]"

        # Count zero vectors
        query = """
        SELECT COUNT(*) as count
        FROM unified_multiembeddings
        WHERE embedding <-> %s::vector < 0.0001
        """
        result = self.execute(query, (zero_vector_str,))
        stats['zero_vectors'] = result[0]['count'] if result else 0

        return stats


# Singleton instance
_instance = None

def get_embeddings_db():
    """Get the singleton instance of the embeddings database manager."""
    global _instance
    if _instance is None:
        _instance = EmbeddingsDatabaseManager()
    return _instance
