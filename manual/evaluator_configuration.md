# Evaluator Configuration

## Overview

The Evaluator Configuration system provides a user interface for managing document evaluators. It allows users to create, edit, and delete evaluators, which are used to assess the relevance of documents to research questions.

## Components

### Evaluator Configuration Widget

The `EvaluatorConfigWidget` class provides a user interface for managing evaluators. It includes:

- A list of existing evaluators
- A form for creating and editing evaluators
- Controls for setting model parameters (temperature, top-k, top-p)
- A text editor for custom prompts

### Models Database Manager

The `ModelsDatabaseManager` class provides access to language models stored in the database. It includes methods for:

- Retrieving all available models
- Filtering models by provider or capability
- Getting model details and capabilities

### Reading Suggestions Manager

The `ReadingSuggestionsManager` class includes methods for managing evaluators:

- `add_evaluator`: Create a new evaluator
- `update_evaluator`: Update an existing evaluator
- `delete_evaluator`: Delete an evaluator
- `get_evaluator`: Get details for a specific evaluator
- `get_evaluators`: Get all evaluators, optionally filtered by user

## Usage

### Accessing the Configuration Widget

The evaluator configuration widget is available as a configuration sidebar in the Document Evaluator plugin. To access it:

1. Open the Document Evaluator plugin
2. Click the "Configuration" button in the plugin toolbar
3. The evaluator configuration widget will appear in the sidebar

### Creating a New Evaluator

To create a new evaluator:

1. Click the "New" button in the evaluator list
2. Enter a name for the evaluator
3. Select a model from the dropdown
4. Configure model parameters (temperature, top-k, top-p)
5. Customize the prompt if needed
6. Click "Save Evaluator"

### Editing an Existing Evaluator

To edit an existing evaluator:

1. Select the evaluator from the list
2. Modify the evaluator details in the form
3. Click "Save Evaluator"

### Deleting an Evaluator

To delete an evaluator:

1. Select the evaluator from the list
2. Click the "Delete" button
3. Confirm the deletion

Note: Evaluators that are in use by reading suggestions cannot be deleted.

## Model Parameters

### Temperature

Controls the randomness of the model's output. Higher values (e.g., 1.0) make the output more random, while lower values (e.g., 0.2) make it more deterministic.

The temperature can be adjusted using either:
- The slider (range: 0.0 to 2.0)
- The numeric input box (for precise values)

### Top-K

Limits the model to consider only the top K most likely next tokens at each step. A higher value allows more diversity, while a lower value makes the output more focused.

The top-k value can be set using the numeric input box (range: 0 to 100).

### Top-P (Nucleus Sampling)

The model considers the smallest set of tokens whose cumulative probability exceeds the probability p. A higher value (e.g., 0.9) includes more low-probability tokens, increasing diversity.

The top-p value can be adjusted using either:
- The slider (range: 0.0 to 1.0)
- The numeric input box (for precise values)

## Custom Prompts

The prompt text editor allows you to customize the instructions given to the model when evaluating documents. The default prompt instructs the model to:

1. Evaluate the relevance of a document to a research question
2. Rate the document on a scale of 0-3
3. Provide a brief reason for the rating
4. Return the result in a specific JSON format

When customizing prompts, make sure to:

- Include placeholders for the research question `{question}` and document text `{document}`
- Specify the rating scale and criteria
- Request a structured response format that can be parsed by the system

## Technical Details

### Database Schema

Evaluators are stored in the `evaluators` table with the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | TEXT | Name of the evaluator |
| user_id | INTEGER | Reference to users table (NULL for system evaluators) |
| model_id | TEXT | Name of the model used by the evaluator |
| parameters | JSONB | Model parameters as JSON |
| prompt | TEXT | Custom prompt used by the evaluator |
| created_at | TIMESTAMP | When the evaluator was created |
| updated_at | TIMESTAMP | When the evaluator was last updated |

### Integration with Document Evaluator

The Document Evaluator plugin uses evaluators to assess the relevance of documents to research questions. When a document is evaluated:

1. The plugin retrieves the evaluator's model and parameters
2. It creates a DocumentEvaluator instance with the specified model
3. The evaluator processes the document and returns a rating and reason
4. The evaluation is stored in the database

## Best Practices

1. **Naming**: Use descriptive names for evaluators that indicate their purpose or model
2. **Parameters**: Adjust temperature based on the desired creativity vs. determinism
3. **Prompts**: Keep prompts clear and specific to get consistent results
4. **Testing**: Test new evaluators on a small set of documents before using them widely
5. **Comparison**: Create multiple evaluators with different models or parameters to compare their effectiveness
