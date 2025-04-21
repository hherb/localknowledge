# Testing

## Overview

This guide provides information on testing the Local Knowledge system. It covers unit testing, integration testing, and end-to-end testing, as well as best practices for writing and running tests.

## Testing Framework

The Local Knowledge system uses pytest as its testing framework. Pytest provides a simple and flexible way to write tests, with features like fixtures, parameterization, and plugins.

## Test Organization

Tests are organized by module, with test files located in the same directory as the module they test:

```
localknowledge/
├── db/
│   ├── test_base.py
│   ├── test_medrxiv.py
│   └── ...
├── ai/
│   ├── test_embeddings.py
│   ├── test_qafinder.py
│   └── ...
└── ...
```

For larger modules, tests may be organized in a `tests` subdirectory:

```
localknowledge/
├── medrxiv/
│   ├── tests/
│   │   ├── test_client.py
│   │   ├── test_update_database.py
│   │   └── ...
│   ├── client.py
│   ├── update_database.py
│   └── ...
└── ...
```

## Running Tests

### Running All Tests

To run all tests:

```bash
# From the project root
pytest

# With verbose output
pytest -v
```

### Running Specific Tests

To run tests for a specific module:

```bash
# Run tests for a specific module
pytest localknowledge/db/test_base.py

# Run tests for a specific class
pytest localknowledge/db/test_base.py::TestDatabaseManager

# Run a specific test
pytest localknowledge/db/test_base.py::TestDatabaseManager::test_connect
```

### Running Tests with Coverage

To run tests with coverage:

```bash
# Run tests with coverage
pytest --cov=localknowledge

# Generate a coverage report
pytest --cov=localknowledge --cov-report=html
```

## Writing Tests

### Unit Tests

Unit tests test individual functions or classes in isolation. They should be fast, independent, and focused on a single unit of functionality.

Example unit test:

```python
# In localknowledge/db/test_base.py
import unittest
from unittest.mock import patch, MagicMock
from localknowledge.db.base import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    @patch('psycopg2.connect')
    def test_connect(self, mock_connect):
        # Arrange
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        db = DatabaseManager()
        
        # Act
        db.connect()
        
        # Assert
        mock_connect.assert_called_once()
        self.assertEqual(db.connection, mock_connection)
```

### Integration Tests

Integration tests test the interaction between multiple components. They may require external resources like a database or API.

Example integration test:

```python
# In localknowledge/medrxiv/tests/test_client.py
import unittest
from localknowledge.medrxiv import MedRxivClient
from localknowledge.db.medrxiv import MedRxivDatabaseManager

class TestMedRxivClient(unittest.TestCase):
    def setUp(self):
        # Set up a test database
        self.db = MedRxivDatabaseManager()
        self.db.execute("CREATE TEMPORARY TABLE preprints AS SELECT * FROM preprints LIMIT 0")
        
        # Create a client with the test database
        self.client = MedRxivClient(db=self.db)
    
    def tearDown(self):
        # Clean up
        self.db.close()
    
    def test_get_preprint_by_doi(self):
        # Arrange
        doi = "10.1101/2023.01.01.12345"
        self.db.execute(
            "INSERT INTO preprints (doi, title) VALUES (%s, %s)",
            (doi, "Test Preprint")
        )
        
        # Act
        preprint = self.client.get_preprint_by_doi(doi)
        
        # Assert
        self.assertIsNotNone(preprint)
        self.assertEqual(preprint['doi'], doi)
        self.assertEqual(preprint['title'], "Test Preprint")
```

### End-to-End Tests

End-to-end tests test the entire system from the user's perspective. They may involve UI interactions and external resources.

Example end-to-end test:

```python
# In localknowledge/ui/tests/test_main.py
import unittest
from unittest.mock import patch
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from localknowledge.ui.main import MainWindow

class TestMainWindow(unittest.TestCase):
    def setUp(self):
        # Create a main window
        self.window = MainWindow()
    
    def tearDown(self):
        # Clean up
        self.window.close()
    
    @patch('localknowledge.medrxiv.MedRxivClient')
    def test_search(self, mock_client):
        # Arrange
        mock_client.return_value.search_preprints.return_value = [
            {'doi': '10.1101/2023.01.01.12345', 'title': 'Test Preprint'}
        ]
        
        # Act
        self.window.search_input.setText("test query")
        QTest.mouseClick(self.window.search_button, Qt.LeftButton)
        
        # Assert
        mock_client.return_value.search_preprints.assert_called_once_with("test query")
        self.assertEqual(self.window.results_list.count(), 1)
        self.assertEqual(self.window.results_list.item(0).text(), "Test Preprint")
```

## Test Fixtures

Test fixtures provide a way to set up and tear down test dependencies. Pytest provides a powerful fixture system that can be used at different levels.

Example fixtures:

