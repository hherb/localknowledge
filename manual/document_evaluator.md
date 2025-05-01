# Document Evaluator Module

The `document_evaluator` module provides functionality for evaluating documents for their relevance to research questions. It uses LLMs to analyze document content and provide ratings and explanations.

## Overview

The module consists of:

1. **Document Evaluation**: The `DocumentEvaluator` class evaluates how relevant a document is to a specific research question using LLMs.
2. **Evaluation Results**: The `DocumentOfInterest` dataclass represents the evaluation results.

## Usage

### Evaluating Document Relevance

```python
from localknowledge.ai.document_evaluator import DocumentEvaluator

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
- **1**: Document is somewhat relevant, tangentially related to the question
- **2**: Document is very likely relevant to answer the question, it should not be missed
- **3**: Document answers the question, it is essential and must be included in the reading list

## API Reference

### Classes

#### `DocumentOfInterest`

Represents a document that has been evaluated with regards to a question.

- **Attributes**:
  - `document_id` (int): The ID of the document in the database
  - `rating` (int): Rating from 0 to 3 indicating relevance
  - `reason_for_rating` (str): Reason for the rating provided by the evaluator
  - `similarity` (float): The similarity score (0-1) between the document and the query (default: 0.0)

#### `DocumentEvaluator`

Evaluates documents for their relevance to a research question.

- **Methods**:
  - `__init__(model_name="gemma3:4b", model_options=None)`: Initialize the evaluator
    - `model_name` (str): Name of the Ollama model to use for evaluation
    - `model_options` (dict, optional): Optional parameters for the Ollama model
  - `evaluate(question, document_id)`: Evaluate a document's relevance to a question
    - `question` (str): The research question
    - `document_id` (int): The ID of the document to evaluate
    - Returns: `DocumentOfInterest` object with the rating and reason for the rating

## Implementation Details

The module uses the following components:

- `DocumentDatabaseManager` from `localknowledge.db.document` for retrieving document content
- `ollama` for generating document evaluations using LLMs

The document evaluation is performed using a prompt-based approach with an LLM. The evaluator:

1. Retrieves the document from the database
2. Formats a prompt with the research question and document abstract
3. Sends the prompt to the LLM for evaluation
4. Parses the JSON response to extract the rating and reason
5. Returns a `DocumentOfInterest` object with the evaluation results

The evaluator includes error handling and fallback mechanisms to ensure robust operation even when the primary model fails.
