# Keywords Extraction Module

## Overview

The Keywords Extraction Module provides functionality for extracting important keywords and phrases from text. This is useful for indexing, searching, and summarizing documents. The module supports multiple extraction methods, including PyTextRank and statistical approaches.

## Core Components

The keywords extraction functionality is implemented in `localknowledge.textprocessing.keywords`:

- `pytextrank_extractor`: Extracts keywords using the PyTextRank algorithm
- `statistical_extractor`: Extracts keywords using statistical methods
- `normalize_keywords`: Normalizes keywords for consistency

## Extraction Methods

### PyTextRank Extractor

The PyTextRank extractor uses the PyTextRank algorithm, which is based on the TextRank algorithm, to extract keywords from text:

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor

text = "Traumatic brain injury (TBI) is a leading cause of death and disability worldwide."
keywords = pytextrank_extractor(text, top_n=5)

print("Keywords:")
for keyword in keywords:
    print(f"- {keyword}")
```

Parameters:
- `text`: The text to extract keywords from
- `top_n`: Number of keywords to extract
- `normalize`: Whether to normalize keywords (lowercase, remove duplicates)
- `min_length`: Minimum length of keywords (in characters)

### Statistical Extractor

The statistical extractor uses statistical methods like TF-IDF to extract keywords from text:

```python
from localknowledge.textprocessing.keywords import statistical_extractor

text = "Traumatic brain injury (TBI) is a leading cause of death and disability worldwide."
keywords = statistical_extractor(text, top_n=5)

print("Keywords:")
for keyword in keywords:
    print(f"- {keyword}")
```

Parameters:
- `text`: The text to extract keywords from
- `top_n`: Number of keywords to extract
- `normalize`: Whether to normalize keywords (lowercase, remove duplicates)
- `min_length`: Minimum length of keywords (in characters)

## Usage Examples

### Basic Usage

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Extract keywords
keywords = pytextrank_extractor(text, top_n=10)

# Print keywords
print("Keywords:")
for keyword in keywords:
    print(f"- {keyword}")
```

### Normalizing Keywords

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor, normalize_keywords

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Extract keywords without normalization
keywords = pytextrank_extractor(text, top_n=10, normalize=False)

# Normalize keywords
normalized_keywords = normalize_keywords(keywords)

# Print keywords
print("Original Keywords:")
for keyword in keywords:
    print(f"- {keyword}")

print("\nNormalized Keywords:")
for keyword in normalized_keywords:
    print(f"- {keyword}")
```

### Comparing Extraction Methods

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor, statistical_extractor

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Extract keywords using PyTextRank
ptr_keywords = pytextrank_extractor(text, top_n=10)

# Extract keywords using statistical methods
stat_keywords = statistical_extractor(text, top_n=10)

# Print keywords
print("PyTextRank Keywords:")
for keyword in ptr_keywords:
    print(f"- {keyword}")

print("\nStatistical Keywords:")
for keyword in stat_keywords:
    print(f"- {keyword}")

# Find common keywords
common_keywords = set(ptr_keywords) & set(stat_keywords)
print("\nCommon Keywords:")
for keyword in common_keywords:
    print(f"- {keyword}")
```

### Extracting Keywords from Multiple Documents

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor
import os

# Directory containing documents
docs_dir = "documents"

# Extract keywords from each document
all_keywords = {}
for filename in os.listdir(docs_dir):
    if filename.endswith(".txt"):
        filepath = os.path.join(docs_dir, filename)
        with open(filepath, "r") as f:
            text = f.read()
        
        # Extract keywords
        keywords = pytextrank_extractor(text, top_n=10)
        all_keywords[filename] = keywords

# Print keywords for each document
for filename, keywords in all_keywords.items():
    print(f"\nKeywords for {filename}:")
    for keyword in keywords:
        print(f"- {keyword}")

# Find common keywords across all documents
if all_keywords:
    common_keywords = set.intersection(*[set(kw) for kw in all_keywords.values()])
    print("\nCommon Keywords Across All Documents:")
    for keyword in common_keywords:
        print(f"- {keyword}")