```python
# In localknowledge/conftest.py
import pytest
import tempfile
import os
from localknowledge.db.base import DatabaseManager

@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def db():
    """Provide a database connection that is closed after the test."""
    db = DatabaseManager()
    yield db
    db.close()

@pytest.fixture
def test_preprint():
    """Provide a test preprint for testing."""
    return {
        'doi': '10.1101/2023.01.01.12345',
        'title': 'Test Preprint',
        'abstract': 'This is a test abstract.',
        'authors': '[{"name": "Test Author"}]',
        'date': '2023-01-01',
        'url': 'https://example.com/preprint',
        'pdf_url': 'https://example.com/preprint.pdf'
    }
```

## Mocking

Mocking is a technique for replacing dependencies with controlled objects. It's useful for isolating the code under test and simulating different scenarios.

Example with mocking:

```python
# In localknowledge/ai/test_embeddings.py
import unittest
from unittest.mock import patch, MagicMock
from localknowledge.ai.embeddings import create_embedding

class TestEmbeddings(unittest.TestCase):
    @patch('ollama.embeddings')
    def test_create_embedding(self, mock_embeddings):
        # Arrange
        mock_response = {'embeddings': [0.1, 0.2, 0.3]}
        mock_embeddings.return_value = mock_response
        
        # Act
        embedding = create_embedding("Test text")
        
        # Assert
        mock_embeddings.assert_called_once_with(model="snowflake-arctic-embed2:latest", prompt="Test text")
        self.assertEqual(embedding, [0.1, 0.2, 0.3])
```

## Test Database

For tests that require a database, it's best to use a separate test database to avoid affecting the development or production database.

Example test database setup:

```python
# In localknowledge/db/test_base.py
import unittest
import os
from localknowledge.db.base import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up a test database
        os.environ['LK_DB_NAME'] = 'localknowledge_test'
        
        # Create the test database
        db = DatabaseManager()
        db.execute("CREATE DATABASE localknowledge_test")
        db.close()
        
        # Initialize the test database
        from localknowledge.db.createdb import create_tables
        create_tables()
    
    @classmethod
    def tearDownClass(cls):
        # Drop the test database
        db = DatabaseManager()
        db.execute("DROP DATABASE localknowledge_test")
        db.close()
        
        # Restore the original database name
        os.environ.pop('LK_DB_NAME')
    
    def setUp(self):
        # Connect to the test database
        self.db = DatabaseManager()
    
    def tearDown(self):
        # Clean up
        self.db.close()
    
    def test_execute(self):
        # Test the execute method
        self.db.execute("CREATE TEMPORARY TABLE test (id SERIAL PRIMARY KEY, name TEXT)")
        self.db.execute("INSERT INTO test (name) VALUES (%s)", ("Test",))
        result = self.db.execute("SELECT * FROM test")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], "Test")
```

## Test Data

For tests that require data, it's best to use small, controlled datasets. These can be defined in the test file or loaded from external files.

Example with test data:

```python
# In localknowledge/textprocessing/test_chunking.py
import unittest
from localknowledge.textprocessing.chunking import markdown_chunker

class TestMarkdownChunker(unittest.TestCase):
    def test_markdown_chunker(self):
        # Test data
        markdown_text = """
        # Introduction
        
        This is the introduction section.
        
        ## Background
        
        This is the background section.
        
        # Methods
        
        This is the methods section.
        """
        
        # Act
        chunks = markdown_chunker(markdown_text)
        
        # Assert
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0]['heading'], "Introduction")
        self.assertEqual(chunks[1]['heading'], "Background")
        self.assertEqual(chunks[2]['heading'], "Methods")
```

## Continuous Integration

The project uses continuous integration (CI) to automatically run tests on code changes. The CI pipeline is configured to:

1. Run all tests
2. Generate a coverage report
3. Run linting and style checks
4. Build and package the application

## Best Practices

### Test Independence

Tests should be independent of each other. One test should not depend on the state left by another test.

### Test Coverage

Aim for high test coverage, but focus on testing critical and complex code paths rather than simple getters and setters.

### Test Readability

Write clear, readable tests with descriptive names and comments. Use the Arrange-Act-Assert pattern to structure tests.

### Test Performance

Tests should be fast to encourage frequent running. Use mocking and fixtures to avoid slow operations like network requests.

### Test Maintenance

Keep tests up to date with code changes. Refactor tests when the code they test changes.

## Troubleshooting

### Common Issues

1. **Tests Failing Intermittently**: This may indicate a dependency on external resources or state. Use mocking and fixtures to isolate tests.

2. **Tests Taking Too Long**: This may indicate slow operations like network requests. Use mocking to avoid these operations.

3. **Tests Failing on CI but Passing Locally**: This may indicate a dependency on local configuration. Use environment variables and fixtures to ensure consistent test environments.

### Debugging Tests

To debug tests:

```bash
# Run tests with verbose output
pytest -v

# Run tests with debug output
pytest --log-cli-level=DEBUG

# Run tests with a debugger
pytest --pdb

# Run tests with a specific configuration
LK_DB_NAME=localknowledge_test pytest
```
