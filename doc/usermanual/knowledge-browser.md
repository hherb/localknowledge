# Knowledge Browser

The Knowledge Browser is the main interface for searching, browsing, and exploring your medical literature database.

## Overview

The Knowledge Browser provides:
- Semantic search across all documents
- Document viewing with abstracts and metadata
- PDF viewing for full-text documents
- Quick access to document evaluation
- Integration with research projects

## Interface Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Search Bar                                    [Settings] [HyDE] │
├───────────────────────┬──────────────────────────────────────────┤
│                       │                                          │
│   Search Results      │       Document View                      │
│   (Document List)     │       (Abstract/PDF)                     │
│                       │                                          │
│   • Result 1          │   Title: Document Title                  │
│   • Result 2          │   Authors: Smith J, et al.               │
│   • Result 3          │   Journal: Nature Medicine               │
│   • Result 4          │                                          │
│   • ...               │   Abstract:                              │
│                       │   Lorem ipsum dolor sit amet...          │
│                       │                                          │
├───────────────────────┴──────────────────────────────────────────┤
│  Status Bar                                                      │
└──────────────────────────────────────────────────────────────────┘
```

## Search Bar

### Basic Search

Type your query and press Enter or click Search:

```
What are the effects of statins on cardiovascular mortality?
```

### Search Options

| Option | Description |
|--------|-------------|
| **HyDE** | Enable Hypothetical Document Embeddings |
| **Max Results** | Limit number of results (default: 50) |
| **Threshold** | Minimum similarity score (0.0-1.0) |
| **Reranking** | Use AI to rerank results |

### Search Settings

Click the Settings icon to configure:
- **Embedding Model** - Select which model to use for search
- **Default Threshold** - Set your preferred minimum similarity
- **Result Limit** - Default number of results

## Search Results Panel

### Result List

Each search result displays:
- **Source Badge** - PubMed (blue) or medRxiv (orange)
- **Title** - Document title (click to view)
- **Authors** - First author and "et al."
- **Date** - Publication date
- **Similarity** - Match percentage (higher = better match)

### Sorting Results

Results are sorted by:
1. **Similarity** (default) - Best matches first
2. **Date** - Most recent first
3. **Title** - Alphabetically

Click column headers to change sort order.

### Filtering Results

Use the filter bar to narrow results:
- **Date Range** - Filter by publication date
- **Source** - Show only PubMed or medRxiv
- **Has PDF** - Show only documents with full text

## Document View Panel

### Abstract View

When you select a document:

**Header**
- Title in large text
- Authors with affiliations
- Journal/Publication name
- Publication date

**Abstract**
- Full abstract text
- Keywords (if available)

**Metadata**
- DOI with clickable link
- PMID (for PubMed articles)
- External links

### PDF View

For documents with full text:
- Click "View PDF" tab
- Navigate pages with arrows or page input
- Zoom controls for comfortable reading
- Search within PDF

### Document Actions

| Button | Action |
|--------|--------|
| **Evaluate** | Open evaluation dialog |
| **Add to Project** | Save to a project |
| **Copy Citation** | Copy formatted citation |
| **Open External** | Open in browser |
| **Download PDF** | Download if available |

## Working with Documents

### Evaluating a Document

1. Click **Evaluate** button
2. Enter your research question
3. Click **Evaluate**
4. Review AI rating and explanation
5. Adjust rating if needed
6. Save evaluation

### Adding to a Project

1. Click **Add to Project**
2. Select project from dropdown
3. Optionally add notes
4. Click **Add**

The document is now saved to your project for later reference.

### Copying Citations

Click **Copy Citation** to copy in various formats:
- **APA** - American Psychological Association
- **MLA** - Modern Language Association
- **Vancouver** - Medical/scientific format
- **BibTeX** - For LaTeX documents

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` / `Cmd+F` | Focus search bar |
| `Enter` | Execute search |
| `Escape` | Clear search |
| `↑` / `↓` | Navigate results |
| `Enter` (on result) | Select document |
| `Ctrl+E` / `Cmd+E` | Evaluate selected |
| `Ctrl+P` / `Cmd+P` | Add to project |
| `Ctrl+C` / `Cmd+C` | Copy citation |

## Tips for Effective Browsing

### Finding Relevant Documents

1. **Start Broad** - Begin with a general query
2. **Review Top Results** - Check the most similar matches
3. **Refine Query** - Add specifics based on what you find
4. **Use HyDE** - Enable for research questions

### Efficient Review

1. **Skim Abstracts** - Read the first sentence of each abstract
2. **Check Methods** - Look for study design in the abstract
3. **Note Sample Size** - Larger studies often more reliable
4. **Mark Promising Docs** - Add to project for later review

### Managing Large Result Sets

When you get too many results:
1. **Increase Threshold** - Set to 0.6 or higher
2. **Add Keywords** - Make your query more specific
3. **Use Date Filter** - Focus on recent publications
4. **Enable Reranking** - AI will prioritize best matches

## Customizing the Interface

### Adjusting Panel Sizes

- **Drag the divider** between panels to resize
- **Double-click divider** to reset to default

### View Options

Access from the menu:
- **Compact View** - Show more results, less detail
- **Detailed View** - Full information per result
- **PDF Default** - Open PDF automatically when available

### Saving Layout

Your panel sizes and view preferences are saved automatically.

## Troubleshooting

### No Search Results

- Check that your database has documents
- Lower the similarity threshold
- Try a different query formulation
- Ensure embeddings are generated

### Slow Search

- Reduce max results
- Check Ollama is running
- Consider indexing if database is large

### PDF Not Showing

- Verify PDF file exists
- Check PDF_BASE_DIR setting
- Try downloading the PDF again

---

Previous: [Getting Started](getting-started.md) | Next: [Search Guide](search-guide.md)
