"""
This module provides an embedder class for creating vector embeddings using PubMedBERT models.

It includes functionality for:
- Creating embeddings for individual texts
- Creating embeddings for batches of texts
- Handling errors and retries
- Configuring the PubMedBERT model
- Memory-efficient processing of large batches
"""
import gc
import os
import logging
import torch
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from localknowledge.embeddings.base_embedder import BaseEmbedder

# Configure logging
logger = logging.getLogger(__name__)

MODELS = [ #"microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext", #-- not suited for semantc searches
          "pritamdeka/S-BioBERT-snli-mnli-scitail-mednli-stsb", #-- recommended for semantic search
          "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
          "NeuML/pubmedbert-base-embeddings",
          "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
          ]

class PubMedBERTEmbedder(BaseEmbedder):
    """Class for creating vector embeddings using PubMedBERT models with memory optimization."""
    def __init__(self, model_name: str = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
                 device: Optional[str] = None, 
                 max_batch_size: int = 1000):
        """
        Initialize the PubMedBERT embedder.

        Args:
            model_name: Name of the model to use
            device: Device to use for computation (None for auto-detection)
            max_batch_size: Maximum batch size for embedding to prevent memory issues
        """
        super().__init__(model_name)

        # Set environment variables for offline mode if needed
        if os.path.exists(os.path.expanduser(f"~/.cache/huggingface/hub/models--{model_name.replace('/', '--')}")):
            logger.info(f"Using local model: {model_name}")
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'

        # Auto-detect device if not specified
        if device is None:
            if torch.cuda.is_available():
                device = 'cuda'
            elif hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'

        logger.info(f"Using device: {device} for PubMedBERT embedder")
        self.device = device
        self.max_batch_size = max_batch_size

        try:
            self.model = SentenceTransformer(model_name, device=device)
            logger.info(f"Successfully loaded model: {model_name} on {device}")
            logger.info(f"Vector size: {self.get_vectorsize()}")
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            raise

    def list_available_models(self) -> List[str]:
        """List available models."""
        return MODELS

    def get_vectorsize(self) -> int:
        """Get the size of the embedding vectors."""
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> List[float]:
        """
        Create an embedding for the given text with minimal memory management.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Create embedding
            embedding = self.model.encode(text, show_progress_bar=False).tolist()

            # No garbage collection here to maintain performance
            # It will be handled at batch level instead

            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            # Return a zero vector of the correct dimension as fallback
            return [0.0] * self.get_vectorsize()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts with memory-efficient batching.

        Args:
            texts: List of texts to embed

        Returns:
            List of vector embeddings
        """
        if not texts:
            return []

        try:
            # Process in a single batch for better performance
            # Only use sub-batching if the batch is very large
            if len(texts) > self.max_batch_size * 2:
                results = []
                # Process in smaller sub-batches to prevent memory issues
                for i in range(0, len(texts), self.max_batch_size):
                    batch = texts[i:i + self.max_batch_size]

                    # Create embeddings for this sub-batch
                    batch_embeddings = self.model.encode(batch, show_progress_bar=False).tolist()
                    results.extend(batch_embeddings)

                    # Only do garbage collection every few batches
                    if i > 0 and i % (self.max_batch_size * 3) == 0:
                        gc.collect()
                        if self.device == 'cuda':
                            torch.cuda.empty_cache()

                return results
            else:
                # For smaller batches, process all at once for better performance
                return self.model.encode(texts, show_progress_bar=False).tolist()
        except Exception as e:
            logger.error(f"Error creating batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.get_vectorsize() for _ in texts]

if __name__== "__main__":
    for model in MODELS:
        print(f"testing model {model} : {model}")
        embedder = PubMedBERTEmbedder(model)
        print(embedder.embed("This is a test"))
        print(embedder.embed_batch(["This is a test", "This is another test"]))
        print(embedder.get_vectorsize())

