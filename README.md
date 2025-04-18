# LocalKnowledge

A Python library for local PubMed and medRxiv database access. This library enables users to:

- Create and maintain a local copy of PubMed and medRxiv articles
- Perform efficient searches on the local database
- Retrieve specific articles by ID
- Keep the local database updated with new publications

## Installation

```bash
pip install localknowledge
```

Or from source:

```bash
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge
pip install -e .
```

## Requirements

- Python 3.12 or higher
- Dependencies listed in pyproject.toml

## Usage

### PubMed Access

```python
from localknowledge.pubmed import PubMedClient

# Initialize the client
pubmed = PubMedClient()

# Search for articles
results = pubmed.search("covid AND treatment", max_results=100)
for article in results:
    print(f"{article.title} - {article.authors} ({article.year})")

# Get a specific article
article = pubmed.get_article("12345678")

# Download updates
new_articles = pubmed.download_updates(from_date="2023-01-01")
print(f"Added {new_articles} new articles to the database")
```

### medRxiv Access

```python
from localknowledge.medrxiv import MedRxivClient

# Initialize the client
medrxiv = MedRxivClient()

# Search for preprints
results = medrxiv.search("vaccine efficacy", max_results=50)
for preprint in results:
    print(f"{preprint.title} - {preprint.authors} ({preprint.date})")

# Get a specific preprint
preprint = medrxiv.get_article("10.1101/2023.01.01.12345")

# Download updates
new_preprints = medrxiv.download_updates(from_date="2023-01-01")
print(f"Added {new_preprints} new preprints to the database")
```

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/yourusername/localknowledge.git
cd localknowledge
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

## License

MIT
