# Frequently Asked Questions

Common questions and answers about LocalKnowledge.

## General Questions

### What is LocalKnowledge?

LocalKnowledge is a desktop application for building and searching a personal medical literature database. It downloads articles from PubMed and medRxiv, stores them locally, and provides AI-powered semantic search and document evaluation.

### Who is LocalKnowledge for?

- Medical researchers conducting literature reviews
- Healthcare professionals staying current with research
- Graduate students managing research literature
- Anyone who needs to organize and search medical publications

### Is LocalKnowledge free?

Yes, LocalKnowledge is open-source software. However, you'll need:
- A computer capable of running it
- Storage space for the database
- Internet connection for downloading data
- (Optional) Powerful hardware for AI features

### What data sources does it support?

Currently:
- **PubMed** - Full MEDLINE database (~35 million citations)
- **medRxiv** - Health sciences preprints

Future sources may be added.

### Do I need internet access?

- **For setup:** Yes, to download data and AI models
- **For daily use:** No, everything runs locally
- **For updates:** Yes, to fetch new publications

## Installation Questions

### What are the system requirements?

- **OS:** Windows 10+, macOS 11+, or Linux
- **Python:** 3.12 or higher
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** 10GB minimum, 200GB+ for full database
- **Database:** PostgreSQL 14+ with pgvector

### How much disk space do I need?

Varies based on your needs:
- Minimal (recent papers only): ~10GB
- Moderate (5 years of data): ~50GB
- Full PubMed baseline: ~200GB+

### Can I use it without AI features?

Yes. You can use keyword search without embeddings. However, semantic search and document evaluation require Ollama.

### Does it work on ARM Macs (M1/M2/M3)?

Yes, LocalKnowledge works on Apple Silicon Macs. Ollama has native ARM support.

## Usage Questions

### How do I search effectively?

- Use natural language questions for semantic search
- Enable HyDE for research questions
- Use specific medical terminology
- See [Search Guide](search-guide.md) for detailed tips

### What's the difference between semantic search and keyword search?

- **Keyword search:** Finds exact words and their variations
- **Semantic search:** Finds documents with similar meaning

Semantic search can find relevant documents even if they use different terminology.

### What is HyDE?

HyDE (Hypothetical Document Embeddings) is an advanced search technique. The AI generates a hypothetical document that would answer your question, then searches for real documents similar to that hypothetical answer.

### How accurate is document evaluation?

AI evaluation is helpful for initial screening but shouldn't replace human judgment. Think of ratings as suggestions. We recommend:
- Using AI to quickly identify promising documents
- Manually reviewing documents rated 2-3
- Adjusting ratings based on your expertise

### Can I evaluate documents manually?

Yes. You can:
- Override AI ratings
- Rate documents without AI
- Add your own notes and categories

### How do I keep my database updated?

Run update commands regularly:
```bash
# PubMed (weekly)
python -m localknowledge.pubmed.async_download_cli --download-updates

# medRxiv (daily)
python -m localknowledge.medrxiv.medrxiv_daily_update
```

Or set up automated scheduling (see [Data Management](data-management.md)).

## Data Questions

### Where is my data stored?

- **Database:** PostgreSQL (configurable location)
- **PDFs:** PDF_BASE_DIR (default: ~/knowledgebase/pdf)
- **Configuration:** .env file in project directory

### Is my data private?

Yes. Everything runs locally on your computer. No data is sent to external servers (unless you choose to use remote MCP connections).

### Can I backup my work?

Yes. Important data to backup:
- PostgreSQL database (evaluations, projects)
- .env configuration file
- PDF files (if you want to preserve them)

### Can I share my database?

The database can be exported and shared, but it's quite large. For sharing:
- Export specific projects
- Share evaluation data as CSV
- Document references as BibTeX

### What happens if I lose my database?

- Documents can be re-downloaded
- Embeddings can be regenerated
- Evaluations and projects would be lost (backup recommended)

## AI Questions

### What AI models does LocalKnowledge use?

By default:
- **Embeddings:** snowflake-arctic-embed2 (via Ollama)
- **Evaluation:** gemma3:4b (via Ollama)

You can configure different Ollama models in settings.

### Does it use ChatGPT or Claude?

Not by default. LocalKnowledge uses Ollama for local AI. However, you can:
- Use the MCP server with Claude
- Configure other LLM providers (advanced)

### Is an API key required?

No, not for standard use. Ollama runs locally without API keys. OpenAI keys are only needed if you choose to use OpenAI models.

### How much RAM do AI models need?

- **Embedding models:** ~2-4GB
- **Language models (4b):** ~4-6GB
- **Larger models (7b+):** ~8-16GB

### Can I use a GPU?

Ollama automatically uses NVIDIA GPUs if available. This significantly speeds up embedding generation and evaluation.

## Integration Questions

### Can I use LocalKnowledge with Claude?

Yes! The MCP server allows Claude to search your database during conversations. See [MCP Integration](mcp-integration.md).

### Can I export to reference managers?

Yes, you can export to:
- BibTeX (for LaTeX/Zotero)
- RIS (for EndNote)
- CSV (for spreadsheets)

### Does it integrate with Zotero/Mendeley?

Not directly, but you can:
- Export BibTeX and import to Zotero
- Export RIS and import to Mendeley
- Copy citations in various formats

### Can I access it from multiple computers?

The database can be accessed from multiple computers if you:
- Run PostgreSQL on a server
- Configure network access properly
- Be aware of security implications

## Troubleshooting Questions

### Why is search slow?

Common causes:
- Ollama not running
- Too many results requested
- Database needs optimization

See [Troubleshooting](troubleshooting.md) for solutions.

### Why am I getting no results?

Possible reasons:
- Database is empty (need to import data)
- No embeddings (need to generate)
- Threshold too high (lower it)

### The application crashed. What do I do?

1. Restart the application
2. Check error messages
3. Verify database connection
4. See [Troubleshooting](troubleshooting.md)

### Embeddings are taking forever

This is normal for large databases. Tips:
- Let it run overnight
- Use a smaller model
- Process in batches
- It can be stopped and resumed

## Feature Questions

### Is there a web interface?

Currently, LocalKnowledge is a desktop application. A web interface may be developed in the future.

### Can I add my own documents?

Currently, LocalKnowledge imports from PubMed and medRxiv. Custom document import may be added in future versions.

### Can I annotate PDFs?

Not currently within LocalKnowledge. You can:
- Open PDFs in external viewers
- Add notes to documents in projects
- Use evaluation fields for annotations

### Is there collaboration support?

Projects are currently single-user. For collaboration:
- Export and share project data
- Each user maintains their own database
- Team sharing features may come in future versions

### What about full-text search?

- Semantic search: Works on abstracts
- Full-text: Available for documents with full text
- PDF content: Converted to searchable markdown

## Getting More Help

### Where can I find more documentation?

- This user manual
- [CONTRIBUTING.md](../../CONTRIBUTING.md) for developers
- [DEVELOPERS.md](../../DEVELOPERS.md) for technical details
- GitHub repository for latest updates

### How do I report bugs?

1. Check if issue exists on GitHub
2. Gather information (error messages, steps to reproduce)
3. Open a new issue with details

### How can I request features?

Open a feature request issue on GitHub with:
- Description of the feature
- Use case explanation
- How it would help your workflow

### Can I contribute?

Yes! LocalKnowledge is open source. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

---

Previous: [Troubleshooting](troubleshooting.md) | [Back to Index](index.md)
