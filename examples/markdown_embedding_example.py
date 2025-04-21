#!/usr/bin/env python3
"""
Example usage of the markdown chunker with the embedding manager.

This script demonstrates how to use the markdown chunker to split markdown text
into chunks based on headings and then create embeddings for those chunks.
"""

import os
import sys
import logging
from pprint import pprint

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.textprocessing.chunking import MarkdownChunker
from localknowledge.embeddings import EmbeddingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example markdown text
EXAMPLE_MARKDOWN = """
# Introduction to Vector Embeddings

Vector embeddings are a way to represent text as numerical vectors in a high-dimensional space.
These vectors capture semantic meaning, allowing us to measure similarity between texts.

## How Embeddings Work

Embeddings work by mapping words or phrases to vectors in a continuous vector space.
Similar words or phrases are mapped to nearby points in this space.

### Training Embedding Models

Embedding models are typically trained on large corpora of text using techniques like:

1. Word2Vec
2. GloVe
3. BERT
4. Transformer models

## Applications of Embeddings

Embeddings have many applications in natural language processing:

### Semantic Search

Embeddings enable semantic search, where documents are retrieved based on meaning rather than keyword matching.

### Document Classification

Embeddings can be used to classify documents by comparing their vectors to known categories.

### Recommendation Systems

Content-based recommendation systems often use embeddings to find similar items.

# Advanced Topics

## Fine-tuning Embeddings

Pre-trained embeddings can be fine-tuned for specific domains or tasks.

## Multilingual Embeddings

Some embedding models support multiple languages, allowing cross-lingual applications.

## Challenges and Limitations

Embeddings have some limitations:

1. They may encode biases present in the training data
2. They may not capture context-dependent meanings well
3. They require significant computational resources for training
"""

def demonstrate_markdown_chunking():
    """Demonstrate markdown chunking."""
    # Create a markdown chunker
    chunker = MarkdownChunker(max_level=2, min_chunk_size=50, max_chunk_size=1000)

    # Chunk the markdown text
    chunks = chunker.chunk(EXAMPLE_MARKDOWN)

    # Print the chunks
    print(f"Found {len(chunks)} chunks in the markdown text:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Heading: {chunk.metadata.get('heading_title')}")
        print(f"  Level: {chunk.metadata.get('heading_level')}")
        print(f"  Type: {chunk.metadata.get('chunk_type')}")
        print(f"  Text length: {len(chunk.text)} characters")
        print(f"  Text preview: {chunk.text[:100]}...")

    return chunks

def create_embeddings_for_chunks(chunks):
    """Create embeddings for the chunks."""
    # Create an embedding manager
    embedding_manager = EmbeddingManager()

    # Create embeddings for each chunk
    print("\nCreating embeddings for chunks:")
    for i, chunk in enumerate(chunks):
        print(f"  Processing chunk {i+1}...")

        # Create embedding
        embedding = embedding_manager.create_embedding(chunk.text)

        # Print embedding info
        print(f"    Created embedding with {len(embedding)} dimensions")

    # Close the embedding manager
    embedding_manager.close()

def process_markdown_document():
    """Process a markdown document using the embedding manager."""
    # Create an embedding manager with a markdown chunker
    embedding_manager = EmbeddingManager(chunker=MarkdownChunker(max_level=2))

    # Process the document
    print("\nProcessing markdown document:")
    chunks = embedding_manager.process_document(
        source_id='example',
        document_id='markdown-example',
        text=EXAMPLE_MARKDOWN,
        is_markdown=True  # This will use MarkdownChunker if no chunker is provided
    )

    print(f"Processed {chunks} chunks from the markdown document")

    # Search for similar chunks
    print("\nSearching for similar chunks:")
    results = embedding_manager.search("semantic search applications", limit=3)

    print(f"Found {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\nResult {i+1} (similarity: {result['similarity']:.4f}):")
        print(f"Text: {result['text'][:200]}...")

    # Close the embedding manager
    embedding_manager.close()

def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Markdown chunking and embedding example')
    parser.add_argument('--action', choices=['chunk', 'embed', 'process'], default='process',
                      help='Action to perform (default: process)')

    args = parser.parse_args()

    if args.action == 'chunk':
        demonstrate_markdown_chunking()
    elif args.action == 'embed':
        chunks = demonstrate_markdown_chunking()
        create_embeddings_for_chunks(chunks)
    elif args.action == 'process':
        process_markdown_document()

if __name__ == '__main__':
    main()
