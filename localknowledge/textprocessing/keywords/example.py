#!/usr/bin/env python3
"""
Example usage of the keyword extraction module.
"""

import logging
import sys
from localknowledge.textprocessing.keywords import PyTextRankExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Example usage of the PyTextRankExtractor."""
    try:
        # Initialize the extractor
        logger.info("Initializing PyTextRankExtractor...")
        extractor = PyTextRankExtractor()
        
        # Sample text
        text = """
        Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals including humans. 
        AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals.
        The term "artificial intelligence" had previously been used to describe machines that mimic and display "human" cognitive skills that are associated with the human mind, such as "learning" and "problem-solving".
        This definition has since been rejected by major AI researchers who now describe AI in terms of rationality and acting rationally, which does not limit how intelligence can be articulated.
        AI applications include advanced web search engines, recommendation systems, understanding human speech, self-driving cars, automated decision-making, and competing at the highest level in strategic game systems.
        As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect.
        """
        
        # Extract keywords
        logger.info("Extracting keywords...")
        keywords = extractor.extract_keywords(text, max_keywords=10)
        
        # Print results
        print("\nExtracted Keywords:")
        for i, keyword in enumerate(keywords, 1):
            print(f"{i}. {keyword}")
            
        # Try with different parameters
        print("\nKeywords with different parameters:")
        keywords2 = extractor.extract_keywords(
            text, 
            max_keywords=5, 
            min_ngram=2, 
            max_ngram=3
        )
        
        for i, keyword in enumerate(keywords2, 1):
            print(f"{i}. {keyword}")
            
    except Exception as e:
        logger.error(f"Error in example: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
