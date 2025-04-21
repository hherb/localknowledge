import sys
import ollama

def get_embeddings(model_name: str, filename: str):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    try:
        response = ollama.embeddings(model=model_name, prompt=text)
        print("Embedding vector:")
        print(response['embedding'])
    except Exception as e:
        print(f"Error generating embedding: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python embed_file.py <model_name> <filename>")
    else:
        model_name = sys.argv[1]
        filename = sys.argv[2]
        get_embeddings(model_name, filename)
