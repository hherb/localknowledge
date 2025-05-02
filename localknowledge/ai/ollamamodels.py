"""
Helper module to interact with Ollama API for retrieving and managing model information.

This module provides functionality to list available models, get detailed information
about specific models, and determine model capabilities using the Ollama API.
"""
import ollama
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    """
    Data class representing information about an Ollama model.

    Attributes:
        model: The name of the model
        family: The model family (e.g., 'gemma', 'llama', 'phi')
        size: The number of parameters in the model
        quantization: The quantization level used (e.g., 'Q4_K_M')
        context_length: Maximum context window size in tokens
        embedding_length: Dimension of the embedding vectors
        is_free: Whether the model is free to use
        is_locally_available: Whether the model is available locally
    """
    model: str
    family: str
    size: int
    quantization: str
    context_length: int
    embedding_length: int
    is_free: bool = True
    is_locally_available: bool = True



def list_models(family: Optional[str] = None) -> List[Optional[ModelInfo]]:
    """
    List available models using the Ollama API.

    Args:
        family: Optional filter to only return models from a specific family
               (e.g., 'gemma', 'llama'). If None, all models are returned.

    Returns:
        A list of ModelInfo objects for the available models.
        Returns an empty list if an error occurs.
    """
    try:
        models = ollama.list()['models']
        if not family:
            models = [model_info(model['model']) for model in models]
        else:
            models = [model_info(model['model']) for model in models if model['model'].lower().startswith(family.lower())]
        return models
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return []

def sizestr2int(sizestr: str) -> int:
    """
    Convert a model size string to an integer representing the number of parameters.

    Args:
        sizestr: A string representing model size (e.g., '7B', '13B', '70K')
                 where B=billion, M=million, K=thousand

    Returns:
        The number of parameters as an integer

    Note:
        'B' suffix indicates billions of parameters (e.g., '7B' → 7,000,000,000)
        'M' suffix indicates millions of parameters (e.g., '70M' → 70,000,000)
        'K' suffix indicates thousands of parameters (e.g., '70K' → 70,000)
    """
    if sizestr.endswith('B'):  # Billion parameters
        return int(float(sizestr[:-1]) * 1000000000)
    elif sizestr.endswith('K'):  # Thousand parameters
        return int(float(sizestr[:-1]) * 1000)
    elif sizestr.endswith('M'):  # Million parameters
        return int(float(sizestr[:-1]) * 1000000)

def model_info(model_name: str) -> Optional[ModelInfo]:
    """
    Get detailed information about a specific Ollama model.

    Args:
        model_name: The name of the model to get information for

    Returns:
        A ModelInfo object containing the model's details, or None if an error occurs

    Note:
        This function attempts to extract information from the Ollama API response,
        with multiple fallback strategies for different model structures.
    """
    try:
        shown = ollama.show(model_name)
        details = shown.details
        # Example details structure:
        # ModelDetails(parent_model='', format='gguf', family='gemma3',
        # families=['gemma3'], parameter_size='4.3B', quantization_level='Q4_K_M')

        modelinfo = shown.modelinfo
        # Example modelinfo structure:
        # {'general.architecture': 'phi3', 'general.basename': 'phi', 'general.file_type': 15,
        # 'general.languages': ['en'], 'general.license': 'mit',
        # 'general.parameter_count': 14659507200,
        # 'general.quantization_version': 2,
        # 'general.size_label': '15B',
        # 'general.tags': ['phi', 'nlp', 'math', 'code', 'chat', 'conversational', 'text-generation'],
        # 'general.type': 'model',
        # 'general.version': '4',
        # 'phi3.context_length': 16384,
        # 'phi3.embedding_length': 5120}

        # Extract size information with fallbacks
        try:
            size = modelinfo.get('general.parameter_count', sizestr2int(details.parameter_size))
        except Exception:
            try:
                size = int(modelinfo.get(f'{details.family}.parameter_count', 0))
            except Exception:
                size = 0

        # Extract context length with fallbacks
        try:
            context_length = modelinfo.get('general.context_length', details.context_length)
        except Exception:
            try:
                context_length = modelinfo.get(f'{details.family}.context_length', 0)
            except Exception:
                context_length = 0

        # Extract embedding length with fallbacks
        try:
            embedding_length = modelinfo.get('general.embedding_length', details.embedding_length)
        except Exception:
            try:
                embedding_length = modelinfo.get(f'{details.family}.embedding_length', 0)
            except Exception:
                embedding_length = 0

        # Create and return the ModelInfo object
        info = ModelInfo(
            model=model_name,
            family=details.family,
            size=size,
            quantization=details.quantization_level,
            context_length=context_length,
            embedding_length=embedding_length,
            is_free=True,
            is_locally_available=True
        )
        return info
    except Exception as e:
        print(f"Error getting model info: {str(e)}")
        return None

def model_capabilities(model_name: str) -> List[str]:
    """
    Get the capabilities of a specific model.

    Args:
        model_name: The name of the model to get capabilities for

    Returns:
        A list of capability strings (e.g., ['embedding', 'chat', 'completion'])
        Returns an empty list if an error occurs or if capabilities cannot be determined

    Note:
        This is a placeholder function that currently returns an empty list.
        Future implementations may query the model for its actual capabilities.
    """
    try:
        # In the future, this could query the model for its capabilities
        # For now, just return an empty list
        return []
    except Exception as e:
        print(f"Error getting capabilities for {model_name}: {str(e)}")
        return []

