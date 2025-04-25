# Bookmarking System

## Overview

The Bookmarking System allows users to save references to publications for later access. It supports both personal bookmarks and project-specific bookmarks, enabling users to organize their research materials effectively.

## Core Components

### Database Structure

The bookmarking system uses a dedicated `bookmarks` table with the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| document_id | INTEGER | Foreign key to document.id |
| user_id | INTEGER | Foreign key to users.id |
| project_id | INTEGER | Foreign key to projects.id (optional) |
| bookmark_type | TEXT | Type of bookmark ('personal', 'project', or 'both') |
| created_at | TIMESTAMP | When the bookmark was created |

The table has a unique constraint on (document_id, user_id, project_id) to prevent duplicate bookmarks.

### Database Manager

The `DocumentDatabaseManager` class in `localknowledge.db.document` provides methods for working with bookmarks:

- `add_bookmark`: Add a bookmark to a document
- `remove_bookmark`: Remove a bookmark from a document
- `is_bookmarked`: Check if a document is bookmarked
- `get_bookmarked_documents`: Get all bookmarked documents for a user or project

### UI Integration

The bookmarking system is integrated into the UI through:

- Bookmark checkboxes in the document view
- A "Bookmarked" filter option in the document list
- Support for both personal and project-specific bookmarks

## Usage Examples

### Adding a Bookmark

```python
from localknowledge.db.document import DocumentDatabaseManager

# Create a document manager
doc_db = DocumentDatabaseManager()

# Add a personal bookmark
doc_db.add_bookmark(
    source_name='medrxiv',
    external_id='10.1101/2023.01.01.12345',
    user_id=1,
    bookmark_type='personal'
)

# Add a project bookmark
doc_db.add_bookmark(
    source_name='pubmed',
    external_id='12345678',
    user_id=1,
    bookmark_type='project',
    project_id=5
)

# Add both personal and project bookmark
doc_db.add_bookmark(
    source_name='medrxiv',
    external_id='10.1101/2023.02.15.54321',
    user_id=1,
    bookmark_type='both',
    project_id=5
)
```

### Checking Bookmark Status

```python
# Check if a document is bookmarked
bookmark_type = doc_db.is_bookmarked(
    source_name='medrxiv',
    external_id='10.1101/2023.01.01.12345',
    user_id=1
)

if bookmark_type:
    print(f"Document is bookmarked as: {bookmark_type}")
else:
    print("Document is not bookmarked")
```

### Getting Bookmarked Documents

```python
# Get all personal bookmarks
personal_bookmarks = doc_db.get_bookmarked_documents(
    user_id=1
)

# Get all project bookmarks
project_bookmarks = doc_db.get_bookmarked_documents(
    user_id=1,
    project_id=5
)
```

## UI Components

### Bookmark Checkboxes

The document view includes checkboxes for:

- Personal bookmarks: Always available
- Project bookmarks: Available when a project is selected

The bookmark checkboxes handle the 'both' bookmark type correctly:
- When a document is bookmarked as 'both', both checkboxes will be checked
- When unchecking one checkbox, the bookmark type will be changed to the other type
- When unchecking both checkboxes, the bookmark will be removed entirely

### Bookmark Filter

The document list includes a "Bookmarked" filter option that shows all documents bookmarked by the current user, either as personal bookmarks or as part of the currently selected project.

### Project Integration

The NewsBrowser can be integrated with project selection to enable project-specific bookmarks:

```python
# Set the current project for the news browser
news_browser.set_current_project(project_id)

# Get the current project from the news browser
current_project_id = news_browser.get_current_project()
```

See the example in `examples/newsbrowser_with_projects.py` for a complete implementation.

## Best Practices

When working with bookmarks:

1. Always check if a document is already bookmarked before adding a new bookmark
2. Use the appropriate bookmark type ('personal', 'project', or 'both')
3. Handle the case where a project is not selected when working with project bookmarks
4. Consider the user's workflow when designing bookmark-related UI components
