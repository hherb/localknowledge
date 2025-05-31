"""
This module provides an embedder class for creating vector embeddings using Ollama models.

It includes functionality for:
- Creating embeddings for individual texts
- Creating embeddings for batches of texts
- Handling errors and retries
- Configuring the Ollama API URL
"""
import ollama
import logging
from localknowledge.embeddings.base_embedder import BaseEmbedder

# Configure logging
logger = logging.getLogger(__name__)

MODELS=["snowflake-arctic-embed2:latest",
        "nomic-embed-text",
        "jina/jina-embeddings-v2-base-en",
        "bge-m3",
        "granite-embedding:278m",
        "mxbai-embed-large"
        ]

class OllamaEmbedder(BaseEmbedder):
    """Class for creating vector embeddings using Ollama models."""
    def __init__(self, model_name: str = "snowflake-arctic-embed2:latest",
                 ollama_host: str = "http://localhost:11434"):
        super().__init__(model_name)
        self.ollama_host = ollama_host
        self.vectorsize=0

        logger.info(f"Initializing OllamaEmbedder with model: {model_name}")

        try:
            response=ollama.embed(model_name, "test")
            self.vectorsize = len(response.embeddings[0])
            logger.info(f"Successfully initialized OllamaEmbedder for {model_name}, vector size: {self.vectorsize}")
        except Exception as e:
            logger.warning(f"Error initializing OllamaEmbedder: {e}")
            logger.info(f"Trying to download model {model_name}")
            try:
                ollama.pull(model_name)
                response=ollama.embed(model_name, "test")
                self.vectorsize = len(response.embeddings[0])
                logger.info(f"Successfully downloaded and initialized OllamaEmbedder for {model_name}, vector size: {self.vectorsize}")
            except Exception as e:
                logger.error(f"Error pulling and initializing OllamaEmbedder: {e}")
                raise

    def list_available_models(self) -> list[str]:
        """List available models."""
        return MODELS

    def get_vectorsize(self):
        """Get the size of the embedding vectors."""
        return self.vectorsize

    def embed(self, text: str) -> list[float]:
        """Create an embedding for the given text."""
        try:
            response = ollama.embed(model=self.model_name, input=text)
            return response.embeddings[0]
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts at once."""
        try:
            logger.debug(f"Creating embeddings for batch of {len(texts)} texts using {self.model_name}")
            response = ollama.embed(model=self.model_name, input=texts)
            logger.debug(f"Successfully created {len(response.embeddings)} embeddings")
            return response.embeddings
        except Exception as e:
            logger.error(f"Error creating batch embeddings: {e}")
            return []

if __name__== "__main__":
    for model in MODELS:
        print(f"testing model : {model}")
        embedder = OllamaEmbedder(model)
        print(f"Vector size: {embedder.get_vectorsize()}")
        print(f"Single embedding: {len(embedder.embed("This is a test"))}")
        print(f"Batch embedding (batches): {len(embedder.embed_batch(["This is a test", "This is another test"]))}")


