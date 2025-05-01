# Project Management

## Overview

The Project Management module provides functionality for managing research projects in the Researcher's Workbench (RWB). It allows users to create, update, and delete projects, as well as manage project contributors.

## Core Components

### Database Structure

The project management system uses two main tables:

| Table | Description |
|-------|-------------|
| projects | Stores project metadata (title, description, creation date, etc.) |
| project_contributors | Stores many-to-many relationships between projects and users |

#### Projects Table

The `projects` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| title | TEXT | Project title |
| description | TEXT | Project description |
| created_at | TIMESTAMP | When the project was created |
| last_worked_on | TIMESTAMP | When the project was last worked on |
| manager_id | INTEGER | Foreign key to users.id for the project manager |

#### Project Contributors Table

The `project_contributors` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| project_id | INTEGER | Foreign key to projects.id |
| user_id | INTEGER | Foreign key to users.id |

This table uses a composite primary key of (project_id, user_id) to ensure uniqueness.

### Database Manager

The `ProjectDatabaseManager` class in `localknowledge.db.project` handles database operations for project data:

- Creating and updating projects
- Managing project contributors
- Retrieving project information
- Searching for projects

## Usage Examples

### Basic Project Operations

```python
from localknowledge.db.project import ProjectDatabaseManager

# Create a project manager
project_db = ProjectDatabaseManager()

# Create a new project
project_id = project_db.create_project(
    title="My Research Project",
    description="This project investigates...",
    manager_id=user_id
)

# Get project details
project = project_db.get_project(project_id)
print(f"Project: {project['title']}")

# Update project
project_db.update_project(
    project_id=project_id,
    data={
        "title": "Updated Project Title",
        "description": "Updated description"
    }
)

# Delete project
project_db.delete_project(project_id)
```

### Managing Contributors

```python
# Add a contributor to a project
project_db.add_contributor(project_id, user_id)

# Get all contributors for a project
contributors = project_db.get_contributors(project_id)
for contributor in contributors:
    print(f"Contributor: {contributor['username']}")

# Remove a contributor from a project
project_db.remove_contributor(project_id, user_id)
```

### Finding Projects

```python
# Get all projects managed by a user
manager_projects = project_db.get_projects_by_manager(user_id)

# Get all projects where a user is a contributor
contributor_projects = project_db.get_projects_by_contributor(user_id)

# Get all projects a user has access to (as manager or contributor)
all_projects = project_db.get_all_user_projects(user_id)

# Search for projects by title or description
search_results = project_db.search_projects("research", user_id)
```

## Integration with UI

The project management functionality integrates with the RWB UI through the `ProjectManagerPlugin` class in `localknowledge.ui.plugins.project_manager`. This plugin provides:

- Project listing and management
- Project creation and editing
- Contributor management
- Recent projects view

### UI Components

The project management UI consists of several components:

#### Project List Widget

The `ProjectListWidget` class in `localknowledge.ui.project_list` provides a list view of projects with:

- Project title in bold
- First two lines of the description
- Metadata (number of contributors, last worked on date)
- Selection functionality

#### Project Form

The `ProjectForm` class in `localknowledge.ui.project_form` provides a form for creating new projects with:

- Title input field
- Description text area
- Contributor selection list
- Create button

#### Recent Projects Widget

The `RecentProjectsWidget` class in `localknowledge.ui.recent_projects` displays recent projects in a grid layout with:

- Project cards with title and description
- Last worked on date
- Click functionality to select a project

#### Project Detail Widget

The `ProjectDetailWidget` class in `localknowledge.ui.project_detail_widget` provides a detailed view of a project with:

- Project title and edit button
- Hypothesis and counterhypothesis editing
- Research questions management
- Tabbed interface for questions, bookmarks, citations, and drafts

#### Hypothesis Widget

The `HypothesisWidget` class in `localknowledge.ui.hypothesis_widget` provides a widget for editing hypotheses with:

- Hypothesis text editing
- Counterhypothesis text editing
- Save functionality

#### Research Question Widget

The `ResearchQuestionWidget` class in `localknowledge.ui.research_question_widget` provides a widget for managing research questions with:

- List of existing questions with delete buttons
- Form for adding new questions
- Question and details editing

### Using the Project Manager

The project manager can be used as a plugin in the RWB or as a standalone application:

```python
# As a plugin in RWB
from localknowledge.ui.rwb_main import MainWindow

# Create the main window
window = MainWindow()

# The project manager will be available in the plugins list
window.show()

# As a standalone application
from localknowledge.ui.plugins.project_manager import ProjectManager
from PySide6.QtWidgets import QApplication

app = QApplication([])
project_manager = ProjectManager()
project_manager.set_current_user(user_id)
project_manager.show()
app.exec()
```

## Best Practices

When working with projects:

1. Always update the `last_worked_on` timestamp when making changes to a project
2. Check if a user has access to a project before allowing operations
3. Use transactions for operations that modify multiple tables
4. Validate project data before saving to the database
