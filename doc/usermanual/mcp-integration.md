# MCP Integration

LocalKnowledge includes a Model Context Protocol (MCP) server that allows AI assistants like Claude to search your personal medical literature database during conversations.

## What is MCP?

The Model Context Protocol (MCP) is a standard that allows AI assistants to use external tools and data sources. With LocalKnowledge's MCP server:

- Claude can search your PubMed and medRxiv documents
- You can ask research questions and get answers backed by your library
- The AI can retrieve full text and document details

## Setting Up MCP

### Prerequisites

- LocalKnowledge installed and configured
- Database populated with documents
- Claude Desktop (or other MCP-compatible client)

### Starting the MCP Server

#### Option 1: stdio Transport (Recommended for Claude Desktop)

```bash
python mcp_server/localknowledge_mcp_server.py
```

The server starts and waits for connections via standard input/output.

#### Option 2: SSE Transport (For Remote Connections)

```bash
python mcp_server/localknowledge_mcp_server.py --transport sse --port 8080
```

Server runs on http://localhost:8080 and supports multiple clients.

### Configuring Claude Desktop

#### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "localknowledge": {
      "command": "python",
      "args": ["/full/path/to/localknowledge/mcp_server/localknowledge_mcp_server.py"],
      "env": {
        "POSTGRES_DB": "localknowledge",
        "POSTGRES_USER": "your_username",
        "POSTGRES_PASSWORD": "your_password",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432"
      }
    }
  }
}
```

#### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json` with the same structure.

#### Linux

Edit `~/.config/Claude/claude_desktop_config.json`.

### Verifying the Connection

After configuring:

1. **Restart Claude Desktop** completely
2. **Start a new conversation**
3. **Ask Claude** to search your database:
   > "Search my local PubMed database for papers about COVID-19 vaccines"
4. **Verify** Claude returns results from your database

## Available MCP Tools

LocalKnowledge provides three tools to Claude:

### 1. search_pubmed_by_keywords

Search your document database by keywords.

**Parameters:**
- `text` (string): Search query with optional boolean operators

**Returns:**
- List of matching documents with ID, DOI, title, and abstract

**Example prompts:**
```
"Search my PubMed database for papers about diabetes and metformin"
"Find articles in my library about cardiovascular outcomes in COVID-19"
"Look for systematic reviews about SGLT2 inhibitors"
```

### 2. get_document_details

Retrieve full metadata for a specific document.

**Parameters:**
- `document_id` (integer): The database ID of the document

**Returns:**
- Complete document details including authors, journal, date, abstract

**Example prompts:**
```
"Get me the full details for document 12345"
"Show me more information about that first result"
```

### 3. get_full_text

Get the full text content of a document.

**Parameters:**
- `document_id` (integer): The database ID of the document
- `only_md` (boolean): Whether to return only markdown (default: true)

**Returns:**
- Full text in markdown format, PDF URL, and local PDF path

**Example prompts:**
```
"Retrieve the full text of document 12345"
"Show me the complete paper for that study"
```

## Using MCP with Claude

### Research Conversations

Example conversation with Claude:

**You:** I'm researching the effects of SGLT2 inhibitors on heart failure. Can you search my database and summarize what I have?

**Claude:** I'll search your LocalKnowledge database for relevant papers.

*[Claude uses search_pubmed_by_keywords]*

Based on your database, I found 47 papers related to SGLT2 inhibitors and heart failure. Here are the key findings...

**You:** Tell me more about the EMPEROR-Reduced trial if I have it.

**Claude:** Let me search for that specific trial.

*[Claude searches and retrieves document]*

The EMPEROR-Reduced trial (document #1234) in your database shows...

### Literature Review Assistance

**You:** Help me identify key papers for my systematic review on anticoagulation duration after PE.

**Claude:** I'll search your database for relevant studies.

*[Claude performs multiple searches]*

I found several relevant papers. Here's a summary organized by study type:

**Randomized Controlled Trials:**
1. [Study 1 summary]
2. [Study 2 summary]

**Meta-analyses:**
1. [Meta-analysis summary]

Would you like me to get the full text of any of these?

### Quick Reference Lookup

**You:** What do I have in my database about appropriate antibiotic duration for community-acquired pneumonia?

**Claude:** *[Searches database]*

You have 12 papers on this topic. The most relevant appears to be...

## Tips for Effective MCP Use

### Good Prompts

```
"Search my database for..." - Clear intent to use your local database
"What papers do I have about..." - Indicates local search
"Find in my library..." - Explicit about local search
"Can you look up document #123..." - Specific document request
```

### Less Effective Prompts

```
"What is X?" - Claude may use general knowledge instead
"Tell me about..." - Ambiguous about data source
"Search for..." - May not trigger MCP tool use
```

### Getting Better Results

1. **Be specific** about wanting to search YOUR database
2. **Use medical terminology** for better matches
3. **Ask follow-up questions** to drill into specific papers
4. **Request full text** when you need details

## Troubleshooting MCP

### Claude Doesn't Use LocalKnowledge

**Symptoms:**
- Claude answers from general knowledge
- No indication of database search

**Solutions:**
1. Restart Claude Desktop after config changes
2. Check config file syntax (valid JSON)
3. Verify server path is correct
4. Test server manually first

### Connection Errors

**Symptoms:**
- Error messages about connection
- Server not responding

**Solutions:**
1. Verify database is running
2. Check environment variables
3. Test database connection manually
4. Check firewall settings

### Empty Results

**Symptoms:**
- Search returns nothing
- Known documents not found

**Solutions:**
1. Verify database has documents
2. Check search syntax
3. Try broader search terms
4. Ensure embeddings are generated

### Server Won't Start

**Symptoms:**
- Python errors on startup
- Missing dependencies

**Solutions:**
1. Verify Python environment
2. Install missing packages
3. Check database credentials
4. Review error messages

## Advanced MCP Configuration

### Multiple Databases

Configure access to different databases:

```json
{
  "mcpServers": {
    "localknowledge-main": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "POSTGRES_DB": "localknowledge"
      }
    },
    "localknowledge-archive": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "POSTGRES_DB": "localknowledge_archive"
      }
    }
  }
}
```

### Custom Port (SSE)

For remote or custom setups:

```json
{
  "mcpServers": {
    "localknowledge": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Logging

Enable verbose logging for debugging:

```bash
# Set log level
export LOG_LEVEL=DEBUG
python mcp_server/localknowledge_mcp_server.py
```

## Security Considerations

### Local Use Only (Recommended)

The stdio transport keeps everything local:
- No network exposure
- Data stays on your machine
- Credentials in config file

### Network Use (SSE)

If using SSE transport:
- Only bind to localhost unless necessary
- Use firewall rules
- Consider authentication
- Encrypt if remote

### Credential Security

- Store credentials in environment variables
- Don't commit config files with passwords
- Use OS credential storage when available

## Use Cases

### Daily Research

Start your day:
1. Ask Claude what's new in your database
2. Get summaries of recently added papers
3. Plan which papers to read

### Writing Support

While writing:
1. Ask Claude to find supporting citations
2. Get specific quotes from full text
3. Verify claims against your literature

### Meeting Preparation

Before meetings:
1. Search for relevant background
2. Get quick summaries
3. Find key references to share

### Teaching

For education:
1. Find example papers for concepts
2. Get accessible explanations
3. Build reading lists

---

Previous: [Project Management](project-management.md) | Next: [Data Management](data-management.md)
