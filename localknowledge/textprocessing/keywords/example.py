#!/usr/bin/env python3
"""
Example usage of the keyword extraction module.

Usage:
    python example.py [file_path]

If file_path is provided, extracts keywords from the specified text file.
Otherwise, uses a sample text for demonstration.
"""

import logging
import sys
import os
import argparse
from localknowledge.textprocessing.keywords import PyTextRankExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_sample_text():
    """Return a sample text for demonstration."""
    return """
    Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals including humans.
    AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals.
    The term "artificial intelligence" had previously been used to describe machines that mimic and display "human" cognitive skills that are associated with the human mind, such as "learning" and "problem-solving".
    This definition has since been rejected by major AI researchers who now describe AI in terms of rationality and acting rationally, which does not limit how intelligence can be articulated.
    AI applications include advanced web search engines, recommendation systems, understanding human speech, self-driving cars, automated decision-making, and competing at the highest level in strategic game systems.
    As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect.
    """


def read_text_file(file_path):
    """Read text from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise


def extract_and_print_keywords(extractor, text, title=""):
    """Extract and print keywords from text."""
    if title:
        print(f"\n{title}")

    # Extract a larger set of keywords without normalization first
    logger.info("Extracting keywords without normalization...")
    keywords_no_norm = extractor.extract_keywords(text, max_keywords=30, normalize=False)

    # Print results
    print("\nExtracted Keywords (WITHOUT normalization):")
    for i, keyword in enumerate(keywords_no_norm, 1):
        print(f"{i}. {keyword}")

    # Count duplicates by lowercase comparison
    lowercase_keywords = [k.lower() for k in keywords_no_norm]
    unique_lowercase = set(lowercase_keywords)
    print(f"\nWithout normalization: {len(keywords_no_norm)} keywords, {len(unique_lowercase)} unique lowercase terms")

    # Find duplicates
    duplicates = {}
    for k in lowercase_keywords:
        duplicates[k] = duplicates.get(k, 0) + 1
    duplicate_terms = [k for k, count in duplicates.items() if count > 1]
    if duplicate_terms:
        print("\nDuplicate terms (case-insensitive):")
        for term in duplicate_terms:
            variants = [k for k in keywords_no_norm if k.lower() == term]
            print(f"  '{term}' appears as: {', '.join([f"'{v}'" for v in variants])}")

    # Find plural/singular pairs
    print("\nPotential plural/singular pairs:")
    for keyword in keywords_no_norm:
        lower_keyword = keyword.lower()
        # Check for simple plurals
        if lower_keyword.endswith('s') and not lower_keyword.endswith(('ss', 'us', 'is')):
            singular = lower_keyword[:-1]
            if singular in lowercase_keywords:
                print(f"  Found pair: '{singular}' and '{lower_keyword}'")

    # Extract keywords with normalization
    logger.info("Extracting keywords with normalization...")
    keywords = extractor.extract_keywords(text, max_keywords=30, normalize=True)

    # Print results
    print("\nExtracted Keywords (WITH normalization):")
    for i, keyword in enumerate(keywords, 1):
        print(f"{i}. {keyword}")
    print(f"\nWith normalization: {len(keywords)} keywords")

    # Try with different parameters for multi-word phrases
    logger.info("Extracting multi-word keywords with normalization...")
    print("\nMulti-word Keywords (2-3 words only, with normalization):")
    keywords2 = extractor.extract_keywords(
        text,
        max_keywords=10,
        min_ngram=2,
        max_ngram=3,
        normalize=True
    )

    for i, keyword in enumerate(keywords2, 1):
        print(f"{i}. {keyword}")


def main():
    """Example usage of the PyTextRankExtractor."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Extract keywords from text using PyTextRank.")
    parser.add_argument('file_path', nargs='?', help='Path to a text file to process')
    args = parser.parse_args()

    try:
        # Initialize the extractor
        logger.info("Initializing PyTextRankExtractor...")
        extractor = PyTextRankExtractor()

        # Get text from file or use sample text
        if args.file_path:
            if not os.path.exists(args.file_path):
                logger.error(f"File not found: {args.file_path}")
                return 1

            logger.info(f"Reading text from file: {args.file_path}")
            text = read_text_file(args.file_path)
            extract_and_print_keywords(extractor, text, f"Keywords from: {args.file_path}")
        else:
            logger.info("No file provided, using sample text")
            text = get_sample_text()
            extract_and_print_keywords(extractor, text, "Keywords from sample text:")

    except Exception as e:
        logger.error(f"Error in example: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
