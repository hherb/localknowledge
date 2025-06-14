# LocalKnowledge MCP Server

This is a Model Context Protocol (MCP) server that provides access to the local PubMed and MedRxiv document database. It allows AI assistants and other clients to search and retrieve documents from your local knowledge base.

## Features

The server provides three main tools:

1. **search_pubmed_by_keywords**: Search documents using boolean keyword expressions
2. **get_document_details**: Get detailed information about a specific document
3. **get_full_text**: Retrieve the full text content of a document

## Installation

Make sure you have the required dependencies installed:

```bash
pip install mcp fastmcp psycopg2-binary
```

## Usage

### Starting the Server

Run the server with default settings (stdio transport):

```bash
python localknowledge_mcp_server.py
```

Or run with SSE transport for web clients:

```bash
python localknowledge_mcp_server.py --transport sse --host 0.0.0.0 --port 8080
```

**Note**: Most MCP clients use stdio transport, so the default is recommended.

### Search Syntax

The search function supports PostgreSQL full-text search syntax:

- **AND operator**: `covid & vaccine`
- **OR operator**: `covid | coronavirus`
- **Grouping**: `(covid | coronavirus) & vaccine`
- **Exact phrases**: `"optic nerve sheath diameter"`
- **Complex expressions**: `(ONSD | "optic nerve sheath diameter") & ultrasound & (ICP | "intracranial pressure")`

### Example Usage

#### Search for Documents

```python
# Search for COVID vaccine papers
results = search_pubmed_by_keywords("covid & vaccine")

# Search with boolean operators
results = search_pubmed_by_keywords("(covid | coronavirus) & (vaccine | vaccination)")

# Search for exact phrases
results = search_pubmed_by_keywords('"machine learning" & "medical imaging"')
```

#### Get Document Details

```python
# Get details for a specific document
details = get_document_details(12345)
print(f"Title: {details.title}")
print(f"Authors: {details.authors}")
print(f"DOI: {details.doi}")
```

#### Get Full Text

```python
# Get full text content
full_text = get_full_text(12345)
print(f"Content: {full_text.markdown}")
print(f"PDF URL: {full_text.pdf_url}")
```

## Data Classes

### ReferenceItem
- `document_id`: Internal database ID
- `doi`: Document DOI or external ID
- `title`: Document title
- `abstract`: Document abstract

### DocumentDetails
- `document_id`: Internal database ID
- `doi`: Document DOI
- `pmid`: PubMed ID (if available)
- `title`: Document title
- `abstract`: Document abstract
- `authors`: List of authors
- `journal`: Publication journal
- `publication_date`: Publication date
- `url`: Document URL

### FullText
- `markdown`: Full text content in markdown format
- `pdf_url`: URL to PDF file
- `pdf_path`: Local path to PDF file

## Database Requirements

The server requires a PostgreSQL database with the following:

1. A `document` table with the required columns
2. A `search_vector` column with full-text search index
3. Proper database connection configuration in your environment

## Environment Setup

Make sure your database connection is properly configured. The server uses the `localknowledge.db.connection_pool` module for database access.

## Testing

Several test scripts are provided to verify functionality:

### 1. Direct Function Testing
Tests the server functions directly (without MCP protocol):
```bash
python test_mcp_server.py
```

### 2. Proper MCP Client Testing (Recommended)
Tests using the official MCP Python library with stdio transport:
```bash
pip install mcp
python proper_mcp_client_test.py
```

### 3. MCP Testing with Environment Setup
Automatically sets up database environment variables and runs MCP test:
```bash
python test_with_env.py
```

### 4. Environment Setup
Set up database environment variables:
```bash
# Option 1: Use the setup script
source setup_env.sh

# Option 2: Set manually
export POSTGRES_DB="your_database_name"
export POSTGRES_USER="your_username"
export POSTGRES_PASSWORD="your_password"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
```

### 5. Legacy HTTP Testing (for SSE transport)
Tests using direct HTTP requests (requires server running with `--transport sse`):
```bash
pip install requests
python simple_test_client.py
```

### 6. Command Line Testing
Tests using curl commands:
```bash
chmod +x test_with_curl.sh
./test_with_curl.sh
```

## Troubleshooting

1. **Database Connection Issues**: Ensure your PostgreSQL database is running and connection parameters are correct
2. **Search Returns No Results**: Check that your `search_vector` column is properly populated and indexed
3. **Import Errors**: Make sure the `localknowledge` package is in your Python path

## MCP Client Configuration

To use this server with an MCP client, configure it to connect to:
- Transport: Server-Sent Events (SSE)
- URL: `http://localhost:8080` (or your configured host/port)

The server will automatically expose the three tools to any connected MCP client.
