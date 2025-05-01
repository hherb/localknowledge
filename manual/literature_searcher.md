# Literature Searcher Module

The `literature_searcher` module provides functionality for searching and evaluating documents that might be helpful to answer a research question. It uses a combination of keyword search and semantic search to find relevant documents.

## Overview

The module consists of two main components:

1. **Document Search**: The `search_literature` function uses semantic search to find documents relevant to a research question.
2. **Document Evaluation**: The `DocumentEvaluator` class evaluates how relevant a document is to a specific research question.

## Usage

### Searching for Relevant Literature

```python
from localknowledge.ai.literature_searcher import search_literature

# Search for documents related to a research question
found_documents = search_literature(
    question="Is machine learning able to predict in-hospital mortality?",
    max_results=10,
    similarity_threshold=0.6,
    source_name="pubmed"  # Optional: filter by source
)

# Process the results
for doc in found_documents:
    print(f"Document ID: {doc.document_id}, Similarity: {doc.similarity:.4f}")
```

The `search_literature` function returns a list of `FoundDocuments` objects, each containing a document ID and a similarity score.

### Evaluating Document Relevance

```python
from localknowledge.ai.literature_searcher import DocumentEvaluator

# Create an evaluator
evaluator = DocumentEvaluator(model_name="gemma3:4b")

# Evaluate a document
evaluation = evaluator.evaluate(
    question="Is machine learning able to predict in-hospital mortality?",
    document_id=123  # ID of the document to evaluate
)

# Process the evaluation
print(f"Document ID: {evaluation.document_id}")
print(f"Rating: {evaluation.rating}/3")
print(f"Reason: {evaluation.reason_for_rating}")
```

The `DocumentEvaluator` class uses an LLM to evaluate how relevant a document is to a research question. It returns a `DocumentOfInterest` object with the following rating scale:

- **0**: Document is not relevant at all
- **1**: Document is somewhat relevant
- **2**: Document is likely relevant
- **3**: Document answers the question

## API Reference

### Classes

#### `FoundDocuments`

Represents the result of a literature search.

- **Attributes**:
  - `document_id` (int): The ID of the document in the database
  - `similarity` (float): The similarity score (0-1) between the document and the query

#### `DocumentOfInterest`

Represents a document that has been evaluated with regards to a question.

- **Attributes**:
  - `document_id` (int): The ID of the document in the database
  - `rating` (int): Rating from 0 to 3 indicating relevance
  - `reason_for_rating` (str): Reason for the rating provided by the evaluator
  - `similarity` (float): The similarity score (0-1) between the document and the query

#### `DocumentEvaluator`

Evaluates documents for their relevance to a research question.

- **Methods**:
  - `__init__(model_name="gemma3:4b", model_params=None)`: Initialize the evaluator
  - `evaluate(question, document_id)`: Evaluate a document's relevance to a question

### Functions

#### `search_literature`

```python
def search_literature(
    question: str,
    research_question_id: Optional[int] = None,
    max_results: int = 10,
    similarity_threshold: float = 0.5,
    source_name: Optional[str] = None
) -> List[FoundDocuments]
```

Search for documents that might be helpful to answer a research question.

- **Parameters**:
  - `question` (str): The research question
  - `research_question_id` (Optional[int]): The ID of the research question in the database (optional). If provided, all found documents will be linked with the research question
  - `max_results` (int): Maximum number of results to return
  - `similarity_threshold` (float): Minimum similarity score (0-1) for results
  - `source_name` (Optional[str]): Filter by source name (optional)

- **Returns**:
  - List of `FoundDocuments` objects with document IDs and similarity scores

## Implementation Details

The module uses the following components:

- `DocumentSearchManager` from `localknowledge.db.document_search` for semantic search
- `DocumentDatabaseManager` from `localknowledge.db.document` for database operations
- `ollama` for generating document evaluations using LLMs

The semantic search is performed using embeddings, and the document evaluation is performed using a prompt-based approach with an LLM.
