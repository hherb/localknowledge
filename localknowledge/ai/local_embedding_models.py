import pathlib
import logging
import ollama
from sentence_transformers import SentenceTransformer, models



def get_pubmedbert_model():
    hf_modelname = 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext'
    savedmodelname = 'BiomedNLP-PubMedBERT-sentence-transformer'
     #create an absolute path at ~/.rwb/models/
    path = pathlib.Path.home() / '.rwb' / 'models' / savedmodelname
    if not path.exists():
        logging.info(f"Creating PubMedBERT model at {path}")
    
        # Create the directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Create the model components
            word_embedding_model = models.Transformer(hf_modelname)
            pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension())

            # Combine them into a SentenceTransformer model
            model = SentenceTransformer(modules=[word_embedding_model, pooling_model])
        
            # Save the model - convert Path to string
            model.save(str(path))
        except Exception as e:
            logging.error(f"Error creating PubMedBERT model: {e}")
            raise

    # Now you can load it without warnings
    model = SentenceTransformer(str(path))
    return model

def get_ollama_embedding_model(model_name: str = "snowflake-arctic-embed2:latest"):
    try:
        import ollama
        ollama.pull(model_name)
        return model_name
    except Exception as e:
        logging.error(f"Error loading Ollama model {model_name}: {e}")
        return None

if __name__ == "__main__":
    model= get_pubmedbert_model()
    text="this is a test"
    embedding = model.encode(text, show_progress_bar=True).tolist()
    print(embedding[:10])
    print(f"Vector size of pubmedbert: {len(embedding)}")
    model_name = get_ollama_embedding_model()
    if model_name:
        print(model_name)
        embedding = ollama.embed(model_name, text)
        print(embedding.embeddings[0][:10])
        print(f"Vector size of ollama: {len(embedding.embeddings[0])}")
    