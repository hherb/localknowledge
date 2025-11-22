# Document Evaluation

LocalKnowledge's AI-powered document evaluation helps you systematically assess the relevance of publications to your research questions.

## Overview

Document evaluation uses a large language model to:
- Read document abstracts
- Compare against your research question
- Provide a relevance rating (0-3)
- Explain the reasoning behind the rating

This accelerates literature screening while maintaining consistent evaluation criteria.

## The Rating Scale

| Rating | Label | Description |
|--------|-------|-------------|
| **0** | Not Relevant | Document does not address your research question |
| **1** | Somewhat Relevant | Tangentially related but unlikely to contribute directly |
| **2** | Very Relevant | Likely to contribute to answering your question; should cite |
| **3** | Essential | Directly answers your question; must include |

### Rating Guidelines

**Rating 0 - Not Relevant**
- Different population, intervention, or outcome
- Unrelated topic despite keyword overlap
- Wrong study context (e.g., animal when you need human)

**Rating 1 - Somewhat Relevant**
- Related topic but different focus
- Background information only
- Methodological papers not directly applicable

**Rating 2 - Very Relevant**
- Addresses your question directly
- Similar population and intervention
- Provides evidence you can cite

**Rating 3 - Essential**
- Key study in the field
- Seminal or highly cited work
- Directly answers your specific question

## Using the Document Evaluator

### From Knowledge Browser

1. **Search** for documents related to your topic
2. **Select** a document from results
3. **Click "Evaluate"** button
4. **Enter** your research question
5. **Review** the AI's rating and explanation
6. **Adjust** the rating if needed
7. **Save** the evaluation

### From Document Evaluator Plugin

1. **Open** Document Evaluator from the sidebar
2. **Enter** your research question at the top
3. **Load** documents to evaluate (from search or project)
4. **Click "Evaluate Next"** to process documents
5. **Review** each evaluation
6. **Save** or adjust as needed

### Batch Evaluation

For multiple documents:

1. **Define** your research question
2. **Add** documents to evaluation queue
3. **Start** batch evaluation
4. **Monitor** progress
5. **Review** results when complete

## Evaluation Best Practices

### Writing Good Research Questions

Your research question determines evaluation quality.

**Effective questions:**
- Specific about population, intervention, and outcome
- Focused on a single research aspect
- Clear about the type of evidence needed

**Examples of good questions:**
```
What is the efficacy of SGLT2 inhibitors in reducing cardiovascular
mortality in patients with Type 2 diabetes and heart failure?

How does early mobilization affect length of hospital stay in
patients after hip replacement surgery?

What are the neurological manifestations of long COVID in
previously healthy adults?
```

**Examples of poor questions:**
```
diabetes drugs (too vague)
is exercise good? (too broad)
cancer treatment outcomes in various populations (multiple questions)
```

### Calibrating Expectations

Before evaluating many documents:

1. **Evaluate 5-10 documents manually** first
2. **Compare your ratings** to AI ratings
3. **Adjust your question** if results seem off
4. **Note patterns** in AI reasoning

### Handling Disagreements

When you disagree with AI ratings:

1. **Consider AI reasoning** - sometimes it catches things you missed
2. **Override if confident** - your judgment is final
3. **Note discrepancies** - may indicate question refinement needed
4. **Update rating** and save

## Configuring the Evaluator

### Evaluator Settings

Access from the Document Evaluator plugin settings:

**Model Selection**
- Choose which AI model to use
- Larger models (gemma3:4b) are more accurate
- Smaller models are faster

**Temperature**
- Lower (0.1-0.3): More consistent, deterministic
- Higher (0.5-0.7): More variable, creative
- Recommended: 0.3 for evaluations

**Custom Prompt**
- Modify the evaluation prompt for specific needs
- Add domain-specific criteria
- Include instructions for edge cases

### Default Prompt

The default evaluation prompt:

```
You are a medical expert evaluating a document for its relevance
to a research question. Consider how likely the document will
contribute toward answering the question.

Research question: {question}
Document abstract: {document}

Rate on a scale of 0-3:
0 = Not relevant
1 = Somewhat relevant, tangential
2 = Very relevant, should cite
3 = Essential, must include

Provide a brief reason (2-3 sentences).
```

### Custom Prompts

For specialized evaluations:

```
You are evaluating literature for a systematic review on {topic}.

Inclusion criteria:
- Human studies only
- Published 2015 or later
- Randomized controlled trials or cohort studies

Exclusion criteria:
- Animal studies
- Case reports
- Non-English publications

Rate based on how well the document meets inclusion criteria...
```

## Evaluation Workflow

### Systematic Review Screening

1. **Define inclusion/exclusion criteria**
2. **Configure custom prompt** with criteria
3. **Run initial search** with broad terms
4. **Batch evaluate** all results
5. **Filter by rating** (2+ for includes)
6. **Manual review** of borderline cases (rating 1)
7. **Export** final selections

### Quick Literature Scan

1. **Enter research question**
2. **Search** relevant topic
3. **Evaluate top 20** results
4. **Focus on ratings 2-3**
5. **Read** those abstracts fully

### Ongoing Research Monitoring

1. **Save research question** in project
2. **Periodically search** for new publications
3. **Evaluate new findings**
4. **Track** accumulating evidence

## Managing Evaluations

### Viewing Past Evaluations

- Evaluations are saved to the database
- Filter documents by "Has Evaluation"
- Sort by rating or evaluation date
- View all evaluations for a project

### Editing Evaluations

1. **Select** evaluated document
2. **Click "Edit Evaluation"**
3. **Update** rating or notes
4. **Save** changes

### Exporting Evaluations

Export your evaluated documents:

1. **Select** documents to export
2. **Choose format** (CSV, BibTeX, etc.)
3. **Include** ratings and reasons
4. **Download** file

## Evaluation Statistics

Track your progress:

| Metric | Description |
|--------|-------------|
| **Total Evaluated** | Number of documents evaluated |
| **Rating Distribution** | Count per rating (0, 1, 2, 3) |
| **Evaluation Rate** | Documents per session |
| **Agreement Rate** | AI vs. your manual ratings |

## Troubleshooting

### Evaluations Are Inconsistent

- Lower temperature setting (0.1-0.2)
- Use larger model
- Refine your research question
- Check prompt for ambiguity

### Evaluations Are Too Slow

- Use smaller model (gemma3:2b)
- Reduce batch size
- Check Ollama resource usage
- Consider evaluating fewer documents

### AI Misunderstands Question

- Rephrase using medical terminology
- Be more specific about criteria
- Add context in custom prompt
- Include example evaluations

### Ratings Seem Too High/Low

- Calibrate with manual evaluations
- Adjust custom prompt
- Consider if question is too broad/narrow
- Check if model understands your field

## Tips for Efficiency

1. **Batch similar documents** - Evaluate related papers together
2. **Use consistent questions** - Don't change question mid-evaluation
3. **Trust but verify** - Spot-check AI ratings periodically
4. **Save frequently** - Don't lose evaluation work
5. **Export regularly** - Back up your evaluated literature

---

Previous: [Search Guide](search-guide.md) | Next: [Project Management](project-management.md)
