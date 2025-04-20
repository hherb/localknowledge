"""
Database functionality for PubMed articles.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger()

class PubMedDatabaseManager(DatabaseManager):
    """Database manager for PubMed articles."""
    
    def __init__(self, create_indices: bool=False):
        """Initialize the PubMed database manager."""
        super().__init__()
        logger.info("Initializing PubMed database manager")
        self.create_tables()
        if create_indices:
            self.create_indices()
    
    def create_tables(self) -> None:
        """Create PubMed tables if they don't exist."""
        # Create articles table
        logger.info("Creating PubMed database tables")
        self.execute("""
        CREATE TABLE IF NOT EXISTS pubmed_articles (
            pmid TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            publication_year TEXT,
            journal TEXT,
            mesh_terms TEXT,
            keywords TEXT,
            doi TEXT,
            date_created TEXT,
            date_completed TEXT,
            date_revised TEXT,
            pdf_path TEXT,
            imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """, commit=True)
        logger.info("PubMed articles table created or verified")
        
        

    def create_indices(self) -> None:
        logger.info("Dropping existing indices for PubMed articles")
        self.execute("DROP INDEX IF EXISTS idx_pmid_pm", commit=True)
        self.execute("DROP INDEX IF EXISTS idx_title_pm", commit=True)
        self.execute("DROP INDEX IF EXISTS idx_abstract_fts_pm", commit=True) 
        self.execute("DROP INDEX IF EXISTS idx_authors_pm", commit=True)
        self.execute("DROP INDEX IF EXISTS idx_year_pm", commit=True)
        self.execute("DROP INDEX IF EXISTS idx_mesh_pm", commit=True)
        
        logger.info("Creating indices (if not existing) for PubMed articles")
        # Create fulltext search indexes
        # Use substring for title to avoid PostgreSQL index size limitations
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_title_pm ON pubmed_articles(substring(title, 1, 2000))
        """, commit=True)
        
        # Use GIN index for full-text search on abstract, which handles large text better
        # than btree indexes as it creates an inverted index of tokens
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_abstract_fts_pm ON pubmed_articles 
        USING gin(to_tsvector('english', left(abstract, 100000)))
        """, commit=True)
        
        # Limit indexed content for other fields to avoid size limits
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_authors_pm ON pubmed_articles(substring(authors, 1, 2000))
        """, commit=True)
        
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_year_pm ON pubmed_articles(publication_year)
        """, commit=True)
        
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_mesh_pm ON pubmed_articles(substring(mesh_terms, 1, 2000))
        """, commit=True)

    
    def store_article(self, article: Dict[str, Any]) -> None:
        """
        Store a PubMed article in the database.
        
        Args:
            article: Dictionary containing article data
        """
        query = """
        INSERT INTO pubmed_articles 
            (pmid, title, abstract, authors, publication_year, journal, mesh_terms, keywords, doi, 
             date_created, date_completed, date_revised, pdf_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (pmid) DO UPDATE SET
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            authors = EXCLUDED.authors,
            publication_year = EXCLUDED.publication_year,
            journal = EXCLUDED.journal,
            mesh_terms = EXCLUDED.mesh_terms,
            keywords = EXCLUDED.keywords,
            doi = EXCLUDED.doi,
            date_created = EXCLUDED.date_created,
            date_completed = EXCLUDED.date_completed,
            date_revised = EXCLUDED.date_revised,
            pdf_path = EXCLUDED.pdf_path,
            imported_date = CURRENT_TIMESTAMP
        """
        params = (
            article.get('pmid', ''),
            article.get('title', ''),
            article.get('abstract', ''),
            article.get('authors', ''),
            article.get('publication_year', ''),
            article.get('journal', ''),
            article.get('mesh_terms', ''),
            article.get('keywords', ''),
            article.get('doi', ''),
            article.get('date_created', ''),
            article.get('date_completed', ''),
            article.get('date_revised', ''),
            article.get('pdf_path', '')
        )
        
        self.execute(query, params, commit=True)
    
    def store_articles_batch(self, articles: List[Dict[str, Any]]) -> int:
        """
        Store multiple PubMed articles in the database in batch.
        
        Args:
            articles: List of dictionaries containing article data
            
        Returns:
            Number of articles stored
        """
        if not articles:
            return 0
            
        # For bulk operations, use execute_many
        query = """
        INSERT INTO pubmed_articles 
            (pmid, title, abstract, authors, publication_year, journal, mesh_terms, keywords, doi, 
             date_created, date_completed, date_revised, pdf_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (pmid) DO UPDATE SET
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            authors = EXCLUDED.authors,
            publication_year = EXCLUDED.publication_year,
            journal = EXCLUDED.journal,
            mesh_terms = EXCLUDED.mesh_terms,
            keywords = EXCLUDED.keywords,
            doi = EXCLUDED.doi,
            date_created = EXCLUDED.date_created,
            date_completed = EXCLUDED.date_completed,
            date_revised = EXCLUDED.date_revised,
            pdf_path = EXCLUDED.pdf_path,
            imported_date = CURRENT_TIMESTAMP
        """
        
        params_list = [
            (
                a.get('pmid', ''),
                a.get('title', ''),
                a.get('abstract', ''),
                a.get('authors', ''),
                a.get('publication_year', ''),
                a.get('journal', ''),
                a.get('mesh_terms', ''),
                a.get('keywords', ''),
                a.get('doi', ''),
                a.get('date_created', ''),
                a.get('date_completed', ''),
                a.get('date_revised', ''),
                a.get('pdf_path', '')
            )
            for a in articles
        ]
        
        try:
            self.execute_many(query, params_list)
            return len(articles)
        except Exception as e:
            logger.error(f"Error storing articles batch: {e}")
            # Fall back to storing one by one if batch fails
            count = 0
            for article in articles:
                try:
                    self.store_article(article)
                    count += 1
                except Exception as ex:
                    logger.error(f"Error storing article {article.get('pmid', 'unknown')}: {ex}")
                    continue
            return count
    
    def get_article_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an article by its PMID.
        
        Args:
            pmid: PubMed ID
            
        Returns:
            Article data or None if not found
        """
        query = "SELECT * FROM pubmed_articles WHERE pmid = %s"
        results = self.execute(query, (pmid,))
        if results and len(results) > 0:
            return results[0]
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the PubMed database.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        # Total articles
        result = self.execute("SELECT COUNT(*) AS total FROM pubmed_articles")
        stats['total_articles'] = result[0]['total'] if result else 0
        
        # Articles by year
        result = self.execute("""
            SELECT publication_year, COUNT(*) as count 
            FROM pubmed_articles 
            GROUP BY publication_year 
            ORDER BY publication_year DESC
        """)
        stats['articles_by_year'] = result if result else []
        
        # Latest import date
        result = self.execute("SELECT MAX(imported_date) AS latest FROM pubmed_articles")
        stats['latest_import'] = result[0]['latest'] if result else None
        
        return stats
