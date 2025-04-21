"""This module finds questions and answers in text using a specified model with ollama locally.

It provides functionality to:
1. Extract questions from text
2. Extract question-answer pairs from text
3. Generate embeddings for QA pairs
"""

import ollama
import json
import re
import logging
import backoff
from typing import List, Dict, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemma3:4b"
DEFAULT_EMBEDDING_MODEL = "snowflake-arctic-embed2:latest"

QUESTIONPROMPT = """Analyze the following text and generate a list of important questions.
Return your response as a JSON array of strings, where each string is a question.
Don't include any additional text before or after the JSON array.
<text>
{text}
</text>"""


# Modified prompt to explicitly request a list of Q&A pairs
QAPROMPT = """Analyze the following text and generate a list of important questions and their answers.
Return your response as a JSON array of objects, where each object has the format
{{"question": "question in one sentence", "answer": "answer in one sentence"}}
Don't include any additional text before or after the JSON array.

<text>
{text}
</text>"""


def find_questions(text: str, model: str = DEFAULT_MODEL) -> List[str]:
    """
    Find important questions in the given text.

    Args:
        text: The text to analyze
        model: The Ollama model to use

    Returns:
        A list of questions
    """
    response = ollama.generate(model=model, prompt=QUESTIONPROMPT.format(text=text))
     # Extract just the JSON part from the response
    json_str = response.response



    # Try to clean up any non-JSON text before or after the array
    try:
        # Look for JSON array pattern
        match = re.search(r'\[\s*\{.*\}\s*\]', json_str, re.DOTALL)
        if match:
            json_str = match.group(0)

        # Parse the JSON
        qa_list = json.loads(json_str)
        return qa_list
    except json.JSONDecodeError:
        # Fallback: try to extract individual JSON objects
        try:
            pattern = r'\{\s*"question"\s*:\s*"[^"]*"\s*,\s*"answer"\s*:\s*"[^"]*"\s*\}'
            matches = re.findall(pattern, json_str)
            return [json.loads(match) for match in matches]
        except:
            # Return raw response if all parsing fails
            logger.error(f"Could not parse JSON response")
            return {"error": "Could not parse JSON", "raw_response": json_str}



def find_questions_and_answers(text: str, model: str = DEFAULT_MODEL) -> List[Dict[str, str]]:
    """
    Find important questions and their answers in the given text.

    Args:
        text: The text to analyze
        model: The Ollama model to use

    Returns:
        A list of dictionaries with 'question' and 'answer' keys
    """
    response = ollama.generate(model=model, prompt=QAPROMPT.format(text=text))

    # Extract just the JSON part from the response
    json_str = response.response


    # Try to clean up any non-JSON text before or after the array
    try:
        # Parse the JSON
        q_list = json.loads(json_str)
        return q_list
    except json.JSONDecodeError:
        # Fallback: try to extract individual JSON objects
        try:
            pattern = r'\{\s*"question"\s*:\s*"[^"]*"\s*,\s*"answer"\s*:\s*"[^"]*"\s*\}'
            matches = re.findall(pattern, json_str)
            return [json.loads(match) for match in matches]
        except:
            # Return raw response if all parsing fails
            logger.error(f"Could not parse JSON response")
            return {"error": "Could not parse JSON", "raw_response": json_str}


@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def create_embedding(text: str, model: str = DEFAULT_EMBEDDING_MODEL) -> List[float]:
    """
    Create an embedding for the given text using Ollama.

    Args:
        text: Text to embed
        model: Name of the Ollama model to use

    Returns:
        Vector embedding as a list of floats
    """
    try:
        response = ollama.embeddings(model=model, prompt=text)
        return response['embedding']
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise


