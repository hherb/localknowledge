"""
Vector embeddings module for LocalKnowledge.

This module provides functionality for creating and searching vector embeddings
using Ollama models and storing them in a PostgreSQL database with pgvector.
"""

import logging

logger = logging.getLogger(__name__)

# Try to import embedders with graceful fallback
OllamaEmbedder = None
PubMedBERTEmbedder = None

try:
    from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
    logger.info("Successfully imported OllamaEmbedder")
except Exception as e:
    logger.warning(f"Failed to import OllamaEmbedder: {e}")

try:
    from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder
    logger.info("Successfully imported PubMedBERTEmbedder")
except Exception as e:
    logger.warning(f"Failed to import PubMedBERTEmbedder: {e}")

# Use lazy import for EmbeddingManager to avoid circular imports
def get_embedding_manager():
    """Get the EmbeddingManager class lazily to avoid circular imports."""
    try:
        from localknowledge.embeddings.embedding_manager import EmbeddingManager
        return EmbeddingManager
    except Exception as e:
        logger.warning(f"Failed to import EmbeddingManager: {e}")
        return None

# Export symbols (only those that were successfully imported)
available_exports = ['get_embedding_manager']
if OllamaEmbedder is not None:
    available_exports.append('OllamaEmbedder')
if PubMedBERTEmbedder is not None:
    available_exports.append('PubMedBERTEmbedder')

__all__ = available_exports
