#!/usr/bin/env python3
"""
Unit tests for the PyTextRankExtractor class.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# Configure logging for tests
logging.basicConfig(level=logging.INFO)

# Import the class to test
from localknowledge.textprocessing.keywords.pytextrank_extractor import PyTextRankExtractor


# Check if spaCy model is available
def is_spacy_model_available(model_name="en_core_web_sm"):
    """Check if the specified spaCy model is available."""
    try:
        import spacy
        import sys
        print(f"\nPython path: {sys.path}")
        print(f"spaCy version: {spacy.__version__}")
        print(f"Available spaCy models: {', '.join(spacy.util.get_installed_models())}")

        # Try to load the model
        nlp = spacy.load(model_name)
        print(f"Successfully loaded model: {model_name}")
        return True
    except Exception as e:
        print(f"Error loading spaCy model: {e}")
        return False


class TestPyTextRankExtractor(unittest.TestCase):
    """Test cases for the PyTextRankExtractor class."""

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.spacy_available = is_spacy_model_available()
        if not cls.spacy_available:
            print("\nWARNING: spaCy model 'en_core_web_sm' is not available.")
            print("Some tests will be skipped or will use mocks.")
            print("To install the required model, run: python -m spacy download en_core_web_sm\n")
            print("\nRunning tests with mocks instead of the actual model.\n")

    def setUp(self):
        """Set up test fixtures."""
        # Sample text for testing
        self.sample_text = """
        Artificial intelligence (AI) is intelligence demonstrated by machines,
        as opposed to natural intelligence displayed by animals including humans.
        AI research has been defined as the field of study of intelligent agents,
        which refers to any system that perceives its environment and takes actions
        that maximize its chance of achieving its goals.

        The term "artificial intelligence" had previously been used to describe
        machines that mimic and display "human" cognitive skills that are associated
        with the human mind, such as "learning" and "problem-solving". This definition
        has since been rejected by major AI researchers who now describe AI in terms
        of rationality and acting rationally, which does not limit how intelligence
        can be articulated.
        """

        # Initialize the extractor if spaCy is available
        if self.spacy_available:
            try:
                self.extractor = PyTextRankExtractor()
            except Exception as e:
                self.skipTest(f"Could not initialize PyTextRankExtractor: {e}")
        else:
            # Create a mock extractor for tests that don't require the actual model
            self.extractor = None

    def test_initialization(self):
        """Test initialization with default and custom parameters."""
        if not self.spacy_available:
            self.skipTest("spaCy model not available")

        # Test default initialization
        extractor = PyTextRankExtractor()
        self.assertEqual(extractor.spacy_model, "en_core_web_sm")

        # Test custom initialization
        with patch('spacy.load'):
            extractor = PyTextRankExtractor(spacy_model="en_core_web_md")
            self.assertEqual(extractor.spacy_model, "en_core_web_md")

    def test_extract_keywords(self):
        """Test keyword extraction with default parameters."""
        if not self.spacy_available:
            self.skipTest("spaCy model not available")

        keywords = self.extractor.extract_keywords(self.sample_text)

        # Check that we got some keywords
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)
        self.assertLessEqual(len(keywords), 10)  # Default max_keywords is 10

        # Check that the keywords are relevant to the text
        relevant_terms = ["artificial intelligence", "intelligence", "human", "researchers",
                          "cognitive", "learning", "problem-solving", "rationality"]

        found_relevant = False
        for keyword in keywords:
            if any(term.lower() in keyword.lower() for term in relevant_terms):
                found_relevant = True
                break

        self.assertTrue(found_relevant, f"No relevant keywords found in {keywords}")

    def test_extract_keywords_with_params(self):
        """Test keyword extraction with custom parameters."""
        if not self.spacy_available:
            self.skipTest("spaCy model not available")

        # Test with different max_keywords
        keywords = self.extractor.extract_keywords(self.sample_text, max_keywords=5)
        self.assertLessEqual(len(keywords), 5)

        # Test with different n-gram parameters
        keywords = self.extractor.extract_keywords(
            self.sample_text,
            max_keywords=10,
            min_ngram=2,
            max_ngram=3
        )

        # Check that we got some keywords
        self.assertGreater(len(keywords), 0)

        # Check that the keywords are multi-word phrases (n-grams)
        for keyword in keywords:
            words = keyword.split()
            self.assertGreaterEqual(len(words), 2, f"Keyword '{keyword}' is not a multi-word phrase")
            self.assertLessEqual(len(words), 3, f"Keyword '{keyword}' has more than 3 words")

    def test_empty_text(self):
        """Test handling of empty text."""
        if not self.spacy_available:
            # Create a mock extractor for this test
            with patch('localknowledge.textprocessing.keywords.pytextrank_extractor.PyTextRankExtractor._initialize_nlp'):
                extractor = PyTextRankExtractor()

                keywords = extractor.extract_keywords("")
                self.assertEqual(keywords, [])

                keywords = extractor.extract_keywords(None)
                self.assertEqual(keywords, [])
        else:
            keywords = self.extractor.extract_keywords("")
            self.assertEqual(keywords, [])

            keywords = self.extractor.extract_keywords(None)
            self.assertEqual(keywords, [])

    def test_fallback_extraction(self):
        """Test the fallback extraction method."""
        # Create a new extractor or use the existing one
        if not self.spacy_available:
            with patch('localknowledge.textprocessing.keywords.pytextrank_extractor.PyTextRankExtractor._initialize_nlp'):
                extractor = PyTextRankExtractor()

                # Test the fallback method directly
                keywords = extractor._fallback_extraction(self.sample_text, max_keywords=5)
        else:
            # Test the fallback method directly
            keywords = self.extractor._fallback_extraction(self.sample_text, max_keywords=5)

        # Check that we got some keywords
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)
        self.assertLessEqual(len(keywords), 5)

        # Check that the keywords are relevant to the text
        relevant_terms = ["artificial", "intelligence", "human", "researchers",
                          "cognitive", "learning", "problem", "solving", "rationality"]

        found_relevant = False
        for keyword in keywords:
            if any(term.lower() in keyword.lower() for term in relevant_terms):
                found_relevant = True
                break

        self.assertTrue(found_relevant, f"No relevant keywords found in {keywords}")

    def test_extraction_error_handling(self):
        """Test error handling during extraction."""
        # Test the fallback mechanism directly
        # We'll create a simple test text and expected keywords
        test_text = "This is a test about artificial intelligence and machine learning."
        expected_keywords = ["artificial", "intelligence", "machine", "learning", "test"]

        # Call the fallback method directly
        if not self.spacy_available:
            with patch('localknowledge.textprocessing.keywords.pytextrank_extractor.PyTextRankExtractor._initialize_nlp'):
                extractor = PyTextRankExtractor()
                keywords = extractor._fallback_extraction(test_text, max_keywords=5)
        else:
            keywords = self.extractor._fallback_extraction(test_text, max_keywords=5)

        # Check that we got some keywords from the fallback method
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)

        # Check that at least some of the expected keywords are present
        found_keywords = 0
        for keyword in keywords:
            if keyword in expected_keywords:
                found_keywords += 1

        self.assertGreater(found_keywords, 0, "No expected keywords found in the results")


    def test_mock_extraction(self):
        """Test extraction with mocked spaCy and PyTextRank."""
        # Create mocks for spaCy and PyTextRank
        mock_doc = MagicMock()
        mock_phrase1 = MagicMock()
        mock_phrase1.text = "artificial intelligence"
        mock_phrase1.rank = 0.8

        mock_phrase2 = MagicMock()
        mock_phrase2.text = "machine learning"
        mock_phrase2.rank = 0.7

        mock_phrase3 = MagicMock()
        mock_phrase3.text = "natural language processing"
        mock_phrase3.rank = 0.6

        # Set up the phrases attribute
        mock_doc._.phrases = [mock_phrase1, mock_phrase2, mock_phrase3]

        with patch('spacy.load'), \
             patch('localknowledge.textprocessing.keywords.pytextrank_extractor.PyTextRankExtractor._initialize_nlp'):

            # Create a new extractor with mocked NLP
            extractor = PyTextRankExtractor()

            # Replace the NLP pipeline with our mock
            extractor.nlp = MagicMock(return_value=mock_doc)

            # Test extraction with mocked objects
            keywords = extractor.extract_keywords("This is a test", max_keywords=2)

            # We should get the top 2 phrases
            self.assertEqual(len(keywords), 2)
            self.assertEqual(keywords[0], "artificial intelligence")
            self.assertEqual(keywords[1], "machine learning")


if __name__ == '__main__':
    unittest.main()