class QAEmbeddingManager:
    """Manager for creating and searching QA embeddings."""

    def __init__(self, model_name: str = DEFAULT_MODEL, embedding_model: str = DEFAULT_EMBEDDING_MODEL):
        """
        Initialize the QA embedding manager.

        Args:
            model_name: Name of the Ollama model to use for QA generation
            embedding_model: Name of the Ollama model to use for embeddings
        """
        from localknowledge.db.qafinder import QAEmbeddingDatabaseManager

        self.model_name = model_name
        self.embedding_model = embedding_model
        self.db = QAEmbeddingDatabaseManager()

        # Verify that the models are available
        self._verify_models()

    def _verify_models(self) -> None:
        """Verify that the required models are available."""
        try:
            # Get list of available models
            models = ollama.list()
            model_names = [model['model'] for model in models['models']]

            # Check if our models are available
            if self.model_name not in model_names:
                logger.warning(f"QA model '{self.model_name}' not found in available models: {model_names}")

            if self.embedding_model not in model_names:
                logger.warning(f"Embedding model '{self.embedding_model}' not found in available models: {model_names}")

        except Exception as e:
            logger.error(f"Error verifying models: {e}")

    def process_text(self,
                    source_id: str,
                    document_id: str,
                    text: str,
                    chunk_no: int = 0,
                    page_no: Optional[int] = None) -> int:
        """
        Process a text by generating QA pairs, creating embeddings, and storing in the database.

        Args:
            source_id: Source identifier (e.g., 'pubmed', 'medrxiv')
            document_id: Document identifier (e.g., PMID, DOI)
            text: Text to process
            chunk_no: Chunk number within the document
            page_no: Page number (optional)

        Returns:
            ID of the stored QA embedding
        """
        if not text:
            logger.warning(f"Empty text for document {document_id}, skipping")
            return -1

        # Generate QA pairs
        logger.debug(f"Generating QA pairs for document {document_id}")
        qa_pairs = find_questions_and_answers(text, model=self.model_name)

        # Handle different response formats
        if isinstance(qa_pairs, list):
            # List of QA pairs - this is the expected format
            logger.debug(f"Generated {len(qa_pairs)} QA pairs for document {document_id}")
            qa_pairs_json = json.dumps(qa_pairs)
        elif isinstance(qa_pairs, dict) and 'error' in qa_pairs:
            # Error response - but we'll still store it
            logger.warning(f"QA generation returned error for document {document_id}, but proceeding anyway")
            # Create a single QA pair with the error
            qa_pairs = [{
                "question": "What is this document about?",
                "answer": "This document could not be processed correctly."
            }]
            qa_pairs_json = json.dumps(qa_pairs)
        else:
            # Unknown format - convert to string and store anyway
            logger.warning(f"QA generation returned unexpected format for document {document_id}")
            # Store whatever we got as a JSON string
            qa_pairs_json = json.dumps(qa_pairs) if not isinstance(qa_pairs, str) else json.dumps([{"question": "What is this document about?", "answer": qa_pairs}])

        # Create embedding for the text
        logger.debug(f"Creating embedding for document {document_id}")
        embedding = create_embedding(text, model=self.embedding_model)

        # Store in database
        return self.db.store_qa_embedding(
            source_id=source_id,
            document_id=document_id,
            chunk_no=chunk_no,
            page_no=page_no,
            qa_pairs=qa_pairs_json,
            embedding=embedding,
            model_name=self.model_name
        )

    def search(self,
              query: str,
              limit: int = 10,
              threshold: float = 0.7,
              source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar QA pairs using semantic search.

        Args:
            query: Search query
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)
            source_id: Filter by source ID (optional)

        Returns:
            List of similar QA pairs with similarity scores
        """
        # Create embedding for the query
        query_embedding = create_embedding(query, model=self.embedding_model)

        # Search for similar QA pairs
        results = self.db.search_similar(
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold,
            source_id=source_id
        )

        # Parse QA pairs from JSON
        for result in results:
            try:
                result['qa_pairs'] = json.loads(result['qa_pairs'])
            except json.JSONDecodeError:
                logger.error(f"Error parsing QA pairs JSON: {result['qa_pairs']}")
                result['qa_pairs'] = []

        return results

    def delete_document(self, source_id: str, document_id: str) -> int:
        """
        Delete all QA embeddings for a specific document.

        Args:
            source_id: Source identifier
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        return self.db.delete_document_qa_embeddings(source_id, document_id)

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()


if __name__=="__main__":
    text = """Background Discharge against medical advice (DAMA), affecting up to 2% of hospital discharges, is a critical public health concern. Patients with traumatic injuries, particularly traumatic brain injury (TBI), exhibit higher DAMA rates. However, TBI-specific DAMA remains understudied. This study aims to quantify the burden of DAMA in an urban TBI cohort, analyze demographic and injury differences between patients who DAMA and those with standard discharges, and determine potential predictors of DAMA in TBI.
Methods A retrospective review of TBI patients treated at an urban trauma center between 2017 and 2022 was conducted using data from our institution’s trauma registry, a subset of the National Trauma Registry of the American College of Surgeons (NTRACS). Discharge against medical advice was defined as any discharge against medical recommendations during the index hospital stay following TBI. Discharge against medical advice status was classified based on the recorded registry discharge disposition and dichotomized as DAMA and n-DAMA (non-DAMA discharge included discharge to home, inpatient facility or hospital transfer based on medical recommendation). Descriptive statistics, univariate analyses, and multivariate modeling were used to compare the DAMA and n-DAMA groups.
Results This study identified 47 (3.7%) patients with DAMA status and 1214 (96.3%) without a premature discharge (n-DAMA). Younger age, male sex, Black race, shorter hospital lengths of stay, alcohol use and intentional injury were associated with DAMA in patients with TBI. Patients with n-DAMA status were more likely to be older and have Medicare insurance. No association was found between discharge against medical advice and TBI severity, GCS score, injury severity score, ventilator usage, intensive care unit days or in-hospital complications. Multivariate analysis found that intentional injury, male sex and alcohol use near the time of injury were predictive of discharge against medical advice.
Conclusion TBI patients leaving against medical advice were disproportionately younger males, often with injuries linked to alcohol and violence. Given the multiple variables associated with DAMA, targeted prevention programs are crucial for this vulnerable population. Further research is necessary to understand the long-term consequences and re-injury risks after DAMA."""

    print(find_questions(text))
    print()
    print('_'*80)
    print()
    print(find_questions_and_answers(text))

