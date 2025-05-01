# News Finder Module

The News Finder module is designed to identify recent publications that are relevant to active research questions and hypotheses in the system. It helps researchers stay up-to-date with the latest literature that might contribute to answering their research questions or confirming/rejecting their hypotheses.

## Overview

The module works by:

1. Fetching recent publications from the database (based on publication date)
2. Evaluating each publication against active research questions and hypotheses
3. Identifying publications that are likely to be relevant (rating > 1)
4. Providing detailed information about why each publication is considered relevant

## Classes

### NewsItem

Represents a news item (publication) that is of interest.

**Attributes**:
- `document_id` (int): The ID of the document in the database
- `rating` (int): Rating from 0 to 3 indicating relevance
- `reason_for_rating` (str): Reason for the rating provided by the evaluator
- `similarity` (float): The similarity score (0-1) between the document and the query
- `model_name` (str): Name of the model used for evaluation

### NewsFinder

Finds new additions to the publication database that are of interest based on research questions and hypotheses.

**Methods**:
- `__init__(most_recent_days=3, max_documents_analyzed=50, model_name="gemma3:4b")`: Initialize the NewsFinder
- `fetch_recent_publications()`: Fetch the most recent publications from the database
- `get_abstract(document_id)`: Get the abstract of a publication
- `get_question_text(question_id)`: Get the text of a research question
- `get_hypothesis_text(hypothesis_id)`: Get the text of a hypothesis
- `evaluate(document_id, question_text)`: Evaluate the relevance of a publication to a question
- `trawl_for_news(document_id, questions, hypotheses=None)`: Trawl for news that is relevant to research questions or hypotheses
- `find_news_for_project(project_id)`: Find news items relevant to a project's research questions and hypotheses

## Usage Examples

### Finding News for a Project

```python
from localknowledge.ai.newsfinder import NewsFinder

# Create a news finder
news_finder = NewsFinder(
    most_recent_days=7,  # Look back 7 days
    max_documents_analyzed=100,  # Analyze up to 100 documents
    model_name="gemma3:4b"  # Use the gemma3:4b model for evaluation
)

# Find news for a project
project_id = 1
news_items = news_finder.find_news_for_project(project_id)

# Process the results
print(f"Found {len(news_items)} relevant news items:")
for item in news_items:
    print(f"Document ID: {item.document_id}")
    print(f"Rating: {item.rating}/3")
    print(f"Reason: {item.reason_for_rating}")
```

### Evaluating a Specific Document

```python
from localknowledge.ai.newsfinder import NewsFinder

# Create a news finder
news_finder = NewsFinder()

# Get research questions and hypotheses
questions = [1, 2, 3]  # List of research question IDs
hypotheses = [4, 5]    # List of hypothesis IDs

# Evaluate a specific document
document_id = 123
news_items = news_finder.trawl_for_news(document_id, questions, hypotheses)

# Process the results
if news_items:
    print(f"Document {document_id} is relevant:")
    for item in news_items:
        print(f"Rating: {item.rating}/3")
        print(f"Reason: {item.reason_for_rating}")
else:
    print(f"Document {document_id} is not relevant to any of the questions or hypotheses.")
```

## Command-Line Interface

The module can be run as a standalone script to find news for a project:

```bash
python -m localknowledge.ai.newsfinder --project 1 --days 7 --max 100 --model gemma3:4b
```

**Arguments**:
- `--project`, `-p`: Project ID to find news for
- `--days`, `-d`: Number of days to look back for recent publications (default: 3)
- `--max`, `-m`: Maximum number of documents to analyze (default: 50)
- `--model`: Model to use for evaluation (default: gemma3:4b)

If no project ID is provided, the script will just show recent publications:

```bash
python -m localknowledge.ai.newsfinder --days 7
```

## Rating Scale

The module uses the following rating scale to evaluate the relevance of publications:

- **0**: Document is not relevant at all
- **1**: Document is somewhat relevant
- **2**: Document is likely relevant
- **3**: Document answers the question

Only publications with a rating > 1 are considered as "news" items.

## Integration with Other Modules

The News Finder module integrates with:

- `DocumentDatabaseManager`: To fetch documents and their abstracts
- `ResearchQuestionsManager`: To get research questions for a project
- `HypothesesDatabaseManager`: To get hypotheses for a project
- `DocumentEvaluator`: To evaluate the relevance of documents to questions and hypotheses

## Performance Considerations

- The module uses the `tqdm` library to show progress when evaluating multiple documents
- For large projects with many research questions and hypotheses, the evaluation process can be time-consuming
- Consider adjusting the `max_documents_analyzed` parameter to limit the number of documents processed
