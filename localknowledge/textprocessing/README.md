# Text Processing Module

This module provides various text processing utilities for analyzing, transforming, and extracting information from text data.

## Submodules

### Keywords

The `keywords` submodule provides various strategies for extracting keywords from text for search, indexing, or analysis purposes.

See the [Keywords README](keywords/README.md) for more information.

### Chunking

The `chunking` submodule provides various strategies for chunking text into smaller, semantically meaningful pieces for processing, embedding, or analysis.

See the [Chunking README](chunking/README.md) for more information.

## Usage

```python
# Import the modules
from localknowledge.textprocessing import keywords, chunking

# Use a keyword extractor
extractor = keywords.PyTextRankExtractor()
keywords_list = extractor.extract_keywords("Your text here", max_keywords=10)

# Use a text chunker
chunker = chunking.TextChunker(chunk_size=1000, overlap=200)
chunks = chunker.chunk("This is a long text that needs to be chunked...")
```
