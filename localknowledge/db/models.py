"""
Database manager for models.

This module provides a database manager for retrieving and managing models from the database.
"""

import logging
from typing import List, Dict, Any, Optional

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class ModelsDatabaseManager(DatabaseManager):
    """Database manager for models."""

    def __init__(self):
        """Initialize the models database manager."""
        super().__init__()

    def get_all_models(self, provider_id: Optional[int] = None, capability_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all models, optionally filtered by provider or capability.

        Args:
            provider_id: Optional provider ID to filter by
            capability_id: Optional capability ID to filter by

        Returns:
            List of model dictionaries
        """
        if provider_id and capability_id:
            # Filter by both provider and capability
            query = """
            SELECT m.*, mp.name as provider_name
            FROM models m
            JOIN model_providers mp ON m.provider_id = mp.id
            JOIN model_capability_junction mcj ON m.id = mcj.model_id
            WHERE m.provider_id = %s AND mcj.capability_id = %s AND m.is_active = true
            ORDER BY m.name
            """
            params = (provider_id, capability_id)
        elif provider_id:
            # Filter by provider only
            query = """
            SELECT m.*, mp.name as provider_name
            FROM models m
            JOIN model_providers mp ON m.provider_id = mp.id
            WHERE m.provider_id = %s AND m.is_active = true
            ORDER BY m.name
            """
            params = (provider_id,)
        elif capability_id:
            # Filter by capability only
            query = """
            SELECT m.*, mp.name as provider_name
            FROM models m
            JOIN model_providers mp ON m.provider_id = mp.id
            JOIN model_capability_junction mcj ON m.id = mcj.model_id
            WHERE mcj.capability_id = %s AND m.is_active = true
            ORDER BY m.name
            """
            params = (capability_id,)
        else:
            # Get all models
            query = """
            SELECT m.*, mp.name as provider_name
            FROM models m
            JOIN model_providers mp ON m.provider_id = mp.id
            WHERE m.is_active = true
            ORDER BY m.name
            """
            params = None

        try:
            result = self.execute(query, params)
            return result or []
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []

    def get_model_by_id(self, model_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a model by ID.

        Args:
            model_id: ID of the model

        Returns:
            Model dictionary or None if not found
        """
        query = """
        SELECT m.*, mp.name as provider_name
        FROM models m
        JOIN model_providers mp ON m.provider_id = mp.id
        WHERE m.id = %s
        """
        try:
            result = self.execute(query, (model_id,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting model by ID: {e}")
            return None

    def get_model_by_name(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a model by name.

        Args:
            model_name: Name of the model

        Returns:
            Model dictionary or None if not found
        """
        query = """
        SELECT m.*, mp.name as provider_name
        FROM models m
        JOIN model_providers mp ON m.provider_id = mp.id
        WHERE m.name = %s
        """
        try:
            result = self.execute(query, (model_name,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting model by name: {e}")
            return None

    def get_model_capabilities(self, model_id: int) -> List[Dict[str, Any]]:
        """
        Get capabilities for a model.

        Args:
            model_id: ID of the model

        Returns:
            List of capability dictionaries
        """
        query = """
        SELECT mc.*
        FROM model_capabilities mc
        JOIN model_capability_junction mcj ON mc.id = mcj.capability_id
        WHERE mcj.model_id = %s
        ORDER BY mc.name
        """
        try:
            result = self.execute(query, (model_id,))
            return result or []
        except Exception as e:
            logger.error(f"Error getting model capabilities: {e}")
            return []

    def get_all_providers(self) -> List[Dict[str, Any]]:
        """
        Get all model providers.

        Returns:
            List of provider dictionaries
        """
        query = """
        SELECT *
        FROM model_providers
        WHERE is_active = true
        ORDER BY name
        """
        try:
            result = self.execute(query)
            return result or []
        except Exception as e:
            logger.error(f"Error getting providers: {e}")
            return []

    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        """
        Get all model capabilities.

        Returns:
            List of capability dictionaries
        """
        query = """
        SELECT *
        FROM model_capabilities
        ORDER BY name
        """
        try:
            result = self.execute(query)
            return result or []
        except Exception as e:
            logger.error(f"Error getting capabilities: {e}")
            return []

    def get_completion_models(self) -> List[Dict[str, Any]]:
        """
        Get all models with completion capability.

        Returns:
            List of model dictionaries
        """
        # Get the ID of the completion capability
        query = """
        SELECT id FROM model_capabilities
        WHERE name = 'completion'
        """
        try:
            result = self.execute(query)
            if not result:
                logger.warning("Completion capability not found")
                return []

            completion_id = result[0]['id']

            # Get models with completion capability
            return self.get_all_models(capability_id=completion_id)
        except Exception as e:
            logger.error(f"Error getting completion models: {e}")
            return []
