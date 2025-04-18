"""
MedRxiv database functionality for the LocalKnowledge library.

This module provides database operations specific to medRxiv data.
"""
import os
import psycopg2
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

from localknowledge.db.base import DatabaseManager


class MedRxivDatabaseManager(DatabaseManager):
    """Database manager for medRxiv preprints."""
    
    def __init__(self):
        """Initialize the medRxiv database manager."""
        super().__init__()
        self.create_tables()
    
    def create_tables(self) -> None:
        """Create medRxiv tables if they don't exist."""
        # Create preprints table
        self.execute("""
        CREATE TABLE IF NOT EXISTS preprints (
            doi TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            date_posted TEXT,
            category TEXT,
            pdf_url TEXT,
            local_pdf_path TEXT,
            full_text TEXT
        )
        """, commit=True)
        
        # Create summaries table
        self.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id SERIAL PRIMARY KEY,
            publication_id TEXT REFERENCES preprints(doi) ON DELETE CASCADE,
            summary TEXT,
            evaluation BOOLEAN,
            reason TEXT,
            interests TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """, commit=True)
        
        # Create indexes for searching
        self.execute("CREATE INDEX IF NOT EXISTS idx_title_rx ON preprints(title)", commit=True)
        # Drop the old B-tree index if it exists
        self.execute("DROP INDEX IF EXISTS idx_abstract_rx", commit=True)
        # Create a fulltext search index on abstract column
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_abstract_fts ON preprints 
        USING gin(to_tsvector('english', abstract))
        """, commit=True)
        self.execute("CREATE INDEX IF NOT EXISTS idx_category ON preprints(category)", commit=True)
        # Create index for summaries
        self.execute("CREATE INDEX IF NOT EXISTS idx_summaries_publication_id ON summaries(publication_id)", commit=True)
    
    def store_preprint(self, preprint: Dict[str, Any]) -> None:
        """
        Store a preprint in the database.
        
        Args:
            preprint: Dictionary containing preprint data
        """
        query = """
        INSERT INTO preprints 
            (doi, title, abstract, authors, date_posted, category, pdf_url, local_pdf_path, full_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (doi) DO UPDATE SET
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            authors = EXCLUDED.authors,
            date_posted = EXCLUDED.date_posted,
            category = EXCLUDED.category,
            pdf_url = EXCLUDED.pdf_url,
            local_pdf_path = EXCLUDED.local_pdf_path,
            full_text = EXCLUDED.full_text
        """
        params = (
            preprint.get('doi', ''),
            preprint.get('title', ''),
            preprint.get('abstract', ''),
            preprint.get('authors', ''),
            preprint.get('date_posted', ''),
            preprint.get('category', ''),
            preprint.get('pdf_url', ''),
            preprint.get('local_pdf_path', ''),
            preprint.get('full_text', '')
        )
        
        self.execute(query, params, commit=True)
    
    def store_preprints(self, preprints: List[Dict[str, Any]]) -> int:
        """
        Store multiple preprints in the database.
        
        Args:
            preprints: List of dictionaries containing preprint data
            
        Returns:
            Number of preprints stored
        """
        if not preprints:
            return 0
            
        # For bulk operations, use execute_many
        query = """
        INSERT INTO preprints 
            (doi, title, abstract, authors, date_posted, category, pdf_url, local_pdf_path, full_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (doi) DO UPDATE SET
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            authors = EXCLUDED.authors,
            date_posted = EXCLUDED.date_posted,
            category = EXCLUDED.category,
            pdf_url = EXCLUDED.pdf_url,
            local_pdf_path = EXCLUDED.local_pdf_path,
            full_text = EXCLUDED.full_text
        """
        
        params_list = [
            (
                p.get('doi', ''),
                p.get('title', ''),
                p.get('abstract', ''),
                p.get('authors', ''),
                p.get('date_posted', ''),
                p.get('category', ''),
                p.get('pdf_url', ''),
                p.get('local_pdf_path', ''),
                p.get('full_text', '')
            )
            for p in preprints
        ]
        
        try:
            self.execute_many(query, params_list)
            return len(preprints)
        except Exception as e:
            print(f"Error storing preprints: {e}")
            # Fall back to storing one by one if batch fails
            count = 0
            for preprint in preprints:
                try:
                    self.store_preprint(preprint)
                    count += 1
                except Exception:
                    continue
            return count
    
    def get_preprint_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a preprint by its DOI.
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Preprint data or None if not found
        """
        query = "SELECT * FROM preprints WHERE doi = %s"
        results = self.execute(query, (doi,))
        if results and len(results) > 0:
            return results[0]
        return None
    
    def search_preprints(self, 
                         query: str, 
                         fields: List[str] = None, 
                         max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search for preprints in the database.
        
        Args:
            query: Search query string
            fields: List of fields to search in (default: title and abstract)
            max_results: Maximum number of results to return
            
        Returns:
            List of matching preprints
        """
        if not fields:
            fields = ['title', 'abstract']
            
        conditions = []
        params = []
        
        normalized_query = " & ".join(query.split())
        
        for field in fields:
            if field == 'abstract':
                # Use the fulltext index for abstract
                conditions.append(f"to_tsvector('english', {field}) @@ plainto_tsquery('english', %s)")
                params.append(query)
            else:
                # For other fields, fallback to ILIKE
                conditions.append(f"{field} ILIKE %s")
                params.append(f"%{query}%")
        
        where_clause = " OR ".join(conditions)
        
        search_query = f"""
        SELECT *, 
               CASE WHEN 'abstract' = ANY(%s) THEN 
                   ts_rank(to_tsvector('english', abstract), plainto_tsquery('english', %s))
               ELSE 0 END as rank
        FROM preprints 
        WHERE {where_clause}
        ORDER BY rank DESC, date_posted DESC
        LIMIT %s
        """
        
        # Add fields as an array parameter and the query again for ranking
        params.insert(0, fields)
        params.insert(1, query)
        params.append(max_results)
        
        return self.execute(search_query, tuple(params)) or []
    
    def get_latest_date(self) -> Optional[str]:
        """
        Get the latest date in the database.
        
        Returns:
            Latest date in YYYY-MM-DD format or None if database is empty
        """
        result = self.execute("SELECT date_posted FROM preprints ORDER BY date_posted DESC LIMIT 1")
        
        if result and result[0]['date_posted']:
            # Get the date part if it contains time
            date_str = result[0]['date_posted']
            return date_str.split()[0] if ' ' in date_str else date_str
        return None
    
    def get_resume_date(self, days_back: int = 1) -> Optional[str]:
        """
        Get the date from which to resume data collection, accounting for 
        potentially partial updates by going back a few days.
        
        Args:
            days_back: Number of days to go back from the latest date
            
        Returns:
            Date string in YYYY-MM-DD format or None if no data
        """
        latest_date = self.get_latest_date()
        if not latest_date:
            return None
            
        try:
            date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
            resume_date = date_obj - timedelta(days=days_back)
            return resume_date.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Error parsing date: {e}")
            return None
    
    def get_preprints_without_pdfs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get preprints without downloaded PDFs.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of preprints without downloaded PDFs
        """
        query = """
        SELECT doi, title, date_posted, category, pdf_url
        FROM preprints
        WHERE (local_pdf_path = '' OR local_pdf_path IS NULL)
        ORDER BY date_posted DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        return self.execute(query) or []
    
    def update_pdf_path(self, doi: str, pdf_path: str, full_text: str = "") -> bool:
        """
        Update the PDF path and full text for a preprint.
        
        Args:
            doi: Digital Object Identifier
            pdf_path: Path to the PDF file (filename only)
            full_text: Full text extracted from the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                """UPDATE preprints 
                   SET local_pdf_path = %s, full_text = %s
                   WHERE doi = %s""",
                (pdf_path, full_text, doi),
                commit=True
            )
            return True
        except Exception as e:
            print(f"Error updating PDF path: {e}")
            return False
    
    # Summary-related methods
    
    def store_summary(self, publication_id: str, summary_data: Dict[str, Any]) -> Optional[int]:
        """
        Store a summary for a preprint.
        
        Args:
            publication_id: DOI of the preprint
            summary_data: Dictionary containing summary data with keys:
                          summary, evaluation, reason, interests
        
        Returns:
            ID of the created/updated summary or None if failed
        """
        try:
            # Check if this publication exists
            if not self.get_preprint_by_doi(publication_id):
                print(f"Cannot store summary for non-existent publication: {publication_id}")
                return None
                
            # Check if summary already exists for this publication
            existing = self.get_summary_by_publication(publication_id)
            
            if existing:
                # Update existing summary
                query = """
                UPDATE summaries
                SET summary = %s, evaluation = %s, reason = %s, interests = %s, created_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
                """
                params = (
                    summary_data.get('response', ''),
                    summary_data.get('evaluation', False),
                    summary_data.get('reason', ''),
                    summary_data.get('interests', []),
                    existing['id']
                )
                result = self.execute(query, params, commit=True)
                return result[0]['id'] if result else None
            else:
                # Create new summary
                query = """
                INSERT INTO summaries (publication_id, summary, evaluation, reason, interests)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """
                params = (
                    publication_id,
                    summary_data.get('response', ''),
                    summary_data.get('evaluation', False),
                    summary_data.get('reason', ''),
                    summary_data.get('interests', []),
                )
                result = self.execute(query, params, commit=True)
                return result[0]['id'] if result else None
        except Exception as e:
            print(f"Error storing summary: {e}")
            return None
    
    def get_summary_by_id(self, summary_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a summary by its ID.
        
        Args:
            summary_id: Summary ID
            
        Returns:
            Summary data or None if not found
        """
        query = "SELECT * FROM summaries WHERE id = %s"
        results = self.execute(query, (summary_id,))
        
        if results and len(results) > 0:
            return results[0]
        return None
    
    def get_summary_by_publication(self, publication_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the summary for a specific publication.
        
        Args:
            publication_id: DOI of the preprint
            
        Returns:
            Summary data or None if not found
        """
        query = "SELECT * FROM summaries WHERE publication_id = %s"
        results = self.execute(query, (publication_id,))
        
        if results and len(results) > 0:
            return results[0]
        return None
    
    def get_preprints_without_summaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get preprints that don't have summaries yet.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of preprints without summaries
        """
        query = """
        SELECT p.doi, p.title, p.abstract, p.date_posted, p.category
        FROM preprints p
        LEFT JOIN summaries s ON p.doi = s.publication_id
        WHERE s.id IS NULL
        ORDER BY p.date_posted DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        return self.execute(query) or []
    
    def get_summaries_by_interests(self, interests: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get summaries that match any of the given interests.
        
        Args:
            interests: List of interest strings
            limit: Maximum number of results to return
            
        Returns:
            List of summaries matching the interests
        """
        if not interests:
            return []
            
        query = """
        SELECT s.*, p.title, p.abstract, p.authors, p.date_posted, p.category
        FROM summaries s
        JOIN preprints p ON s.publication_id = p.doi
        WHERE s.interests && %s
        ORDER BY p.date_posted DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        return self.execute(query, (interests,)) or []
    
    def delete_summary(self, summary_id: int) -> bool:
        """
        Delete a summary.
        
        Args:
            summary_id: Summary ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM summaries WHERE id = %s", (summary_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting summary: {e}")
            return False
