"""
This module provides an embedder class for creating vector embeddings using PubMedBERT models.

It includes functionality for:
- Creating embeddings for individual texts
- Creating embeddings for batches of texts
- Handling errors and retries
- Configuring the PubMedBERT model
"""
from sentence_transformers import SentenceTransformer
from localknowledge.embeddings.base_embedder import BaseEmbedder

MODELS = ["microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
          "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
          "NeuML/pubmedbert-base-embeddings"
          ]

class PubMedBERTEmbedder(BaseEmbedder):
    """Class for creating vector embeddings using PubMedBERT models."""
    def __init__(self, model_name: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"):
        super().__init__(model_name)
        self.model = SentenceTransformer(model_name)

    def list_available_models(self) -> list[str]:
        """List available models."""
        return MODELS

    def get_vectorsize(self):
        """Get the size of the embedding vectors."""
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        """Create an embedding for the given text."""
        return self.model.encode(text, show_progress_bar=False).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts at once."""
        return self.model.encode(texts, show_progress_bar=False).tolist()

if __name__== "__main__":
    for model in MODELS:
        print(f"testing model {model} : {model}")
        embedder = PubMedBERTEmbedder(model)
        print(embedder.embed("This is a test"))
        print(embedder.embed_batch(["This is a test", "This is another test"]))
        print(embedder.get_vectorsize())

