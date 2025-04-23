#!/usr/bin/env python3
"""
Database manager for embedding sources.

This module provides a database manager for the embedding_source table,
which tracks different sources of embeddings (e.g., abstract, full text, QA pairs).
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger(__name__)


class EmbeddingSourceDatabaseManager(DatabaseManager):
    """Database manager for embedding sources."""

    def __init__(self):
        """Initialize the embedding source database manager."""
        super().__init__()
        self.create_tables()

    def create_tables(self):
        """Create the embedding_source table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS embedding_source (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.execute(query, commit=True)
        logger.info("Created embedding_source table")

        # Insert default sources if they don't exist
        self._ensure_default_sources()

    def _ensure_default_sources(self):
        """Ensure default embedding sources exist in the table."""
        default_sources = [
            {
                'name': 'abstract',
                'description': 'Embeddings generated from document abstracts'
            },
            {
                'name': 'full_text',
                'description': 'Embeddings generated from document full text'
            },
            {
                'name': 'qa_pairs',
                'description': 'Embeddings generated from question-answer pairs'
            },
            {
                'name': 'synthetic',
                'description': 'Embeddings generated from synthetic text'
            }
        ]

        for source in default_sources:
            self.add_embedding_source(source['name'], source['description'])

    def add_embedding_source(self, name: str, description: Optional[str] = None) -> int:
        """Add a new embedding source.
        
        Args:
            name: Name of the embedding source
            description: Description of the embedding source
            
        Returns:
            ID of the new embedding source
        """
        query = """
        INSERT INTO embedding_source (name, description)
        VALUES (%s, %s)
        ON CONFLICT (name) DO UPDATE
        SET description = EXCLUDED.description
        RETURNING id;
        """
        result = self.execute(query, (name, description), commit=True)
        
        if result:
            source_id = result[0]['id']
            logger.info(f"Added embedding source: {name} (ID: {source_id})")
            return source_id
        
        # If insertion failed, try to get the existing ID
        query = "SELECT id FROM embedding_source WHERE name = %s"
        result = self.execute(query, (name,))
        
        if result:
            return result[0]['id']
        
        logger.error(f"Failed to add embedding source: {name}")
        return -1

    def get_embedding_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Get an embedding source by ID.
        
        Args:
            source_id: ID of the embedding source
            
        Returns:
            Embedding source record or None if not found
        """
        query = "SELECT * FROM embedding_source WHERE id = %s"
        result = self.execute(query, (source_id,))
        
        if result:
            return result[0]
        
        return None

    def get_embedding_source_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an embedding source by name.
        
        Args:
            name: Name of the embedding source
            
        Returns:
            Embedding source record or None if not found
        """
        query = "SELECT * FROM embedding_source WHERE name = %s"
        result = self.execute(query, (name,))
        
        if result:
            return result[0]
        
        return None

    def get_all_embedding_sources(self) -> List[Dict[str, Any]]:
        """Get all embedding sources.
        
        Returns:
            List of embedding source records
        """
        query = "SELECT * FROM embedding_source ORDER BY name"
        result = self.execute(query)
        
        return result or []

    def update_embedding_source(self, source_id: int, name: Optional[str] = None, 
                               description: Optional[str] = None) -> bool:
        """Update an embedding source.
        
        Args:
            source_id: ID of the embedding source to update
            name: New name for the embedding source
            description: New description for the embedding source
            
        Returns:
            True if the update was successful, False otherwise
        """
        # Build the SET clause dynamically based on provided parameters
        set_clause = []
        params = []
        
        if name is not None:
            set_clause.append("name = %s")
            params.append(name)
        
        if description is not None:
            set_clause.append("description = %s")
            params.append(description)
        
        if not set_clause:
            logger.warning("No parameters provided for update")
            return False
        
        query = f"""
        UPDATE embedding_source
        SET {', '.join(set_clause)}
        WHERE id = %s
        """
        
        params.append(source_id)
        
        self.execute(query, tuple(params), commit=True)
        logger.info(f"Updated embedding source ID: {source_id}")
        
        return True

    def delete_embedding_source(self, source_id: int) -> bool:
        """Delete an embedding source.
        
        Args:
            source_id: ID of the embedding source to delete
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        query = "DELETE FROM embedding_source WHERE id = %s"
        self.execute(query, (source_id,), commit=True)
        logger.info(f"Deleted embedding source ID: {source_id}")
        
        return True


# Singleton instance
_instance = None

def get_embedding_source_db():
    """Get the singleton instance of the embedding source database manager."""
    global _instance
    if _instance is None:
        _instance = EmbeddingSourceDatabaseManager()
    return _instance
