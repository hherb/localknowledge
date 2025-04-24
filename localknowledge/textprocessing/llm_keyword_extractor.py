import ollama

# Define the model and prompt
MODEL = 'gemma3:4b'

PROMPT_TEMPLATE = """
Extract a concise list of essential keywords suitable for a PubMed keyword search from the following question. Do not include stopwords or unnecessary words. List only the keywords, separated by commas.

Question: {question}

Keywords:
"""

SYNONYMS_TEMPLATE="""From the following question, extract essential keywords and expand each with relevant synonyms or related terms that would improve a full-text search. 
Use a structured format:

(keywordA, synonymA1, synonymA2...), (keywordB, synonymB1...), (keyword_without_helpful_synonyms)...

Do not include stopwords. Only include meaningful terms. 
Answer with ONLY the list of keywords and synonyms in the format specified and nothing else.

Question: {question}

Keywords and synonyms:"""

def extract_keywords(question: str, model_name: str = MODEL, template=SYNONYMS_TEMPLATE) -> str:
    """Extract keywords from a question using Ollama."""
    prompt = template.format(question=question)
    response = ollama.generate(model=model_name, prompt=prompt)
    return response.response.strip()

if __name__ == "__main__":
    #get question from command line argument:
    import sys
    question = sys.argv[1]
    keywords = extract_keywords(question)
    print(keywords)

#Example:
#Q: "what is the role of ultrasound in the management of head injury patients?"
#A: (head injury, traumatic brain injury, TBI, brain trauma, neurological injury), (ultrasound, sonography, neurosonography, brain imaging, diagnostic imaging), (management, treatment, care, intervention, therapy)
