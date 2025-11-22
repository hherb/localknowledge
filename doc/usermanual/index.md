# LocalKnowledge User Manual

Welcome to LocalKnowledge, your personal medical literature research assistant. This manual will help you get started and make the most of LocalKnowledge's powerful features.

## What is LocalKnowledge?

LocalKnowledge is a desktop application that helps medical researchers and healthcare professionals:

- **Build a personal medical literature database** from PubMed and medRxiv
- **Search intelligently** using AI-powered semantic search
- **Evaluate documents** for relevance to your research questions
- **Organize research** into projects
- **Integrate with AI assistants** like Claude for enhanced research workflows

## Table of Contents

### Getting Started
1. [Installation Guide](installation.md) - Set up LocalKnowledge on your system
2. [Getting Started](getting-started.md) - Your first steps with LocalKnowledge

### Using LocalKnowledge
3. [Knowledge Browser](knowledge-browser.md) - Browse and search your document library
4. [Search Guide](search-guide.md) - Master semantic and hybrid search
5. [Document Evaluation](document-evaluation.md) - AI-powered relevance assessment
6. [Project Management](project-management.md) - Organize your research

### Advanced Features
7. [MCP Integration](mcp-integration.md) - Use LocalKnowledge with Claude and other AI assistants
8. [Data Management](data-management.md) - Import, update, and maintain your database

### Help
9. [Troubleshooting](troubleshooting.md) - Common issues and solutions
10. [FAQ](faq.md) - Frequently asked questions

## Quick Start

If you're eager to get started, here's the fastest path:

1. **Install** - Follow the [Installation Guide](installation.md)
2. **Launch** - Start the desktop application
3. **Search** - Enter a research question in the Knowledge Browser
4. **Explore** - Click on results to read abstracts and full text

## Key Features at a Glance

### Semantic Search
Find documents by meaning, not just keywords. Ask questions like "What are the effects of aspirin on cardiovascular outcomes?" and get relevant results even if they don't contain your exact words.

### Hybrid Search with HyDE
Combines traditional semantic search with Hypothetical Document Embeddings (HyDE) for even better results. The system generates a hypothetical answer to your question and uses it to find similar real documents.

### AI-Powered Evaluation
Let AI help you evaluate document relevance. Rate documents on a 0-3 scale:
- **0** - Not relevant
- **1** - Somewhat relevant
- **2** - Very relevant, should cite
- **3** - Essential, must include

### Research Projects
Organize your work into projects. Save searches, track evaluations, and keep your research organized.

### Claude Integration
Use LocalKnowledge as a tool for Claude Desktop, allowing Claude to search your personal medical literature database during conversations.

## System Requirements

- **Operating System**: Windows 10+, macOS 11+, or Linux
- **Python**: 3.12 or higher
- **Database**: PostgreSQL 14+ with pgvector extension
- **AI Models**: Ollama (for local AI features)
- **Memory**: 8GB RAM minimum, 16GB recommended
- **Storage**: Depends on your database size (10GB+ for full PubMed)

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](troubleshooting.md) guide
2. Review the [FAQ](faq.md)
3. Search existing issues on GitHub
4. Open a new issue at the project repository

## Document Conventions

Throughout this manual:

- `Code formatting` indicates commands or code
- **Bold text** highlights important concepts
- *Italic text* indicates emphasis or new terms
- > Blockquotes provide tips and notes

> **Tip**: Look for tip boxes like this one for helpful suggestions!

---

Next: [Installation Guide](installation.md)
