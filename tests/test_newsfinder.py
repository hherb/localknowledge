"""Unit tests for the newsfinder module."""

import unittest
from unittest.mock import patch, MagicMock
from localknowledge.ai.newsfinder import NewsFinder, NewsItem

class TestNewsFinder(unittest.TestCase):
    """Test cases for the NewsFinder class."""

    def setUp(self):
        """Set up test fixtures."""
        self.news_finder = NewsFinder(
            most_recent_days=3,
            max_documents_analyzed=10,
            model_name="test-model"
        )

        # Mock the database managers
        self.news_finder.doc_db = MagicMock()
        self.news_finder.questions_db = MagicMock()
        self.news_finder.hypotheses_db = MagicMock()

    def test_fetch_recent_publications(self):
        """Test fetching recent publications."""
        # Mock the execute method to return some test data
        self.news_finder.doc_db.execute.return_value = [
            {'id': 1},
            {'id': 2},
            {'id': 3}
        ]

        # Call the method
        result = self.news_finder.fetch_recent_publications()

        # Check the result
        self.assertEqual(result, [1, 2, 3])

        # Verify the execute method was called with the correct parameters
        self.news_finder.doc_db.execute.assert_called_once()
        args, kwargs = self.news_finder.doc_db.execute.call_args
        self.assertIn("SELECT id", args[0])  # Check part of the query
        self.assertEqual(len(args[1]), 2)    # Check that there are two parameters

    def test_get_abstract(self):
        """Test getting an abstract."""
        # Mock the get_document method to return a test document
        self.news_finder.doc_db.get_document.return_value = {
            'id': 1,
            'title': 'Test Document',
            'abstract': 'This is a test abstract.'
        }

        # Call the method
        result = self.news_finder.get_abstract(1)

        # Check the result
        self.assertEqual(result, 'This is a test abstract.')

        # Verify the get_document method was called with the correct parameters
        self.news_finder.doc_db.get_document.assert_called_once_with(1)

    def test_get_abstract_not_found(self):
        """Test getting an abstract when the document is not found."""
        # Mock the get_document method to return None
        self.news_finder.doc_db.get_document.return_value = None

        # Call the method
        result = self.news_finder.get_abstract(1)

        # Check the result
        self.assertEqual(result, '')

    def test_get_question_text(self):
        """Test getting a question text."""
        # Mock the get_question method to return a test question
        self.news_finder.questions_db.get_question.return_value = {
            'id': 1,
            'question': 'This is a test question?'
        }

        # Call the method
        result = self.news_finder.get_question_text(1)

        # Check the result
        self.assertEqual(result, 'This is a test question?')

        # Verify the get_question method was called with the correct parameters
        self.news_finder.questions_db.get_question.assert_called_once_with(1)

    def test_get_hypothesis_text(self):
        """Test getting a hypothesis text."""
        # Mock the get_hypothesis method to return a test hypothesis
        self.news_finder.hypotheses_db.get_hypothesis.return_value = {
            'id': 1,
            'hypothesis': 'This is a test hypothesis.'
        }

        # Call the method
        result = self.news_finder.get_hypothesis_text(1)

        # Check the result
        self.assertEqual(result, 'This is a test hypothesis.')

        # Verify the get_hypothesis method was called with the correct parameters
        self.news_finder.hypotheses_db.get_hypothesis.assert_called_once_with(1)

    @patch('localknowledge.ai.newsfinder.DocumentEvaluator')
    def test_evaluate(self, mock_evaluator_class):
        """Test evaluating a document."""
        # Mock the DocumentEvaluator
        mock_evaluator = MagicMock()
        mock_evaluator_class.return_value = mock_evaluator

        # Mock the evaluate method to return a test evaluation
        mock_evaluator.evaluate.return_value = MagicMock(
            document_id=1,
            rating=2,
            reason_for_rating="This document is relevant.",
            similarity=0.8
        )

        # Call the method
        result = self.news_finder.evaluate(1, "Test question?")

        # Check the result
        self.assertEqual(result.document_id, 1)
        self.assertEqual(result.rating, 2)
        self.assertEqual(result.reason_for_rating, "This document is relevant.")
        self.assertEqual(result.similarity, 0.8)
        self.assertEqual(result.model_name, "test-model")

        # Verify the evaluate method was called with the correct parameters
        mock_evaluator.evaluate.assert_called_once()
        args, kwargs = mock_evaluator.evaluate.call_args
        self.assertEqual(kwargs['question'], "Test question?")
        self.assertEqual(kwargs['document_id'], 1)

    def test_trawl_for_news(self):
        """Test trawling for news."""
        # Mock the get_abstract method
        self.news_finder.get_abstract = MagicMock(return_value="Test abstract")

        # Mock the get_question_text method
        self.news_finder.get_question_text = MagicMock(return_value="Test question?")

        # Mock the get_hypothesis_text method
        self.news_finder.get_hypothesis_text = MagicMock(return_value="Test hypothesis.")

        # Mock the evaluate method to return different ratings
        self.news_finder.evaluate = MagicMock(side_effect=[
            NewsItem(document_id=1, rating=1, reason_for_rating="Not very relevant", model_name="test-model"),
            NewsItem(document_id=1, rating=3, reason_for_rating="Highly relevant", model_name="test-model")
        ])

        # Call the method
        result = self.news_finder.trawl_for_news(1, [101], [201])

        # Check the result
        self.assertEqual(len(result), 1)  # Only the hypothesis evaluation has rating > 1
        self.assertEqual(result[0].rating, 3)
        self.assertEqual(result[0].reason_for_rating, "Highly relevant")

        # Verify the methods were called with the correct parameters
        self.news_finder.get_abstract.assert_called_once_with(1)
        self.news_finder.get_question_text.assert_called_once_with(101)
        self.news_finder.get_hypothesis_text.assert_called_once_with(201)
        self.assertEqual(self.news_finder.evaluate.call_count, 2)

    def test_find_news_for_project(self):
        """Test finding news for a project."""
        # Mock the get_project_questions method
        self.news_finder.questions_db.get_project_questions.return_value = [
            {'id': 101},
            {'id': 102}
        ]

        # Mock the get_project_hypotheses method
        self.news_finder.hypotheses_db.get_project_hypotheses.return_value = [
            {'id': 201},
            {'id': 202}
        ]

        # Mock the fetch_recent_publications method
        self.news_finder.fetch_recent_publications = MagicMock(return_value=[1, 2])

        # Mock the trawl_for_news method
        self.news_finder.trawl_for_news = MagicMock(side_effect=[
            [NewsItem(document_id=1, rating=2, reason_for_rating="Relevant", model_name="test-model")],
            [NewsItem(document_id=2, rating=3, reason_for_rating="Highly relevant", model_name="test-model")]
        ])

        # Call the method
        result = self.news_finder.find_news_for_project(1)

        # Check the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].document_id, 1)
        self.assertEqual(result[0].rating, 2)
        self.assertEqual(result[1].document_id, 2)
        self.assertEqual(result[1].rating, 3)

        # Verify the methods were called with the correct parameters
        self.news_finder.questions_db.get_project_questions.assert_called_once_with(1)
        self.news_finder.hypotheses_db.get_project_hypotheses.assert_called_once_with(1)
        self.news_finder.fetch_recent_publications.assert_called_once()
        self.assertEqual(self.news_finder.trawl_for_news.call_count, 2)

        # Check that trawl_for_news was called with the correct parameters
        args1, _ = self.news_finder.trawl_for_news.call_args_list[0]
        self.assertEqual(args1[0], 1)  # document_id
        self.assertEqual(args1[1], [101, 102])  # question_ids
        self.assertEqual(args1[2], [201, 202])  # hypothesis_ids

        args2, _ = self.news_finder.trawl_for_news.call_args_list[1]
        self.assertEqual(args2[0], 2)  # document_id
        self.assertEqual(args2[1], [101, 102])  # question_ids
        self.assertEqual(args2[2], [201, 202])  # hypothesis_ids


if __name__ == '__main__':
    unittest.main()
