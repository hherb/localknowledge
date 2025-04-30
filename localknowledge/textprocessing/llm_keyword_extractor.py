import ollama

# Recommended model (from performance testing)
MODEL = 'gemma3:4b'

PROMPT_TEMPLATE = """
Extract a concise list of essential keywords suitable for a PubMed keyword search from the 
following question. Do not include stopwords or unnecessary words. 
List only the keywords, separated by commas.

Question: {question}

Keywords:
{thinktag}
"""

SYNONYMS_TEMPLATE="""From the following question, extract essential keywords,
and if relevant for fulltext search, expand each keyword with relevant 
synonyms or related terms that would improve a full-text search. 
Use a structured format:

(keywordA, synonymA1, synonymA2...), (keywordB, synonymB1...), (keyword)...

Do not include stopwords. Only include meaningful terms. 
Answer with ONLY the list of keywords and synonyms 
in the format specified and nothing else.

Question: {question}

Keywords and synonyms:
{thinktag}"""

def time_decorator(func):
    """Decorator to measure the execution time of a function."""
    def wrapper(*args, **kwargs):
        import time
        #load model first, do not count first round
        _ = func(*args, **kwargs)
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time:.2f} seconds to execute.")
        return result
    return wrapper

def strip_thinktags(text: str) -> str:
    """Strip thinktags from the response."""
    return text.replace("<think>", "").replace("</think>", "")

@time_decorator
def extract_keywords(question: str, model_name: str = MODEL, template=SYNONYMS_TEMPLATE) -> str:
    """Extract keywords from a question using Ollama."""
    thinktag=''
    if model_name.startswith('qwen3'):
        thinktag='</nothink>'
    prompt = template.format(question=question, thinktag=thinktag)
    response = ollama.generate(model=model_name, prompt=prompt)
    return strip_thinktags(response.response.strip())

if __name__ == "__main__":
    #get question from command line argument:
    import sys
    question = sys.argv[1]
    for model in ["gemma3:4b", "qwen3:1.7b-q8_0", "qwen3:4b"]:
        print(f"Testing model {model}")
        keywords = extract_keywords(question, model)
        print(keywords)


#Example:
#Q: "what is the role of ultrasound in the management of head injury patients?"
#A: (head injury, traumatic brain injury, TBI, brain trauma, neurological injury), (ultrasound, sonography, neurosonography, brain imaging, diagnostic imaging), (management, treatment, care, intervention, therapy)
