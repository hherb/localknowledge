"""
Rerankers for semantic search results.

This module provides rerankers that can be used to rerank semantic search results
based on the relevance of the document to the query.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class Reranker(ABC):
    """Base class for rerankers."""
    
    @abstractmethod
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank documents based on their relevance to the query.
        
        Args:
            query: The search query.
            documents: List of document dictionaries to rerank.
                       Each document should have a 'text' field.
        
        Returns:
            Reranked list of documents with updated similarity scores.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of the reranker."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get a description of the reranker."""
        pass


class CrossEncoderReranker(Reranker):
    """Reranker using SentenceTransformers CrossEncoder models."""
    
    def __init__(self, model_name: str):
        """
        Initialize the CrossEncoder reranker.
        
        Args:
            model_name: Name of the CrossEncoder model to use.
        """
        self.model_name = model_name
        self._model = None
        self._descriptions = {
            "BAAI/bge-reranker-base": "BGE Reranker Base - Good general purpose reranker with balanced performance",
            "cross-encoder/ms-marco-MiniLM-L-6-v2": "MS MARCO MiniLM - Fast and efficient reranker optimized for web search",
            "cross-encoder/ms-marco-TinyBERT-L-2-v2": "MS MARCO TinyBERT - Very lightweight reranker for resource-constrained environments"
        }
    
    @property
    def model(self):
        """Lazy-load the model when first needed."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading CrossEncoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info(f"Successfully loaded CrossEncoder model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load CrossEncoder model {self.model_name}: {e}")
                raise
        return self._model
    
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank documents using the CrossEncoder model.
        
        Args:
            query: The search query.
            documents: List of document dictionaries to rerank.
        
        Returns:
            Reranked list of documents with updated similarity scores.
        """
        if not documents:
            return []
        
        # Extract text from documents for reranking
        texts = [doc.get('text', '') for doc in documents]
        
        # Create pairs of (query, document) for the model
        pairs = [(query, text) for text in texts]
        
        try:
            # Get scores from the model
            scores = self.model.predict(pairs)
            
            # Update documents with new scores
            for i, score in enumerate(scores):
                documents[i]['original_similarity'] = documents[i].get('similarity', 0)
                documents[i]['similarity'] = float(score)
                documents[i]['similarity_value'] = float(score)
                documents[i]['reranked'] = True
                # Format similarity as percentage for display
                documents[i]['similarity_pct'] = f"{float(score) * 100:.1f}%"
            
            # Sort documents by new scores
            reranked_docs = sorted(documents, key=lambda x: x['similarity'], reverse=True)
            
            logger.info(f"Reranked {len(documents)} documents using {self.model_name}")
            return reranked_docs
            
        except Exception as e:
            logger.error(f"Error during reranking with {self.model_name}: {e}")
            # Return original documents if reranking fails
            return documents
    
    @property
    def name(self) -> str:
        """Get the name of the reranker."""
        return self.model_name.split('/')[-1]
    
    @property
    def description(self) -> str:
        """Get a description of the reranker."""
        return self._descriptions.get(self.model_name, "CrossEncoder reranker")


def get_available_rerankers() -> List[Dict[str, str]]:
    """
    Get a list of available rerankers.
    
    Returns:
        List of dictionaries with 'id', 'name', and 'description' for each reranker.
    """
    rerankers = [
        {
            'id': 'BAAI/bge-reranker-base',
            'name': 'BGE Reranker Base',
            'description': 'Good general purpose reranker with balanced performance'
        },
        {
            'id': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'name': 'MS MARCO MiniLM',
            'description': 'Fast and efficient reranker optimized for web search'
        },
        {
            'id': 'cross-encoder/ms-marco-TinyBERT-L-2-v2',
            'name': 'MS MARCO TinyBERT',
            'description': 'Very lightweight reranker for resource-constrained environments'
        }
    ]
    return rerankers


def get_reranker(model_name: str) -> Optional[Reranker]:
    """
    Get a reranker by model name.
    
    Args:
        model_name: Name of the reranker model.
    
    Returns:
        A Reranker instance or None if the model is not supported.
    """
    if model_name in [
        "BAAI/bge-reranker-base",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "cross-encoder/ms-marco-TinyBERT-L-2-v2"
    ]:
        return CrossEncoderReranker(model_name)
    
    logger.warning(f"Unsupported reranker model: {model_name}")
    return None
