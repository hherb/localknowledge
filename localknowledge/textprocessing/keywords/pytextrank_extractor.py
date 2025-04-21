"""
Keyword extraction using PyTextRank.

This module provides keyword extraction functionality using the PyTextRank library,
which implements the TextRank algorithm for extracting keywords from text.
"""

import logging
import spacy
import pytextrank
from typing import List, Dict, Any, Optional, Tuple
import re

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

    def _normalize_keyword(self, keyword: str) -> str:
        """
        Normalize a keyword by:
        1. Converting to lowercase
        2. Removing trailing 's' for plurals
        3. Standardizing common variations
        4. Handling domain-specific terms

        Args:
            keyword: The keyword to normalize

        Returns:
            Normalized keyword
        """
        # Convert to lowercase
        normalized = keyword.lower()

        # Handle simple plurals (words ending with 's')
        # Only remove trailing 's' if it's a simple plural (not words like 'analysis')
        if normalized.endswith('s') and not normalized.endswith(('ss', 'us', 'is')):
            singular = normalized[:-1]
            # Check if removing 's' makes sense (avoid changing words like 'status')
            if len(singular) > 3:  # Avoid short words like 'bus' -> 'bu'
                normalized = singular

        # Handle common variations (e.g., 'mismatch' vs 'mismatches')
        # This is a more aggressive normalization than just handling trailing 's'
        if 'mismatches' in normalized:
            normalized = normalized.replace('mismatches', 'mismatch')
        if 'alleles' in normalized:
            normalized = normalized.replace('alleles', 'allele')

        # Handle domain-specific terms
        # Standardize capitalization for gene names and medical terms
        # For example, convert 'dpb1' to 'DPB1' for consistency
        if 'dpb1' in normalized:
            # Keep the original capitalization for gene names
            parts = keyword.split()
            normalized_parts = []
            for part in parts:
                if part.upper() == 'DPB1' or part.lower() == 'dpb1':
                    normalized_parts.append('DPB1')
                else:
                    normalized_parts.append(part.lower())
            normalized = ' '.join(normalized_parts)

        # Standardize HLA terms
        if 'hla' in normalized:
            normalized = normalized.replace('hla', 'HLA')

        return normalized

    def _get_normalized_phrases(self, phrases: List[Tuple[str, float]]) -> List[Tuple[str, float, str]]:
        """
        Get normalized phrases with their original form and rank.

        Args:
            phrases: List of (phrase, rank) tuples

        Returns:
            List of (original_phrase, rank, normalized_phrase) tuples
        """
        normalized_phrases = []
        for phrase, rank in phrases:
            normalized = self._normalize_keyword(phrase)
            normalized_phrases.append((phrase, rank, normalized))
        return normalized_phrases

    def _remove_duplicates(self, phrases: List[Tuple[str, float, str]]) -> List[Tuple[str, float]]:
        """
        Remove duplicate phrases based on their normalized form.
        Keep the phrase with the highest rank when duplicates are found.

        Args:
            phrases: List of (original_phrase, rank, normalized_phrase) tuples

        Returns:
            List of (phrase, rank) tuples with duplicates removed
        """
        # Group phrases by their normalized form
        grouped = {}
        duplicates_found = {}

        for original, rank, normalized in phrases:
            if normalized not in grouped:
                grouped[normalized] = (original, rank)
                duplicates_found[normalized] = [original]
            else:
                duplicates_found[normalized].append(original)
                # Keep the phrase with the highest rank
                if rank > grouped[normalized][1]:
                    grouped[normalized] = (original, rank)

        # Log duplicates for debugging
        duplicates = {norm: variants for norm, variants in duplicates_found.items() if len(variants) > 1}
        if duplicates:
            logger.debug(f"Found {len(duplicates)} normalized terms with duplicates:")
            for norm, variants in duplicates.items():
                logger.debug(f"  '{norm}' appears as: {', '.join([f"'{v}'" for v in variants])}")
                logger.debug(f"  Selected: '{grouped[norm][0]}'")

        # Return the unique phrases
        return list(grouped.values())

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
                - normalize: Whether to normalize keywords (default: True)

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
            normalize = kwargs.get("normalize", True)

            # Get the phrases with their ranks
            phrases = []
            for phrase in doc._.phrases:
                if min_ngram <= len(phrase.text.split()) <= max_ngram:
                    phrases.append((phrase.text, phrase.rank))

            # Sort by rank
            sorted_phrases = sorted(phrases, key=lambda x: x[1], reverse=True)

            # Normalize and remove duplicates if requested
            if normalize:
                # First, get normalized phrases
                normalized_phrases = self._get_normalized_phrases(sorted_phrases)

                # Remove duplicates based on normalized form
                unique_phrases = self._remove_duplicates(normalized_phrases)

                # Limit the number of phrases after deduplication
                top_phrases = unique_phrases[:min(limit_phrases, len(unique_phrases))]

                # Log the deduplication results
                logger.info(f"Normalized and deduplicated keywords: {len(unique_phrases)} unique from {len(sorted_phrases)} original")
            else:
                # Just limit the number of phrases without deduplication
                top_phrases = sorted_phrases[:min(limit_phrases, len(sorted_phrases))]

            # Extract the top keywords up to max_keywords
            keywords = [phrase[0] for phrase in top_phrases[:max_keywords]]

            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords with PyTextRank: {e}")
            # Fallback to simple word frequency if PyTextRank fails
            return self._fallback_extraction(text, max_keywords)

    def _fallback_extraction(self, text: str, max_keywords: int = 10, **kwargs) -> List[str]:
        """
        Fallback keyword extraction using simple word frequency.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            **kwargs: Additional parameters for extraction
                - normalize: Whether to normalize keywords (default: True)

        Returns:
            List of keywords
        """
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

        # Check if normalization is requested
        normalize = kwargs.get("normalize", True)

        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            # Normalize the word if requested
            if normalize:
                word = self._normalize_keyword(word)
            word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top keywords
        return [word for word, _ in sorted_words[:max_keywords]]
