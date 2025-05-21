import argparse
from sentence_transformers import SentenceTransformer

class SentenceTransformerHelper:
    def __init__(self, model_name="microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"):
        self.model_name = model_name
        self.model = SentenceTransformer(self.model_name)
        self.tokenizer = self.model.tokenizer
        self.max_seq_length = self.model.max_seq_length

    def max_sequence_length(self):
        return self.max_seq_length

    def count_tokens(self, text):
        encoded = self.tokenizer.encode(text, add_special_tokens=True)
        #tokens = self.tokenizer.convert_ids_to_tokens(encoded)
        return {
            'token_count': len(encoded),
            #'tokens': tokens,
            'character_count': len(text),
            'model_max_length': self.max_seq_length,
            'will_be_truncated': len(encoded) > self.max_seq_length
        }   
    
    def truncate_text(self, text):
        encoded = self.tokenizer.encode(text, add_special_tokens=True)
        decoded = text
        if len(encoded) > self.max_seq_length:
            encoded = encoded[:self.max_seq_length]
            decoded = self.tokenizer.decode(encoded)
        return encoded, decoded

def check_max_sequence_length(model_name):
    """
    Check the maximum sequence length (context window size) of a sentence transformer model.

    Args:
        model_name (str): Name or path of the sentence transformer model

    Returns:
        int: The maximum sequence length of the model
    """
    # Load the model
    model = SentenceTransformer(model_name)

    # Access the max_seq_length from the first transformer in the model
    if hasattr(model, 'auto_model'):
        # For newer versions of sentence_transformers
        max_length = model.max_seq_length
        print(f"Model max_seq_length: {max_length}")
        return max_length

    # For older versions or different model structures
    if hasattr(model[0], 'max_seq_length'):
        max_length = model[0].max_seq_length
        print(f"Model max_seq_length: {max_length}")
        return max_length

    # If the above methods fail, try to get the config
    if hasattr(model[0], 'auto_model') and hasattr(model[0].auto_model, 'config'):
        if hasattr(model[0].auto_model.config, 'max_position_embeddings'):
            max_length = model[0].auto_model.config.max_position_embeddings
            print(f"Model max_position_embeddings: {max_length}")
            return max_length

    print("Could not determine max sequence length")
    return None


def count_tokens_for_model(text, model_name="microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"):
    """
    Calculate the number of tokens in a text for a specific SentenceTransformers model.
    
    Args:
        model_name (str): Name or path of the sentence transformer model
        text (str): The text to tokenize and count
        
    Returns:
        dict: A dictionary containing token count and other tokenization info
    """
    # Load the model
    model = SentenceTransformer(model_name)
    
    # Access the tokenizer from the transformer component (usually the first component)
    if hasattr(model[0], 'tokenizer'):
        tokenizer = model[0].tokenizer
        
        # Tokenize the text
        encoded = tokenizer.encode(text, add_special_tokens=True)
        tokens = tokenizer.convert_ids_to_tokens(encoded)
        
        # Get the model's max sequence length
        max_seq_length = model[0].max_seq_length if hasattr(model[0], 'max_seq_length') else None
        
        # Prepare results
        result = {
            'token_count': len(encoded),
            'tokens': tokens,
            'character_count': len(text),
            'model_max_length': max_seq_length,
            'will_be_truncated': max_seq_length is not None and len(encoded) > max_seq_length
        }
        
        # Add warning if tokens will be truncated
        if result['will_be_truncated']:
            result['truncation_info'] = f"Text exceeds the model's maximum sequence length of {max_seq_length} tokens. It will be truncated."
        
        return result
    else:
        raise ValueError("Could not access tokenizer from the model")

def main():
    """
    Main function to parse command line arguments and check model's max sequence length.
    """
    parser = argparse.ArgumentParser(description='Check the maximum sequence length of a sentence transformer model')
    parser.add_argument('--model', type=str,
                        default="microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
                        help='Name or path of the sentence transformer model')

    args = parser.parse_args()

    print(f"Checking model: {args.model}")
    check_max_sequence_length(args.model)

# Examples of usage
if __name__ == "__main__":
    main()
