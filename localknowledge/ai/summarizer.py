"""This module summarizes a text using a specified model with ollama locally"""

import ollama
import json
from pprint import pprint


SYSTEMPROMPT="""
<system>
You are a helpful assistant that ALWAYS responds in valid JSON format. 
Each response must be parseable by json.loads() in Python.
You are a medical expert and you are summarizing the text in the style of a medical journal article.
You always respond in the form of a JSON object with the following fields:
- response: The summarized text
- error: An error message if any
- evaluation: A boolean indicating whether this publication aligns with at least one of the stated interests (True) or not (False)
- reason: The reason why you think this is of interest or not (brief single sentence)
- interests: A list of interests related to the text
</system>"""


INTERESTS = ['emergency medicine', 
             'rural and remote medicine', 
             'AI use in medicine', 
             'machine learning']

SUMMARIZE_PROMPT = """<user>
Read the provided text carefully and consider whether this text is important
in the context of my interests. 
Please extract the core information from this text and provide a concise summary in a few sentences.
These are my interests: <interests> {interests} </interests>
The text is: <text> {text} </text>
</user>
"""

def summarize_interesting_text(text: str, interests: list[str], model="phi4:latest") -> str:
    """
    Summarize the text using the specified model with ollama locally.
    
    Args:
        text (str): The text to summarize.
        
    Returns:
        str: The summarized text.
    """
    interests_str = ', '.join(interests)
    # Create a prompt for the model
    prompt = f"{SYSTEMPROMPT}\n {SUMMARIZE_PROMPT.format(text=text, interests=interests_str)}"
    
    # Use the ollama model to generate a summary
    response = ollama.generate(model=model, prompt=prompt)
    # Check if the response is valid JSON
    try:
        # Attempt to parse the response as JSON
        maybejson = response.response
        # Remove backticks and JSON code block markers
        maybejson = maybejson.replace('`', '')
        if maybejson.startswith('```json'):
            maybejson = maybejson[7:]
        elif maybejson.startswith('json'):
            maybejson = maybejson[4:]
        # Remove closing code block markers if present
        if '```' in maybejson:
            maybejson = maybejson.split('```')[0]
        # Strip leading and trailing spaces, newline characters
        maybejson = maybejson.strip()
        # Parse the cleaned JSON
        summary = json.loads(maybejson)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {
            "response": f"{maybejson}",
            "error": str(e),
            "evaluation": False,
            "reason": "Invalid JSON response",
            "interests": interests
        }
    
    return summary

if __name__ == "__main__":
    # Example usage
    text1 = """Leprosy-related stigma is deeply rooted in history and permeates every aspect of society, and stigmatization

by healthcare professionals is no exception. This paper explores the experiences of persons affected by

Leprosy with stigma in the healthcare setting throughout their treatment-seeking journey. We conducted

one-on-one interviews with 112 individuals who experienced a Leprosy diagnosis and underwent treatment.

Data was collected in July and August 2022, in 9 villages and 1 urban neighborhood in the region of Maradi,

Niger. Over two-thirds of participants experienced some form of visible impairment due to Leprosy.

Throughout their treatment-seeking journey, healthcare providers were reported to have stigmatized

patients by using hurtful language, isolating patients, physically distancing from patients, or refusing to

treat. The extent of the stigmatization depended on, first, whether Leprosy was recognized or not.

Unfortunately, many healthcare providers did not detect the early signs of Leprosy, therefore, patients were

then not able to obtain treatment prior to physical impairment. Second, the level of stigmatization varied

based on the degree and type of visible physical impairments (e.g., missing fingers or toes, limbs,

blindness). These negative experiences with healthcare workers made treatment-seeking and adherence to

treatment regimen less likely for patients. Our findings confirm the presence of Leprosy stigma in the

healthcare context in Niger. Increasing Leprosy knowledge and addressing stigma among healthcare

professionals is key to early diagnosis and treatment of Leprosy.

"""

    text2="""The integration of artificial intelligence (AI) into healthcare promises groundbreaking advancements in patient care, revolutionizing clinical diagnosis, predictive medicine, and decision-making. This transformative technology uses machine learning, natural language processing, and large language models (LLMs) to process and reason like human intelligence. OpenAI's ChatGPT, a sophisticated LLM, holds immense potential in medical practice, research, and education. However, as AI in healthcare gains momentum, it brings forth profound ethical challenges that demand careful consideration. This comprehensive review explores key ethical concerns in the domain, including privacy, transparency, trust, responsibility, bias, and data quality. Protecting patient privacy in data-driven healthcare is crucial, with potential implications for psychological well-being and data sharing. Strategies like homomorphic encryption (HE) and secure multiparty computation (SMPC) are vital to preserving confidentiality. Transparency and trustworthiness of AI systems are essential, particularly in high-risk decision-making scenarios. Explainable AI (XAI) emerges as a critical aspect, ensuring a clear understanding of AI-generated predictions. Cybersecurity becomes a pressing concern as AI's complexity creates vulnerabilities for potential breaches. Determining responsibility in AI-driven outcomes raises important questions, with debates on AI's moral agency and human accountability. Shifting from data ownership to data stewardship enables responsible data management in compliance with regulations. Addressing bias in healthcare data is crucial to avoid AI-driven inequities. Biases present in data collection and algorithm development can perpetuate healthcare disparities. A public-health approach is advocated to address inequalities and promote diversity in AI research and the workforce. Maintaining data quality is imperative in AI applications, with convolutional neural networks showing promise in multi-input/mixed data models, offering a comprehensive patient perspective. In this ever-evolving landscape, it is imperative to adopt a multidimensional approach involving policymakers, developers, healthcare practitioners, and patients to mitigate ethical concerns. By understanding and addressing these challenges, we can harness the full potential of AI in healthcare while ensuring ethical and equitable outcomes."""
    
    #MODEL="gemma3:4b"
    #MODEL="granite3.3:8b"
    MODEL="phi4:latest"
    for text in text1, text2:
        print(f"Summarizing text with model {MODEL}...")
        pprint(summarize_interesting_text(text, INTERESTS, model=MODEL))
        print("\n" + "="*80 + "\n")
        print()