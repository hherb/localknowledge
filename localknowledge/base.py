"""
Base module for common functionality across different knowledge sources.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class LocalKnowledgeBase(ABC):
    """
    Abstract base class for accessing and managing local knowledge databases.
    
    This class provides a common interface for different knowledge sources
    like PubMed and medRxiv, making it easier to add new sources in the future.
    """
    
    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize the knowledge base client.
        
        Args:
            database_path: Path to the local database. If None, uses default location.
        """
        self.database_path = database_path
        self._initialize_database()
    
    def _initialize_database(self):
        """
        Set up the database connection and create necessary tables if they don't exist.
        """
        # Placeholder for database initialization logic
        pass
    
    @abstractmethod
    def search(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search the local database.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of articles matching the query
        """
        pass
    
    @abstractmethod
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific article by ID.
        
        Args:
            article_id: ID of the article (specific to the knowledge source)
            
        Returns:
            Article data or None if not found
        """
        pass
    
    @abstractmethod
    def download_updates(self, from_date: Optional[datetime] = None) -> int:
        """
        Update the local database with the latest articles.
        
        Args:
            from_date: Download articles published after this date
            
        Returns:
            Number of new articles added
        """
        pass
    
    def validate_article(self, article_data: Dict[str, Any]) -> bool:
        """
        Validate article data before adding to database.
        
        Args:
            article_data: Article data to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Common validation logic
        required_fields = ['title', 'authors', 'date', 'abstract']
        return all(field in article_data for field in required_fields)
    
    def cleanup(self):
        """
        Cleanup resources like database connections.
        """
        # Common cleanup logic
        pass
