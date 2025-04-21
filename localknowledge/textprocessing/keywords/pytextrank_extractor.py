"""
Keyword extraction using PyTextRank.

This module provides keyword extraction functionality using the PyTextRank library,
which implements the TextRank algorithm for extracting keywords from text.
"""

import logging
import spacy
import pytextrank
from typing import List, Dict, Any, Optional

from localknowledge.textprocessing.keywords.base import BaseKeywordExtractor

# Configure logging
logger = logging.getLogger(__name__)


class PyTextRankExtractor(BaseKeywordExtractor):
    """
    Keyword extractor using PyTextRank.
    """

    def __init__(self, spacy_model: str = "en_core_web_sm", **kwargs):
        """
        Initialize the PyTextRank keyword extractor.

        Args:
            spacy_model: Name of the spaCy model to use
            **kwargs: Additional parameters for the extractor
        """
        super().__init__(**kwargs)
        self.spacy_model = spacy_model
        self._initialize_nlp()

    def _initialize_nlp(self):
        """Initialize the spaCy NLP pipeline with PyTextRank."""
        try:
            # Load spaCy model
            self.nlp = spacy.load(self.spacy_model)
            
            # Add PyTextRank to the pipeline
            self.nlp.add_pipe("textrank")
            
            logger.info(f"Successfully initialized PyTextRank with spaCy model {self.spacy_model}")
        except Exception as e:
            logger.error(f"Error initializing PyTextRank: {e}")
            raise

    def extract_keywords(self, text: str, max_keywords: int = 10, **kwargs) -> List[str]:
        """
        Extract keywords from text using PyTextRank.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            **kwargs: Additional parameters for extraction
                - min_ngram: Minimum n-gram size (default: 1)
                - max_ngram: Maximum n-gram size (default: 3)
                - limit_phrases: Limit number of phrases to consider (default: 20)

        Returns:
            List of keywords
        """
        if not text:
            return []

        try:
            # Process the text with spaCy and PyTextRank
            doc = self.nlp(text)
            
            # Extract parameters
            min_ngram = kwargs.get("min_ngram", 1)
            max_ngram = kwargs.get("max_ngram", 3)
            limit_phrases = kwargs.get("limit_phrases", 20)
            
            # Get the phrases with their ranks
            phrases = []
            for phrase in doc._.phrases:
                if min_ngram <= len(phrase.text.split()) <= max_ngram:
                    phrases.append((phrase.text, phrase.rank))
            
            # Sort by rank and limit the number of phrases
            sorted_phrases = sorted(phrases, key=lambda x: x[1], reverse=True)
            top_phrases = sorted_phrases[:min(limit_phrases, len(sorted_phrases))]
            
            # Extract the top keywords up to max_keywords
            keywords = [phrase[0] for phrase in top_phrases[:max_keywords]]
            
            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords with PyTextRank: {e}")
            # Fallback to simple word frequency if PyTextRank fails
            return self._fallback_extraction(text, max_keywords)

    def _fallback_extraction(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Fallback keyword extraction using simple word frequency.
        
        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            
        Returns:
            List of keywords
        """
        import re
        
        # Remove common punctuation and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into words
        words = text.split()
        
        # Remove common stop words
        stop_words = {'the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'with', 'on', 'at', 'from',
                     'by', 'an', 'this', 'that', 'these', 'those', 'it', 'as', 'be', 'are', 'was',
                     'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but',
                     'or', 'if', 'because', 'not', 'what', 'which', 'who', 'whom', 'whose', 'when',
                     'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
                     'other', 'some', 'such', 'no', 'nor', 'only', 'own', 'same', 'so', 'than',
                     'too', 'very', 'can', 'will', 'just', 'should', 'now'}
        
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Return top keywords
        return [word for word, _ in sorted_words[:max_keywords]]
