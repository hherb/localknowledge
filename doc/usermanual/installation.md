# Installation Guide

This guide will walk you through installing LocalKnowledge on your system.

## Prerequisites

Before installing LocalKnowledge, ensure you have:

1. **Python 3.12 or higher**
2. **PostgreSQL 14 or higher** with pgvector extension
3. **Ollama** for AI features (embeddings and evaluation)

## Step 1: Install Python

### macOS

```bash
# Using Homebrew
brew install python@3.12
```

Or download from [python.org](https://www.python.org/downloads/)

### Windows

Download and install Python 3.12+ from [python.org](https://www.python.org/downloads/windows/)

> **Important**: Check "Add Python to PATH" during installation

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

## Step 2: Install PostgreSQL

### macOS

```bash
# Using Homebrew
brew install postgresql@14
brew services start postgresql@14

# Install pgvector
brew install pgvector
```

### Windows

1. Download PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/)
2. Run the installer and follow the prompts
3. Remember the password you set for the postgres user

For pgvector on Windows, see [pgvector installation guide](https://github.com/pgvector/pgvector#windows)

### Linux (Ubuntu/Debian)

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install pgvector
sudo apt install postgresql-14-pgvector
```

## Step 3: Create the Database

Connect to PostgreSQL and create the LocalKnowledge database:

```bash
# Connect as postgres user
psql -U postgres
```

```sql
-- Create database
CREATE DATABASE localknowledge;

-- Connect to database
\c localknowledge

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Exit
\q
```

## Step 4: Install Ollama

Ollama provides local AI models for embeddings and document evaluation.

### macOS/Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

Download from [ollama.com/download](https://ollama.com/download)

### Pull Required Models

After installing Ollama, pull the required models:

```bash
# Embedding model (required for search)
ollama pull snowflake-arctic-embed2

# Language model (for document evaluation)
ollama pull gemma3:4b
```

> **Note**: The first time you pull models, it may take several minutes depending on your internet connection.

## Step 5: Install LocalKnowledge

### Option A: Install from Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install LocalKnowledge
pip install -e .

# Install spaCy language model
python -m spacy download en_core_web_sm
```

### Option B: Install via pip

```bash
pip install localknowledge
python -m spacy download en_core_web_sm
```

## Step 6: Configure LocalKnowledge

Create a configuration file in the LocalKnowledge directory:

```bash
# Create .env file
touch .env
```

Edit `.env` with your database credentials:

```bash
# Database Configuration
POSTGRES_DB=localknowledge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Optional: PDF Storage Location
PDF_BASE_DIR=~/knowledgebase/pdf
```

> **Security**: Never share your `.env` file or commit it to version control.

## Step 7: Initialize the Database

Run the database initialization scripts:

```bash
# Create database tables
python -m localknowledge.db.create_baseline_db

# Run any pending migrations
python -m localknowledge.db.migrations_system.run_migrations
```

You should see output indicating successful table creation.

## Step 8: Verify Installation

Test that everything is working:

```bash
# Run the test suite
python run_tests.py --skip-baseline
```

If all tests pass, your installation is complete!

## Step 9: Launch LocalKnowledge

Start the desktop application:

```bash
python -m localknowledge.ui.pyside6_main_window
```

The LocalKnowledge window should appear, ready for use.

## Importing Data

Your database is empty after installation. To populate it with medical literature:

### Import PubMed Articles

```bash
# Download recent PubMed updates
python -m localknowledge.pubmed.async_download_cli

# This may take several hours for the initial download
```

### Import medRxiv Preprints

```bash
# Fetch recent medRxiv preprints
python -m localknowledge.medrxiv.medrxiv_daily_update
```

### Generate Embeddings

After importing documents, generate embeddings for semantic search:

```bash
python update_embeddings_for_abstracts.py
```

> **Note**: Embedding generation can take a long time for large databases. You can stop and resume this process.

## Troubleshooting Installation

### "psycopg2 installation failed"

Install PostgreSQL development files:

```bash
# macOS
brew install libpq

# Ubuntu/Debian
sudo apt install libpq-dev python3-dev

# Then reinstall
pip install psycopg2
```

### "pgvector extension not found"

Ensure pgvector is installed and enabled:

```sql
-- Connect to your database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### "Ollama connection refused"

Start the Ollama service:

```bash
# macOS/Linux
ollama serve

# Or restart it
pkill ollama && ollama serve
```

### "Python version not supported"

Ensure you're using Python 3.12+:

```bash
python --version
# Should show Python 3.12.x or higher
```

## Updating LocalKnowledge

To update to the latest version:

```bash
# If installed from source
cd localknowledge
git pull
pip install -e .

# Run any new migrations
python -m localknowledge.db.migrations_system.run_migrations
```

## Uninstalling

To remove LocalKnowledge:

```bash
# If installed from source
pip uninstall localknowledge
rm -rf /path/to/localknowledge

# Remove database (optional)
psql -U postgres -c "DROP DATABASE localknowledge;"
```

---

Previous: [User Manual Index](index.md) | Next: [Getting Started](getting-started.md)
