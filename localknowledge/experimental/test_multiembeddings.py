# Initialize managers with different models
from localknowledge.embeddings.multiembeddings import EmbeddingManager

snowflake_manager = EmbeddingManager("snowflake-arctic-embed2:latest")
nomic_manager = EmbeddingManager("nomic-embed-text:latest")

# Store embeddings
text = "Sample medical research text..."
snowflake_manager.process_text("medrxiv", "doc1", text)
nomic_manager.process_text("medrxiv", "doc1", text)

# Compare search results
query = "treatment effectiveness"
results = snowflake_manager.compare_models(
    query,
    [
        "snowflake-arctic-embed2:latest",
        "nomic-embed-text:latest",
        "granite-embedding:278m",
        "mxbai-embed-large:latest",
        "jina/jina-embeddings-v2-base-en:latest",
        "bge-m3:latest",
    ]
)

# Print comparison
for model, data in results.items():
    print(f"\nModel: {model}")
    print(f"Total embeddings: {data['stats']['total_embeddings']}")
    print(f"Vector dimension: {data['stats']['vector_dim']}")
    print("\nTop results:")
    for r in data['results']:
        print(f"Similarity: {r['similarity']:.3f} - {r['text'][:100]}...")