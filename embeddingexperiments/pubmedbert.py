import torch
import warnings
import logging
from sentence_transformers import SentenceTransformer, models

# Suppress the specific warning about creating a new model with mean pooling
warnings.filterwarnings("ignore", message="No sentence-transformers model found with name.*Creating a new one with mean pooling.")

# Also suppress the warning at the logger level
logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(logging.ERROR)

MODELS = ["microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
        "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",

]
MODEL = MODELS[0]

# Automatically detect device
DEVICE = 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')    

def setup_model():
    # Create the model with explicit configuration
    word_embedding_model = models.Transformer('microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext')
    pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension(), pooling_mode='mean')
    model = SentenceTransformer(modules=[word_embedding_model, pooling_model], device=DEVICE)

class PubMedBERT:
    def __init__(self, modelname=MODEL, timeout=60):
        """
        Initialize the PubMedBERT model.

        Args:
            modelname: Name of the model to use
            timeout: Timeout in seconds for model operations
        """
        self.modelname = modelname
        self.timeout = timeout

        # Use a timeout to prevent hanging during model initialization
        import threading
        import time

        def load_model():
            self.model = SentenceTransformer(self.modelname, device=DEVICE)

        # Start model loading in a separate thread
        thread = threading.Thread(target=load_model)
        thread.daemon = True  # Allow the thread to be killed when the program exits

        logging.info(f"Loading model {modelname} with timeout {timeout}s...")
        thread.start()

        # Wait for the thread to complete with timeout
        start_time = time.time()
        while thread.is_alive():
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Model initialization timed out after {timeout} seconds")
            time.sleep(0.1)

        logging.info(f"Model loaded successfully in {time.time() - start_time:.2f}s")

    def get_dimension(self) -> int:
        """Get the dimension of the model's embeddings."""
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text:str) -> list:
        """Embed a single text string."""
        try:
            return self.model.encode(text, show_progress_bar=False).tolist()
        except Exception as e:
            logging.error(f"Error embedding text: {e}")
            # Return a zero vector of the correct dimension as fallback
            return [0.0] * self.get_dimension()

    def embed_batch(self, texts:list) -> list[list]:
        """
        Embed a batch of texts with timeout protection.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        import threading
        import time
        import queue

        result_queue = queue.Queue()
        error_queue = queue.Queue()

        def embed_worker():
            try:
                # Use batch_size to avoid memory issues with very large batches
                batch_size = 32
                results = []

                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
                    batch_embeddings = self.model.encode(
                        batch,
                        show_progress_bar=False,
                        convert_to_numpy=True
                    ).tolist()
                    results.extend(batch_embeddings)

                result_queue.put(results)
            except Exception as e:
                error_queue.put(str(e))

        # Start embedding in a separate thread
        thread = threading.Thread(target=embed_worker)
        thread.daemon = True
        thread.start()

        # Wait for the thread to complete with timeout
        start_time = time.time()
        while thread.is_alive():
            if time.time() - start_time > self.timeout:
                # If timeout occurs, return zero vectors
                logging.error(f"Embedding timed out after {self.timeout} seconds")
                return [[0.0] * self.get_dimension() for _ in texts]
            time.sleep(0.1)

        # Check for errors
        if not error_queue.empty():
            error = error_queue.get()
            logging.error(f"Error in embedding: {error}")
            return [[0.0] * self.get_dimension() for _ in texts]

        # Get the result
        if not result_queue.empty():
            return result_queue.get()
        else:
            logging.error("No results returned from embedding thread")
            return [[0.0] * self.get_dimension() for _ in texts]

    def get_modelname(self) -> str:
        """Get the name of the model."""
        return self.modelname

    def cleanup(self):
        """
        Clean up resources used by the model.
        This helps prevent semaphore leaks when using multiprocessing.
        """
        logging.info("Cleaning up PubMedBERT model resources...")

        # Delete the model to free up resources
        if hasattr(self, 'model'):
            try:
                del self.model
                logging.info("Model deleted successfully")
            except Exception as e:
                logging.error(f"Error deleting model: {e}")

        # Force garbage collection
        try:
            import gc
            gc.collect()
            logging.info("Garbage collection completed")
        except Exception as e:
            logging.error(f"Error during garbage collection: {e}")

        # Clear CUDA cache if available
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logging.info("CUDA cache cleared")
        except Exception as e:
            logging.info(f"Error clearing CUDA cache: {e}")

        logging.info("Cleanup completed")


if __name__ == "__main__":
    batch = ["This is a test", "This is another test", "This is yet another test"]
    pubmedbert = PubMedBERT(modelname=MODEL[1])
    print(pubmedbert.get_dimension())
    print(pubmedbert.embed("This is a test")[:10])
    embeddings = pubmedbert.embed_batch(batch)
    print(embeddings[0][:10])
    print(embeddings[1][:10])
    print(embeddings[2][:10])


