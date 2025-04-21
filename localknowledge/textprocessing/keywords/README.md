# Keyword Extraction Module

This module provides various strategies for extracting keywords from text for search, indexing, or analysis purposes.

## Available Keyword Extractors

### PyTextRankExtractor

A keyword extractor that uses the PyTextRank library, which implements the TextRank algorithm for extracting keywords from text.

```python
from localknowledge.textprocessing.keywords import PyTextRankExtractor

# Initialize the extractor
extractor = PyTextRankExtractor(spacy_model="en_core_web_sm")

# Extract keywords from text
text = "This is a sample text about artificial intelligence and machine learning. AI systems can learn from data and make predictions."
keywords = extractor.extract_keywords(text, max_keywords=5)

print(f"Keywords: {keywords}")
```

#### Parameters

- `spacy_model`: Name of the spaCy model to use (default: "en_core_web_sm")
- `max_keywords`: Maximum number of keywords to extract (default: 10)
- `min_ngram`: Minimum n-gram size (default: 1)
- `max_ngram`: Maximum n-gram size (default: 3)
- `limit_phrases`: Limit number of phrases to consider (default: 20)

## Usage with Embedding Manager

The keyword extraction module can be used with the embedding manager to create embeddings with keywords:

```python
from localknowledge.textprocessing.keywords import PyTextRankExtractor
from localknowledge.embeddings import EmbeddingManager

# Create a keyword extractor
keyword_extractor = PyTextRankExtractor()

# Initialize the embedding manager
embedding_manager = EmbeddingManager(model_name="snowflake-arctic-embed2:latest")

# Process a document
text = "This is the full text of the document..."
chunks = embedding_manager.chunk_text(text)

for i, chunk in enumerate(chunks):
    # Extract keywords
    keywords = keyword_extractor.extract_keywords(chunk)
    
    # Create embedding
    embedding = embedding_manager.create_embedding(chunk)
    
    # Store in database
    embedding_manager.db.store_embedding(
        source_id='example',
        document_id='doc123',
        chunk_no=i,
        text=chunk,
        embedding=embedding,
        model_name=embedding_manager.model_name,
        keywords=keywords
    )
```

## Creating Custom Keyword Extractors

You can create custom keyword extractors by extending the `BaseKeywordExtractor` class:

```python
from localknowledge.textprocessing.keywords import BaseKeywordExtractor

class CustomKeywordExtractor(BaseKeywordExtractor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize your extractor
        
    def extract_keywords(self, text: str, max_keywords: int = 10, **kwargs) -> List[str]:
        # Implement your keyword extraction logic
        # ...
        return keywords
```
