"""This module finds new additions to the publication database that are of interest,
eg able to contribute to answering a research question or confirming/rejecting a hypothesis."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from tqdm import tqdm

from localknowledge.ai.literature_searcher import DocumentEvaluator
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.hypotheses import HypothesesDatabaseManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.context import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class NewsItem:
    """Represents a news item that is of interest."""
    document_id: int
    rating: int
    reason_for_rating: str
    model_name: str
    similarity: float = 0.0
    #evaluator: int # id in the evaluators table

class NewsFinder:
    """Finds new additions to the publication database that are of interest.
    Interest is defined by research questions and hypotheses in our database that are active"""

    def __init__(self, most_recent_days=3, max_documents_analyzed=50, model_name: str = "gemma3:4b", user_id: Optional[int] = None):
        """
        Initialize the NewsFinder.

        Args:
            most_recent_days: Number of days to consider for recent publications
            max_documents_analyzed: Maximum number of documents to analyze
            model_name: Name of the Ollama model to use for evaluation
            user_id: User ID for reading suggestions (if None, will try to get from context)
        """
        self.model_name = model_name
        self.most_recent_days = most_recent_days
        self.max_documents_analyzed = max_documents_analyzed
        self.doc_db = DocumentDatabaseManager()
        self.questions_db = ResearchQuestionsManager()
        self.hypotheses_db = HypothesesDatabaseManager()
        self.suggestions_db = ReadingSuggestionsManager()
        self.user_db = UserDatabaseManager()

        # Get user ID from context if not provided
        if user_id is None:
            user = get_current_user()
            self.user_id = user.get('id', 1) if user else 1  # Default to user_id 1
        else:
            self.user_id = user_id

        # Verify the user exists
        self._verify_user_id()

        # Get or create evaluator for the model
        self.evaluator_id = self._get_or_create_evaluator()

    def _verify_user_id(self):
        """Verify that the user ID exists in the database, or find a valid one."""
        # Check if the user exists
        user = self.user_db.get_user(self.user_id)
        if not user:
            logger.warning(f"User ID {self.user_id} not found in database, looking for a valid user")
            try:
                # Get the first user from the database
                result = self.user_db.execute("SELECT id FROM users LIMIT 1")
                if result and len(result) > 0:
                    self.user_id = result[0]['id']
                    logger.info(f"Using user ID {self.user_id} for reading suggestions")
                else:
                    # Try to create a default user for testing
                    try:
                        self.user_id = self.user_db.create_user(
                            username="newsfinder_user",
                            firstname="NewsFinder",
                            surname="User",
                            email="newsfinder@example.com",
                            password="password123"
                        )
                        logger.info(f"Created new user with ID {self.user_id} for reading suggestions")
                    except Exception as e:
                        logger.error(f"Error creating default user: {e}")
                        logger.warning("Will use user_id=1 but reading suggestions may fail")
                        self.user_id = 1
            except Exception as e:
                logger.error(f"Error finding valid user: {e}")
                self.user_id = 1

    def fetch_recent_publications(self) -> List[int]:
        """
        Fetch the most recent publications from the database.

        Returns:
            List of document IDs for recent publications
        """
        # Calculate the date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.most_recent_days)

        # Format dates for SQL query
        start_date_str = start_date.strftime('%Y-%m-%d')

        # Query to get recent documents
        query = """
        SELECT id
        FROM document
        WHERE publication_date >= %s
        ORDER BY publication_date DESC
        LIMIT %s
        """

        try:
            results = self.doc_db.execute(query, (start_date_str, self.max_documents_analyzed))
            if results:
                return [doc['id'] for doc in results]
            return []
        except Exception as e:
            logger.error(f"Error fetching recent publications: {e}")
            return []

    def get_abstract(self, document_id: int) -> str:
        """
        Get the abstract of a publication.

        Args:
            document_id: The ID of the document

        Returns:
            The abstract text or empty string if not found
        """
        document = self.doc_db.get_document(document_id)
        if document and 'abstract' in document:
            return document['abstract']
        return ""

    def get_question_text(self, question_id: int) -> str:
        """
        Get the text of a research question.

        Args:
            question_id: The ID of the research question

        Returns:
            The question text or empty string if not found
        """
        question = self.questions_db.get_question(question_id)
        if question and 'question' in question:
            return question['question']
        return ""

    def get_hypothesis_text(self, hypothesis_id: int) -> str:
        """
        Get the text of a hypothesis.

        Args:
            hypothesis_id: The ID of the hypothesis

        Returns:
            The hypothesis text or empty string if not found
        """
        hypothesis = self.hypotheses_db.get_hypothesis(hypothesis_id)
        if hypothesis and 'hypothesis' in hypothesis:
            return hypothesis['hypothesis']
        return ""

    def _get_or_create_evaluator(self) -> int:
        """
        Get or create an evaluator for the current model.

        Returns:
            ID of the evaluator
        """
        # Check if an evaluator for this model already exists
        evaluators = self.suggestions_db.get_evaluators()
        for evaluator in evaluators:
            if evaluator.get('model_id') == self.model_name:
                logger.info(f"Using existing evaluator ID {evaluator['id']} for model {self.model_name}")
                return evaluator['id']

        # Create a new evaluator
        evaluator_name = f"NewsFinder ({self.model_name})"
        parameters = {"type": "newsfinder"}
        prompt = "Evaluate document relevance to research questions and hypotheses"

        # Use None for user_id to avoid foreign key constraint issues
        # The evaluator will be system-owned rather than user-owned
        evaluator_id = self.suggestions_db.add_evaluator(
            name=evaluator_name,
            user_id=None,  # Set to None to avoid foreign key constraint
            model_id=self.model_name,
            parameters=parameters,
            prompt=prompt
        )

        if evaluator_id:
            logger.info(f"Created new evaluator ID {evaluator_id} for model {self.model_name}")
            return evaluator_id
        else:
            logger.error(f"Failed to create evaluator for model {self.model_name}")
            # Return a default ID as fallback
            return 1

    def add_to_reading_suggestions(self, news_item: NewsItem) -> Optional[int]:
        """
        Add a news item to the reading suggestions table if rating >= 2.

        Args:
            news_item: The NewsItem to add

        Returns:
            ID of the reading suggestion or None if not added
        """
        # Only add items with rating >= 2
        if news_item.rating < 2:
            return None

        # Map rating to recommendation strength (2->3, 3->5)
        recommendation_strength = 3 if news_item.rating == 2 else 5

        # Add to reading suggestions
        try:
            suggestion_id = self.suggestions_db.add_reading_suggestion(
                document_id=news_item.document_id,
                user_id=self.user_id,
                evaluator_id=self.evaluator_id,
                recommendation_strength=recommendation_strength,
                confidence_level=news_item.similarity,
                comment=news_item.reason_for_rating
            )

            if suggestion_id:
                logger.info(f"Added document ID {news_item.document_id} to reading suggestions with ID {suggestion_id}")
            else:
                logger.error(f"Failed to add document ID {news_item.document_id} to reading suggestions")

            return suggestion_id
        except Exception as e:
            logger.error(f"Error adding reading suggestion: {e}")
            return None

    def evaluate(self, document_id: int, question_text: str) -> NewsItem:
        """
        Evaluate the relevance of a publication to a question.

        Args:
            document_id: The ID of the document to evaluate
            question_text: The research question text

        Returns:
            NewsItem with evaluation results
        """
        logger.info(f"Evaluating document ID {document_id} for question: {question_text[:50]}...")

        # Get document abstract to check if it exists and has content
        document = self.doc_db.get_document(document_id)
        abstract = document.get('abstract', '') if document else ''

        if not abstract or len(abstract.strip()) < 10:
            logger.warning(f"Document ID {document_id} has no usable abstract (length: {len(abstract) if abstract else 0})")
            return NewsItem(
                document_id=document_id,
                rating=0,
                reason_for_rating="Document has no usable abstract",
                similarity=0.0,
                model_name=self.model_name
            )

        # Create evaluator and evaluate document
        try:
            evaluator = DocumentEvaluator(model_name=self.model_name)
            logger.info(f"Sending document to LLM for evaluation (abstract length: {len(abstract)})")
            evaluation = evaluator.evaluate(question=question_text, document_id=document_id)

            logger.info(f"Evaluation result: rating={evaluation.rating}, reason={evaluation.reason_for_rating[:50]}...")

            return NewsItem(
                document_id=evaluation.document_id,
                rating=evaluation.rating,
                reason_for_rating=evaluation.reason_for_rating,
                similarity=evaluation.similarity,
                model_name=self.model_name
            )
        except Exception as e:
            logger.error(f"Error evaluating document: {e}")
            return NewsItem(
                document_id=document_id,
                rating=0,
                reason_for_rating=f"Error during evaluation: {str(e)}",
                similarity=0.0,
                model_name=self.model_name
            )

    def trawl_for_news(self, document_id: int, questions: List[int], hypotheses: Optional[List[int]]=None) -> List[NewsItem]:
        """
        Trawl for news that is relevant to research questions or hypotheses.

        Args:
            document_id: The ID of the document to evaluate
            questions: List of research question IDs
            hypotheses: Optional list of hypothesis IDs

        Returns:
            List of NewsItem objects for relevant documents
        """
        news = []
        abstract = self.get_abstract(document_id)

        if not abstract:
            logger.warning(f"No abstract found for document ID {document_id}")
            return news

        # Track which documents have been added to reading suggestions
        # Use a set to avoid duplicate entries
        added_to_suggestions = False
        best_evaluation = None  # Keep track of the highest-rated evaluation

        # Evaluate against research questions
        for question_id in questions:
            question_text = self.get_question_text(question_id)
            if question_text:
                evaluation = self.evaluate(document_id, question_text)
                if evaluation.rating > 1:
                    news.append(evaluation)
                    # Keep track of the highest-rated evaluation
                    if evaluation.rating >= 2 and (best_evaluation is None or evaluation.rating > best_evaluation.rating):
                        best_evaluation = evaluation
            else:
                logger.warning(f"No text found for research question ID {question_id}")

        # Evaluate against hypotheses if provided
        if hypotheses:
            for hypothesis_id in hypotheses:
                hypothesis_text = self.get_hypothesis_text(hypothesis_id)
                if hypothesis_text:
                    evaluation = self.evaluate(document_id, hypothesis_text)
                    if evaluation.rating > 1:
                        news.append(evaluation)
                        # Keep track of the highest-rated evaluation
                        if evaluation.rating >= 2 and (best_evaluation is None or evaluation.rating > best_evaluation.rating):
                            best_evaluation = evaluation
                else:
                    logger.warning(f"No text found for hypothesis ID {hypothesis_id}")

        # Add the highest-rated evaluation to reading suggestions if rating >= 2
        if best_evaluation is not None:
            self.add_to_reading_suggestions(best_evaluation)
            logger.info(f"Added document ID {document_id} to reading suggestions with rating {best_evaluation.rating}")

        return news

    def find_news_for_project(self, project_id: int) -> List[NewsItem]:
        """
        Find news items relevant to a project's research questions and hypotheses.

        Args:
            project_id: The ID of the project

        Returns:
            List of NewsItem objects for relevant documents
        """
        # Get all research questions for the project
        project_questions = self.questions_db.get_project_questions(project_id)
        question_ids = [q['id'] for q in project_questions]
        logger.info(f"Found {len(question_ids)} research questions for project {project_id}")

        # Get all hypotheses for the project
        project_hypotheses = self.hypotheses_db.get_project_hypotheses(project_id)
        hypothesis_ids = [h['id'] for h in project_hypotheses]
        logger.info(f"Found {len(hypothesis_ids)} hypotheses for project {project_id}")

        # Check if we have any questions or hypotheses to evaluate against
        if not question_ids and not hypothesis_ids:
            logger.warning(f"No research questions or hypotheses found for project {project_id}")
            return []

        # Get project users
        try:
            from localknowledge.db.project import ProjectDatabaseManager
            project_db = ProjectDatabaseManager()
            project_users = project_db.get_project_users(project_id)

            if project_users:
                # Use the first project user's ID for reading suggestions
                self.user_id = project_users[0]['user_id']
                logger.info(f"Using project user ID {self.user_id} for reading suggestions")

                # Verify this user exists
                self._verify_user_id()
        except Exception as e:
            logger.error(f"Error getting project users: {e}")
            # Continue with the current user ID

        # Get recent publications
        recent_doc_ids = self.fetch_recent_publications()

        # Deduplicate document IDs using a set - much cleaner approach
        unique_doc_ids = set(recent_doc_ids)
        logger.info(f"Found {len(recent_doc_ids)} recent publications, {len(unique_doc_ids)} unique IDs to evaluate")

        # Trawl for news
        all_news = []

        # Evaluate each unique document ID
        for doc_id in tqdm(unique_doc_ids, desc="Evaluating documents"):
            news_items = self.trawl_for_news(doc_id, question_ids, hypothesis_ids)
            all_news.extend(news_items)

        return all_news


if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Find news items relevant to research questions and hypotheses")
    parser.add_argument("--project", "-p", type=int, help="Project ID to find news for")
    parser.add_argument("--days", "-d", type=int, default=3, help="Number of days to look back for recent publications")
    parser.add_argument("--max", "-m", type=int, default=50, help="Maximum number of documents to analyze")
    parser.add_argument("--model", type=str, default="gemma3:4b", help="Model to use for evaluation")
    parser.add_argument("--user", "-u", type=int, help="User ID for reading suggestions (optional, will use project user if not specified)")

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create news finder
    news_finder = NewsFinder(
        most_recent_days=args.days,
        max_documents_analyzed=args.max,
        model_name=args.model,
        user_id=args.user
    )

    if args.project:
        # Find news for project
        print(f"Finding news for project ID {args.project}...")
        news_items = news_finder.find_news_for_project(args.project)

        # Display results
        print(f"\nFound {len(news_items)} relevant news items:")

        # Count items added to reading suggestions
        suggestions_count = 0
        for item in news_items:
            if item.rating >= 2:
                suggestions_count += 1

        print(f"Added {suggestions_count} items to reading suggestions (ratings >= 2)")

        for i, item in enumerate(news_items):
            print(f"\n{i+1}. Document ID: {item.document_id}")
            print(f"   Rating: {item.rating}/3")
            print(f"   Reason: {item.reason_for_rating}")

            if item.rating >= 2:
                print(f"   Added to reading suggestions: YES")
            else:
                print(f"   Added to reading suggestions: NO")

            # Get document details
            doc = news_finder.doc_db.get_document(item.document_id)
            if doc:
                print(f"   Title: {doc.get('title', 'Unknown')}")
                print(f"   Source: {doc.get('source_name', 'Unknown')}")
                print(f"   Publication Date: {doc.get('publication_date', 'Unknown')}")

    else:
        # If no project ID provided, just show recent publications
        print("No project ID provided. Fetching recent publications...")
        recent_docs = news_finder.fetch_recent_publications()
        print(f"Found {len(recent_docs)} recent publications")

        # Display a few documents
        for i, doc_id in enumerate(recent_docs[:5]):
            doc = news_finder.doc_db.get_document(doc_id)
            if doc:
                print(f"\n{i+1}. Document ID: {doc_id}")
                print(f"   Title: {doc.get('title', 'Unknown')}")
                print(f"   Source: {doc.get('source_name', 'Unknown')}")
                print(f"   Publication Date: {doc.get('publication_date', 'Unknown')}")

        print("\nUse --project/-p argument to find news for a specific project")