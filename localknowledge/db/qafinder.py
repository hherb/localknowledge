"""
Database manager for QA embeddings.

This module provides a database manager for storing and retrieving QA embeddings
generated from abstracts and other text sources.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class QAEmbeddingDatabaseManager(DatabaseManager):
    """Database manager for QA embeddings."""

    def __init__(self):
        """Initialize the QA embedding database manager."""
        super().__init__()
        self.create_tables()
        self.create_indices()

    def begin_transaction(self):
        """
        Begin a new transaction.

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
        """
        Commit the current transaction.

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
        """
        Roll back the current transaction.

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

    def create_tables(self) -> None:
        """Create QA embeddings table if it doesn't exist."""
        logger.debug("Creating or verifying QA embeddings table")

        # Begin a transaction for all table creation operations
        self.begin_transaction()

        try:
            # First, ensure pgvector extension is installed
            logger.debug("Checking pgvector extension")
            self.execute("CREATE EXTENSION IF NOT EXISTS vector", commit=False)
            logger.debug("pgvector extension created or verified")

            # Create qaembeddings table
            logger.debug("Creating qaembeddings table if it doesn't exist")
            self.execute("""
            CREATE TABLE IF NOT EXISTS qaembeddings (
                id SERIAL PRIMARY KEY,
                source_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_no INTEGER NOT NULL,
                page_no INTEGER,
                qa_pairs TEXT NOT NULL,
                embedding vector(1024),
                model_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, document_id, chunk_no)
            )
            """, commit=False)
            logger.debug("QA embeddings table created or verified")

            # Commit all table creation operations
            self.commit_transaction()
            logger.debug("Table creation transaction committed")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.rollback_transaction()
            logger.error("Please make sure pgvector is installed in your PostgreSQL instance")
            raise

    def create_indices(self) -> None:
        """Create indices for the QA embeddings table."""
        logger.debug("Creating or verifying QA embedding indices")

        # Begin a transaction for all index creation operations
        self.begin_transaction()

        try:
            # Create indices for faster lookups
            logger.debug("Creating source_id index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_qaembeddings_source_id
            ON qaembeddings(source_id)
            """, commit=False)

            logger.debug("Creating document_id index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_qaembeddings_document_id
            ON qaembeddings(document_id)
            """, commit=False)

            # Create vector index for similarity search
            logger.debug("Creating vector index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_qaembeddings_vector
            ON qaembeddings
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """, commit=False)

            # Commit all index creation operations
            self.commit_transaction()
            logger.debug("Index creation transaction committed")

        except Exception as e:
            logger.error(f"Error creating indices: {e}")
            self.rollback_transaction()
            raise

    def store_qa_embedding(self,
                        source_id: str,
                        document_id: str,
                        chunk_no: int,
                        qa_pairs: str,
                        embedding: List[float],
                        model_name: str,
                        page_no: Optional[int] = None,
                        commit: bool = True) -> int:
        """
        Store a QA embedding in the database.

        Args:
            source_id: Source identifier (e.g., 'pubmed', 'medrxiv')
            document_id: Document identifier (e.g., PMID, DOI)
            chunk_no: Chunk number within the document
            qa_pairs: JSON string containing question-answer pairs
            embedding: Vector embedding as a list of floats
            model_name: Name of the model used to create the embedding
            page_no: Page number (optional)
            commit: Whether to commit the transaction immediately (default: True)

        Returns:
            ID of the stored QA embedding
        """

        query = """
        INSERT INTO qaembeddings
            (source_id, document_id, chunk_no, page_no, qa_pairs, embedding, model_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, document_id, chunk_no) DO UPDATE SET
            page_no = EXCLUDED.page_no,
            qa_pairs = EXCLUDED.qa_pairs,
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
            qa_pairs,
            embedding_str,
            model_name
        )

        try:
            start_time = time.time()
            result = self.execute(query, params, commit=commit)
            execution_time = time.time() - start_time
            logger.debug(f"Stored QA embedding for {source_id}/{document_id} in {execution_time:.2f}s")

            if result and len(result) > 0:
                logger.debug(f"Successfully stored QA embedding with ID: {result[0]['id']}")
                return result[0]['id']

            logger.debug(f"No ID returned from store_qa_embedding for {source_id}/{document_id}")
            # Even if no ID is returned, the operation might have succeeded (e.g., in case of an update)
            # So we'll return 1 instead of -1 to indicate success
            return 1
        except Exception as e:
            logger.error(f"Error storing QA embedding: {e}")
            if commit:
                self.rollback_transaction()  # Ensure we're not left in a bad state
            raise

    def store_qa_embeddings_batch(self, embeddings: List[Dict[str, Any]], commit: bool = True) -> int:
        """
        Store multiple QA embeddings in the database.

        Args:
            embeddings: List of embedding dictionaries with the following keys:
                - source_id: Source identifier
                - document_id: Document identifier
                - chunk_no: Chunk number
                - qa_pairs: JSON string containing question-answer pairs
                - embedding: Vector embedding
                - model_name: Model name
                - page_no: Page number (optional)
            commit: Whether to commit the transaction immediately (default: True)

        Returns:
            Number of embeddings stored
        """
        if not embeddings:
            logger.warning("No embeddings provided to store_qa_embeddings_batch")
            return 0

        # Begin a transaction for the batch operation
        self.begin_transaction()

        query = """
        INSERT INTO qaembeddings
            (source_id, document_id, chunk_no, page_no, qa_pairs, embedding, model_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, document_id, chunk_no) DO UPDATE SET
            page_no = EXCLUDED.page_no,
            qa_pairs = EXCLUDED.qa_pairs,
            embedding = EXCLUDED.embedding,
            model_name = EXCLUDED.model_name,
            created_at = CURRENT_TIMESTAMP
        """

        # Prepare parameters for each embedding
        params_list = []
        for emb in embeddings:
            # Convert embedding to PostgreSQL vector format
            embedding_str = f"[{','.join(map(str, emb['embedding']))}]"

            params = (
                emb['source_id'],
                emb['document_id'],
                emb['chunk_no'],
                emb.get('page_no'),  # Optional
                emb['qa_pairs'],
                embedding_str,
                emb['model_name']
            )
            params_list.append(params)

        try:
            # Execute the batch insert
            start_time = time.time()
            self.execute_many(query, params_list, commit=False)
            execution_time = time.time() - start_time
            logger.debug(f"Stored batch of {len(embeddings)} QA embeddings in {execution_time:.2f}s")

            # Commit the transaction if requested
            if commit:
                self.commit_transaction()

            return len(embeddings)
        except Exception as e:
            logger.error(f"Error storing QA embeddings batch: {e}")
            self.rollback_transaction()

            # Try to store embeddings individually
            logger.info("Attempting to store embeddings individually")
            count = 0
            for emb in embeddings:
                try:
                    self.store_qa_embedding(
                        source_id=emb['source_id'],
                        document_id=emb['document_id'],
                        chunk_no=emb['chunk_no'],
                        qa_pairs=emb['qa_pairs'],
                        embedding=emb['embedding'],
                        model_name=emb['model_name'],
                        page_no=emb.get('page_no'),
                        commit=False
                    )
                    count += 1
                except Exception as individual_e:
                    logger.error(f"Error storing individual QA embedding: {individual_e}")

            # Commit all successful individual embeddings at the end if requested
            if commit and count > 0:
                try:
                    self.commit_transaction()
                except Exception as commit_e:
                    logger.error(f"Error committing individual QA embeddings: {commit_e}")
                    self.rollback_transaction()
                    return 0

            return count

    def search_similar(self,
                       query_embedding: List[float],
                       limit: int = 10,
                       threshold: float = 0.7,
                       source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar QA pairs using vector similarity.

        Args:
            query_embedding: Vector embedding of the query
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (optional)

        Returns:
            List of similar QA pairs with similarity scores
        """

        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Build the query
        query = """
        SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, model_name,
               1 - (embedding <=> %s::vector) AS similarity
        FROM qaembeddings
        """

        # Start building the WHERE clause
        where_clauses = []
        params = [embedding_str]

        # Add source_id filter if provided
        if source_id:
            where_clauses.append("source_id = %s")
            params.append(source_id)

        # Add similarity threshold
        where_clauses.append("1 - (embedding <=> %s::vector) >= %s")
        params.append(embedding_str)  # Add embedding again for the threshold calculation
        params.append(threshold)

        # Combine WHERE clauses if any
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Add ORDER BY and LIMIT
        query += """
        ORDER BY similarity DESC
        LIMIT %s
        """
        params.append(limit)

        try:
            start_time = time.time()
            results = self.execute(query, tuple(params))
            execution_time = time.time() - start_time
            logger.debug(f"Similarity search completed in {execution_time:.2f}s")
            return results or []
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            self.rollback_transaction()  # Ensure we're not left in a bad state
            return []

    def get_document_qa_embeddings(self, source_id: str, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all QA embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            List of QA embeddings for the document
        """
        query = """
        SELECT id, source_id, document_id, chunk_no, page_no, qa_pairs, model_name
        FROM qaembeddings
        WHERE source_id = %s AND document_id = %s
        ORDER BY chunk_no
        """

        try:
            start_time = time.time()
            results = self.execute(query, (source_id, document_id))
            execution_time = time.time() - start_time
            return results or []
        except Exception as e:
            logger.error(f"Error getting document QA embeddings for {source_id}/{document_id}: {e}")
            self.rollback_transaction()  # Ensure we're not left in a bad state
            return []

    def delete_document_qa_embeddings(self, source_id: str, document_id: str) -> int:
        """
        Delete all QA embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        query = """
        DELETE FROM qaembeddings
        WHERE source_id = %s AND document_id = %s
        RETURNING id
        """

        try:
            start_time = time.time()
            results = self.execute(query, (source_id, document_id), commit=True)
            execution_time = time.time() - start_time
            logger.debug(f"Deleted QA embeddings for {source_id}/{document_id} in {execution_time:.2f}s")
            return len(results) if results else 0
        except Exception as e:
            logger.error(f"Error deleting QA embeddings for {source_id}/{document_id}: {e}")
            self.rollback_transaction()  # Ensure we're not left in a bad state
            return 0
