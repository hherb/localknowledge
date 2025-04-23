"""Database manager for multiple embedding models with dynamic table creation.

This module provides functionality for managing multiple embedding models with different vector dimensions
by creating separate tables for each model. This allows for performance tracking and comparison between
different embedding models.
"""

from typing import Optional, List, Dict, Any
import re
import logging
import ollama
import backoff
from functools import lru_cache

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


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




class EmbeddingTableManager(DatabaseManager):
    """Manages dynamic embedding tables for different models.

    This class creates and manages separate database tables for each embedding model,
    allowing for different vector dimensions and performance tracking across models.
    """

    def __init__(self):
        """Initialize the embedding table manager.

        Connects to the database and initializes the table cache.
        """
        super().__init__()
        self.table_cache = {}  # Cache table existence

    @lru_cache(maxsize=100)
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def get_model_dimension(self, model_name: str) -> int:
        """Get the vector dimension for a specific model.

        Args:
            model_name: Name of the embedding model

        Returns:
            Vector dimension (number of elements in the embedding vector)

        Note:
            This method dynamically determines the dimension by creating a test
            embedding and measuring its length. Results are cached for efficiency.
        """
        try:
            # Try to get the dimension dynamically by creating a test embedding
            logger.info(f"Determining vector dimension for model {model_name}")

            # Generate embedding
            embedding_response = ollama.embeddings(model=model_name, prompt='text')

            # Get the vector and its size
            vector = embedding_response['embedding']
            vector_size = len(vector)

            logger.info(f"Detected dimension for {model_name}: {vector_size}")
            return vector_size

        except Exception as e:
            logger.warning(f"Error determining dimension for {model_name}: {e}")
            logger.warning("Falling back to lookup table for model dimensions")

            # Fallback to lookup table if Ollama call fails
            model_dimensions = {
                "snowflake-arctic-embed2": 1024,
                "nomic-embed-text": 768,
                "jina-embeddings-v2-base-en": 768,
                "bge-m3": 1024,
                "granite-embedding": 768,
                "mxbai-embed-large": 1024
            }

            # Extract base model name without version
            base_model = model_name.split(':')[0]

            # Look up dimension or use default
            for model_key, dimension in model_dimensions.items():
                if model_key in base_model:
                    logger.info(f"Using lookup table dimension for {model_name}: {dimension}")
                    return dimension

            # Default dimension if model not found
            logger.warning(f"Unknown model dimension for {model_name}, using default of 1024")
            return 1024

    def ensure_table_exists(self, model_name: str) -> str:
        """Create table if it doesn't exist and return table name.

        Args:
            model_name: Name of the embedding model

        Returns:
            Name of the database table for this model
        """
        table_name = model_to_tablename(model_name)

        if table_name not in self.table_cache:
            # Get vector dimension for this model
            dimension = self.get_model_dimension(model_name)

            # Create table with appropriate vector dimension
            self.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                source_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_no INTEGER NOT NULL,
                page_no INTEGER,
                text TEXT NOT NULL,
                keywords TEXT[],
                embedding vector({dimension}),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, document_id, chunk_no)
            )""", commit=True)

            # Create vector index
            self.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_vector
            ON {table_name} USING ivfflat (embedding vector_cosine_ops)
            """, commit=True)

            self.table_cache[table_name] = True
            logger.info(f"Created table {table_name} with dimension {dimension}")

        return table_name

    def store_embedding(self, model_name: str, data: Dict[str, Any]) -> int:
        """Store embedding in the appropriate table for the model.

        Args:
            model_name: Name of the embedding model
            data: Dictionary containing embedding data with keys:
                - source_id: Source identifier (e.g., 'medrxiv', 'pubmed')
                - document_id: Document identifier (e.g., DOI, PMID)
                - chunk_no: Chunk number within the document
                - page_no: Page number (optional)
                - text: Text that was embedded
                - keywords: List of keywords (optional)
                - embedding: Vector embedding

        Returns:
            ID of the inserted record
        """
        table_name = self.ensure_table_exists(model_name)

        query = f"""
        INSERT INTO {table_name}
        (source_id, document_id, chunk_no, page_no, text, keywords, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """

        result = self.execute(
            query,
            (
                data['source_id'],
                data['document_id'],
                data['chunk_no'],
                data.get('page_no'),
                data['text'],
                data.get('keywords', []),
                data['embedding']
            ),
            commit=True
        )

        return result[0]['id'] if result else None

    def search_similar(
        self,
        model_name: str,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        source_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings in the model-specific table.

        Args:
            model_name: Name of the embedding model
            query_embedding: Vector embedding to search for
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold (0-1)
            source_id: Optional source ID to filter results

        Returns:
            List of dictionaries containing search results with similarity scores
        """
        table_name = model_to_tablename(model_name)

        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        query = f"""
        SELECT id, source_id, document_id, chunk_no, page_no, text, keywords,
               1 - (embedding <=> %s::vector) AS similarity
        FROM {table_name}
        WHERE 1 - (embedding <=> %s::vector) >= %s
        """

        params = [embedding_str, embedding_str, threshold]

        if source_id:
            query += " AND source_id = %s"
            params.append(source_id)

        query += f" ORDER BY similarity DESC LIMIT {limit}"

        return self.execute(query, params) or []

    def get_model_stats(self, model_name: str) -> Dict[str, Any]:
        """Get statistics for a specific model's embeddings.

        Args:
            model_name: Name of the embedding model

        Returns:
            Dictionary containing statistics:
                - total_embeddings: Total number of embeddings
                - unique_sources: Number of unique sources
                - unique_documents: Number of unique documents
                - table_size: Size of the table in human-readable format
                - vector_dim: Dimension of the vectors
        """
        table_name = model_to_tablename(model_name)

        try:
            stats = self.execute(f"""
            SELECT
                COUNT(*) as total_embeddings,
                COUNT(DISTINCT source_id) as unique_sources,
                COUNT(DISTINCT document_id) as unique_documents,
                pg_size_pretty(pg_total_relation_size('{table_name}')) as table_size,
                (SELECT dimension FROM vector_dims WHERE tablename = '{table_name}') as vector_dim
            FROM {table_name}
            """)

            if not stats or not stats[0]:
                # Table might not exist or be empty
                return {
                    'total_embeddings': 0,
                    'unique_sources': 0,
                    'unique_documents': 0,
                    'table_size': '0 bytes',
                    'vector_dim': self.get_model_dimension(model_name)
                }

            return dict(stats[0])
        except Exception as e:
            logger.error(f"Error getting stats for model {model_name}: {e}")
            # Return default values if there's an error
            return {
                'total_embeddings': 0,
                'unique_sources': 0,
                'unique_documents': 0,
                'table_size': '0 bytes',
                'vector_dim': self.get_model_dimension(model_name),
                'error': str(e)
            }