"""
Database manager for vector embeddings.

This module provides a database manager for storing and retrieving vector embeddings
using PostgreSQL with the pgvector extension.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
import re
from functools import lru_cache

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class EmbeddingDatabaseManager(DatabaseManager):
    """Database manager for vector embeddings."""

    def __init__(self):
        """Initialize the embedding database manager."""
        super().__init__()
        #self.create_tables()
        #self.create_indices()

    def create_tables(self) -> None:
        """Create embedding-related tables if they don't exist."""
        logger.info("Creating or verifying embedding-related tables")

        # Begin a transaction for all table creation operations
        self.begin_transaction()

        try:
            # First, ensure pgvector extension is installed
            logger.debug("Checking pgvector extension")
            self.execute("CREATE EXTENSION IF NOT EXISTS vector", commit=False)
            logger.info("pgvector extension created or verified")

            # Create embeddings table
            logger.debug("Creating embeddings table if it doesn't exist")
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

            # Commit all table creation operations
            self.commit_transaction()
            logger.debug("Table creation transaction committed")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.rollback_transaction()
            logger.error("Please make sure pgvector is installed in your PostgreSQL instance")
            raise

    def create_indices(self) -> None:
        """Create indices for the embeddings table."""
        logger.info("Creating or verifying embedding indices")

        # Begin a transaction for all index creation operations
        self.begin_transaction()

        try:
            # Create index for source_id and document_id
            logger.debug("Creating source_id index")
            self.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_source_id ON embeddings(source_id)", commit=False)

            logger.debug("Creating document_id index")
            self.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_document_id ON embeddings(document_id)", commit=False)

            # Create index for the embedding vector
            logger.debug("Creating vector index (this may take some time for large tables)")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """, commit=False)

            # Commit all index creation operations
            self.commit_transaction()
            logger.debug("Index creation transaction committed")

            logger.info("Embedding indices created or verified")
        except Exception as e:
            logger.error(f"Error creating indices: {e}")
            self.rollback_transaction()
            raise

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

    def store_embedding(self,
                        source_id: str,
                        document_id: str,
                        chunk_no: int,
                        text: str,
                        embedding: List[float],
                        model_name: str,
                        page_no: Optional[int] = None,
                        keywords: Optional[List[str]] = None,
                        commit: bool = True) -> int:
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
            commit: Whether to commit the transaction immediately (default: True)

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
            # Execute the query
            start_time = time.time()
            result = self.execute(query, params, commit=False)
            execution_time = time.time() - start_time

            # Commit if requested
            if commit:
                self.commit_transaction()

            if result and len(result) > 0:
                embedding_id = result[0]['id']
                return embedding_id

            logger.warning("No ID returned from embedding insertion")
            return -1
        except Exception as e:
            logger.error(f"Error storing embedding for {source_id}/{document_id}: {e}")
            # Roll back on error
            self.rollback_transaction()
            raise

    def store_embeddings_batch(self, embeddings: List[Dict[str, Any]], commit: bool = True) -> int:
        """
        Store multiple embeddings in the database.

        Args:
            embeddings: List of dictionaries containing embedding data
            commit: Whether to commit the transaction immediately (default: True)

        Returns:
            Number of embeddings stored
        """
        if not embeddings:
            logger.debug("No embeddings provided to store_embeddings_batch")
            return 0

        logger.debug(f"Storing batch of {len(embeddings)} embeddings")

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
        for i, emb in enumerate(embeddings):
            # Convert embedding to PostgreSQL vector format
            embedding_str = f"[{','.join(map(str, emb['embedding']))}]"

            source_id = emb.get('source_id', '')
            document_id = emb.get('document_id', '')
            chunk_no = emb.get('chunk_no', 0)

            params = (
                source_id,
                document_id,
                chunk_no,
                emb.get('page_no'),
                emb.get('text', ''),
                emb.get('keywords'),
                embedding_str,
                emb.get('model_name', '')
            )
            params_list.append(params)

        try:
            # Execute the batch operation
            start_time = time.time()
            self.execute_many(query, params_list, commit=False)
            execution_time = time.time() - start_time

            # Commit if requested
            if commit:
                self.commit_transaction()

            return len(embeddings)
        except Exception as e:
            logger.error(f"Error storing embeddings batch: {e}")
            # Roll back on error
            self.rollback_transaction()

            # Fall back to storing one by one if batch fails
            count = 0
            for emb in embeddings:
                try:
                    # Use commit=False for individual embeddings until the end
                    self.store_embedding(
                        emb.get('source_id', ''),
                        emb.get('document_id', ''),
                        emb.get('chunk_no', 0),
                        emb.get('text', ''),
                        emb.get('embedding', []),
                        emb.get('model_name', ''),
                        page_no=emb.get('page_no'),
                        keywords=emb.get('keywords'),
                        commit=False
                    )
                    count += 1
                except Exception as inner_e:
                    logger.error(f"Error in fallback individual embedding storage: {inner_e}")
                    continue

            # Commit all successful individual embeddings at the end if requested
            if commit and count > 0:
                try:
                    self.commit_transaction()
                except Exception as commit_e:
                    logger.error(f"Error committing individual embeddings: {commit_e}")
                    self.rollback_transaction()
                    return 0

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

        # Start building the WHERE clause
        where_clauses = []
        params = [embedding_str]

        # Add source_id filter if provided
        if source_id:
            where_clauses.append("source_id = %s")
            params.append(source_id)

        # Add similarity threshold
        # We need to add the embedding parameter again since we're using it twice in the query
        where_clauses.append(f"1 - (embedding <=> %s::vector) > {threshold}")
        # Add embedding_str again because we're using it twice in the query
        params.append(embedding_str)

        # Combine WHERE clauses
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY similarity DESC"
        query += f" LIMIT {limit}"


        try:
            start_time = time.time()
            results = self.execute(query, tuple(params))
            execution_time = time.time() - start_time

            if results:
                print(f"Database: Found {len(results)} similar documents in {execution_time:.3f} seconds")
            else:
                print(f"Database: No similar documents found in {execution_time:.3f} seconds")

                # Let's try a simpler query to see if we have any embeddings at all
                count_query = "SELECT COUNT(*) FROM embeddings"
                count_result = self.execute(count_query)
                if count_result and count_result[0].get('count', 0) > 0:
                    print(f"Database: There are {count_result[0].get('count')} embeddings in the database")

                    # Try with a much lower threshold
                    low_threshold = 0.1

                    # Modify the query with a lower threshold
                    modified_query = query.replace(f"> {threshold}", f"> {low_threshold}")
                    modified_results = self.execute(modified_query, tuple(params))

                    if modified_results:
                        print(f"Database: Found {len(modified_results)} results with threshold {low_threshold}")
                        print(f"Database: First result similarity: {modified_results[0].get('similarity')}")
                    else:
                        print(f"Database: Still no results with threshold {low_threshold}")
                else:
                    print("Database: No embeddings found in the database")

            return results or []
        except Exception as e:
            print(f"Database: Error searching similar documents: {e}")
            import traceback
            print(traceback.format_exc())
            self.rollback_transaction()  # Ensure we're not left in a bad state
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
            start_time = time.time()
            results = self.execute(query, (source_id, document_id))
            execution_time = time.time() - start_time
            return results or []
        except Exception as e:
            logger.error(f"Error getting document embeddings for {source_id}/{document_id}: {e}")
            self.rollback_transaction()  # Ensure we're not left in a bad state
            return []

    def get_embedding_dimension(self) -> Optional[int]:
        """
        Get the dimension of embeddings stored in the database.

        Returns:
            Dimension (vector size) of the embeddings, or None if no embeddings exist
        """

        query = """
        SELECT embedding
        FROM embeddings
        LIMIT 1
        """

        try:
            results = self.execute(query)

            if not results or not results[0]['embedding']:
                logger.debug("No embeddings found in database")
                return None

            # Parse the embedding vector to get its dimension
            # The embedding is stored as a string like '[0.1,0.2,0.3,...]'
            embedding_str = results[0]['embedding']

            # Remove brackets and split by comma
            if isinstance(embedding_str, str) and embedding_str.startswith('[') and embedding_str.endswith(']'):
                values = embedding_str[1:-1].split(',')
                dimension = len(values)
                return dimension
            else:
                # If the embedding is already a list or array
                dimension = len(embedding_str)
                return dimension

        except Exception as e:
            logger.error(f"Error getting embedding dimension: {e}")
            return None

    def delete_document_embeddings(self, source_id: str, document_id: str, commit: bool = True) -> int:
        """
        Delete all embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier
            commit: Whether to commit the transaction immediately (default: True)

        Returns:
            Number of embeddings deleted
        """
        logger.debug(f"Deleting embeddings for document {source_id}/{document_id}")

        query = """
        DELETE FROM embeddings
        WHERE source_id = %s AND document_id = %s
        RETURNING id
        """

        try:
            start_time = time.time()
            results = self.execute(query, (source_id, document_id), commit=False)
            execution_time = time.time() - start_time

            deleted_count = len(results) if results else 0
            logger.debug(f"Deleted {deleted_count} embeddings for document {source_id}/{document_id} in {execution_time:.3f} seconds")

            # Commit if requested
            if commit:
                self.commit_transaction()
                logger.debug("Deletion committed to database")

            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting document embeddings for {source_id}/{document_id}: {e}")
            self.rollback_transaction()  # Ensure we're not left in a bad state
            return 0

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
