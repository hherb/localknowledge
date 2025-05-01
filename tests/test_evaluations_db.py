"""
Tests for the EvaluationsDatabaseManager class.
"""
import unittest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from localknowledge.db.evaluations import EvaluationsDatabaseManager


class TestEvaluationsDatabaseManager(unittest.TestCase):
    """Test cases for the EvaluationsDatabaseManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock for the database connection
        self.patcher = patch('localknowledge.db.base.DatabaseManager.__init__')
        self.mock_db_init = self.patcher.start()
        self.mock_db_init.return_value = None

        # Create an instance of EvaluationsDatabaseManager with mocked connection
        self.evaluations_db = EvaluationsDatabaseManager()
        self.evaluations_db.execute = MagicMock()

        # Sample data for testing
        self.research_question_id = 1
        self.chunk_id = 100
        self.evaluator_id = 10
        self.document_id = 1000
        self.is_human_evaluator = False
        self.rating = 4
        self.confidence_level = 0.85
        self.rating_reason = "This chunk directly addresses the research question"

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()

    def test_create_evaluation(self):
        """Test creating an evaluation."""
        # Set up the mock to return a success result
        self.evaluations_db.execute.return_value = True

        # Call the method
        result = self.evaluations_db.create_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id,
            document_id=self.document_id,
            is_human_evaluator=self.is_human_evaluator,
            rating=self.rating,
            confidence_level=self.confidence_level,
            rating_reason=self.rating_reason
        )

        # Verify the result
        self.assertTrue(result, "Failed to create evaluation")

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, kwargs = self.evaluations_db.execute.call_args

        # Check that the query contains the INSERT statement
        self.assertIn("INSERT INTO evaluations", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], self.chunk_id)
        self.assertEqual(args[1][2], self.evaluator_id)
        self.assertEqual(args[1][3], self.document_id)
        self.assertEqual(args[1][4], self.is_human_evaluator)
        self.assertEqual(args[1][5], self.rating)
        self.assertEqual(args[1][6], self.rating_reason)
        self.assertEqual(args[1][7], self.confidence_level)

        # Check that commit is True
        self.assertTrue(kwargs.get('commit', False))

    def test_create_evaluation_invalid_rating(self):
        """Test creating an evaluation with an invalid rating."""
        # Call the method with an invalid rating
        result = self.evaluations_db.create_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id,
            document_id=self.document_id,
            is_human_evaluator=self.is_human_evaluator,
            rating=6,  # Invalid: should be 0-5
            confidence_level=self.confidence_level,
            rating_reason=self.rating_reason
        )

        # Verify the result
        self.assertFalse(result, "Should fail with invalid rating")

        # Verify that execute was not called
        self.evaluations_db.execute.assert_not_called()

    def test_create_evaluation_invalid_confidence(self):
        """Test creating an evaluation with an invalid confidence level."""
        # Call the method with an invalid confidence level
        result = self.evaluations_db.create_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id,
            document_id=self.document_id,
            is_human_evaluator=self.is_human_evaluator,
            rating=self.rating,
            confidence_level=1.5,  # Invalid: should be 0.0-1.0
            rating_reason=self.rating_reason
        )

        # Verify the result
        self.assertFalse(result, "Should fail with invalid confidence level")

        # Verify that execute was not called
        self.evaluations_db.execute.assert_not_called()

    def test_get_evaluation(self):
        """Test getting an evaluation by its composite primary key."""
        # Set up the mock to return a sample evaluation
        sample_evaluation = {
            'research_question_id': self.research_question_id,
            'chunk_id': self.chunk_id,
            'evaluator_id': self.evaluator_id,
            'document_id': self.document_id,
            'is_human_evaluator': self.is_human_evaluator,
            'rating': self.rating,
            'confidence_level': self.confidence_level,
            'rating_reason': self.rating_reason,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'evaluation_version': 1
        }
        self.evaluations_db.execute.return_value = [sample_evaluation]

        # Call the method
        result = self.evaluations_db.get_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id
        )

        # Verify the result
        self.assertEqual(result, sample_evaluation)

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT statement
        self.assertIn("SELECT *", args[0])
        self.assertIn("FROM evaluations", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], self.chunk_id)
        self.assertEqual(args[1][2], self.evaluator_id)

    def test_get_evaluations_by_research_question(self):
        """Test getting evaluations by research question."""
        # Set up the mock to return sample evaluations
        sample_evaluations = [
            {
                'research_question_id': self.research_question_id,
                'chunk_id': self.chunk_id,
                'evaluator_id': self.evaluator_id,
                'document_id': self.document_id,
                'is_human_evaluator': self.is_human_evaluator,
                'rating': self.rating,
                'confidence_level': self.confidence_level,
                'rating_reason': self.rating_reason,
                'chunk_text': 'Sample chunk text',
                'document_title': 'Sample Document',
                'evaluator_name': 'Test Evaluator'
            },
            {
                'research_question_id': self.research_question_id,
                'chunk_id': self.chunk_id + 1,
                'evaluator_id': self.evaluator_id,
                'document_id': self.document_id,
                'is_human_evaluator': self.is_human_evaluator,
                'rating': self.rating - 1,
                'confidence_level': self.confidence_level - 0.1,
                'rating_reason': 'Another reason',
                'chunk_text': 'Another chunk text',
                'document_title': 'Sample Document',
                'evaluator_name': 'Test Evaluator'
            }
        ]
        self.evaluations_db.execute.return_value = sample_evaluations

        # Call the method
        result = self.evaluations_db.get_evaluations_by_research_question(
            research_question_id=self.research_question_id,
            min_rating=3,
            human_only=False,
            limit=10,
            offset=0
        )

        # Verify the result
        self.assertEqual(result, sample_evaluations)

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT statement with JOINs
        self.assertIn("SELECT e.*, c.text as chunk_text, c.document_title, ev.name as evaluator_name", args[0])
        self.assertIn("JOIN chunks c ON e.chunk_id = c.id", args[0])
        self.assertIn("JOIN evaluators ev ON e.evaluator_id = ev.id", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], 3)  # min_rating
        self.assertEqual(args[1][2], 10)  # limit
        self.assertEqual(args[1][3], 0)   # offset

    def test_update_evaluation(self):
        """Test updating an evaluation."""
        # Set up the mock to return a success result
        self.evaluations_db.execute.return_value = [{'affected_rows': 1}]

        # Call the method
        result = self.evaluations_db.update_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id,
            rating=5,
            confidence_level=0.9,
            rating_reason="Updated reason"
        )

        # Verify the result
        self.assertTrue(result, "Failed to update evaluation")

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, kwargs = self.evaluations_db.execute.call_args

        # Check that the query contains the UPDATE statement
        self.assertIn("UPDATE evaluations", args[0])

        # Check that the parameters are correct (last three are the primary key)
        self.assertEqual(args[1][0], 5)  # rating
        self.assertEqual(args[1][1], 0.9)  # confidence_level
        self.assertEqual(args[1][2], "Updated reason")  # rating_reason
        self.assertEqual(args[1][3], self.research_question_id)
        self.assertEqual(args[1][4], self.chunk_id)
        self.assertEqual(args[1][5], self.evaluator_id)

        # Check that commit is True
        self.assertTrue(kwargs.get('commit', False))

    def test_delete_evaluation(self):
        """Test deleting an evaluation."""
        # Set up the mock to return a success result
        self.evaluations_db.execute.return_value = True

        # Call the method
        result = self.evaluations_db.delete_evaluation(
            research_question_id=self.research_question_id,
            chunk_id=self.chunk_id,
            evaluator_id=self.evaluator_id
        )

        # Verify the result
        self.assertTrue(result, "Failed to delete evaluation")

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, kwargs = self.evaluations_db.execute.call_args

        # Check that the query contains the DELETE statement
        self.assertIn("DELETE FROM evaluations", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], self.chunk_id)
        self.assertEqual(args[1][2], self.evaluator_id)

        # Check that commit is True
        self.assertTrue(kwargs.get('commit', False))

    def test_get_evaluation_stats_by_question(self):
        """Test getting evaluation statistics for a research question."""
        # Set up the mock to return sample statistics
        sample_stats = {
            'total_evaluations': 25,
            'average_rating': 3.8,
            'average_confidence': 0.75,
            'unique_documents': 10,
            'unique_chunks': 15,
            'unique_evaluators': 3,
            'human_evaluations': 5,
            'ai_evaluations': 20
        }
        self.evaluations_db.execute.return_value = [sample_stats]

        # Call the method
        result = self.evaluations_db.get_evaluation_stats_by_question(
            research_question_id=self.research_question_id
        )

        # Verify the result
        self.assertEqual(result, sample_stats)

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT statement with aggregations
        self.assertIn("SELECT", args[0])
        self.assertIn("COUNT(*) as total_evaluations", args[0])
        self.assertIn("AVG(rating) as average_rating", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)

    def test_get_top_rated_chunks_for_question(self):
        """Test getting top-rated chunks for a research question."""
        # Set up the mock to return sample top-rated chunks
        sample_top_chunks = [
            {
                'chunk_id': self.chunk_id,
                'document_id': self.document_id,
                'chunk_text': 'Sample chunk text',
                'document_title': 'Sample Document',
                'average_rating': 4.5,
                'average_confidence': 0.85,
                'evaluator_count': 3,
                'evaluators': 'Evaluator1, Evaluator2, Evaluator3'
            },
            {
                'chunk_id': self.chunk_id + 1,
                'document_id': self.document_id,
                'chunk_text': 'Another chunk text',
                'document_title': 'Sample Document',
                'average_rating': 4.0,
                'average_confidence': 0.8,
                'evaluator_count': 2,
                'evaluators': 'Evaluator1, Evaluator2'
            }
        ]
        self.evaluations_db.execute.return_value = sample_top_chunks

        # Call the method
        result = self.evaluations_db.get_top_rated_chunks_for_question(
            research_question_id=self.research_question_id,
            min_rating=3,
            limit=10,
            human_only=False
        )

        # Verify the result
        self.assertEqual(result, sample_top_chunks)

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT statement with GROUP BY
        self.assertIn("SELECT", args[0])
        self.assertIn("AVG(e.rating) as average_rating", args[0])
        self.assertIn("GROUP BY", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], 3)  # min_rating
        self.assertEqual(args[1][2], 10)  # limit

    def test_documents_by_rating_for_question(self):
        """Test getting document IDs by rating for a research question."""
        # Set up the mock to return sample document IDs
        sample_document_ids = [
            {'document_id': 1000},
            {'document_id': 1001},
            {'document_id': 1002}
        ]
        self.evaluations_db.execute.return_value = sample_document_ids

        # Call the method
        result = self.evaluations_db.documents_by_rating_for_question(
            rating=4,
            question_id=self.research_question_id
        )

        # Verify the result
        self.assertEqual(result, [1000, 1001, 1002])

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT DISTINCT statement
        self.assertIn("SELECT DISTINCT document_id", args[0])
        self.assertIn("FROM evaluations", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], 4)  # rating

    def test_documents_by_rating_for_question_with_evaluator(self):
        """Test getting document IDs by rating for a research question with specific evaluator."""
        # Set up the mock to return sample document IDs
        sample_document_ids = [
            {'document_id': 1000},
            {'document_id': 1001}
        ]
        self.evaluations_db.execute.return_value = sample_document_ids

        # Call the method with evaluator_id
        result = self.evaluations_db.documents_by_rating_for_question(
            rating=4,
            question_id=self.research_question_id,
            evaluator_id=self.evaluator_id
        )

        # Verify the result
        self.assertEqual(result, [1000, 1001])

        # Verify that execute was called with the correct parameters
        self.evaluations_db.execute.assert_called_once()
        args, _ = self.evaluations_db.execute.call_args

        # Check that the query contains the SELECT DISTINCT statement
        self.assertIn("SELECT DISTINCT document_id", args[0])
        self.assertIn("FROM evaluations", args[0])
        self.assertIn("AND evaluator_id = %s", args[0])

        # Check that the parameters are correct
        self.assertEqual(args[1][0], self.research_question_id)
        self.assertEqual(args[1][1], 4)  # rating
        self.assertEqual(args[1][2], self.evaluator_id)

    def test_documents_by_rating_for_question_invalid_rating(self):
        """Test getting document IDs with an invalid rating."""
        # Call the method with an invalid rating
        result = self.evaluations_db.documents_by_rating_for_question(
            rating=6,  # Invalid: should be 0-5
            question_id=self.research_question_id
        )

        # Verify the result is an empty list
        self.assertEqual(result, [])

        # Verify that execute was not called
        self.evaluations_db.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
