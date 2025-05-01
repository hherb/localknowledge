# Hypotheses and Research Questions

## Overview

The Hypotheses and Research Questions modules provide functionality for managing research hypotheses and questions in the Local Knowledge system. These modules allow users to create, update, and delete hypotheses and research questions, as well as associate them with research projects.

## Core Components

### Database Structure

The system uses four main tables:

| Table | Description |
|-------|-------------|
| hypotheses | Stores hypothesis data (hypothesis statement, counter-hypothesis, creation date) |
| hypotheses_projects | Stores many-to-many relationships between hypotheses and projects |
| research_questions | Stores research question data (question text, details) |
| project_questions | Stores many-to-many relationships between research questions and projects |

#### Hypotheses Table

The `hypotheses` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| hypothesis | TEXT | The main hypothesis statement |
| counterhypothesis | TEXT | Optional counter-hypothesis statement |
| created_at | TIMESTAMP | When the hypothesis was created (default: CURRENT_TIMESTAMP) |

#### Hypotheses Projects Table

The `hypotheses_projects` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| project_id | INTEGER | Foreign key to projects.id |
| hypothesis_id | INTEGER | Foreign key to hypotheses.id |

This table uses a composite primary key of (project_id, hypothesis_id) to ensure uniqueness.

#### Research Questions Table

The `research_questions` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| question | TEXT | The research question text |
| details | TEXT | Optional additional details or context |

#### Project Questions Table

The `project_questions` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| project_id | INTEGER | Foreign key to projects.id |
| research_question_id | INTEGER | Foreign key to research_questions.id |

This table uses a composite primary key of (project_id, research_question_id) to ensure uniqueness.

### Database Managers

#### HypothesesDatabaseManager

The `HypothesesDatabaseManager` class in `localknowledge.db.hypotheses` handles database operations for hypothesis data:

- Creating and updating hypotheses
- Managing hypothesis-project associations
- Retrieving hypothesis information
- Searching for hypotheses

#### ResearchQuestionsManager

The `ResearchQuestionsManager` class in `localknowledge.db.research_questions` handles database operations for research question data:

- Creating and updating research questions
- Managing question-project associations
- Retrieving question information
- Searching for research questions

## Usage Examples

### Working with Hypotheses

```python
from localknowledge.db.hypotheses import HypothesesDatabaseManager

# Create a hypotheses manager
hypotheses_db = HypothesesDatabaseManager()

# Create a new hypothesis
hypothesis_id = hypotheses_db.create_hypothesis(
    hypothesis="Regular exercise reduces the risk of cardiovascular disease.",
    counterhypothesis="Exercise has no significant impact on cardiovascular health."
)

# Get hypothesis details
hypothesis = hypotheses_db.get_hypothesis(hypothesis_id)
print(f"Hypothesis: {hypothesis['hypothesis']}")
print(f"Counter-hypothesis: {hypothesis['counterhypothesis']}")

# Update hypothesis
hypotheses_db.update_hypothesis(
    hypothesis_id=hypothesis_id,
    data={
        "hypothesis": "Regular exercise significantly reduces the risk of cardiovascular disease.",
        "counterhypothesis": "The relationship between exercise and cardiovascular health is not causal."
    }
)

# Associate hypothesis with a project
hypotheses_db.associate_with_project(hypothesis_id, project_id)

# Get all hypotheses for a project
project_hypotheses = hypotheses_db.get_project_hypotheses(project_id)
for h in project_hypotheses:
    print(f"Project hypothesis: {h['hypothesis']}")

# Remove hypothesis from a project
hypotheses_db.remove_from_project(hypothesis_id, project_id)

# Delete hypothesis
hypotheses_db.delete_hypothesis(hypothesis_id)

# Search for hypotheses
search_results = hypotheses_db.search_hypotheses("cardiovascular")
```

### Working with Research Questions

```python
from localknowledge.db.research_questions import ResearchQuestionsManager

# Create a research questions manager
questions_db = ResearchQuestionsManager()

# Create a new research question
question_id = questions_db.create_question(
    question="What is the optimal frequency of exercise for cardiovascular health?",
    details="Looking at different exercise regimens and their impact on various cardiovascular health markers."
)

# Get question details
question = questions_db.get_question(question_id)
print(f"Question: {question['question']}")
print(f"Details: {question['details']}")

# Update question
questions_db.update_question(
    question_id=question_id,
    data={
        "question": "What is the optimal frequency and intensity of exercise for cardiovascular health?",
        "details": "Examining the relationship between exercise parameters and cardiovascular outcomes."
    }
)

# Associate question with a project
questions_db.associate_with_project(question_id, project_id)

# Get all questions for a project
project_questions = questions_db.get_project_questions(project_id)
for q in project_questions:
    print(f"Project question: {q['question']}")

# Remove question from a project
questions_db.remove_from_project(question_id, project_id)

# Delete question
questions_db.delete_question(question_id)

# Search for questions
search_results = questions_db.search_questions("exercise")
```

## Integration with Project Management

The hypotheses and research questions modules integrate with the project management system, allowing users to associate hypotheses and questions with specific research projects. This enables researchers to organize their research around specific questions and hypotheses.

### Project-Hypothesis Relationships

- A project can have multiple hypotheses
- A hypothesis can be associated with multiple projects
- When a project is deleted, its associations with hypotheses are automatically removed (via ON DELETE CASCADE)

### Project-Question Relationships

- A project can have multiple research questions
- A research question can be associated with multiple projects
- When a project is deleted, its associations with research questions are automatically removed (via ON DELETE CASCADE)

## UI Components

The hypotheses and research questions functionality integrates with the RWB UI through several components:

### Project Detail Widget

The `ProjectDetailWidget` class in `localknowledge.ui.project_detail_widget` provides a comprehensive view of a project, including:

- Project title and edit button
- Hypothesis and counterhypothesis editing
- Research questions management
- Tabbed interface for questions, bookmarks, citations, and drafts

### Hypothesis Widget

The `HypothesisWidget` class in `localknowledge.ui.hypothesis_widget` provides a widget for editing hypotheses with:

- Hypothesis text editing
- Counterhypothesis text editing
- Save functionality

### Research Question Widget

The `ResearchQuestionWidget` class in `localknowledge.ui.research_question_widget` provides a widget for managing research questions with:

- List of existing questions with delete buttons
- Form for adding new questions
- Question and details editing

## Best Practices

When working with hypotheses and research questions:

1. Formulate clear, testable hypotheses with specific variables
2. Create counter-hypotheses to help evaluate evidence objectively
3. Develop research questions that are specific, measurable, and achievable
4. Associate related hypotheses and questions with the same projects
5. Use the search functionality to find existing hypotheses and questions before creating new ones
6. Consider the relationship between hypotheses and research questions when designing research projects