```

## Advanced Usage

### Custom Keyword Extraction

You can create a custom keyword extraction method by implementing a function that takes text and parameters and returns a list of keywords:

```python
def custom_extractor(text, **kwargs):
    """
    Custom keyword extraction method.
    
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

# Use the custom extractor
keywords = custom_extractor(text, custom_param=42)
```

### Keyword Extraction with Domain-Specific Vocabulary

For domain-specific texts, you can enhance keyword extraction with a domain-specific vocabulary:

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor

# Load a document
with open("medical_document.txt", "r") as f:
    text = f.read()

# Load a domain-specific vocabulary
with open("medical_vocabulary.txt", "r") as f:
    vocabulary = [line.strip() for line in f]

# Extract keywords
keywords = pytextrank_extractor(text, top_n=10)

# Enhance with domain-specific vocabulary
enhanced_keywords = []
for keyword in keywords:
    enhanced_keywords.append(keyword)

# Add domain-specific terms that appear in the text
for term in vocabulary:
    if term.lower() in text.lower() and term not in enhanced_keywords:
        enhanced_keywords.append(term)

# Print enhanced keywords
print("Enhanced Keywords:")
for keyword in enhanced_keywords:
    print(f"- {keyword}")
```

## Performance Considerations

### Extraction Performance

For optimal keyword extraction performance:

- Pre-process text to remove noise (HTML tags, special characters)
- Use caching for frequently processed texts
- Consider batch processing for multiple documents

### Memory Usage

For large documents, consider:

- Processing the document in chunks
- Using generators instead of lists for keyword processing
- Implementing a keyword extraction pipeline that processes text as it is read

## Implementation Details

### PyTextRank Extractor

The PyTextRank extractor works by:

1. Parsing the text to identify noun phrases and other potential keywords
2. Building a graph of keyword co-occurrences
3. Running the TextRank algorithm on the graph to rank keywords
4. Selecting the top-ranked keywords

### Statistical Extractor

The statistical extractor works by:

1. Tokenizing the text into words and phrases
2. Calculating statistical measures like term frequency and inverse document frequency
3. Ranking terms based on these measures
4. Selecting the top-ranked terms

### Keyword Normalization

The keyword normalization process:

1. Converts keywords to lowercase
2. Removes duplicates (case-insensitive)
3. Removes keywords that are substrings of other keywords
4. Sorts keywords by length (longest first)

## Maintenance

### Adding a New Extractor

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

### Improving Existing Extractors

To improve an existing extractor:

1. Identify the issue or enhancement
2. Implement the change in the extractor function
3. Add tests for the new behavior
4. Update documentation

## Troubleshooting

### Common Issues

1. **Poor Quality Keywords**: Try different extraction methods or adjust parameters.

2. **Duplicate Keywords with Different Capitalization**: Enable normalization or use the `normalize_keywords` function.

3. **Missing Domain-Specific Terms**: Consider using a domain-specific vocabulary or a custom extractor.

### Debugging

For detailed debugging:

1. Enable verbose logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logging.getLogger('localknowledge.textprocessing.keywords').setLevel(logging.DEBUG)
   ```

2. Inspect intermediate results:
   ```python
   from localknowledge.textprocessing.keywords import pytextrank_extractor
   
   keywords = pytextrank_extractor(text, debug=True)
   for i, keyword in enumerate(keywords):
       print(f"{i+1}. {keyword}")
   ```

3. Use the example script in the module directory:
   ```bash
   python -m localknowledge.textprocessing.keywords.example example.md
   ```

## Command-Line Usage

The module provides a command-line interface for extracting keywords:

```bash
# Extract keywords from a file
python -m localknowledge.textprocessing.keywords.example document.txt

# Extract keywords with specific parameters
python -m localknowledge.textprocessing.keywords.example document.txt --method pytextrank --top-n 20 --normalize
```

## Integration with Other Modules

### Integration with Chunking

Combine keyword extraction with chunking for large documents:

```python
from localknowledge.textprocessing.chunking import markdown_chunker
from localknowledge.textprocessing.keywords import pytextrank_extractor

# Load a markdown document
with open("document.md", "r") as f:
    text = f.read()

# Split into chunks
chunks = markdown_chunker(text)

# Extract keywords from each chunk
for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1} (Level {chunk['level']}): {chunk['heading']}")
    
    # Extract keywords from the chunk
    keywords = pytextrank_extractor(chunk['text'], top_n=5)
    print("Keywords:", ", ".join(keywords))
    print()
```

### Integration with Embeddings

Use keywords to enhance embeddings:

```python
from localknowledge.textprocessing.keywords import pytextrank_extractor
from localknowledge.ai.embeddings import create_embedding

# Load a document
with open("document.txt", "r") as f:
    text = f.read()

# Extract keywords
keywords = pytextrank_extractor(text, top_n=10)

# Create an embedding for the text
embedding = create_embedding(text)

# Store the embedding with keywords
result = {
    'text': text,
    'keywords': keywords,
    'embedding': embedding
}

print(f"Created embedding with {len(keywords)} keywords")
```
