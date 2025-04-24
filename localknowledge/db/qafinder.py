"""
Database manager for QA embeddings using the unified document and multiembeddings structure.

This module provides a database manager for storing and retrieving QA embeddings
generated from abstracts and other text sources, using the unified document and
multiembeddings tables.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple

from localknowledge.db.base import DatabaseManager
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.embeddings import EmbeddingsDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class QAEmbeddingDatabaseManager(DatabaseManager):
    """
    Database manager for QA embeddings using the unified document and multiembeddings structure.

    This class provides methods for working with QA embeddings stored in the
    unified_multiembeddings table. It does not create any tables or indices,
    as those are handled by the migration system.
    """

    def __init__(self):
        """Initialize the QA embedding database manager."""
        super().__init__()
        self.document_db = DocumentDatabaseManager()
        self.embeddings_db = EmbeddingsDatabaseManager()
        self.qa_embed_source_id = self._get_qa_embed_source_id()

    def _get_qa_embed_source_id(self) -> int:
        """
        Get the embedding source ID for QA embeddings.

        Returns:
            int: Embedding source ID for QA embeddings
        """
        # Get or create the embedding source for QA
        query = """
        SELECT id FROM embedding_source WHERE name = 'qa'
        """
        result = self.execute(query)

        if result and result[0]['id']:
            return result[0]['id']

        # If not found, create it
        query = """
        INSERT INTO embedding_source (name, description)
        VALUES ('qa', 'Question-Answer pair embeddings')
        RETURNING id
        """
        result = self.execute(query, commit=True)

        if result and result[0]['id']:
            return result[0]['id']

        raise ValueError("Could not get or create QA embedding source")

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
        Store a QA embedding in the unified multiembeddings table.

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
        try:
            # First, get the document ID from the document table
            doc = self.document_db.get_document_by_external_id(source_id, document_id)
            if not doc:
                logger.error(f"Document not found: {source_id}/{document_id}")
                return 0

            doc_id = doc['id']

            # Store the embedding in the unified_multiembeddings table
            metadata = {
                'qa_pairs': qa_pairs
            }

            # Use the embeddings database manager to store the embedding
            embedding_id = self.embeddings_db.store_embedding(
                document_id=doc_id,
                embed_source='qa',
                chunk_no=chunk_no,
                text=qa_pairs,  # Store the QA pairs as text
                embedding=embedding,
                model_name=model_name,
                page_no=page_no,
                metadata=metadata,
                commit=commit
            )

            logger.debug(f"Stored QA embedding for document ID {doc_id}, chunk {chunk_no}")
            return embedding_id
        except Exception as e:
            logger.error(f"Error storing QA embedding: {e}")
            if commit:
                self.rollback_transaction()  # Ensure we're not left in a bad state
            return 0

    def store_qa_embeddings_batch(self, embeddings: List[Dict[str, Any]], commit: bool = True) -> int:
        """
        Store multiple QA embeddings in the unified multiembeddings table.

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

        try:
            # Process embeddings one by one
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

            # Commit all successful embeddings at the end if requested
            if commit and count > 0:
                self.commit_transaction()
                logger.debug(f"Successfully stored {count} QA embeddings")

            return count
        except Exception as e:
            logger.error(f"Error storing QA embeddings batch: {e}")
            self.rollback_transaction()
            return 0

    def search_similar(self,
                       query_embedding: List[float],
                       limit: int = 10,
                       threshold: float = 0.7,
                       source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar QA pairs using vector similarity in the unified multiembeddings table.

        Args:
            query_embedding: Vector embedding of the query
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (optional)

        Returns:
            List of similar QA pairs with similarity scores
        """
        try:
            # Use the embeddings database manager to search for similar embeddings
            results = self.embeddings_db.search_similar_embeddings(
                embedding=query_embedding,
                embed_source='qa',
                threshold=threshold,
                limit=limit
            )

            # If source_id filter is provided, filter the results
            if source_id and results:
                filtered_results = []
                for result in results:
                    # Get the document to check its source
                    doc = self.document_db.get_document_by_id(result['document_id'])
                    if doc and doc.get('source_name') == source_id:
                        # Add the source_id and document_id (external_id) to the result
                        result['source_id'] = source_id
                        result['document_id'] = doc.get('external_id')
                        # Extract QA pairs from metadata
                        if result.get('metadata') and 'qa_pairs' in result['metadata']:
                            result['qa_pairs'] = result['metadata']['qa_pairs']
                        filtered_results.append(result)

                return filtered_results[:limit]

            # If no source_id filter, just process the results
            processed_results = []
            for result in results:
                # Get the document to add its source and external_id
                doc = self.document_db.get_document_by_id(result['document_id'])
                if doc:
                    # Add the source_id and document_id (external_id) to the result
                    result['source_id'] = doc.get('source_name')
                    result['document_id'] = doc.get('external_id')
                    # Extract QA pairs from metadata
                    if result.get('metadata') and 'qa_pairs' in result['metadata']:
                        result['qa_pairs'] = result['metadata']['qa_pairs']
                    processed_results.append(result)

            return processed_results
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []

    def get_document_qa_embeddings(self, source_id: str, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all QA embeddings for a specific document from the unified multiembeddings table.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            List of QA embeddings for the document
        """
        try:
            # First, get the document ID from the document table
            doc = self.document_db.get_document_by_external_id(source_id, document_id)
            if not doc:
                logger.error(f"Document not found: {source_id}/{document_id}")
                return []

            doc_id = doc['id']

            # Get all QA embeddings for this document
            embeddings = self.embeddings_db.get_embeddings_by_document(
                document_id=doc_id,
                embed_source='qa'
            )

            # Process the results to match the expected format
            results = []
            for emb in embeddings:
                result = {
                    'id': emb['id'],
                    'source_id': source_id,
                    'document_id': document_id,
                    'chunk_no': emb['chunk_no'],
                    'page_no': emb.get('page_no'),
                    'model_name': emb['model_name']
                }

                # Extract QA pairs from metadata
                if emb.get('metadata') and 'qa_pairs' in emb['metadata']:
                    result['qa_pairs'] = emb['metadata']['qa_pairs']
                else:
                    # Fallback to text if metadata is not available
                    result['qa_pairs'] = emb.get('text', '')

                results.append(result)

            return sorted(results, key=lambda x: x['chunk_no'])
        except Exception as e:
            logger.error(f"Error getting document QA embeddings for {source_id}/{document_id}: {e}")
            return []

    def delete_document_qa_embeddings(self, source_id: str, document_id: str) -> int:
        """
        Delete all QA embeddings for a specific document from the unified multiembeddings table.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        try:
            # First, get the document ID from the document table
            doc = self.document_db.get_document_by_external_id(source_id, document_id)
            if not doc:
                logger.error(f"Document not found: {source_id}/{document_id}")
                return 0

            doc_id = doc['id']

            # Delete all QA embeddings for this document
            count = self.embeddings_db.delete_embeddings(
                document_id=doc_id,
                embed_source='qa'
            )

            logger.debug(f"Deleted {count} QA embeddings for document {source_id}/{document_id}")
            return count
        except Exception as e:
            logger.error(f"Error deleting QA embeddings for {source_id}/{document_id}: {e}")
            return 0
