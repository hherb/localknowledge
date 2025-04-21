# Text Chunking Module

This module provides various strategies for chunking text into smaller, semantically meaningful pieces for processing, embedding, or analysis.

## Available Chunkers

### TextChunker

A simple chunker that splits text based on character count, trying to break at sentence boundaries.

```python
from localknowledge.chunking import TextChunker

# Create metadata with contextual information
metadata = {
    'file_name': 'example.txt',
    'author': 'John Doe',
    'source': 'Example Source'
}

chunker = TextChunker(chunk_size=1000, overlap=200)
chunks = chunker.chunk("This is a long text that needs to be chunked...", metadata=metadata)

for chunk in chunks:
    print(f"Chunk {chunk.metadata['chunk_number']}: {chunk.text[:50]}...")
    print(f"File: {chunk.metadata['file_name']}, Author: {chunk.metadata['author']}")
    print(f"Start line: {chunk.metadata.get('start_line')}, End line: {chunk.metadata.get('end_line')}")
```

### MarkdownChunker

A chunker that splits markdown text based on headings and subheadings.

```python
from localknowledge.chunking import MarkdownChunker

# Create metadata with contextual information
metadata = {
    'file_name': 'example.md',
    'author': 'Jane Smith',
    'source': 'Documentation',
    'document_type': 'markdown'
}

chunker = MarkdownChunker(max_level=3, min_chunk_size=100, max_chunk_size=2000)
chunks = chunker.chunk("""
# Main Heading

Some introduction text.

## Section 1

Content for section 1.

### Subsection 1.1

Content for subsection 1.1.

## Section 2

Content for section 2.
""", metadata=metadata)

for chunk in chunks:
    print(f"Heading: {chunk.metadata.get('heading_title')}, Level: {chunk.metadata.get('heading_level')}")
    print(f"Text: {chunk.text[:50]}...")
    print(f"File: {chunk.metadata['file_name']}, Author: {chunk.metadata['author']}")
    print(f"Document Type: {chunk.metadata['document_type']}")
```

## Chunk Object

Each chunker returns a list of `Chunk` objects, which have the following properties:

- `text`: The text content of the chunk
- `metadata`: A dictionary of metadata about the chunk
- `chunk_id`: An optional identifier for the chunk

The metadata dictionary typically includes:

- `chunk_number`: The index of the chunk in the sequence
- `chunk_type`: The type of chunk (e.g., 'text', 'markdown')
- Additional chunker-specific metadata

## Creating Custom Chunkers

You can create custom chunkers by extending the `BaseChunker` class:

```python
from localknowledge.chunking import BaseChunker, Chunk

class MyCustomChunker(BaseChunker):
    def __init__(self, my_param=10, **kwargs):
        super().__init__(**kwargs)
        self.my_param = my_param

    def chunk(self, text, **kwargs):
        # Override parameters if provided
        my_param = kwargs.get('my_param', self.my_param)

        # Implement your chunking logic here
        chunks = []
        # ...

        return chunks
```

## Usage with Embedding Manager

The chunking module can be used with the embedding manager to create embeddings for chunks:

```python
from localknowledge.chunking import MarkdownChunker
from localknowledge.embeddings import EmbeddingManager

# Create a chunker
chunker = MarkdownChunker(max_level=3)

# Get chunks from a markdown document
markdown_text = "# Document Title\n\nContent...\n\n## Section\n\nMore content..."
chunks = chunker.chunk(markdown_text)

# Create embeddings for each chunk
embedding_manager = EmbeddingManager()

for i, chunk in enumerate(chunks):
    embedding = embedding_manager.create_embedding(chunk.text)

    # Store the embedding with metadata
    embedding_manager.db.store_embedding(
        source_id='document_source',
        document_id='document_id',
        chunk_no=i,
        text=chunk.text,
        embedding=embedding,
        model_name=embedding_manager.model_name,
        keywords=embedding_manager.extract_keywords(chunk.text),
        page_no=chunk.metadata.get('page_number')
    )

# Search for similar chunks
results = embedding_manager.search("Query text...")
```
