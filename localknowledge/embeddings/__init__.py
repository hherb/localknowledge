"""
Vector embeddings module for LocalKnowledge.

This module provides functionality for creating and searching vector embeddings
using Ollama models and storing them in a PostgreSQL database with pgvector.
"""

from localknowledge.embeddings.embedding_manager import EmbeddingManager
from localknowledge.embeddings.database import EmbeddingDatabaseManager
from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder

__all__ = ['EmbeddingManager', 'EmbeddingDatabaseManager', OllamaEmbedder, PubMedBERTEmbedder]
