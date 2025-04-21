# Chunking Module

## Overview

The Chunking Module provides functionality for splitting text into manageable chunks for processing. This is essential for working with large documents, as many AI models have input size limitations. The module supports various chunking strategies optimized for different types of text.

## Core Components

The chunking functionality is implemented in `localknowledge.textprocessing.chunking`:

- `fixed_size_chunker`: Splits text into chunks of a fixed size
- `sentence_chunker`: Splits text along sentence boundaries
- `markdown_chunker`: Splits markdown text along headings
- `markdown_chunker_basic`: A simpler version of the markdown chunker

## Chunking Strategies

### Fixed Size Chunker

The fixed size chunker splits text into chunks of a specified size, with optional overlap between chunks:

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker

text = "This is a long text that needs to be split into chunks for processing..."
chunks = fixed_size_chunker(text, chunk_size=500, overlap=50)

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {chunk[:50]}...")
```

Parameters:
- `text`: The text to chunk
- `chunk_size`: Maximum size of each chunk (in characters)
- `overlap`: Overlap between consecutive chunks (in characters)
- `min_chunk_size`: Minimum size of a chunk (to avoid tiny chunks)

### Sentence Chunker

The sentence chunker splits text along sentence boundaries, ensuring that sentences are not broken across chunks:

```python
from localknowledge.textprocessing.chunking import sentence_chunker

text = "This is the first sentence. This is the second sentence. This is the third sentence."
chunks = sentence_chunker(text, max_chunk_size=100)

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {chunk}")
```

Parameters:
- `text`: The text to chunk
- `max_chunk_size`: Maximum size of each chunk (in characters)
- `overlap`: Overlap between consecutive chunks (in characters)
- `min_chunk_size`: Minimum size of a chunk (to avoid tiny chunks)

### Markdown Chunker

The markdown chunker splits markdown text along headings, preserving the document structure:

```python
from localknowledge.textprocessing.chunking import markdown_chunker

markdown_text = """
# Introduction

This is the introduction section.

## Background

This is the background section.

# Methods

This is the methods section.
"""

chunks = markdown_chunker(markdown_text)

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1} (Level {chunk['level']}): {chunk['heading']}")
    print(f"Text: {chunk['text'][:50]}...")
```

Parameters:
- `text`: The markdown text to chunk
- `max_chunk_size`: Maximum size of each chunk (in characters)
- `min_chunk_size`: Minimum size of a chunk (to avoid tiny chunks)

The markdown chunker returns chunks with the following structure:
- `text`: The chunk text
- `heading`: The heading text
- `level`: The heading level (1 for #, 2 for ##, etc.)
- `metadata`: Additional metadata (if provided)

## Usage Examples

### Basic Usage

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Split into chunks
chunks = fixed_size_chunker(text, chunk_size=1000, overlap=100)

# Process each chunk
for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}/{len(chunks)}: {len(chunk)} characters")
    # Process the chunk...
```

### Chunking with Metadata

```python
from localknowledge.textprocessing.chunking import markdown_chunker

# Load a markdown document
with open("document.md", "r") as f:
    text = f.read()

# Metadata for the document
metadata = {
    "source": "example.md",
    "author": "John Doe",
    "date": "2023-01-01"
}

# Split into chunks with metadata
chunks = markdown_chunker(text, metadata=metadata)

# Process each chunk
for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}/{len(chunks)}: {chunk['heading']}")
    print(f"Metadata: {chunk['metadata']}")
    # Process the chunk...
```

### Chunking for Embedding

```python
from localknowledge.textprocessing.chunking import sentence_chunker
from localknowledge.ai.embeddings import create_embedding

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Split into chunks
chunks = sentence_chunker(text, max_chunk_size=1000)

# Create embeddings for each chunk
embeddings = []
for i, chunk in enumerate(chunks):
    embedding = create_embedding(chunk)
    embeddings.append({
        'chunk_no': i,
        'text': chunk,
        'embedding': embedding
    })

print(f"Created {len(embeddings)} embeddings")
```

## Advanced Usage

### Custom Chunking Strategy

You can create a custom chunking strategy by implementing a function that takes text and parameters and returns a list of chunks:

```python
def custom_chunker(text, **kwargs):
    """
    Custom chunking strategy.
    
    Args:
        text: Text to chunk
        **kwargs: Additional parameters
        
    Returns:
        List of chunks
    """
    # Implementation
    chunks = []
    # ...
    return chunks

# Use the custom chunker
chunks = custom_chunker(text, custom_param=42)
```

### Chunking with Page Numbers

For PDF documents, you can include page numbers in the metadata:

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker

# Text extracted from a PDF with page numbers
pages = [
    {"text": "Page 1 content...", "page_no": 1},
    {"text": "Page 2 content...", "page_no": 2},
    # ...
]

# Combine the text
text = "\n".join(page["text"] for page in pages)

# Create a mapping of character positions to page numbers
page_map = {}
pos = 0
for page in pages:
    page_text = page["text"]
    for i in range(len(page_text)):
        page_map[pos + i] = page["page_no"]
    pos += len(page_text) + 1  # +1 for the newline

# Split into chunks
chunks = fixed_size_chunker(text, chunk_size=1000, overlap=100)

# Add page numbers to chunks
chunk_with_pages = []
for i, chunk in enumerate(chunks):
    # Find the start position of the chunk in the original text
    start_pos = text.find(chunk)
    if start_pos != -1:
        # Get the page number for the start of the chunk
        page_no = page_map.get(start_pos, None)
        chunk_with_pages.append({
            'text': chunk,
            'page_no': page_no,
            'chunk_no': i
        })

# Process chunks with page numbers
for chunk in chunk_with_pages:
    print(f"Chunk {chunk['chunk_no']} (Page {chunk['page_no']}): {chunk['text'][:50]}...")
```

## Performance Considerations

### Chunking Performance

For optimal chunking performance:

- Use the appropriate chunker for the text type (markdown, plain text)
- Adjust chunk size based on the downstream task (embedding, QA generation)
- Process chunks in parallel for large documents

### Memory Usage

For large documents, consider:

- Processing the document in streaming mode to avoid loading the entire text into memory
- Using generators instead of lists for chunk processing
- Implementing a chunking pipeline that processes chunks as they are generated

## Implementation Details

### Fixed Size Chunker

The fixed size chunker works by:

1. Initializing an empty list of chunks
2. Setting the start position to 0
3. While the start position is less than the text length:
   a. Setting the end position to start + chunk_size
   b. If end is beyond the text length, setting end to the text length
   c. If end is not at the text length, trying to find a natural break (space, newline)
   d. Adding the text from start to end to the chunks list
   e. Setting start to end - overlap
4. Returning the list of chunks

### Sentence Chunker

The sentence chunker works by:

1. Splitting the text into sentences using a sentence tokenizer
2. Initializing an empty list of chunks and a current chunk
3. For each sentence:
   a. If adding the sentence to the current chunk would exceed max_chunk_size:
      i. Adding the current chunk to the chunks list
      ii. Starting a new chunk with the sentence
   b. Otherwise, adding the sentence to the current chunk
4. Adding the final chunk to the chunks list
5. Returning the list of chunks

### Markdown Chunker

The markdown chunker works by:

1. Parsing the markdown text to identify headings and their levels
2. Splitting the text at each heading
3. For each section:
   a. Creating a chunk with the section text, heading, and level
   b. If the section is too large, further splitting it using a fixed size chunker
4. Returning the list of chunks

## Maintenance

### Adding a New Chunker

To add a new chunking strategy:

1. Create a new function in `localknowledge.textprocessing.chunking`:
   ```python
   def new_chunker(text, **kwargs):
       """
       New chunking strategy.
       
       Args:
           text: Text to chunk
           **kwargs: Additional parameters
           
       Returns:
           List of chunks
       """
       # Implementation
       chunks = []
       # ...
       return chunks
   ```

2. Add tests in `localknowledge.textprocessing.tests.test_chunking`

3. Update documentation

### Improving Existing Chunkers

To improve an existing chunker:

1. Identify the issue or enhancement
2. Implement the change in the chunker function
3. Add tests for the new behavior
4. Update documentation

## Troubleshooting

### Common Issues

1. **Chunks Breaking in the Middle of Sentences**: Use the sentence chunker or adjust the fixed size chunker to find natural breaks.

2. **Chunks Too Small or Too Large**: Adjust the chunk size parameters.

3. **Metadata Loss During Chunking**: Use chunkers that preserve metadata or add metadata to chunks after chunking.

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.textprocessing.chunking').setLevel(logging.DEBUG)
   ```

2. Inspect intermediate results:
   ```python
   from localknowledge.textprocessing.chunking import markdown_chunker
   
   chunks = markdown_chunker(text, debug=True)
   for chunk in chunks:
       print(f"Heading: {chunk.get('heading')}")
       print(f"Level: {chunk.get('level')}")
       print(f"Text length: {len(chunk.get('text'))}")
       print(f"First 50 chars: {chunk.get('text')[:50]}...")
       print()
   ```

3. Use the example scripts in the module directory:
   ```bash
   python -m localknowledge.textprocessing.chunking.example example.md
   ```
