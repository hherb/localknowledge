# Setting Up Development Environment

## Overview

This guide provides instructions for setting up a development environment for the Local Knowledge system. It covers installing dependencies, configuring the database, setting up Ollama, and preparing the development environment.

## Prerequisites

Before setting up the development environment, ensure you have the following prerequisites:

- Python 3.9 or later
- PostgreSQL 14 or later with pgvector extension
- Git
- Ollama (for local AI models)
- A code editor (VS Code, PyCharm, etc.)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge
```

### 2. Create a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install the package in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### 4. Set Up PostgreSQL

#### Install PostgreSQL

- **Ubuntu/Debian**:
  ```bash
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  ```

- **macOS** (using Homebrew):
  ```bash
  brew install postgresql
  ```

- **Windows**: Download and install from [PostgreSQL website](https://www.postgresql.org/download/windows/)

#### Install pgvector Extension

- **Ubuntu/Debian**:
  ```bash
  sudo apt install postgresql-14-pgvector
  ```

- **macOS** (using Homebrew):
  ```bash
  brew install pgvector
  ```

- **Windows**: Follow instructions on [pgvector GitHub](https://github.com/pgvector/pgvector)

#### Create Database

```bash
# Create a database
sudo -u postgres createdb localknowledge

# Create a user (if needed)
sudo -u postgres createuser --interactive

# Connect to the database
sudo -u postgres psql -d localknowledge

# In PostgreSQL prompt, create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Exit PostgreSQL prompt
\q
```

### 5. Set Up Ollama

#### Install Ollama

Follow the instructions on the [Ollama website](https://ollama.ai/download) to install Ollama for your platform.

#### Pull Required Models

```bash
# Pull the embedding model
ollama pull snowflake-arctic-embed2:latest

# Pull the QA model
ollama pull gemma3:4b
```

### 6. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Database configuration
LK_DB_HOST=localhost
LK_DB_PORT=5432
LK_DB_NAME=localknowledge
LK_DB_USER=your_username
LK_DB_PASSWORD=your_password

# Ollama configuration
OLLAMA_HOST=http://localhost:11434

# PDF storage configuration
LK_PDF_DIR=/path/to/pdf/storage

# Logging configuration
LOG_LEVEL=INFO
```

### 7. Initialize the Database

```bash
# Run the database initialization script
python -m localknowledge.db.createdb
```

### 8. Run Tests

```bash
# Run all tests
pytest

# Run specific tests
pytest localknowledge/tests/test_embeddings.py
```

## Development Workflow

### Code Organization

The Local Knowledge system is organized into several modules:

- `localknowledge.db`: Database functionality
- `localknowledge.ai`: AI functionality
- `localknowledge.textprocessing`: Text processing functionality
- `localknowledge.ui`: User interface functionality
- `localknowledge.medrxiv`: MedRxiv-specific functionality
- `localknowledge.pubmed`: PubMed-specific functionality

### Running the Application

```bash
# Run the main application
python -m localknowledge.ui.main

# Run specific modules
python -m localknowledge.medrxiv.update_database
```

### Development Guidelines

#### Code Style

The project follows PEP 8 style guidelines. Use tools like `flake8` and `black` to ensure code quality:

```bash
# Check code style
flake8 localknowledge

# Format code
black localknowledge
```

#### Documentation

Document your code using docstrings and comments:

```python
def example_function(param1, param2):
    """
    Example function that does something.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    """
    # Implementation
    return result
```

#### Testing

Write tests for new functionality:

```python
# In localknowledge/tests/test_example.py
import unittest
from localknowledge.example import example_function

class TestExample(unittest.TestCase):
    def test_example_function(self):
        result = example_function(1, 2)
        self.assertEqual(result, expected_result)
```

## IDE Setup

### VS Code

1. Install the Python extension
2. Configure settings:
   ```json
   {
     "python.linting.enabled": true,
     "python.linting.flake8Enabled": true,
     "python.formatting.provider": "black",
     "editor.formatOnSave": true,
     "python.testing.pytestEnabled": true,
     "python.testing.unittestEnabled": false,
     "python.testing.nosetestsEnabled": false,
     "python.testing.pytestArgs": [
       "localknowledge"
     ]
   }
   ```

### PyCharm

1. Open the project in PyCharm
2. Configure the Python interpreter:
   - Go to Settings > Project > Python Interpreter
   - Add the virtual environment as the interpreter
3. Configure code style:
   - Go to Settings > Editor > Code Style > Python
   - Set the code style to PEP 8
4. Configure testing:
   - Go to Settings > Tools > Python Integrated Tools
   - Set the default test runner to pytest

## Troubleshooting

### Common Issues

1. **Database Connection Issues**:
   - Check PostgreSQL service is running
   - Verify connection parameters in `.env` file
   - Ensure the user has appropriate permissions

2. **Ollama Issues**:
   - Check Ollama service is running
   - Verify models are installed
   - Check network connectivity to Ollama API

3. **Import Errors**:
   - Ensure the package is installed in development mode
   - Check virtual environment is activated
   - Verify Python path includes the project directory

### Getting Help

If you encounter issues:

1. Check the project documentation
2. Look for similar issues in the issue tracker
3. Ask for help in the project's communication channels

## Advanced Configuration

### Custom Database Setup

For advanced database configuration:

```bash
# Create a custom PostgreSQL configuration
sudo -u postgres psql -c "ALTER SYSTEM SET shared_buffers = '1GB';"
sudo -u postgres psql -c "ALTER SYSTEM SET work_mem = '50MB';"
sudo -u postgres psql -c "ALTER SYSTEM SET maintenance_work_mem = '256MB';"

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Development with GPU Acceleration

To use GPU acceleration with Ollama:

1. Install CUDA and cuDNN
2. Configure Ollama to use GPU
3. Verify GPU usage:
   ```bash
   nvidia-smi
   ```

### Multiple Development Environments

For working with multiple configurations:

```bash
# Create environment-specific .env files
cp .env .env.dev
cp .env .env.test

# Use a specific environment
export ENV_FILE=.env.dev
python -m localknowledge.ui.main
```

## Next Steps

After setting up your development environment:

1. Familiarize yourself with the codebase
2. Run the application and explore its features
3. Check the issue tracker for tasks to work on
4. Read the contributing guidelines
