"""This class handles all chunking related SQL database functionality"""

import json
import logging
import time
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    """Dataclass representing a chunk of text with metadata."""
    chunk_id: int
    document_id: int
    chunking_strategy_id: int
    chunktype_id: int
    document_title: str
    text: str
    chunklength: int
    chunk_no: int
    page_start: int
    page_end: int
    metadata: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chunk':
        """Create a Chunk instance from a dictionary."""
        # Handle the case where the id field might be named 'id' or 'chunk_id'
        chunk_id = data.get('id', data.get('chunk_id', 0))

        # Handle metadata that might be a JSON string or already a dict
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            chunk_id=chunk_id,
            document_id=data['document_id'],
            chunking_strategy_id=data['chunking_strategy_id'],
            chunktype_id=data['chunktype_id'],
            document_title=data.get('document_title', ''),
            text=data['text'],
            chunklength=data['chunklength'],
            chunk_no=data['chunk_no'],
            page_start=data.get('page_start', 0),
            page_end=data.get('page_end', 0),
            metadata=metadata
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the chunk to a dictionary."""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'chunking_strategy_id': self.chunking_strategy_id,
            'chunktype_id': self.chunktype_id,
            'document_title': self.document_title,
            'text': self.text,
            'chunklength': self.chunklength,
            'chunk_no': self.chunk_no,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'metadata': self.metadata
        }



class ChunkingDatabaseManager(DatabaseManager):
    """Database manager for chunking related operations."""
    def __init__(self):
        """Initialize the chunking database manager."""
        super().__init__()
        # Database creation is done centrally in db.createdb.py by calling create_tables()

    def commit(self):
        """Commit the current transaction."""
        if self.connection:
            self.connection.commit()

    def list_chunking_strategies(self) -> List[Dict[str, Any]]:
        """
        List all chunking strategies in the database.

        Returns:
            List of dictionaries containing strategy information
        """
        query = """
        SELECT id, strategy_name, modelname, parameters
        FROM chunking_strategies
        ORDER BY id
        """
        return self.execute(query) or []

    def get_or_create_chunking_strategy(self, strategy_name: str, parameters: dict) -> int:
        """
        Create a new chunking strategy if it doesn't exist yet (else select the existing)
        and return its ID.

        Args:
            strategy_name: Name of the chunking strategy
            parameters: Dictionary of parameters for the strategy

        Returns:
            ID of the chunking strategy
        """
        # First check if the strategy already exists
        query = """
        SELECT id FROM chunking_strategies
        WHERE strategy_name = %s AND parameters = %s
        """
        result = self.execute(query, (strategy_name, json.dumps(parameters)))

        if result and len(result) > 0:
            return result[0]['id']

        # If not, create a new strategy
        insert_query = """
        INSERT INTO chunking_strategies (strategy_name, parameters)
        VALUES (%s, %s)
        RETURNING id
        """
        result = self.execute(insert_query, (strategy_name, json.dumps(parameters)), commit=True)

        if result and len(result) > 0:
            return result[0]['id']
        else:
            raise ValueError(f"Failed to create chunking strategy: {strategy_name}")

    def list_chunktypes(self) -> List[Dict[str, Any]]:
        """
        List all chunktypes in the database.

        Returns:
            List of dictionaries containing chunktype information
        """
        query = """
        SELECT id, chunktype
        FROM chunktypes
        ORDER BY id
        """
        return self.execute(query) or []

    def get_or_create_chunktype(self, chunktype_name: str) -> int:
        """
        Create a new chunktype if it doesn't exist yet (else select the existing)
        and return its ID.

        Args:
            chunktype_name: Name of the chunk type

        Returns:
            ID of the chunk type
        """
        # First check if the chunktype already exists
        query = """
        SELECT id FROM chunktypes
        WHERE chunktype = %s
        """
        result = self.execute(query, (chunktype_name,))

        if result and len(result) > 0:
            return result[0]['id']

        # If not, create a new chunktype
        insert_query = """
        INSERT INTO chunktypes (chunktype)
        VALUES (%s)
        RETURNING id
        """
        result = self.execute(insert_query, (chunktype_name,), commit=True)

        if result and len(result) > 0:
            return result[0]['id']
        else:
            raise ValueError(f"Failed to create chunktype: {chunktype_name}")

    def get_or_create_chunk(self, chunk: Chunk) -> int:
        """
        Create a new chunk if it doesn't exist yet (else select the existing)
        and return its ID.

        Args:
            chunk: Chunk object containing all necessary data

        Returns:
            ID of the chunk
        """
        # First check if the chunk already exists
        query = """
        SELECT id FROM chunks
        WHERE document_id = %s
        AND chunking_strategy_id = %s
        AND chunktype_id = %s
        AND chunk_no = %s
        """
        result = self.execute(query, (
            chunk.document_id,
            chunk.chunking_strategy_id,
            chunk.chunktype_id,
            chunk.chunk_no
        ))

        if result and len(result) > 0:
            return result[0]['id']

        # If not, create a new chunk
        insert_query = """
        INSERT INTO chunks (
            document_id, chunking_strategy_id, chunktype_id, text,
            document_title, chunklength, chunk_no, page_start, page_end, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        params = (
            chunk.document_id,
            chunk.chunking_strategy_id,
            chunk.chunktype_id,
            chunk.text,
            chunk.document_title,
            chunk.chunklength,
            chunk.chunk_no,
            chunk.page_start,
            chunk.page_end,
            json.dumps(chunk.metadata)
        )

        result = self.execute(insert_query, params, commit=True)

        if result and len(result) > 0:
            return result[0]['id']
        else:
            raise ValueError(f"Failed to create chunk for document {chunk.document_id}, chunk {chunk.chunk_no}")

    def batch_insert_chunks(self, chunks: List[Chunk], commit: bool=True) -> List[int]:
        """
        Insert multiple chunks in a batch operation.

        Args:
            chunks: List of Chunk objects to insert
            commit: Whether to commit the transaction (default: True)

        Returns:
            List of chunk IDs that were inserted
        """
        if not chunks:
            return []

        # For a more efficient approach, we'll insert all chunks at once
        # and then query for their IDs

        # First, prepare the parameters for all chunks
        params_list = []
        for chunk in chunks:
            params = (
                chunk.document_id,
                chunk.chunking_strategy_id,
                chunk.chunktype_id,
                chunk.text,
                chunk.document_title,
                chunk.chunklength,
                chunk.chunk_no,
                chunk.page_start,
                chunk.page_end,
                json.dumps(chunk.metadata)
            )
            params_list.append(params)

        # Create a temporary table to hold the chunks and their IDs
        temp_table_name = f"temp_chunks_{int(time.time())}"

        try:
            # Create a temporary table
            create_temp_table_query = f"""
            CREATE TEMPORARY TABLE {temp_table_name} (
                temp_id SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL,
                chunking_strategy_id INTEGER NOT NULL,
                chunktype_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                document_title TEXT,
                chunklength INTEGER NOT NULL,
                chunk_no INTEGER NOT NULL,
                page_start INTEGER,
                page_end INTEGER,
                metadata JSONB
            )
            """
            self.execute(create_temp_table_query, commit=False)

            # Insert chunks into the temporary table
            insert_temp_query = f"""
            INSERT INTO {temp_table_name} (
                document_id, chunking_strategy_id, chunktype_id, text,
                document_title, chunklength, chunk_no, page_start, page_end, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Use execute_many for better performance
            self.execute_many(insert_temp_query, params_list, commit=False)

            # Insert from temporary table to the actual chunks table and get IDs
            insert_query = f"""
            INSERT INTO chunks (
                document_id, chunking_strategy_id, chunktype_id, text,
                document_title, chunklength, chunk_no, page_start, page_end, metadata
            )
            SELECT
                document_id, chunking_strategy_id, chunktype_id, text,
                document_title, chunklength, chunk_no, page_start, page_end, metadata
            FROM {temp_table_name}
            RETURNING id
            """

            result = self.execute(insert_query, commit=False)

            # Get the IDs
            chunk_ids = [row['id'] for row in result] if result else []

            # Commit if requested
            if commit:
                self.commit()

            return chunk_ids

        except Exception as e:
            logger.error(f"Error in batch_insert_chunks: {e}")
            self.connection.rollback()

            # Fall back to the slower but more reliable method
            logger.info("Falling back to individual inserts")

            # Prepare the query
            insert_query = """
            INSERT INTO chunks (
                document_id, chunking_strategy_id, chunktype_id, text,
                document_title, chunklength, chunk_no, page_start, page_end, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """

            # Execute individual inserts with a longer timeout
            chunk_ids = []
            for chunk in chunks:
                params = (
                    chunk.document_id,
                    chunk.chunking_strategy_id,
                    chunk.chunktype_id,
                    chunk.text,
                    chunk.document_title,
                    chunk.chunklength,
                    chunk.chunk_no,
                    chunk.page_start,
                    chunk.page_end,
                    json.dumps(chunk.metadata)
                )

                # Use a longer timeout for individual inserts
                result = self.execute(insert_query, params, commit=False, timeout=60)
                if result and len(result) > 0:
                    chunk_ids.append(result[0]['id'])

            # Commit if requested
            if commit and chunk_ids:
                self.commit()

            return chunk_ids
        finally:
            # Drop the temporary table if it exists
            try:
                drop_temp_table_query = f"DROP TABLE IF EXISTS {temp_table_name}"
                self.execute(drop_temp_table_query, commit=False)
                if commit:
                    self.commit()
            except Exception as e:
                logger.error(f"Error dropping temporary table: {e}")
                # Don't raise this exception as it's just cleanup

    def _convert_to_chunks(self, results: List[Dict[str, Any]]) -> List[Chunk]:
        """
        Convert database query results to Chunk objects.

        Args:
            results: List of dictionaries from database query

        Returns:
            List of Chunk objects
        """
        if not results:
            return []

        chunks = []
        for result in results:
            # Create a copy of the result to avoid modifying the original
            data = dict(result)

            # Add any additional fields from the query to metadata
            metadata = data.get('metadata', {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # Add any extra fields from joins to metadata
            extra_fields = {}
            for key in ['strategy_name', 'chunktype', 'document_title_from_doc', 'external_id']:
                if key in data:
                    extra_fields[key] = data[key]

            if extra_fields:
                metadata.update(extra_fields)
                data['metadata'] = metadata

            chunks.append(Chunk.from_dict(data))

        return chunks

    def get_chunks_by_document(self, document_id: int) -> List[Chunk]:
        """
        Get all chunks for a specific document.

        Note: For large result sets, use iter_chunks_by_document instead.

        Args:
            document_id: ID of the document

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, cs.strategy_name, ct.chunktype
        FROM chunks c
        JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
        JOIN chunktypes ct ON c.chunktype_id = ct.id
        WHERE c.document_id = %s
        ORDER BY c.chunktype_id, c.chunk_no
        """
        results = self.execute(query, (document_id,)) or []
        return self._convert_to_chunks(results)

    def get_chunks_by_chunktype(self, chunktype_id: int) -> List[Chunk]:
        """
        Get all chunks of a specific type.

        Note: For large result sets, use iter_chunks_by_chunktype instead.

        Args:
            chunktype_id: ID of the chunk type

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, cs.strategy_name
        FROM chunks c
        JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
        WHERE c.chunktype_id = %s
        ORDER BY c.document_id, c.chunk_no
        """
        results = self.execute(query, (chunktype_id,)) or []
        return self._convert_to_chunks(results)

    def iter_chunks_by_chunktype(self, chunktype_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks of a specific type as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            chunktype_id: ID of the chunk type
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, cs.strategy_name
            FROM chunks c
            JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
            WHERE c.chunktype_id = %s
            ORDER BY c.document_id, c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (chunktype_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size

    def get_chunks_by_chunking_strategy(self, chunking_strategy_id: int) -> List[Chunk]:
        """
        Get all chunks created with a specific chunking strategy.

        Note: For large result sets, use iter_chunks_by_chunking_strategy instead.

        Args:
            chunking_strategy_id: ID of the chunking strategy

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, ct.chunktype
        FROM chunks c
        JOIN chunktypes ct ON c.chunktype_id = ct.id
        WHERE c.chunking_strategy_id = %s
        ORDER BY c.document_id, c.chunktype_id, c.chunk_no
        """
        results = self.execute(query, (chunking_strategy_id,)) or []
        return self._convert_to_chunks(results)

    def iter_chunks_by_chunking_strategy(self, chunking_strategy_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks created with a specific chunking strategy as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            chunking_strategy_id: ID of the chunking strategy
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, ct.chunktype
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE c.chunking_strategy_id = %s
            ORDER BY c.document_id, c.chunktype_id, c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (chunking_strategy_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size

    def get_chunks_by_document_and_chunktype(self, document_id: int, chunktype_id: int) -> List[Chunk]:
        """
        Get all chunks of a specific type for a specific document.

        Note: For large result sets, use iter_chunks_by_document_and_chunktype instead.

        Args:
            document_id: ID of the document
            chunktype_id: ID of the chunk type

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, cs.strategy_name
        FROM chunks c
        JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
        WHERE c.document_id = %s AND c.chunktype_id = %s
        ORDER BY c.chunk_no
        """
        results = self.execute(query, (document_id, chunktype_id)) or []
        return self._convert_to_chunks(results)

    def iter_chunks_by_document_and_chunktype(self, document_id: int, chunktype_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks of a specific type for a specific document as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            document_id: ID of the document
            chunktype_id: ID of the chunk type
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, cs.strategy_name
            FROM chunks c
            JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
            WHERE c.document_id = %s AND c.chunktype_id = %s
            ORDER BY c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (document_id, chunktype_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size

    def get_chunks_by_document_and_chunking_strategy(self, document_id: int, chunking_strategy_id: int) -> List[Chunk]:
        """
        Get all chunks created with a specific chunking strategy for a specific document.

        Note: For large result sets, use iter_chunks_by_document_and_chunking_strategy instead.

        Args:
            document_id: ID of the document
            chunking_strategy_id: ID of the chunking strategy

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, ct.chunktype
        FROM chunks c
        JOIN chunktypes ct ON c.chunktype_id = ct.id
        WHERE c.document_id = %s AND c.chunking_strategy_id = %s
        ORDER BY c.chunktype_id, c.chunk_no
        """
        results = self.execute(query, (document_id, chunking_strategy_id)) or []
        return self._convert_to_chunks(results)

    def iter_chunks_by_document_and_chunking_strategy(self, document_id: int, chunking_strategy_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks created with a specific chunking strategy for a specific document as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            document_id: ID of the document
            chunking_strategy_id: ID of the chunking strategy
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, ct.chunktype
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE c.document_id = %s AND c.chunking_strategy_id = %s
            ORDER BY c.chunktype_id, c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (document_id, chunking_strategy_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size

    def get_all_chunks_for_strategy_and_type(self, chunking_strategy_id: int, chunktype_id: int) -> List[Chunk]:
        """
        Get all chunks of a specific type created with a specific chunking strategy for a specified chunk type.
        For example, all abstract chunks created with the adaptive_splitter strategy
        (which would include the chunking parameters).

        Note: For large result sets, use iter_chunks_by_strategy_and_type instead.

        Args:
            chunking_strategy_id: ID of the chunking strategy
            chunktype_id: ID of the chunk type

        Returns:
            List of Chunk objects
        """
        query = """
        SELECT c.*, d.title as document_title_from_doc, d.external_id
        FROM chunks c
        JOIN document d ON c.document_id = d.id
        WHERE c.chunking_strategy_id = %s AND c.chunktype_id = %s
        ORDER BY c.document_id, c.chunk_no
        """
        results = self.execute(query, (chunking_strategy_id, chunktype_id)) or []
        return self._convert_to_chunks(results)

    def iter_chunks_by_strategy_and_type(self, chunking_strategy_id: int, chunktype_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks of a specific type created with a specific chunking strategy as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            chunking_strategy_id: ID of the chunking strategy
            chunktype_id: ID of the chunk type
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, d.title as document_title_from_doc, d.external_id
            FROM chunks c
            JOIN document d ON c.document_id = d.id
            WHERE c.chunking_strategy_id = %s AND c.chunktype_id = %s
            ORDER BY c.document_id, c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (chunking_strategy_id, chunktype_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size

    def get_chunk_by_id(self, chunk_id: int) -> Optional[Chunk]:
        """
        Get a specific chunk by its ID.

        Args:
            chunk_id: ID of the chunk

        Returns:
            Chunk object if found, None otherwise
        """
        query = """
        SELECT c.*, cs.strategy_name, ct.chunktype
        FROM chunks c
        JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
        JOIN chunktypes ct ON c.chunktype_id = ct.id
        WHERE c.id = %s
        """
        results = self.execute(query, (chunk_id,)) or []
        chunks = self._convert_to_chunks(results)
        return chunks[0] if chunks else None

    def iter_chunks_by_document(self, document_id: int, batch_size: int = 100) -> Iterator[Chunk]:
        """
        Get all chunks for a specific document as an iterator.
        This is more memory-efficient for large result sets.

        Args:
            document_id: ID of the document
            batch_size: Number of chunks to fetch in each database query

        Returns:
            Iterator of Chunk objects
        """
        offset = 0
        while True:
            query = """
            SELECT c.*, cs.strategy_name, ct.chunktype
            FROM chunks c
            JOIN chunking_strategies cs ON c.chunking_strategy_id = cs.id
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE c.document_id = %s
            ORDER BY c.chunktype_id, c.chunk_no
            LIMIT %s OFFSET %s
            """
            results = self.execute(query, (document_id, batch_size, offset)) or []
            if not results:
                break

            chunks = self._convert_to_chunks(results)
            for chunk in chunks:
                yield chunk

            if len(results) < batch_size:
                break

            offset += batch_size
