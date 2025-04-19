# MedRxiv to Markdown Converter

A Python tool for fetching preprints from medRxiv in HTML or XML format, converting them to Markdown, and downloading associated images.

## Features

- Fetches preprints from medRxiv in PDF, HTML, and XML formats
- Uses the official medRxiv API to reliably locate XML documents
- Supports multiple DOI formats and handles various input format issues
- Converts both HTML and XML content to clean Markdown
- Downloads and stores all images locally (only when images are present)
- Handles tables and document structure properly

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/medrxiv-to-markdown.git
   cd medrxiv-to-markdown
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   Or install them manually:
   ```bash
   pip install requests beautifulsoup4 markdownify lxml
   ```

## Usage

### Basic Usage

To convert a medRxiv preprint to Markdown:

```bash
python medrxiv_to_markdown.py 10.1101/2023.01.15.23284593
```

The script is flexible with DOI formats and accepts:

```bash
# Full DOI
python medrxiv_to_markdown.py 10.1101/2023.01.15.23284593

# Just the ID portion
python medrxiv_to_markdown.py 2023.01.15.23284593

# DOI with underscores instead of slashes
python medrxiv_to_markdown.py 10.1101_2023.01.15.23284593
```

### Output Options

You can specify custom output directories:

```bash
python medrxiv_to_markdown.py 10.1101/2023.01.15.23284593 --output-dir ./papers --image-dir images
```

By default:
- Markdown files are saved to `./output/`
- Images are saved to `./output/assets/[article_id]/` (only if images are present)

### Format Preference

The tool tries to get the HTML version first, and if not available, falls back to the XML version. Both are converted to Markdown with images saved locally.

## How It Works

1. **DOI Handling**: The tool normalizes DOI formats, handling underscores, missing prefixes, etc.
2. **API Integration**: Uses the medRxiv API to get accurate metadata including the exact XML URL
3. **Format Selection**: Attempts to download HTML first, then XML if HTML isn't available
4. **Multiple Fallbacks**: If the API fails, tries direct URL construction based on known patterns
5. **Conversion**: 
   - HTML is directly converted to Markdown using markdownify
   - XML is first converted to HTML, then to Markdown
6. **Smart Image Handling**: Only creates image directories when images are actually present

## Requirements

- Python 3.6+
- requests
- beautifulsoup4
- markdownify
- lxml (required for XML parsing)

## Advanced Usage

### Using the MedRxivFetcher Module

You can use the MedRxivFetcher module directly in your Python code:

```python
from medrxiv_fetcher import MedRxivFetcher

fetcher = MedRxivFetcher(output_dir="./downloads")

# Search for preprints
preprints = fetcher.search("machine learning COVID", max_results=5)

# Check format availability
availability = fetcher.check_format_availability("10.1101/2023.01.15.23284593")
print(availability)  # {'pdf': True, 'html': True, 'xml': True}

# Download specific formats
downloaded = fetcher.download_preprint("10.1101/2023.01.15.23284593", formats=["xml"])
```

### Using the MedRxivMarkdownConverter

```python
from medrxiv_to_markdown import MedRxivMarkdownConverter

converter = MedRxivMarkdownConverter(output_dir="./papers", image_dir="figures")
markdown_content, markdown_path, has_images = converter.convert_doi_to_markdown("10.1101/2023.01.15.23284593")

if has_images:
    print("Document contains images")
```

## Troubleshooting

- **XML Parsing Errors**: If you see "Failed to convert XML to HTML" errors, make sure you have installed the lxml library.
- **DOI Format Issues**: The tool now handles various DOI input formats including those with underscores instead of slashes.
- **API Not Finding the DOI**: For very recent papers, the API might not have indexed them yet. The tool will fall back to direct URL construction.

## Notes

- MedRxiv's statement that all preprints are available in HTML/XML format is not entirely accurate. Some papers may only be available as PDFs.
- The XML format is more commonly available than HTML for many papers, especially recent ones.
- This tool uses the official medRxiv API to find the correct XML URLs when possible, and falls back to alternative methods when needed.

## License

MIT

