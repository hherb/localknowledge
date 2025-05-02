"""
Database manager for models.

This module provides a database manager for retrieving and managing models from the database.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

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

    def get_provider_by_name(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider dictionary or None if not found
        """
        query = """
        SELECT *
        FROM model_providers
        WHERE name = %s
        """
        try:
            result = self.execute(query, (provider_name,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting provider by name: {e}")
            return None

    def add_model(self,
                 provider_id: int,
                 name: str,
                 description: Optional[str] = None,
                 params: Optional[int] = None,
                 quantization: Optional[str] = None,
                 context_length: Optional[int] = None,
                 embedding_length: Optional[int] = None,
                 is_free: bool = True,
                 is_locally_available: bool = True) -> Optional[int]:
        """
        Add a new model to the database.

        Args:
            provider_id: ID of the provider
            name: Name of the model
            description: Description of the model
            params: Number of parameters in the model
            quantization: Quantization level of the model
            context_length: Context length of the model
            embedding_length: Embedding length of the model
            is_free: Whether the model is free to use
            is_locally_available: Whether the model is available locally

        Returns:
            ID of the newly added model, or None if an error occurred
        """
        # Check if model already exists
        existing_model = self.get_model_by_name(name)
        if existing_model:
            logger.info(f"Model {name} already exists with ID {existing_model['id']}")
            return existing_model['id']

        query = """
        INSERT INTO models
        (provider_id, name, description, params, quantization, context_length, embedding_length, is_free, is_locally_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        try:
            result = self.execute(
                query,
                (provider_id, name, description, params, quantization, context_length, embedding_length, is_free, is_locally_available),
                commit=True
            )
            model_id = result[0]['id'] if result else None
            if model_id:
                logger.info(f"Added model {name} with ID {model_id}")
            return model_id
        except Exception as e:
            logger.error(f"Error adding model: {e}")
            return None

    def update_model(self,
                    model_id: int,
                    description: Optional[str] = None,
                    params: Optional[int] = None,
                    quantization: Optional[str] = None,
                    context_length: Optional[int] = None,
                    embedding_length: Optional[int] = None,
                    is_free: Optional[bool] = None,
                    is_locally_available: Optional[bool] = None) -> bool:
        """
        Update an existing model in the database.

        Args:
            model_id: ID of the model to update
            description: New description of the model
            params: New number of parameters in the model
            quantization: New quantization level of the model
            context_length: New context length of the model
            embedding_length: New embedding length of the model
            is_free: New value for whether the model is free to use
            is_locally_available: New value for whether the model is available locally

        Returns:
            True if the update was successful, False otherwise
        """
        # Build the update query dynamically based on which fields are provided
        update_fields = []
        params_list = []

        if description is not None:
            update_fields.append("description = %s")
            params_list.append(description)

        if params is not None:
            update_fields.append("params = %s")
            params_list.append(params)

        if quantization is not None:
            update_fields.append("quantization = %s")
            params_list.append(quantization)

        if context_length is not None:
            update_fields.append("context_length = %s")
            params_list.append(context_length)

        if embedding_length is not None:
            update_fields.append("embedding_length = %s")
            params_list.append(embedding_length)

        if is_free is not None:
            update_fields.append("is_free = %s")
            params_list.append(is_free)

        if is_locally_available is not None:
            update_fields.append("is_locally_available = %s")
            params_list.append(is_locally_available)

        # If no fields to update, return early
        if not update_fields:
            logger.warning("No fields provided for model update")
            return False

        query = f"""
        UPDATE models
        SET {", ".join(update_fields)}
        WHERE id = %s
        """
        params_list.append(model_id)

        try:
            self.execute(query, tuple(params_list), commit=True)
            logger.info(f"Updated model with ID {model_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating model: {e}")
            return False

    def set_model_capability(self, model_id: int, capability_id: int) -> bool:
        """
        Set a capability for a model.

        Args:
            model_id: ID of the model
            capability_id: ID of the capability

        Returns:
            True if successful, False otherwise
        """
        # Check if the capability is already set for this model
        query = """
        SELECT 1 FROM model_capability_junction
        WHERE model_id = %s AND capability_id = %s
        """
        try:
            result = self.execute(query, (model_id, capability_id))
            if result:
                logger.debug(f"Capability {capability_id} already set for model {model_id}")
                return True

            # Add the capability
            query = """
            INSERT INTO model_capability_junction (model_id, capability_id)
            VALUES (%s, %s)
            """
            self.execute(query, (model_id, capability_id), commit=True)
            logger.info(f"Set capability {capability_id} for model {model_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting model capability: {e}")
            return False

    def get_capability_by_name(self, capability_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a capability by name.

        Args:
            capability_name: Name of the capability

        Returns:
            Capability dictionary or None if not found
        """
        query = """
        SELECT *
        FROM model_capabilities
        WHERE name = %s
        """
        try:
            result = self.execute(query, (capability_name,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting capability by name: {e}")
            return None
