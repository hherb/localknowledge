#!/usr/bin/env python3
import ollama
import time

def test_embedding():
    text = "This is a test sentence for embedding."
    
    start_time = time.time()
    response = ollama.embeddings(model="snowflake-arctic-embed2:latest", prompt=text)
    end_time = time.time()
    
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    print(f"Embedding length: {len(response['embedding'])}")
    print(f"First few values: {response['embedding'][:5]}")

if __name__ == "__main__":
    test_embedding()
