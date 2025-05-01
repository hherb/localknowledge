"""Helper class to list available models using the Ollama API."""
import ollama
from dataclasses import dataclass

@dataclass
class ModelInfo:
    model: str
    family: str
    size: int
    quantization: str
    context_length: int
    embedding_length: int
    is_free: bool = True
    is_locally_available: bool = True



def list_models(family=None):
    """List available models using the Ollama API."""
    try:
        models = ollama.list()['models']
        if not family:
            models = [model_info(model['model']) for model in models]
        else:
            models = [model_info(model['model']) for model in models if model['model'].lower().startswith(family.lower())]
        return models
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return []

def sizestr2int(sizestr : str) -> int:
    """Convert a size string to an integer."""
    if sizestr.endswith('B'):  #Billion parameters
        return int(float(sizestr[:-1]) * 1000000000)
    elif sizestr.endswith('K'):  #Thousand parameters
        return int(float(sizestr[:-1]) * 1000000)
    elif sizestr.endswith('M'):  #Million parameters
        return int(float(sizestr[:-1]) * 1000000000)

def model_info(model_name : str) -> ModelInfo:
    """Get information about a specific model."""
    try:
        shown = ollama.show(model_name)
        details = shown.details
        # ModelDetails(parent_model='', format='gguf', family='gemma3',
        # families=['gemma3'], parameter_size='4.3B', quantization_level='Q4_K_M')

        modelinfo = shown.modelinfo
        #ollama.show('phi4:latest').modelinfo
        #{'general.architecture': 'phi3', 'general.basename': 'phi', 'general.file_type': 15,
        # 'general.languages': ['en'], 'general.license': 'mit',
        # 'general.parameter_count': 14659507200,
        # 'general.quantization_version': 2,
        # 'general.size_label': '15B',
        # 'general.tags': ['phi', 'nlp', 'math', 'code', 'chat', 'conversational', 'text-generation'],
        # 'general.type': 'model',
        # 'general.version': '4',
        # 'phi3.context_length': 16384,
        # 'phi3.embedding_length': 5120,

        try:
            size=modelinfo.get('general.parameter_count', sizestr2int(details.parameter_size) )
        except Exception as e:
            try:
                size=int(modelinfo.get(f'{details.family}.parameter_count', 0))
            except Exception:
                size=0

        try:
            context_length=modelinfo.get('general.context_length', details.context_length)
        except Exception:
            try:
                context_length=modelinfo.get(f'{details.family}.context_length', 0)
            except Exception:
                context_length=0

        try:
            embedding_length=modelinfo.get('general.embedding_length', details.embedding_length)
        except Exception:
            try:
                embedding_length=modelinfo.get(f'{details.family}.embedding_length', 0)
            except Exception:
                embedding_length=0


        info=ModelInfo(
            model=model_name,
            family=details.family,
            size=size,
            quantization=details.quantization_level,
            context_length=context_length,
            embedding_length=embedding_length,
            is_free=True,
            is_locally_available=True
        )
        return info
    except Exception as e:
        print(f"Error getting model info: {str(e)}")
        return None

def model_capabilities(model_name : str) -> list[str]:
    """Get capabilities of a specific model."""
    try:
        # In the future, this could query the model for its capabilities
        # For now, just return an empty list
        return []
    except Exception as e:
        print(f"Error getting capabilities for {model_name}: {str(e)}")
        return []


if __name__=="__main__":
    print(list_models("gemma"))
    print()
    print('-'*80)
    models = list_models()
    #print(models)
    for model in models:
        # model is already a ModelInfo object, so just print it directly
        print(model)
        print('-'*80)
        print()

