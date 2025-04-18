"""
Base database functionality for the LocalKnowledge library.

This module provides a base class for database connections and operations
that can be extended for different data sources.
"""
import os
import psycopg2
from psycopg2.extras import DictCursor
from typing import List, Dict, Any, Optional, Tuple, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseManager:
    """Base class for database operations."""
    
    def __init__(self):
        """
        Initialize the database manager.
        
        Uses environment variables for connection parameters:
        - POSTGRES_DB: Database name
        - POSTGRES_USER: Database user
        - POSTGRES_PASSWORD: Database password
        - POSTGRES_HOST: Database host
        - POSTGRES_PORT: Database port
        """
        self.connection = None
        self.connect()
        
    def connect(self):
        """Connect to the database using environment variables."""
        dbname = os.environ.get('POSTGRES_DB')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        
        if not dbname:
            raise ValueError("POSTGRES_DB environment variable must be set")
        
        try:
            self.connection = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL database: {e}")
    
    def execute(self, query: str, params: Optional[Tuple] = None, commit: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit the transaction
            
        Returns:
            Query results as a list of dictionaries, or None for non-SELECT queries
        """
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor(cursor_factory=DictCursor)
        try:
            cursor.execute(query, params or ())
            
            if commit:
                self.connection.commit()
                return None
            
            if cursor.description:  # This is a SELECT query
                return [dict(row) for row in cursor.fetchall()]
            return None
            
        except psycopg2.Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Execute a SQL query with multiple parameter sets.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
        """
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor()
        try:
            cursor.executemany(query, params_list)
            self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def create_tables(self) -> None:
        """
        Create database tables if they do not exist.
        
        Should be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement create_tables()")
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        """Enable context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection when exiting context."""
        self.close()