def update_local_model_database() -> Tuple[int, int, int]:
    """
    Update the local database of available models.

    This function retrieves the list of available models and their details using the
    Ollama API, and updates the local database accordingly. It uses the model_info()
    function to get detailed information about each model.

    It also checks whether models already in the database that are marked as
    available locally are still available - if ollama.list() doesn't show them
    anymore, their is_locally_available flag is set to False.

    Returns:
        Tuple[int, int, int]: A tuple containing (models_added, models_updated, models_marked_unavailable)
    """
    from localknowledge.db.models import ModelsDatabaseManager

    db_manager = ModelsDatabaseManager()

    # Get the Ollama provider ID
    ollama_provider = db_manager.get_provider_by_name("ollama")
    if not ollama_provider:
        logger.error("Ollama provider not found in the database")
        return 0, 0, 0

    ollama_provider_id = ollama_provider['id']

    # Get all models currently in the database from the Ollama provider
    query = """
    SELECT id, name, is_locally_available FROM models
    WHERE provider_id = %s
    """
    db_models = db_manager.execute(query, (ollama_provider_id,))

    # Create a dictionary of model names to IDs for quick lookup
    # Only include models that are marked as locally available for the unavailability check
    db_model_names = {model['name']: model['id'] for model in db_models if model['is_locally_available']} if db_models else {}

    # Get all models from Ollama
    try:
        # Get the list of models from Ollama
        models_list = ollama.list()['models']
        model_names = [model['model'] for model in models_list]
    except Exception as e:
        logger.error(f"Error listing models from Ollama: {e}")
        return 0, 0, 0

    # Track statistics
    models_added = 0
    models_updated = 0

    # Process each model from Ollama
    for model_name in model_names:
        # Get detailed information about the model
        model_info_obj = model_info(model_name)
        if not model_info_obj:  # Skip if we couldn't get model info
            logger.warning(f"Could not get information for model {model_name}")
            continue

        # Extract model details
        family = model_info_obj.family
        size = model_info_obj.size
        quantization = model_info_obj.quantization
        context_length = model_info_obj.context_length
        embedding_length = model_info_obj.embedding_length

        # Check if this model is already in the database
        if model_name in db_model_names:
            # Update the model with the latest information
            model_id = db_model_names[model_name]
            success = db_manager.update_model(
                model_id=model_id,
                description=f"{family} model",
                params=size,
                quantization=quantization,
                context_length=context_length,
                embedding_length=embedding_length,
                is_free=True,  # Ollama models are free
                is_locally_available=True
            )
            if success:
                models_updated += 1
                # Remove from the dictionary to track which models are still available
                db_model_names.pop(model_name)
        else:
            # Add the model to the database
            model_id = db_manager.add_model(
                provider_id=ollama_provider_id,
                name=model_name,
                description=f"{family} model",
                params=size,
                quantization=quantization,
                context_length=context_length,
                embedding_length=embedding_length,
                is_free=True,  # Ollama models are free
                is_locally_available=True
            )
            if model_id:
                models_added += 1

                # Set capabilities based on model family and name
                # Check for embedding models
                if "embed" in model_name.lower() or model_name.lower().endswith("-e"):
                    embedding_capability = db_manager.get_capability_by_name("embedding")
                    if embedding_capability:
                        db_manager.set_model_capability(model_id, embedding_capability['id'])

                # Check for completion/chat models (most models support this)
                if "embed" not in model_name.lower() and not model_name.lower().endswith("-e"):
                    completion_capability = db_manager.get_capability_by_name("completion")
                    if completion_capability:
                        db_manager.set_model_capability(model_id, completion_capability['id'])

                # Check for vision models
                if "vision" in model_name.lower() or "-v" in model_name.lower() or "clip" in family.lower():
                    vision_capability = db_manager.get_capability_by_name("vision")
                    if vision_capability:
                        db_manager.set_model_capability(model_id, vision_capability['id'])

                # Check for reasoning models
                if "reasoning" in model_name.lower():
                    reasoning_capability = db_manager.get_capability_by_name("reasoning")
                    if reasoning_capability:
                        db_manager.set_model_capability(model_id, reasoning_capability['id'])

    # Mark models that are no longer available as unavailable
    # ONLY for models provided by Ollama
    models_marked_unavailable = 0
    for model_name, model_id in db_model_names.items():
        success = db_manager.update_model(
            model_id=model_id,
            is_locally_available=False
        )
        if success:
            models_marked_unavailable += 1
            logger.info(f"Marked Ollama model {model_name} as no longer locally available")

    logger.info(f"Models added: {models_added}, updated: {models_updated}, marked unavailable: {models_marked_unavailable}")
    return models_added, models_updated, models_marked_unavailable

if __name__=="__main__":
    # Test listing models
    print("Testing list_models():")
    print(list_models("gemma"))
    print()
    print('-'*80)

    # Test model_info
    print("Testing model_info() for a specific model:")
    info = model_info("qwen3:4b")
    print(info)
    print('-'*80)
    print()

    # Test update_local_model_database
    print("Testing update_local_model_database():")
    added, updated, unavailable = update_local_model_database()
    print(f"Models added: {added}")
    print(f"Models updated: {updated}")
    print(f"Models marked unavailable: {unavailable}")
    print('-'*80)
    print()

    # List all models
    print("All available models:")
    models = list_models()
    for model in models:
        # model is already a ModelInfo object, so just print it directly
        print(model)
        print('-'*80)
        print()

