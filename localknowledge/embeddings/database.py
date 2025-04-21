"""
Database manager for vector embeddings.

This module provides a database manager for storing and retrieving vector embeddings
using PostgreSQL with the pgvector extension.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class EmbeddingDatabaseManager(DatabaseManager):
    """Database manager for vector embeddings."""

    def __init__(self):
        """Initialize the embedding database manager."""
        super().__init__()
        self.create_tables()
        self.create_indices()

    def create_tables(self) -> None:
        """Create embedding-related tables if they don't exist."""
        # First, ensure pgvector extension is installed
        try:
            self.execute("CREATE EXTENSION IF NOT EXISTS vector", commit=False)
            logger.info("pgvector extension created or verified")
        except Exception as e:
            logger.error(f"Error creating pgvector extension: {e}")
            logger.error("Please make sure pgvector is installed in your PostgreSQL instance")
            raise

        # Create embeddings table
        self.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            chunk_no INTEGER NOT NULL,
            page_no INTEGER,
            text TEXT NOT NULL,
            keywords TEXT[],
            embedding vector(1024),
            model_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_id, document_id, chunk_no)
        )
        """, commit=False)
        logger.info("Embeddings table created or verified")

    def create_indices(self) -> None:
        """Create indices for the embeddings table."""
        # Create index for source_id and document_id
        self.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_source_id ON embeddings(source_id)", commit=False)
        self.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_document_id ON embeddings(document_id)", commit=False)

        # Create index for the embedding vector
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """, commit=False)
        logger.info("Embedding indices created or verified")

    def store_embedding(self,
                        source_id: str,
                        document_id: str,
                        chunk_no: int,
                        text: str,
                        embedding: List[float],
                        model_name: str,
                        page_no: Optional[int] = None,
                        keywords: Optional[List[str]] = None) -> int:
        """
        Store an embedding in the database.

        Args:
            source_id: Source identifier (e.g., 'pubmed', 'medrxiv')
            document_id: Document identifier (e.g., PMID, DOI)
            chunk_no: Chunk number within the document
            text: Text that was embedded
            embedding: Vector embedding as a list of floats
            model_name: Name of the model used to create the embedding
            page_no: Page number (optional)
            keywords: List of keywords (optional)

        Returns:
            ID of the stored embedding
        """
        query = """
        INSERT INTO embeddings
            (source_id, document_id, chunk_no, page_no, text, keywords, embedding, model_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, document_id, chunk_no) DO UPDATE SET
            page_no = EXCLUDED.page_no,
            text = EXCLUDED.text,
            keywords = EXCLUDED.keywords,
            embedding = EXCLUDED.embedding,
            model_name = EXCLUDED.model_name,
            created_at = CURRENT_TIMESTAMP
        RETURNING id
        """

        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        params = (
            source_id,
            document_id,
            chunk_no,
            page_no,
            text,
            keywords,
            embedding_str,
            model_name
        )

        try:
            result = self.execute(query, params, commit=False)
            if result and len(result) > 0:
                return result[0]['id']
            return -1
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            raise

    def store_embeddings_batch(self, embeddings: List[Dict[str, Any]]) -> int:
        """
        Store multiple embeddings in the database.

        Args:
            embeddings: List of dictionaries containing embedding data

        Returns:
            Number of embeddings stored
        """
        if not embeddings:
            return 0

        # For bulk operations, use execute_many
        query = """
        INSERT INTO embeddings
            (source_id, document_id, chunk_no, page_no, text, keywords, embedding, model_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, document_id, chunk_no) DO UPDATE SET
            page_no = EXCLUDED.page_no,
            text = EXCLUDED.text,
            keywords = EXCLUDED.keywords,
            embedding = EXCLUDED.embedding,
            model_name = EXCLUDED.model_name,
            created_at = CURRENT_TIMESTAMP
        """

        params_list = []
        for emb in embeddings:
            # Convert embedding to PostgreSQL vector format
            embedding_str = f"[{','.join(map(str, emb['embedding']))}]"

            params = (
                emb.get('source_id', ''),
                emb.get('document_id', ''),
                emb.get('chunk_no', 0),
                emb.get('page_no'),
                emb.get('text', ''),
                emb.get('keywords'),
                embedding_str,
                emb.get('model_name', '')
            )
            params_list.append(params)

        try:
            self.execute_many(query, params_list, commit=False)
            return len(embeddings)
        except Exception as e:
            logger.error(f"Error storing embeddings batch: {e}")
            # Fall back to storing one by one if batch fails
            count = 0
            for emb in embeddings:
                try:
                    self.store_embedding(
                        emb.get('source_id', ''),
                        emb.get('document_id', ''),
                        emb.get('chunk_no', 0),
                        emb.get('text', ''),
                        emb.get('embedding', []),
                        emb.get('model_name', ''),
                        emb.get('page_no'),
                        emb.get('keywords')
                    )
                    count += 1
                except Exception:
                    continue
            return count

    def search_similar(self,
                       query_embedding: List[float],
                       limit: int = 10,
                       threshold: float = 0.7,
                       source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity.

        Args:
            query_embedding: Vector embedding of the query
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (optional)

        Returns:
            List of similar documents with similarity scores
        """
        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Build the query
        query = """
        SELECT id, source_id, document_id, chunk_no, page_no, text, keywords, model_name,
               1 - (embedding <=> %s::vector) AS similarity
        FROM embeddings
        """

        # Add source_id filter if provided
        params = [embedding_str]
        if source_id:
            query += " WHERE source_id = %s"
            params.append(source_id)

        # Add similarity threshold and limit
        query += f" WHERE 1 - (embedding <=> %s::vector) > {threshold}"
        query += " ORDER BY similarity DESC"
        query += f" LIMIT {limit}"

        try:
            results = self.execute(query, tuple(params))
            return results or []
        except Exception as e:
            logger.error(f"Error searching similar documents: {e}")
            return []

    def get_document_embeddings(self, source_id: str, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            List of embeddings for the document
        """
        query = """
        SELECT id, source_id, document_id, chunk_no, page_no, text, keywords, model_name
        FROM embeddings
        WHERE source_id = %s AND document_id = %s
        ORDER BY chunk_no
        """

        try:
            results = self.execute(query, (source_id, document_id))
            return results or []
        except Exception as e:
            logger.error(f"Error getting document embeddings: {e}")
            return []

    def delete_document_embeddings(self, source_id: str, document_id: str) -> int:
        """
        Delete all embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        query = """
        DELETE FROM embeddings
        WHERE source_id = %s AND document_id = %s
        RETURNING id
        """

        try:
            results = self.execute(query, (source_id, document_id))
            return len(results) if results else 0
        except Exception as e:
            logger.error(f"Error deleting document embeddings: {e}")
            return 0
