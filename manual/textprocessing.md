# Text Processing Module

## Overview

The Text Processing Module provides functionality for processing and analyzing text in the Local Knowledge system. It includes capabilities for chunking text, extracting keywords, and preparing text for embedding and search.

## Core Components

### Chunking

The chunking functionality is implemented in `localknowledge.textprocessing.chunking`:

- Splitting text into manageable chunks for processing
- Multiple chunking strategies (fixed size, sentence-based, markdown-based)
- Metadata preservation during chunking

### Keywords Extraction

The keywords extraction functionality is implemented in `localknowledge.textprocessing.keywords`:

- Extracting important keywords and phrases from text
- Multiple extraction strategies (PyTextRank, statistical methods)
- Normalization of keywords for consistency

## Chunking Strategies

### Fixed Size Chunker

Splits text into chunks of a fixed size:

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker

text = "This is a long text that needs to be split into chunks for processing..."
chunks = fixed_size_chunker(text, chunk_size=500, overlap=50)

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {chunk[:50]}...")
```

### Sentence Chunker

Splits text along sentence boundaries:

```python
from localknowledge.textprocessing.chunking import sentence_chunker

text = "This is the first sentence. This is the second sentence. This is the third sentence."
chunks = sentence_chunker(text, max_chunk_size=100)

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {chunk}")
```

### Markdown Chunker

Splits markdown text along headings:

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
    print(f"Chunk {i+1} (Level {chunk['level']}): {chunk['text'][:50]}...")
```

## Keyword Extraction

### PyTextRank Extractor

Extracts keywords using the PyTextRank algorithm:

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor

text = "Traumatic brain injury (TBI) is a leading cause of death and disability worldwide."
keywords = pytextrank_extractor(text, top_n=5)

print("Keywords:")
for keyword in keywords:
    print(f"- {keyword}")
```

### Statistical Extractor

Extracts keywords using statistical methods:

```python
from localknowledge.textprocessing.keywords import statistical_extractor

text = "Traumatic brain injury (TBI) is a leading cause of death and disability worldwide."
keywords = statistical_extractor(text, top_n=5)

print("Keywords:")
for keyword in keywords:
    print(f"- {keyword}")
```

## Usage Examples

### Processing a Document

```python
from localknowledge.textprocessing.chunking import markdown_chunker
from localknowledge.textprocessing.keywords import pytextrank_extractor

# Load a markdown document
with open("document.md", "r") as f:
    text = f.read()

# Split into chunks
chunks = markdown_chunker(text)

# Process each chunk
for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1} (Level {chunk['level']}): {chunk['heading']}")
    
    # Extract keywords from the chunk
    keywords = pytextrank_extractor(chunk['text'], top_n=5)
    print("Keywords:", ", ".join(keywords))
    
    # Additional processing...
    print()
```

### Preparing Text for Embedding

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker
from localknowledge.ai.embeddings import create_embedding

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Split into chunks
chunks = fixed_size_chunker(text, chunk_size=1000, overlap=100)

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

## Configuration

### Chunking Configuration

Chunking parameters can be configured:

- `chunk_size`: Maximum size of each chunk (in characters)
- `overlap`: Overlap between consecutive chunks (in characters)
- `min_chunk_size`: Minimum size of a chunk (to avoid tiny chunks)

Example:

```python
from localknowledge.textprocessing.chunking import fixed_size_chunker

# Configure chunking parameters
CHUNK_SIZE = 1000
OVERLAP = 100
MIN_CHUNK_SIZE = 100

# Create chunks
chunks = fixed_size_chunker(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=OVERLAP,
    min_chunk_size=MIN_CHUNK_SIZE
)
```

### Keywords Configuration

Keyword extraction parameters can be configured:

- `top_n`: Number of keywords to extract
- `normalize`: Whether to normalize keywords (lowercase, remove duplicates)
- `min_length`: Minimum length of keywords (in characters)

Example:

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor

# Configure keyword extraction parameters
TOP_N = 10
NORMALIZE = True
MIN_LENGTH = 3

# Extract keywords
keywords = pytextrank_extractor(
    text,
    top_n=TOP_N,
    normalize=NORMALIZE,
    min_length=MIN_LENGTH
)
```

## Performance Considerations

### Chunking Performance

For optimal chunking performance:

- Use the appropriate chunker for the text type (markdown, plain text)
- Adjust chunk size based on the downstream task (embedding, QA generation)
- Process chunks in parallel for large documents

### Keywords Performance

For optimal keyword extraction performance:

- Pre-process text to remove noise (HTML tags, special characters)
- Use caching for frequently processed texts
- Consider batch processing for multiple documents

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

### Adding a New Keyword Extractor

To add a new keyword extraction method:

1. Create a new function in `localknowledge.textprocessing.keywords`:
   ```python
   def new_extractor(text, **kwargs):
       """
       New keyword extraction method.
       
       Args:
           text: Text to extract keywords from
           **kwargs: Additional parameters
           
       Returns:
           List of keywords
       """
       # Implementation
       keywords = []
       # ...
       return keywords
   ```

2. Add tests in `localknowledge.textprocessing.tests.test_keywords`

3. Update documentation

## Troubleshooting

### Common Issues

1. **Chunking Issues**:
   - Chunks too small or too large: Adjust chunk size parameters
   - Chunks breaking in the middle of sentences: Use sentence-aware chunkers
   - Metadata loss during chunking: Use chunkers that preserve metadata

2. **Keyword Extraction Issues**:
   - Poor quality keywords: Try different extraction methods
   - Duplicate keywords with different capitalization: Enable normalization
   - Missing domain-specific terms: Consider using a domain-specific vocabulary

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.textprocessing').setLevel(logging.DEBUG)
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
   python -m localknowledge.textprocessing.keywords.example example.md
   ```
