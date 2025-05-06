"""
Vector embeddings module for LocalKnowledge.

This module provides functionality for creating and searching vector embeddings
using Ollama models and storing them in a PostgreSQL database with pgvector.
"""

# Import embedders directly
from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder

# Use lazy import for EmbeddingManager to avoid circular imports
def get_embedding_manager():
    """Get the EmbeddingManager class lazily to avoid circular imports."""
    from localknowledge.embeddings.embedding_manager import EmbeddingManager
    return EmbeddingManager

# Export symbols
__all__ = ['get_embedding_manager', 'OllamaEmbedder', 'PubMedBERTEmbedder']
