#!/usr/bin/env python3
"""
Database functionality for embedding sources in the LocalKnowledge library.

This module provides database operations for working with embedding sources,
which are used to categorize different types of embeddings (e.g., abstract, full_text).
"""

import logging
from typing import List, Dict, Any, Optional

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingSourceDatabaseManager(DatabaseManager):
    """Database manager for embedding sources."""

    def __init__(self):
        """Initialize the embedding source database manager."""
        super().__init__()
        # Tables are created by the migration system, not here

    def get_embedding_source_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an embedding source by name.

        Args:
            name: Name of the embedding source

        Returns:
            Embedding source record or None if not found
        """
        query = "SELECT * FROM embedding_source WHERE name = %s"
        result = self.execute(query, (name,))
        return result[0] if result else None

    def get_embedding_source_by_id(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Get an embedding source by ID.

        Args:
            source_id: ID of the embedding source

        Returns:
            Embedding source record or None if not found
        """
        query = "SELECT * FROM embedding_source WHERE id = %s"
        result = self.execute(query, (source_id,))
        return result[0] if result else None

    def get_all_embedding_sources(self) -> List[Dict[str, Any]]:
        """Get all embedding sources.

        Returns:
            List of embedding source records
        """
        query = "SELECT * FROM embedding_source ORDER BY name"
        return self.execute(query) or []

    def add_embedding_source(self, name: str, description: Optional[str] = None) -> int:
        """Add a new embedding source.

        Args:
            name: Name of the embedding source
            description: Description of the embedding source (optional)

        Returns:
            ID of the new embedding source
        """
        # Check if the embedding source already exists
        existing = self.get_embedding_source_by_name(name)
        if existing:
            return existing['id']

        # Add the new embedding source
        query = """
        INSERT INTO embedding_source (name, description)
        VALUES (%s, %s)
        RETURNING id
        """
        result = self.execute(query, (name, description), commit=True)
        
        if result:
            source_id = result[0]['id']
            logger.info(f"Added embedding source '{name}' with ID {source_id}")
            return source_id
        
        logger.error(f"Failed to add embedding source '{name}'")
        return -1

    def update_embedding_source(self, source_id: int, name: Optional[str] = None, 
                              description: Optional[str] = None) -> bool:
        """Update an embedding source.

        Args:
            source_id: ID of the embedding source
            name: New name for the embedding source (optional)
            description: New description for the embedding source (optional)

        Returns:
            True if successful, False otherwise
        """
        # Build the update query based on provided parameters
        update_parts = []
        params = []

        if name is not None:
            update_parts.append("name = %s")
            params.append(name)

        if description is not None:
            update_parts.append("description = %s")
            params.append(description)

        if not update_parts:
            logger.warning("No updates provided for embedding source")
            return False

        query = f"""
        UPDATE embedding_source
        SET {', '.join(update_parts)}
        WHERE id = %s
        """
        params.append(source_id)

        try:
            self.execute(query, tuple(params), commit=True)
            logger.info(f"Updated embedding source with ID {source_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating embedding source with ID {source_id}: {e}")
            return False

    def delete_embedding_source(self, source_id: int) -> bool:
        """Delete an embedding source.

        Args:
            source_id: ID of the embedding source

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM embedding_source WHERE id = %s", (source_id,), commit=True)
            logger.info(f"Deleted embedding source with ID {source_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting embedding source with ID {source_id}: {e}")
            return False


# Singleton instance
_instance = None

def get_embedding_source_db():
    """Get the singleton instance of the embedding source database manager."""
    global _instance
    if _instance is None:
        _instance = EmbeddingSourceDatabaseManager()
    return _instance
