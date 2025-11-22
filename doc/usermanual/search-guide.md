# Search Guide

Master LocalKnowledge's powerful search capabilities to find the most relevant medical literature for your research.

## Understanding Search Types

LocalKnowledge offers three main search approaches:

### 1. Semantic Search (Default)

Finds documents by meaning, not just keywords.

**How it works:**
1. Your query is converted to a vector embedding
2. The system finds documents with similar embeddings
3. Results are ranked by semantic similarity

**Best for:**
- Natural language questions
- Conceptual searches
- Finding related work

**Example queries:**
```
What causes insulin resistance in Type 2 diabetes?
treatments for chronic lower back pain
neurological complications of COVID-19
```

### 2. Hybrid Search (HyDE)

Combines semantic search with Hypothetical Document Embeddings for improved results.

**How it works:**
1. AI generates a hypothetical abstract that would answer your question
2. Both your query and the hypothetical abstract are embedded
3. Results combine matches from both approaches
4. Duplicates are merged, keeping highest scores

**Best for:**
- Complex research questions
- When semantic search returns too few results
- Exploratory literature reviews

**Enable HyDE:**
- Check the "Use HyDE" checkbox before searching
- Or enable by default in Settings

**Example queries:**
```
What is the optimal duration of anticoagulation therapy after pulmonary embolism?
How do SGLT2 inhibitors affect kidney function in heart failure patients?
What biomarkers predict response to immunotherapy in lung cancer?
```

### 3. Keyword Search

Traditional keyword matching using PostgreSQL full-text search.

**How it works:**
- Uses PostgreSQL's built-in text search
- Matches exact words and stems
- Boolean operators supported

**Best for:**
- Known specific terms
- Author name searches
- Exact phrase matching

**Syntax:**
```
"exact phrase"           # Match exact phrase
term1 & term2            # Both terms required (AND)
term1 | term2            # Either term (OR)
!term                    # Exclude term (NOT)
(term1 | term2) & term3  # Grouped expressions
```

**Examples:**
```
"randomized controlled trial" & metformin
aspirin | clopidogrel
diabetes & !gestational
```

## Search Parameters

### Similarity Threshold

Controls the minimum relevance score for results.

| Threshold | Effect |
|-----------|--------|
| **0.3** | Very inclusive, many results |
| **0.5** | Balanced (recommended) |
| **0.7** | High relevance only |
| **0.9** | Near-exact matches |

**When to adjust:**
- **Lower (0.3-0.4)** - Broad literature reviews, exploratory searches
- **Higher (0.6-0.8)** - Focused questions, known topics

### Result Limit

Maximum number of results to return.

| Limit | Use Case |
|-------|----------|
| **10-20** | Quick reference |
| **50** | Standard search |
| **100-200** | Comprehensive review |

> **Tip:** Start with fewer results and increase if needed.

### Reranking

AI-powered result reordering for better relevance.

**How it works:**
1. Initial search returns candidates
2. Reranker model scores each result against your query
3. Results are reordered by reranker scores

**When to use:**
- Complex queries where initial ranking is imperfect
- When top results don't seem most relevant
- For systematic reviews

**Note:** Reranking adds processing time but often improves results.

## Crafting Effective Queries

### Question Formulation

**Good queries are:**
- Specific about population/intervention/outcome
- Phrased as research questions
- Focused on a single concept

**Examples of good queries:**
```
# Specific and focused
"What is the efficacy of metformin monotherapy in newly diagnosed Type 2 diabetes?"

# Clear PICO format
"In elderly patients with atrial fibrillation, how does apixaban compare to warfarin?"

# Outcome-focused
"What are the long-term cognitive effects of repeated general anesthesia in children?"
```

**Examples of poor queries:**
```
# Too vague
"diabetes treatment"

# Too broad
"cancer"

# Multiple unrelated concepts
"diabetes heart disease kidney transplant"
```

### Query Refinement Strategies

#### Start Broad, Then Narrow

1. Begin with a general concept
2. Review initial results
3. Add specific terms from relevant abstracts
4. Iterate until satisfied

```
Step 1: "hypertension treatment"
Step 2: "hypertension treatment elderly patients"
Step 3: "resistant hypertension management in elderly with chronic kidney disease"
```

#### Use Domain-Specific Terms

Medical literature uses specific terminology:

| Lay Term | Medical Term |
|----------|--------------|
| Heart attack | Myocardial infarction |
| High blood pressure | Hypertension |
| Sugar disease | Diabetes mellitus |
| Stroke | Cerebrovascular accident |

#### Include Study Type When Relevant

```
"randomized controlled trial" aspirin cardiovascular prevention
meta-analysis SGLT2 inhibitors heart failure
systematic review depression psychotherapy
```

## Search Strategies by Use Case

### Literature Review

1. **Define your question** clearly
2. **Search broadly** with low threshold (0.3-0.4)
3. **Enable HyDE** for comprehensive coverage
4. **Review abstracts** systematically
5. **Iterate** with refined queries

### Finding Specific Studies

1. **Use known details** - author names, key terms
2. **Use keyword search** with exact phrases
3. **Set high threshold** (0.7+)
4. **Limit results** to manageable number

### Current Awareness

1. **Search your topic** of interest
2. **Filter by recent date** (last 30-90 days)
3. **Save search** to project
4. **Repeat regularly** to catch new publications

### Systematic Review Prep

1. **Develop PICO question**
2. **Search with multiple query variations**
3. **Document each search** with parameters
4. **Export results** for screening
5. **Track evaluated documents**

## Advanced Techniques

### Combining Search Methods

Run multiple searches and compare:

1. Semantic search with your main question
2. HyDE search with the same question
3. Keyword search with key terms

Review results from all three for comprehensive coverage.

### Using Negative Terms

When results include irrelevant topics:

```
# Exclude pediatric studies
diabetes treatment -pediatric -children

# Focus on humans, not animal studies
alzheimer biomarkers -mouse -mice -rat
```

### Leveraging Citation Networks

When you find a highly relevant paper:

1. Note its key terms and concepts
2. Search for similar language
3. Look for the same authors' other work
4. Check papers citing/cited by it (externally)

## Interpreting Results

### Similarity Scores

| Score | Interpretation |
|-------|----------------|
| **90-100%** | Very strong match, likely directly relevant |
| **70-89%** | Strong match, probably relevant |
| **50-69%** | Moderate match, review abstract |
| **30-49%** | Weak match, may be tangential |
| **<30%** | Unlikely to be relevant |

### Result Quality Indicators

**Signs of good results:**
- Titles clearly relate to your query
- Top results are highly similar (>70%)
- Results span relevant subtopics

**Signs to refine your search:**
- Top results seem unrelated
- Low similarity scores overall
- Results are too narrow or too broad

## Troubleshooting Searches

### Too Few Results

1. Lower the similarity threshold
2. Broaden your query
3. Check for spelling/terminology
4. Try HyDE search
5. Verify database has relevant documents

### Too Many Results

1. Raise the similarity threshold
2. Add specific terms
3. Use date filters
4. Enable reranking
5. Reduce result limit

### Irrelevant Results

1. Add domain-specific terms
2. Use negative terms to exclude
3. Phrase as a specific question
4. Try keyword search for known terms

### Search is Slow

1. Reduce max results
2. Ensure Ollama is running
3. Check system resources
4. Consider smaller embedding model

---

Previous: [Knowledge Browser](knowledge-browser.md) | Next: [Document Evaluation](document-evaluation.md)
