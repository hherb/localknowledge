# Evaluations System

## Overview

The Evaluations System provides functionality for rating and tracking the relevance of document chunks to specific research questions. It supports both human and AI-based evaluations, with version tracking to maintain a history of evaluation changes.

## Database Structure

The evaluations system is built around the `evaluations` table, which has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| research_question_id | INTEGER | Part of primary key, references research_questions(id) |
| chunk_id | INTEGER | Part of primary key, references chunks(id) |
| evaluator_id | INTEGER | Part of primary key, references evaluators(id) |
| document_id | INTEGER | Denormalized for performance, the document containing the chunk |
| is_human_evaluator | BOOLEAN | Whether the evaluation was done by a human (TRUE) or AI (FALSE) |
| rating | INTEGER | Rating value from 0-5 |
| rating_reason | TEXT | Optional explanation for the rating |
| confidence_level | FLOAT | Confidence level from 0.0 to 1.0 |
| created_at | TIMESTAMP | When the evaluation was created |
| updated_at | TIMESTAMP | When the evaluation was last updated |
| evaluation_version | INTEGER | Version number, automatically incremented on updates |

The table has a composite primary key of (research_question_id, chunk_id, evaluator_id), which means that each combination of research question, chunk, and evaluator can have only one evaluation.

## Automatic Version Tracking

The evaluations table includes automatic version tracking through a PostgreSQL trigger. Whenever an evaluation is updated, the `evaluation_version` is automatically incremented and the `updated_at` timestamp is updated.

## Performance Optimizations

The evaluations table includes several indexes to optimize different query patterns:

- `idx_eval_question`: For queries filtering by research question
- `idx_eval_chunk`: For queries filtering by chunk
- `idx_eval_document`: For queries filtering by document
- `idx_eval_evaluator`: For queries filtering by evaluator
- `idx_eval_llm`: For efficiently filtering AI evaluations
- `idx_eval_question_doc`: For analytics queries combining research questions and documents

## Usage

### Creating Evaluations

```python
from localknowledge.db.evaluations import EvaluationsDatabaseManager

# Create an evaluations database manager
evaluations_db = EvaluationsDatabaseManager()

# Create a new evaluation
success = evaluations_db.create_evaluation(
    research_question_id=1,
    chunk_id=100,
    evaluator_id=10,
    document_id=1000,
    is_human_evaluator=False,
    rating=4,
    confidence_level=0.85,
    rating_reason="This chunk directly addresses the research question"
)
```

### Retrieving Evaluations

```python
# Get a specific evaluation
evaluation = evaluations_db.get_evaluation(
    research_question_id=1,
    chunk_id=100,
    evaluator_id=10
)

# Get evaluations for a research question
evaluations = evaluations_db.get_evaluations_by_research_question(
    research_question_id=1,
    min_rating=3,  # Optional: filter by minimum rating
    human_only=False,  # Optional: only include human evaluations
    limit=10,  # Optional: limit results
    offset=0  # Optional: pagination offset
)

# Get evaluations for a document
evaluations = evaluations_db.get_evaluations_by_document(
    document_id=1000,
    research_question_id=1,  # Optional: filter by research question
    min_rating=3,  # Optional: filter by minimum rating
    human_only=False  # Optional: only include human evaluations
)
```

### Updating and Deleting Evaluations

```python
# Update an evaluation
success = evaluations_db.update_evaluation(
    research_question_id=1,
    chunk_id=100,
    evaluator_id=10,
    rating=5,  # Optional: new rating
    confidence_level=0.9,  # Optional: new confidence level
    rating_reason="Updated reason"  # Optional: new reason
)

# Delete an evaluation
success = evaluations_db.delete_evaluation(
    research_question_id=1,
    chunk_id=100,
    evaluator_id=10
)
```

### Analytics

```python
# Get statistics for a research question
stats = evaluations_db.get_evaluation_stats_by_question(
    research_question_id=1
)

# Get top-rated chunks for a research question
top_chunks = evaluations_db.get_top_rated_chunks_for_question(
    research_question_id=1,
    min_rating=3,  # Optional: minimum rating to include
    limit=10,  # Optional: maximum number of results
    human_only=False  # Optional: only include human evaluations
)

# Get document relevance for a research question
relevance = evaluations_db.get_document_relevance_for_question(
    research_question_id=1,
    document_id=1000
)

# Get all document IDs with a specific rating for a research question
document_ids = evaluations_db.documents_by_rating_for_question(
    rating=4,  # Exact rating to filter by
    question_id=1,
    evaluator_id=10  # Optional: filter by specific evaluator
)
```

## Integration with Other Systems

The evaluations system integrates with:

1. **Research Questions**: Each evaluation is linked to a specific research question
2. **Document Chunks**: Evaluations rate the relevance of specific chunks of text
3. **Evaluators**: Both human users and AI models can provide evaluations
4. **Reading Suggestions**: High-rated evaluations can be used to generate reading suggestions

## Best Practices

1. **Rating Scale**: Use consistent criteria for ratings:
   - 0: Not relevant at all
   - 1: Minimally relevant
   - 2: Somewhat relevant
   - 3: Moderately relevant
   - 4: Very relevant
   - 5: Extremely relevant/direct answer

2. **Confidence Levels**: Use confidence levels to indicate certainty:
   - 0.0-0.3: Low confidence
   - 0.4-0.7: Medium confidence
   - 0.8-1.0: High confidence

3. **Human vs. AI Evaluations**: Use the `is_human_evaluator` flag to distinguish between human and AI evaluations. This allows for filtering and comparison between the two types.

4. **Batch Processing**: For processing large datasets, use the `get_evaluations_by_batch` method to retrieve evaluations in manageable chunks.

5. **Performance**: When querying for evaluations, use the most specific method available to take advantage of the optimized indexes.
