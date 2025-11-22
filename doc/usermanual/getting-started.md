# Getting Started

This guide will help you take your first steps with LocalKnowledge after installation.

## Launching LocalKnowledge

Start the application from the command line:

```bash
python -m localknowledge.ui.pyside6_main_window
```

The main window will appear with several components:
- **Plugin Selector** on the left sidebar
- **Main Content Area** in the center
- **Status Bar** at the bottom

## The Main Interface

LocalKnowledge uses a plugin-based interface. The main plugins are:

| Plugin | Purpose |
|--------|---------|
| **Knowledge Browser** | Search and browse documents |
| **News Browser** | Discover new preprints |
| **Document Evaluator** | Evaluate document relevance |
| **Project Manager** | Organize research projects |
| **Chat Interface** | Interactive AI chat |

Click on a plugin in the sidebar to switch views.

## Your First Search

Let's perform your first search:

1. **Open Knowledge Browser** - Click on "Knowledge Browser" in the sidebar
2. **Enter a Query** - Type a research question in the search box, for example:
   > "What are the cardiovascular effects of COVID-19?"
3. **Click Search** - Press Enter or click the Search button
4. **View Results** - Browse the list of matching documents

### Understanding Search Results

Each result shows:
- **Title** - Document title
- **Authors** - Author names
- **Source** - PubMed or medRxiv badge
- **Date** - Publication date
- **Similarity** - How closely it matches your query (0-100%)

Click on any result to view the full abstract.

## Reading a Document

When you click on a search result:

1. **Abstract Panel** - Shows the full abstract
2. **Metadata** - Authors, journal, publication date, DOI
3. **PDF Viewer** - If available, view the full PDF

### Actions You Can Take

- **Copy Citation** - Copy formatted citation to clipboard
- **Open in Browser** - Open the original publication
- **Evaluate** - Rate the document's relevance
- **Add to Project** - Save to a research project

## Trying Different Search Types

LocalKnowledge offers multiple search methods:

### Semantic Search
The default search mode. Enter natural language queries:
> "treatments for diabetic neuropathy"

### Hybrid Search
Combines semantic search with HyDE for better results. Enable by checking "Use HyDE" option:
> "How effective is metformin for Type 2 diabetes management?"

### Keyword Search
For traditional keyword matching, use quotes:
> "metformin" AND "diabetes"

## Creating Your First Project

Organize your research with projects:

1. **Open Project Manager** - Click "Project Manager" in the sidebar
2. **Create New Project** - Click the "New Project" button
3. **Enter Details**:
   - **Title**: Your research topic
   - **Description**: Brief description of your research goals
4. **Save Project** - Click "Create"

### Adding Documents to a Project

From the Knowledge Browser:
1. Find a relevant document
2. Click "Add to Project" button
3. Select your project from the dropdown

## Evaluating Documents

Use AI-powered evaluation to assess relevance:

1. **Search** for documents related to your research question
2. **Select a Document** from the results
3. **Click "Evaluate"** button
4. **Enter Your Research Question** in the dialog
5. **View Rating** - AI provides a 0-3 rating with explanation

### Understanding Ratings

| Rating | Meaning |
|--------|---------|
| **0** | Not relevant to your question |
| **1** | Somewhat relevant, tangential |
| **2** | Very relevant, should cite |
| **3** | Essential, must include |

## Keeping Your Database Updated

To get the latest publications:

### Update PubMed (Weekly Recommended)

```bash
python -m localknowledge.pubmed.async_download_cli --download-updates
```

### Update medRxiv (Daily Recommended)

```bash
python -m localknowledge.medrxiv.medrxiv_daily_update
```

> **Tip**: Set up a cron job or scheduled task to automate these updates.

## Quick Tips

### Better Search Results

1. **Be Specific** - "COVID-19 mRNA vaccine efficacy in elderly patients" works better than "COVID vaccine"
2. **Ask Questions** - "What causes diabetic retinopathy?" often returns better results than keywords
3. **Use HyDE** - Enable hybrid search for complex research questions

### Efficient Workflow

1. **Create Projects First** - Set up your project before searching
2. **Evaluate As You Go** - Rate documents while reviewing them
3. **Use Keyboard Shortcuts** - Press Enter to search, Escape to clear

### Managing Large Results

1. **Increase Threshold** - Raise similarity threshold for more relevant results
2. **Limit Results** - Set a reasonable limit (20-50) for manageable review
3. **Sort by Date** - Focus on recent publications when relevant

## What's Next?

Now that you know the basics, explore more advanced features:

- [Knowledge Browser](knowledge-browser.md) - Deep dive into browsing features
- [Search Guide](search-guide.md) - Master advanced search techniques
- [Document Evaluation](document-evaluation.md) - Efficient relevance assessment
- [Project Management](project-management.md) - Organize complex research

## Getting Help

If you're stuck:
- Check the [Troubleshooting](troubleshooting.md) guide
- Review the [FAQ](faq.md)
- Look at specific feature guides in this manual

---

Previous: [Installation Guide](installation.md) | Next: [Knowledge Browser](knowledge-browser.md)
