"""Base class for embedder modules."""

class BaseEmbedder:
    """Base class for embedder modules."""
    def __init__(self, model_name: str=None):
        """Initialize the base embedder."""
        self.model_name = model_name

    def list_available_models(self) -> list[str]:
        """List available models."""
        raise NotImplementedError("Subclasses must implement the list_available_models method.")
        
    def get_vectorsize(self):
        """Get the size of the embedding vectors."""
        raise NotImplementedError("Subclasses must implement the get_vectorsize method.")
    
    def get_model_name(self) -> str:
        """Get the name of the model."""
        return self.model_name

    def embed(self, text:str) -> list[float]: 
        """Embed the given text."""
        raise NotImplementedError("Subclasses must implement the embed method.")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        raise NotImplementedError("Subclasses must implement the embed_batch method.")
