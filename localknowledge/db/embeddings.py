#!/usr/bin/env python3
"""
Database functionality for embeddings in the LocalKnowledge library.

This module provides database operations for working with embeddings stored in the
emb_{vectorsize} tables. It abstracts all SQL statements and provides a clean
interface for other modules to interact with embeddings data.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import re
from functools import lru_cache

from localknowledge.db.base import DatabaseManager
from localknowledge.db.embedding_source import get_embedding_source_db

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingsDatabaseManager(DatabaseManager):
    """Database manager for embeddings operations.

    This class provides methods for working with embeddings stored in the
    emb_{vectorsize} tables. It does not create any tables or indices,
    as those are handled by the migration system.
    """

    def __init__(self):
        """Initialize the embeddings database manager."""
        super().__init__()
        self.embedding_source_db = get_embedding_source_db()

    def begin_transaction(self):
        """Begin a new transaction.

        This allows multiple operations to be grouped together and committed or rolled back as a unit.

        Note: In psycopg2, transactions are automatically started when needed, so this method
        mainly ensures we have a valid connection.
        """
        if not self.connection:
            self.connect()

        try:
            # Check if we're already in a transaction
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            logger.debug("Transaction ready")

        except Exception as e:
            logger.error(f"Error preparing transaction: {e}")
            raise

    def commit_transaction(self):
        """Commit the current transaction.

        This saves all changes made since the transaction began.
        """
        if not self.connection:
            logger.warning("No active connection to commit")
            return

        try:
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error committing transaction: {e}")
            raise

    def rollback_transaction(self):
        """Roll back the current transaction.

        This discards all changes made since the transaction began.
        """
        if not self.connection:
            logger.warning("No active connection to roll back")
            return

        logger.debug("Rolling back transaction")
        try:
            self.connection.rollback()
            logger.debug("Transaction rolled back successfully")
        except Exception as e:
            logger.error(f"Error rolling back transaction: {e}")
            # Don't raise here, as this is often called in exception handlers

    def get_tablename_for_vectorsize(self, vector_size: int) -> str:
        """Get the table name for a specific vector size.

        Args:
            vector_size: Size of the vector

        Returns:
            Name of the table for the specified vector size
        """
        return f"emb_{str(vector_size)}"

    def get_model_id(self, model_name: str) -> int:
        """Get the ID of a model by name.

        Args:
            model_name: Name of the model

        Returns:
            ID of the model or -1 if not found
        """
        query = """
        SELECT id FROM embedding_models
        WHERE model_name = %s
        """
        result = self.execute(query, (model_name,))

        if result and len(result) > 0:
            return result[0]['id']

        logger.warning(f"Model not found: {model_name}")
        return -1

    def ensure_table_for_vectorsize(self, vector_size: int) -> str:
        """Ensure a table exists for a specific vector size.
        Embedding tables follow a naming pattern depending on vector size.
        If we use a new embedding model with a previously not used vector size,
        we have to call this function to create the required table.

        Tables are created as inheritance from embedding_base table.

        Args:
            vector_size: Size of the vector

        Returns:
            Name of the table for the specified vector size
        """
        tablename = self.get_tablename_for_vectorsize(vector_size)

        # First check if the table already exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
        """
        table_exists = self.execute(check_query, (tablename,))

        if not table_exists or not table_exists[0]['exists']:
            # If the table doesn't exist, create it as inheritance from embedding_base
            self.execute(f"""
            CREATE TABLE {tablename} (
                embedding vector({vector_size})
            ) INHERITS (embedding_base)
            """, commit=True)

            # Create index for vector similarity search
            self.execute(f"""
            CREATE INDEX IF NOT EXISTS {tablename}_embedding_idx ON {tablename} USING ivfflat (embedding vector_cosine_ops)
            """, commit=True)

            # Create a unique constraint on chunk_id and model_id
            self.execute(f"""
            ALTER TABLE {tablename} ADD CONSTRAINT {tablename}_chunk_model_unique UNIQUE (chunk_id, model_id)
            """, commit=True)

            logger.info(f"Created table {tablename} for vector size {vector_size}")

        return tablename


    def add_embedding(
        self,
        chunk_id: int,
        model_id: int,
        embedding: List[float]
    ) -> int:
        """Add a new embedding.

        Args:
            chunk_id: ID of the chunk
            model_id: ID of the embedding model
            embedding: Embedding vector

        Returns:
            ID of the new embedding or -1 if failed
        """
        try:
            # Validate chunk_id
            if not isinstance(chunk_id, int) or chunk_id <= 0:
                raise ValueError(f"Invalid chunk_id: {chunk_id}")

            # Validate model_id
            if not isinstance(model_id, int) or model_id <= 0:
                raise ValueError(f"Invalid model_id: {model_id}")

            # For pgvector, the embedding can be in various formats
            # PostgreSQL will handle the conversion to the vector type
            # We just need to ensure it's not None
            if embedding is None:
                raise ValueError("Embedding cannot be None")

            # Get the vector size to determine the table name
            vector_size = len(embedding)
            tablename = self.get_tablename_for_vectorsize(vector_size)

            # Ensure the table exists
            self.ensure_table_for_vectorsize(vector_size)

            # Begin a transaction
            self.begin_transaction()

            try:
                # First check if the embedding already exists
                check_query = f"""
                SELECT id FROM {tablename}
                WHERE chunk_id = %s AND model_id = %s
                """

                check_result = self.execute(check_query, (chunk_id, model_id), commit=False)

                if check_result:
                    embedding_id = check_result[0]['id']
                    logger.info(f"Embedding already exists for chunk {chunk_id}, model {model_id} in table {tablename}")

                    # Update the existing embedding
                    update_query = f"""
                    UPDATE {tablename}
                    SET embedding = %s
                    WHERE id = %s
                    RETURNING id;
                    """

                    update_result = self.execute(update_query, (embedding, embedding_id), commit=False)

                    if update_result:
                        self.commit_transaction()
                        logger.info(f"Updated embedding for chunk {chunk_id}, model {model_id} in table {tablename}")
                        return update_result[0]['id']
                    else:
                        self.rollback_transaction()
                        logger.error(f"Failed to update embedding for chunk {chunk_id}, model {model_id} in table {tablename}")
                        return -1
                else:
                    # If the embedding doesn't exist, insert it
                    insert_query = f"""
                    INSERT INTO {tablename} (
                        chunk_id, model_id, embedding
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """

                    insert_result = self.execute(
                        insert_query,
                        (chunk_id, model_id, embedding),
                        commit=False
                    )

                    if insert_result:
                        self.commit_transaction()
                        embedding_id = insert_result[0]['id']
                        logger.info(f"Added embedding for chunk {chunk_id}, model {model_id} to table {tablename}")
                        return embedding_id
                    else:
                        self.rollback_transaction()
                        logger.debug(f"Failed to add embedding for chunk {chunk_id}, model {model_id} to table {tablename}")
                        return -1
            except Exception as inner_e:
                self.rollback_transaction()
                logger.error(f"Transaction error for chunk {chunk_id}, model {model_id}: {inner_e}")
                raise
        except Exception as e:
            logger.error(f"Error adding embedding for chunk {chunk_id}, model {model_id}: {e}")
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
        offset: int = 0,
        model_name: Optional[str] = None,
        vector_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get a batch of documents with abstracts that don't have embeddings for a specific source.

        Args:
            embed_source: Name of the embedding source (e.g., 'abstract')
            limit: Maximum number of documents to retrieve
            offset: Number of documents to skip
            model_name: Name of the model (optional)
            vector_size: Size of the embedding vector (optional)

        Returns:
            List of documents without embeddings for the specified source
        """
        # Get model_id if model_name is provided
        model_id = None
        if model_name:
            model_id = self.get_model_id(model_name)
            if model_id == -1:
                logger.warning(f"Model '{model_name}' not found in embedding_models table")
                # If the model doesn't exist, all documents need embeddings
                query = """
                SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
                FROM document d
                JOIN sources s ON d.source_id = s.id
                WHERE d.abstract IS NOT NULL
                AND d.abstract != ''
                ORDER BY d.id
                """
                params = []

                # Add OFFSET and LIMIT clauses
                if offset > 0:
                    query += f" OFFSET {offset}"
                if limit:
                    query += f" LIMIT {limit}"

                documents = self.execute(query, params)
                logger.debug(f"Found {len(documents)} documents with abstracts (model '{model_name}' not found)")
                return documents or []

        # Determine which table to check based on vector size
        if vector_size:
            tablename = self.get_tablename_for_vectorsize(vector_size)

            # Check if the table exists
            check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
            """
            table_exists = self.execute(check_table_query, (tablename,))

            if not table_exists or not table_exists[0]['exists']:
                # If the table doesn't exist, all documents need embeddings
                logger.info(f"Table '{tablename}' doesn't exist, all documents need embeddings")
                query = """
                SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
                FROM document d
                JOIN sources s ON d.source_id = s.id
                WHERE d.abstract IS NOT NULL
                AND d.abstract != ''
                ORDER BY d.id
                """
                params = []
            else:
                # Query for documents with abstracts that don't have embeddings in this specific table
                # We need to join with chunks table to get document_id
                query = f"""
                SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
                FROM document d
                JOIN sources s ON d.source_id = s.id
                LEFT JOIN (
                    SELECT DISTINCT c.document_id
                    FROM {tablename} e
                    JOIN chunks c ON e.chunk_id = c.id
                    WHERE c.chunktype_id = (SELECT id FROM chunktypes WHERE name = 'abstract')
                    {f"AND e.model_id = {model_id}" if model_id else ""}
                ) emb ON d.id = emb.document_id
                WHERE d.abstract IS NOT NULL
                AND d.abstract != ''
                AND emb.document_id IS NULL
                ORDER BY d.id
                """
                params = []
        else:
            # Without a vector size, we need to check all possible embedding tables
            # This is less efficient but necessary if we don't know the vector size

            # Get all embedding tables
            tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'emb_%'
            """
            tables = self.execute(tables_query)

            if not tables:
                # If no embedding tables exist, all documents need embeddings
                logger.info("No embedding tables found, all documents need embeddings")
                query = """
                SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
                FROM document d
                JOIN sources s ON d.source_id = s.id
                WHERE d.abstract IS NOT NULL
                AND d.abstract != ''
                ORDER BY d.id
                """
                params = []
            else:
                # Build a query that checks all embedding tables
                table_subqueries = []
                for table in tables:
                    tablename = table['table_name']
                    table_subqueries.append(f"""
                    SELECT DISTINCT c.document_id
                    FROM {tablename} e
                    JOIN chunks c ON e.chunk_id = c.id
                    WHERE c.chunktype_id = (SELECT id FROM chunktypes WHERE name = 'abstract')
                    {f"AND e.model_id = {model_id}" if model_id else ""}
                    """)

                # Combine all subqueries with UNION
                union_query = " UNION ".join(table_subqueries)

                # Main query
                query = f"""
                SELECT d.id, d.source_id, s.name as source_name, d.external_id, d.title, d.abstract
                FROM document d
                JOIN sources s ON d.source_id = s.id
                LEFT JOIN (
                    {union_query}
                ) emb ON d.id = emb.document_id
                WHERE d.abstract IS NOT NULL
                AND d.abstract != ''
                AND emb.document_id IS NULL
                ORDER BY d.id
                """
                params = []

        # Add OFFSET and LIMIT clauses
        if offset > 0:
            query += f" OFFSET {offset}"

        if limit:
            query += f" LIMIT {limit}"

        documents = self.execute(query, params)
        logger.debug(f"Found {len(documents)} documents with abstracts that need embeddings (offset: {offset}, limit: {limit})")
        return documents or []

    def count_documents_without_embeddings(self, embed_source: str, model_name: Optional[str] = None, vector_size: Optional[int] = None) -> int:
        """Count documents that don't have embeddings for a specific source.

        Args:
            embed_source: Name of the embedding source (e.g., 'abstract')
            model_name: Name of the model (optional)
            vector_size: Size of the embedding vector (optional)

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

            # Determine which table to check based on vector size
            if vector_size:
                tablename = self.get_tablename_for_vectorsize(vector_size)

                # Check if the table exists
                check_table_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                )
                """
                table_exists = self.execute(check_table_query, (tablename,))

                if not table_exists or not table_exists[0]['exists']:
                    # If the table doesn't exist, all documents need embeddings
                    logger.info(f"Table '{tablename}' doesn't exist, counting all documents with abstracts")
                    query = """
                    SELECT COUNT(*) as count
                    FROM document
                    WHERE abstract IS NOT NULL
                    AND abstract != ''
                    """
                    params = []
                else:
                    # Count documents with abstracts that don't have embeddings in this specific table
                    query = f"""
                    SELECT COUNT(*) as count
                    FROM document d
                    LEFT JOIN (
                        SELECT DISTINCT document_id
                        FROM {tablename}
                        WHERE embed_source_id = %s
                        {f"AND model_name = '{model_name}'" if model_name else ""}
                    ) e ON d.id = e.document_id
                    WHERE d.abstract IS NOT NULL
                    AND d.abstract != ''
                    AND e.document_id IS NULL
                    """
                    params = [embed_source_id]
            else:
                # Without a vector size, we need to check all possible embedding tables
                # This is less efficient but necessary if we don't know the vector size

                # Get all embedding tables
                tables_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name LIKE 'emb_%'
                """
                tables = self.execute(tables_query)

                if not tables:
                    # If no embedding tables exist, all documents need embeddings
                    logger.info("No embedding tables found, counting all documents with abstracts")
                    query = """
                    SELECT COUNT(*) as count
                    FROM document
                    WHERE abstract IS NOT NULL
                    AND abstract != ''
                    """
                    params = []
                else:
                    # Build a query that checks all embedding tables
                    table_subqueries = []
                    for table in tables:
                        tablename = table['table_name']
                        table_subqueries.append(f"""
                        SELECT DISTINCT document_id
                        FROM {tablename}
                        WHERE embed_source_id = %s
                        {f"AND model_name = '{model_name}'" if model_name else ""}
                        """)

                    # Combine all subqueries with UNION
                    union_query = " UNION ".join(table_subqueries)

                    # Main query
                    query = f"""
                    SELECT COUNT(*) as count
                    FROM document d
                    LEFT JOIN (
                        {union_query}
                    ) e ON d.id = e.document_id
                    WHERE d.abstract IS NOT NULL
                    AND d.abstract != ''
                    AND e.document_id IS NULL
                    """

                    # For each table in the UNION, we need to add the embed_source_id parameter
                    params = [embed_source_id] * len(tables)

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

    @lru_cache(maxsize=100)
    def sanity_check(self, embed_source: Union[str, int], vector_size: int) -> Tuple[bool, Optional[str], Optional[int]]:
        """Perform sanity checks for embedding operations.

        This method checks:
        1. If the embedding source exists
        2. If pgvector extension is installed
        3. If the table for the vector size exists
        4. If the embedding column is of the correct type

        Args:
            embed_source: Name of the embedding source or source ID
            vector_size: Size of the embedding vector

        Returns:
            Tuple of (success, tablename, embed_source_id)
            - success: True if all checks pass, False otherwise
            - tablename: Name of the table for the vector size if success is True, None otherwise
            - embed_source_id: ID of the embedding source if success is True, None otherwise
        """
        # Handle both string and integer embed_source
        if isinstance(embed_source, str):
            # Get the embedding source ID by name
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)

            if not embed_source_record:
                logger.error(f"Embedding source not found: {embed_source}")
                return False, None, None

            embed_source_id = embed_source_record['id']
        else:
            # Use the provided ID directly
            embed_source_id = embed_source

            # Verify that the ID exists
            embed_source_record = self.embedding_source_db.get_embedding_source_by_id(embed_source_id)

            if not embed_source_record:
                logger.error(f"Embedding source ID not found: {embed_source_id}")
                return False, None, None

        # Check if pgvector extension is installed
        check_query = "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        result = self.execute(check_query)

        if not result or not result[0]['exists']:
            logger.warning("pgvector extension is not installed. Vector search is not available.")
            return False, None, None

        # Get the table name for the vector size
        tablename = self.get_tablename_for_vectorsize(vector_size)

        # Check if the table exists
        check_table_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
        """
        table_exists = self.execute(check_table_query, (tablename,))

        if not table_exists or not table_exists[0]['exists']:
            logger.warning(f"Table '{tablename}' doesn't exist. Vector search is not available.")
            return False, None, None

        # Check if the embedding column is of type vector
        column_query = f"""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = '{tablename}' AND column_name = 'embedding'
        """
        column_result = self.execute(column_query)

        if not column_result:
            logger.warning(f"Could not determine embedding column type for table {tablename}. Vector search is not available.")
            return False, None, None

        # PostgreSQL reports the vector type as 'USER-DEFINED'
        if column_result[0]['data_type'] != 'USER-DEFINED':
            logger.warning(f"Embedding column in table {tablename} is of type {column_result[0]['data_type']}, not vector. Vector search is not available.")
            return False, None, None

        # All checks passed
        return True, tablename, embed_source_id

    def search_similar(
        self,
        embedding: List[float],
        embed_source: Union[str, int],
        model_name: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings.

        Args:
            embedding: Query embedding vector
            embed_source: Name of the embedding source or source ID
            model_name: Name of the model
            limit: Maximum number of results
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar embedding records with similarity scores
        """
        # Get the vector size to determine the table name
        vector_size = len(embedding)

        # Perform sanity checks
        success, tablename, embed_source_id = self.sanity_check(embed_source, vector_size)
        if not success:
            return []

        try:
            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(embedding)

            query = f"""
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.title, d.abstract
            FROM {tablename} e
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
        model_name: Optional[str] = None,
        vector_size: Optional[int] = None
    ) -> int:
        """Delete embeddings for a document.

        Args:
            document_id: ID of the document
            embed_source: Name of the embedding source (optional)
            model_name: Name of the model (optional)
            vector_size: Size of the embedding vector (optional)

        Returns:
            Number of embeddings deleted
        """
        total_deleted = 0

        # Get embed_source_id if provided
        embed_source_id = None
        if embed_source:
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)
            if embed_source_record:
                embed_source_id = embed_source_record['id']

        # Get model_id if model_name is provided
        model_id = None
        if model_name:
            model_id = self.get_model_id(model_name)
            if model_id == -1:
                logger.warning(f"Model '{model_name}' not found in embedding_models table")

        # If vector_size is provided, delete from that specific table
        if vector_size:
            tablename = self.get_tablename_for_vectorsize(vector_size)

            # Check if the table exists
            check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
            """
            table_exists = self.execute(check_table_query, (tablename,))

            if table_exists and table_exists[0]['exists']:
                query = f"DELETE FROM {tablename} WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = %s)"
                params = [document_id]

                if model_id:
                    query += f" AND model_id = %s"
                    params.append(model_id)

                # Add RETURNING to get the count of deleted rows
                query += " RETURNING id"

                result = self.execute(query, tuple(params), commit=True)
                deleted_count = len(result) if result else 0
                total_deleted += deleted_count
                logger.info(f"Deleted embeddings for document {document_id} from table {tablename}")
        else:
            # Without a vector size, delete directly from embedding_base
            # This will cascade to all inherited tables due to PostgreSQL inheritance
            query = """
            DELETE FROM embedding_base
            WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = %s)
            """
            params = [document_id]

            if model_id:
                query += f" AND model_id = %s"
                params.append(model_id)

            # Add RETURNING to get the count of deleted rows
            query += " RETURNING id"

            result = self.execute(query, tuple(params), commit=True)
            deleted_count = len(result) if result else 0
            total_deleted = deleted_count
            logger.info(f"Deleted {deleted_count} embeddings for document {document_id} from embedding_base (affects all embedding tables)")

        return total_deleted

    def find_zero_vectors(self, embed_source: Optional[str] = None, vector_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find embeddings that are all zeros (likely created by error).

        Args:
            embed_source: Name of the embedding source (optional)
            vector_size: Size of the embedding vector (optional)

        Returns:
            List of embedding records with zero vectors
        """
        all_results = []

        # Get embed_source_id if provided
        embed_source_id = None
        if embed_source:
            embed_source_record = self.embedding_source_db.get_embedding_source_by_name(embed_source)
            if embed_source_record:
                embed_source_id = embed_source_record['id']

        # If vector_size is provided, check that specific table
        if vector_size:
            tablename = self.get_tablename_for_vectorsize(vector_size)

            # Check if the table exists
            check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
            """
            table_exists = self.execute(check_table_query, (tablename,))

            if table_exists and table_exists[0]['exists']:
                # Create a properly formatted zero vector with the correct dimensions
                zero_vector_str = f"[{','.join(['0' for _ in range(vector_size)])}]"

                # Base query to find zero vectors
                query = f"""
                SELECT e.id, e.document_id, s.name as embed_source, e.model_name, e.chunk_no, e.page_no, '{tablename}' as table_name
                FROM {tablename} e
                JOIN embedding_source s ON e.embed_source_id = s.id
                WHERE e.embedding <-> %s::vector < 0.0001
                """

                params = [zero_vector_str]

                if embed_source_id:
                    query += " AND e.embed_source_id = %s"
                    params.append(embed_source_id)

                query += " ORDER BY e.document_id, e.chunk_no, e.page_no"

                result = self.execute(query, tuple(params))
                if result:
                    all_results.extend(result)
                logger.info(f"Found {len(result) if result else 0} embeddings with zero vectors in table {tablename}")
        else:
            # Without a vector size, check all embedding tables
            # Get all embedding tables
            tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'emb_%'
            """
            tables = self.execute(tables_query)

            if tables:
                for table in tables:
                    tablename = table['table_name']

                    # Extract vector size from table name
                    try:
                        table_vector_size = int(tablename.split('_')[1])
                    except (IndexError, ValueError):
                        logger.warning(f"Could not determine vector size from table name: {tablename}")
                        continue

                    # Create a properly formatted zero vector with the correct dimensions
                    zero_vector_str = f"[{','.join(['0' for _ in range(table_vector_size)])}]"

                    # Base query to find zero vectors
                    query = f"""
                    SELECT e.id, e.document_id, s.name as embed_source, e.model_name, e.chunk_no, e.page_no, '{tablename}' as table_name
                    FROM {tablename} e
                    JOIN embedding_source s ON e.embed_source_id = s.id
                    WHERE e.embedding <-> %s::vector < 0.0001
                    """

                    params = [zero_vector_str]

                    if embed_source_id:
                        query += " AND e.embed_source_id = %s"
                        params.append(embed_source_id)

                    query += " ORDER BY e.document_id, e.chunk_no, e.page_no"

                    result = self.execute(query, tuple(params))
                    if result:
                        all_results.extend(result)
                    logger.info(f"Found {len(result) if result else 0} embeddings with zero vectors in table {tablename}")

        logger.info(f"Found a total of {len(all_results)} embeddings with zero vectors")
        return all_results

    def delete_zero_vectors(self, embed_source: Optional[str] = None, vector_size: Optional[int] = None) -> int:
        """Delete embeddings that are all zeros (likely created by error).

        Args:
            embed_source: Name of the embedding source (optional)
            vector_size: Size of the embedding vector (optional)

        Returns:
            Number of embeddings deleted
        """
        # Find zero vectors first
        zero_vectors = self.find_zero_vectors(embed_source, vector_size)

        if not zero_vectors:
            logger.info("No zero vectors found")
            return 0

        # Group zero vectors by table
        vectors_by_table = {}
        for record in zero_vectors:
            table = record['table_name']
            if table not in vectors_by_table:
                vectors_by_table[table] = []
            vectors_by_table[table].append(record['id'])

        total_deleted = 0

        # Delete zero vectors from each table
        for table, ids in vectors_by_table.items():
            query = f"DELETE FROM {table} WHERE id = ANY(%s)"
            self.execute(query, (ids,), commit=True)

            deleted_count = len(ids)
            total_deleted += deleted_count
            logger.info(f"Deleted {deleted_count} embeddings with zero vectors from table {table}")

        logger.info(f"Deleted a total of {total_deleted} embeddings with zero vectors")
        return total_deleted

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about the embeddings.

        Returns:
            Dictionary with statistics
        """
        stats = {}

        # Get all embedding tables
        tables_query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name LIKE 'emb_%'
        """
        tables = self.execute(tables_query)

        if not tables:
            logger.warning("No embedding tables found")
            return {
                'total_embeddings': 0,
                'embeddings_by_source': [],
                'embeddings_by_model': [],
                'embeddings_by_table': [],
                'documents_with_embeddings': 0,
                'zero_vectors': 0
            }

        # Initialize counters
        total_embeddings = 0
        embeddings_by_source = {}
        embeddings_by_model = {}
        embeddings_by_table = []
        documents_with_embeddings_set = set()
        total_zero_vectors = 0

        # Process each table
        for table in tables:
            tablename = table['table_name']

            # Count embeddings in this table
            count_query = f"SELECT COUNT(*) as count FROM {tablename}"
            count_result = self.execute(count_query)
            table_count = count_result[0]['count'] if count_result else 0
            total_embeddings += table_count

            # Add to embeddings_by_table
            embeddings_by_table.append({
                'table_name': tablename,
                'count': table_count
            })

            # Count embeddings by source in this table
            source_query = f"""
            SELECT s.name, COUNT(*) as count
            FROM {tablename} e
            JOIN embedding_source s ON e.embed_source_id = s.id
            GROUP BY s.name
            """
            source_result = self.execute(source_query)

            if source_result:
                for row in source_result:
                    source_name = row['name']
                    if source_name in embeddings_by_source:
                        embeddings_by_source[source_name] += row['count']
                    else:
                        embeddings_by_source[source_name] = row['count']

            # Count embeddings by model in this table
            model_query = f"""
            SELECT model_name, COUNT(*) as count
            FROM {tablename}
            GROUP BY model_name
            """
            model_result = self.execute(model_query)

            if model_result:
                for row in model_result:
                    model_name = row['model_name']
                    if model_name in embeddings_by_model:
                        embeddings_by_model[model_name] += row['count']
                    else:
                        embeddings_by_model[model_name] = row['count']

            # Get document IDs with embeddings in this table
            doc_query = f"SELECT DISTINCT document_id FROM {tablename}"
            doc_result = self.execute(doc_query)

            if doc_result:
                for row in doc_result:
                    documents_with_embeddings_set.add(row['document_id'])

            # Extract vector size from table name
            try:
                vector_size = int(tablename.split('_')[1])

                # Create a properly formatted zero vector with the correct dimensions
                zero_vector_str = f"[{','.join(['0' for _ in range(vector_size)])}]"

                # Count zero vectors in this table
                zero_query = f"""
                SELECT COUNT(*) as count
                FROM {tablename}
                WHERE embedding <-> %s::vector < 0.0001
                """
                zero_result = self.execute(zero_query, (zero_vector_str,))

                if zero_result:
                    total_zero_vectors += zero_result[0]['count']
            except (IndexError, ValueError):
                logger.warning(f"Could not determine vector size from table name: {tablename}")

        # Convert dictionaries to sorted lists
        embeddings_by_source_list = [
            {'name': name, 'count': count}
            for name, count in embeddings_by_source.items()
        ]
        embeddings_by_source_list.sort(key=lambda x: x['count'], reverse=True)

        embeddings_by_model_list = [
            {'model_name': name, 'count': count}
            for name, count in embeddings_by_model.items()
        ]
        embeddings_by_model_list.sort(key=lambda x: x['count'], reverse=True)

        # Sort embeddings_by_table
        embeddings_by_table.sort(key=lambda x: x['count'], reverse=True)

        # Build the final stats dictionary
        stats['total_embeddings'] = total_embeddings
        stats['embeddings_by_source'] = embeddings_by_source_list
        stats['embeddings_by_model'] = embeddings_by_model_list
        stats['embeddings_by_table'] = embeddings_by_table
        stats['documents_with_embeddings'] = len(documents_with_embeddings_set)
        stats['zero_vectors'] = total_zero_vectors

        return stats


    @staticmethod
    @lru_cache(maxsize=100)
    def model_to_tablename(model_name: str) -> str:
        """
        Convert model name to valid SQL table name, ensuring it's under 63 bytes.

        Args:
            model_name: Name of the embedding model

        Returns:
            Valid PostgreSQL table name under 63 bytes
        """
        # Remove version tags and convert to lowercase
        base_name = model_name.split(':')[0].lower()

        # Replace non-alphanumeric chars with underscore
        clean_name = re.sub(r'[^a-z0-9]+', '_', base_name)

        # Remove consecutive underscores
        clean_name = re.sub(r'_+', '_', clean_name)

        # Trim underscores from ends
        clean_name = clean_name.strip('_')

        # Prefix for embedding tables
        prefix = "emb_"

        # Calculate maximum length for the name part (63 bytes - prefix length)
        max_name_length = 63 - len(prefix)

        # Truncate if necessary
        if len(clean_name) > max_name_length:
            # Keep the start and end, remove from middle
            half_length = (max_name_length - 1) // 2  # -1 for the joining underscore
            clean_name = f"{clean_name[:half_length]}_{clean_name[-half_length:]}"

        return f"{prefix}{clean_name}"


# Singleton instance
_instance = None

def get_embeddings_db():
    """Get the singleton instance of the embeddings database manager."""
    global _instance
    if _instance is None:
        _instance = EmbeddingsDatabaseManager()
    return _instance
