"""This module provides functionality for evaluating documents for their relevance to research questions.
It uses LLMs to analyze document content and provide ratings and explanations."""

import logging
from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.ai.ask_llm import generate_answer

# Configure logging
logger = logging.getLogger(__name__)

DEFAULT_EVALUATIN_PROMPT = """
You are writing a litearure review  for a medical journal and you need to decide on which publications 
you want to include as citations, depending on how useful or critival they are to your research question. 
You need to evaluate the relevance of each publication to your research question carefully.
Do population and intervention in the publication match the population and intervention in the research question? 
Consider carefully how likely the provided text will contribute towards answering the question directly, and
not just in some tangential or circumferential way..

The research question is: {question}
The text is: {document}

Please rate the text on a scale of 0 to 3, where:
0 means the document is not relevant at all
1 means the document is somewhat relevant. It would not be good to completely omit it from citations.
2 means the document is very likely relevant to answer the question, it should be used as citation
3 means the document answers the question, it is essential and must be included as citationin the paper

Provide a brief reason for your rating in no more than 3 brief sentences. Keep it short.

IMPORTANT: You must respond ONLY with a valid JSON object in the following format:
{{"rating": <rating>, "reason": "<reason>"}}

Do not include any other text, explanations, or formatting outside of this JSON object.
The rating must be a number (0, 1, 2, or 3) and the reason must be a string.
"""


# Define Pydantic model for LLM response
class EvaluationResponse(BaseModel):
    rating: int
    reason: str

@dataclass
class DocumentOfInterest:
    """Represents a document that has been evaluated with regards to a question"""
    document_id: int  # the id of the document in the database
    rating: int  # 0= not suited,
                 # 1 maybe contributing a little to answer the question
                 # 2= likely to contribute to answer the question,
                 # 3= answers the question
    reason_for_rating: str  # reason for the rating provided by the evaluator
    # evaluator: int # id in the evaluators table
    similarity: float = 0.0


class DocumentEvaluator:
    """Evaluates documents for their relevance to a research question."""
    def __init__(self, model_name: str = "gemma3:4b", model_options = None):
        """
        Initialize the DocumentEvaluator.

        Args:
            model_name: Name of the Ollama model to use for evaluation
            model_options: Optional parameters for the Ollama model
        """
        self.model_name = model_name
        self.model_options = model_options
        self.evaluator_id = None  # TODO: get the evaluator id from the database based on model and parameters
        self.db = DocumentDatabaseManager()

        self.prompt = """
        You are a medical expert. You are evaluating a text for its relevance to a research question.
        Consider carefully how likely the provided text will contribute towards answering the question.

        The research question is: {question}
        The text is: {document}

        Please rate the text on a scale of 0 to 3, where:
        0 means the document is not relevant at all
        1 means the document is somewhat relevant, tangentially related to the question
        2 means the document is very likely relevant to answer the question, it should not be missed
        3 means the document answers the question, it is essential and must be included in the reading list

        Provide a brief reason for your rating in no more than 3 brief sentences. Keep it short.

        IMPORTANT: You must respond ONLY with a valid JSON object in the following format:
        {{"rating": <rating>, "reason": "<reason>"}}

        Do not include any other text, explanations, or formatting outside of this JSON object.
        The rating must be a number (0, 1, 2, or 3) and the reason must be a string.
        """

    def evaluate(self, question: str, document_id: int) -> DocumentOfInterest:
        """Evaluate the document for its relevance to the research question.

        Args:
            question: The research question
            document_id: The ID of the document to evaluate

        Returns:
            DocumentOfInterest object with the rating and reason for the rating
        """
        # Get the document from the database
        document = self.db.get_document(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return DocumentOfInterest(
                document_id=document_id,
                rating=0,
                reason_for_rating="Document not found in database",
                similarity=0.0
            )

        # Format the prompt with the question and document abstract
        prompt = self.prompt.format(question=question, document=document.get('abstract', ''))

        # Generate the evaluation using ask_llm
        try:
            # Use generate_answer with our Pydantic model to ensure valid JSON
            result = generate_answer(
                question=prompt,
                model_name=self.model_name,
                model_options=self.model_options,
                pydantic_model=EvaluationResponse,
                enable_thinking=False
            )

            # Create and return the DocumentOfInterest object
            return DocumentOfInterest(
                document_id=document_id,
                rating=int(result.get('rating', 0)),
                reason_for_rating=result.get('reason', "No reason provided"),
                similarity=0.0  # This will be set later if needed
            )
        except Exception as e:
            logger.error(f"Error generating evaluation: {e}")

            # Try with a different model if the first one fails
            try:
                fallback_model = "gemma3:4b"  # Use a different model as fallback
                logger.info(f"Trying fallback model: {fallback_model}")

                # Use generate_answer with fallback model
                result = generate_answer(
                    question=prompt,
                    model_name=fallback_model,
                    pydantic_model=EvaluationResponse,
                    enable_thinking=False
                )

                # Create and return the DocumentOfInterest object
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=int(result.get('rating', 0)),
                    reason_for_rating=result.get('reason', "No reason provided"),
                    similarity=0.0  # This will be set later if needed
                )
            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")

                # Return a default object with error information
                return DocumentOfInterest(
                    document_id=document_id,
                    rating=0,
                    reason_for_rating=f"Evaluation error: {str(e)}. Fallback also failed: {str(fallback_error)}",
                    similarity=0.0
                )
