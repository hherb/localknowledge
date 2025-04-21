"""
Base class for keyword extraction strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseKeywordExtractor(ABC):
    """
    Base class for keyword extraction strategies.
    """

    def __init__(self, **kwargs):
        """
        Initialize the keyword extractor with optional parameters.

        Args:
            **kwargs: Additional parameters for the extractor
        """
        self.params = kwargs

    @abstractmethod
    def extract_keywords(self, text: str, max_keywords: int = 10, **kwargs) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            **kwargs: Additional parameters for extraction

        Returns:
            List of keywords
        """
        pass
