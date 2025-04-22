"""
Unified document database functionality for the LocalKnowledge library.

This module provides a database manager for a unified document table that references
different data sources (e.g., PubMed, MedRxiv) to simplify document management and
reduce complexity as more data sources are added to the system.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from localknowledge.db.base import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class DocumentDatabaseManager(DatabaseManager):
    """Database manager for the unified document table."""

    def __init__(self):
        """Initialize the document database manager."""
        super().__init__()
        # Database creation is done centrally in db.createdb.py by calling create_tables()

    def create_tables(self) -> None:
        """Create document-related tables if they don't exist."""
        logger.info("Creating document database tables")

        # Begin a transaction for all table creation operations
        self.begin_transaction()

        try:
            # Create sources table
            logger.debug("Creating sources table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                url TEXT,
                is_reputable BOOLEAN DEFAULT FALSE,
                is_free BOOLEAN DEFAULT TRUE
            )
            """, commit=False)

            # Insert default sources if they don't exist
            logger.debug("Inserting default sources")
            self.execute("""
            INSERT INTO sources (name, url, is_reputable, is_free)
            VALUES ('pubmed', 'https://pubmed.ncbi.nlm.nih.gov/', TRUE, TRUE)
            ON CONFLICT (name) DO NOTHING
            """, commit=False)

            self.execute("""
            INSERT INTO sources (name, url, is_reputable, is_free)
            VALUES ('medrxiv', 'https://www.medrxiv.org/', TRUE, TRUE)
            ON CONFLICT (name) DO NOTHING
            """, commit=False)

            # Create categories table
            logger.debug("Creating categories table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
            """, commit=False)

            # Create document table
            logger.debug("Creating document table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS document (
                id SERIAL PRIMARY KEY,
                source_id INTEGER REFERENCES sources(id),
                external_id TEXT NOT NULL,  -- e.g., DOI or PMID
                doi TEXT,
                title TEXT,
                abstract TEXT,
                category_id INTEGER REFERENCES categories(id),
                keywords TEXT[],
                augmented_keywords TEXT[],  -- keywords expanded and AI generated
                mesh_terms TEXT[],
                authors TEXT[],
                publication TEXT,
                publication_date DATE,
                url TEXT,
                pdf_url TEXT,
                pdf_filename TEXT,
                full_text TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                withdrawn_date TIMESTAMP,
                withdrawn_reason TEXT,
                UNIQUE (source_id, external_id)
            )
            """, commit=False)

            # Create keywords table
            logger.debug("Creating keywords table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                keyword TEXT PRIMARY KEY
            )
            """, commit=False)

            # Create document_keywords table
            logger.debug("Creating document_keywords table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS document_keywords (
                document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
                keyword TEXT REFERENCES keywords(keyword) ON DELETE CASCADE,
                PRIMARY KEY (document_id, keyword)
            )
            """, commit=False)

            # Create tags table
            logger.debug("Creating tags table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
                user_id INTEGER,  -- Will reference users table
                tag TEXT NOT NULL,
                UNIQUE (document_id, user_id, tag)
            )
            """, commit=False)

            # Commit all table creation operations
            self.commit_transaction()
            logger.info("Document tables created successfully")

        except Exception as e:
            # Roll back on error
            self.rollback_transaction()
            logger.error(f"Error creating document tables: {e}")
            raise

    def create_indices(self) -> None:
        """Create indices for document-related tables."""
        logger.info("Creating document table indices")

        # Begin a transaction for all index creation operations
        self.begin_transaction()

        try:
            # Create index for external_id
            logger.debug("Creating external_id index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_external_id ON document(external_id)
            """, commit=False)

            # Create index for doi
            logger.debug("Creating doi index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_doi ON document(doi)
            """, commit=False)

            # Create index for title using GIN for full-text search
            logger.debug("Creating title index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_title ON document USING gin(to_tsvector('english', title))
            """, commit=False)

            # Create index for abstract using GIN for full-text search
            logger.debug("Creating abstract index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_abstract ON document USING gin(to_tsvector('english', abstract))
            """, commit=False)

            # Create index for keywords
            logger.debug("Creating keywords index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_keywords ON document USING gin(keywords)
            """, commit=False)

            # Create index for publication_date
            logger.debug("Creating publication_date index")
            self.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_publication_date ON document(publication_date)
            """, commit=False)

            # Commit all index creation operations
            self.commit_transaction()
            logger.info("Document indices created successfully")

        except Exception as e:
            # Roll back on error
            self.rollback_transaction()
            logger.error(f"Error creating document indices: {e}")
            raise

    def get_source_id(self, source_name: str) -> Optional[int]:
        """
        Get the ID for a source by name.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')

        Returns:
            Source ID or None if not found
        """
        query = "SELECT id FROM sources WHERE name = %s"
        result = self.execute(query, (source_name,))
        return result[0]['id'] if result else None

    def add_document(self, document_data: Dict[str, Any]) -> Optional[int]:
        """
        Add a new document to the unified document table.

        Args:
            document_data: Dictionary containing document data with keys:
                - source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
                - external_id: External identifier (e.g., DOI, PMID)
                - doi: DOI (optional)
                - title: Document title
                - abstract: Document abstract
                - category_name: Category name (optional)
                - keywords: List of keywords (optional)
                - augmented_keywords: List of AI-generated keywords (optional)
                - mesh_terms: List of MeSH terms (optional)
                - authors: List of authors (optional)
                - publication: Publication name (optional)
                - publication_date: Publication date (optional)
                - url: Document URL (optional)
                - pdf_url: PDF URL (optional)
                - pdf_filename: Local PDF filename (optional)
                - full_text: Full text content (optional)

        Returns:
            ID of the inserted document or None if insertion failed
        """
        # Get source ID
        source_name = document_data.get('source_name')
        if not source_name:
            logger.error("Source name is required")
            return None

        source_id = self.get_source_id(source_name)
        if not source_id:
            logger.error(f"Source '{source_name}' not found")
            return None

        # Get category ID if provided
        category_id = None
        category_name = document_data.get('category_name')
        if category_name:
            category_query = "SELECT id FROM categories WHERE name = %s"
            category_result = self.execute(category_query, (category_name,))
            if category_result:
                category_id = category_result[0]['id']
            else:
                # Create category if it doesn't exist
                insert_category = "INSERT INTO categories (name) VALUES (%s) RETURNING id"
                category_result = self.execute(insert_category, (category_name,), commit=True)
                if category_result:
                    category_id = category_result[0]['id']

        # Insert document
        query = """
        INSERT INTO document (
            source_id, external_id, doi, title, abstract, category_id,
            keywords, augmented_keywords, mesh_terms, authors,
            publication, publication_date, url, pdf_url, pdf_filename, full_text
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (source_id, external_id) DO UPDATE SET
            doi = EXCLUDED.doi,
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            category_id = EXCLUDED.category_id,
            keywords = EXCLUDED.keywords,
            augmented_keywords = EXCLUDED.augmented_keywords,
            mesh_terms = EXCLUDED.mesh_terms,
            authors = EXCLUDED.authors,
            publication = EXCLUDED.publication,
            publication_date = EXCLUDED.publication_date,
            url = EXCLUDED.url,
            pdf_url = EXCLUDED.pdf_url,
            pdf_filename = EXCLUDED.pdf_filename,
            full_text = EXCLUDED.full_text,
            updated_date = CURRENT_TIMESTAMP
        RETURNING id
        """

        params = (
            source_id,
            document_data.get('external_id'),
            document_data.get('doi'),
            document_data.get('title'),
            document_data.get('abstract'),
            category_id,
            document_data.get('keywords'),
            document_data.get('augmented_keywords'),
            document_data.get('mesh_terms'),
            document_data.get('authors'),
            document_data.get('publication'),
            document_data.get('publication_date'),
            document_data.get('url'),
            document_data.get('pdf_url'),
            document_data.get('pdf_filename'),
            document_data.get('full_text')
        )

        try:
            result = self.execute(query, params, commit=True)
            if result:
                document_id = result[0]['id']
                
                # Process keywords if provided
                keywords = document_data.get('keywords', [])
                if keywords:
                    self._process_keywords(document_id, keywords)
                
                return document_id
            return None
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return None

    def _process_keywords(self, document_id: int, keywords: List[str]) -> None:
        """
        Process and store keywords for a document.

        Args:
            document_id: Document ID
            keywords: List of keywords
        """
        if not keywords:
            return

        # Begin a transaction
        self.begin_transaction()

        try:
            # Insert keywords into keywords table
            for keyword in keywords:
                self.execute(
                    "INSERT INTO keywords (keyword) VALUES (%s) ON CONFLICT (keyword) DO NOTHING",
                    (keyword,),
                    commit=False
                )

            # Link keywords to document
            for keyword in keywords:
                self.execute(
                    """
                    INSERT INTO document_keywords (document_id, keyword)
                    VALUES (%s, %s)
                    ON CONFLICT (document_id, keyword) DO NOTHING
                    """,
                    (document_id, keyword),
                    commit=False
                )

            # Commit the transaction
            self.commit_transaction()
        except Exception as e:
            # Roll back on error
            self.rollback_transaction()
            logger.error(f"Error processing keywords: {e}")

    def get_document_by_external_id(self, source_name: str, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by its external ID and source.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)

        Returns:
            Document data or None if not found
        """
        source_id = self.get_source_id(source_name)
        if not source_id:
            logger.error(f"Source '{source_name}' not found")
            return None

        query = """
        SELECT d.*, s.name as source_name, c.name as category_name
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.source_id = %s AND d.external_id = %s
        """

        result = self.execute(query, (source_id, external_id))
        return result[0] if result else None

    def get_document_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by its DOI.

        Args:
            doi: Document DOI

        Returns:
            Document data or None if not found
        """
        query = """
        SELECT d.*, s.name as source_name, c.name as category_name
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.doi = %s
        """

        result = self.execute(query, (doi,))
        return result[0] if result else None

    def search_documents(self, 
                        search_text: str, 
                        source_name: Optional[str] = None,
                        limit: int = 100, 
                        offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search for documents using full-text search.

        Args:
            search_text: Text to search for
            source_name: Filter by source name (optional)
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching documents
        """
        # Convert search text to tsquery format
        search_terms = ' & '.join(search_text.split())
        
        query = """
        SELECT d.*, s.name as source_name, c.name as category_name,
               ts_rank_cd(to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')), 
                         to_tsquery('english', %s)) as rank
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE to_tsvector('english', d.title || ' ' || COALESCE(d.abstract, '')) @@ to_tsquery('english', %s)
        """
        
        params = [search_terms, search_terms]
        
        # Add source filter if provided
        if source_name:
            source_id = self.get_source_id(source_name)
            if source_id:
                query += " AND d.source_id = %s"
                params.append(source_id)
        
        query += " ORDER BY rank DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        return self.execute(query, tuple(params)) or []

    def get_recent_documents(self, 
                           limit: int = 100, 
                           offset: int = 0,
                           source_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent documents ordered by publication date.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip
            source_name: Filter by source name (optional)

        Returns:
            List of recent documents
        """
        query = """
        SELECT d.*, s.name as source_name, c.name as category_name
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        """
        
        params = []
        
        # Add source filter if provided
        if source_name:
            source_id = self.get_source_id(source_name)
            if source_id:
                query += " WHERE d.source_id = %s"
                params.append(source_id)
        
        query += " ORDER BY d.publication_date DESC NULLS LAST, d.added_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        return self.execute(query, tuple(params)) or []

    def mark_document_withdrawn(self, 
                              source_name: str, 
                              external_id: str, 
                              reason: str) -> bool:
        """
        Mark a document as withdrawn.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            reason: Reason for withdrawal

        Returns:
            True if successful, False otherwise
        """
        source_id = self.get_source_id(source_name)
        if not source_id:
            logger.error(f"Source '{source_name}' not found")
            return False

        query = """
        UPDATE document
        SET withdrawn_date = CURRENT_TIMESTAMP, withdrawn_reason = %s
        WHERE source_id = %s AND external_id = %s
        """

        try:
            self.execute(query, (reason, source_id, external_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error marking document as withdrawn: {e}")
            return False

    def add_tag(self, 
               source_name: str, 
               external_id: str, 
               user_id: int, 
               tag: str) -> bool:
        """
        Add a tag to a document.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            user_id: User ID
            tag: Tag text

        Returns:
            True if successful, False otherwise
        """
        # Get document ID
        document = self.get_document_by_external_id(source_name, external_id)
        if not document:
            logger.error(f"Document not found: {source_name}/{external_id}")
            return False

        document_id = document['id']

        # Add tag
        query = """
        INSERT INTO tags (document_id, user_id, tag)
        VALUES (%s, %s, %s)
        ON CONFLICT (document_id, user_id, tag) DO NOTHING
        """

        try:
            self.execute(query, (document_id, user_id, tag), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error adding tag: {e}")
            return False

    def get_document_tags(self, 
                         source_name: str, 
                         external_id: str, 
                         user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get tags for a document.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            user_id: Filter by user ID (optional)

        Returns:
            List of tags
        """
        # Get document ID
        document = self.get_document_by_external_id(source_name, external_id)
        if not document:
            logger.error(f"Document not found: {source_name}/{external_id}")
            return []

        document_id = document['id']

        # Get tags
        query = """
        SELECT id, user_id, tag
        FROM tags
        WHERE document_id = %s
        """
        
        params = [document_id]
        
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        
        return self.execute(query, tuple(params)) or []

    def remove_tag(self, tag_id: int) -> bool:
        """
        Remove a tag.

        Args:
            tag_id: Tag ID

        Returns:
            True if successful, False otherwise
        """
        query = "DELETE FROM tags WHERE id = %s"

        try:
            self.execute(query, (tag_id,), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error removing tag: {e}")
            return False

    def count_documents(self, source_name: Optional[str] = None) -> int:
        """
        Count documents in the database.

        Args:
            source_name: Filter by source name (optional)

        Returns:
            Number of documents
        """
        query = "SELECT COUNT(*) as count FROM document"
        params = []
        
        if source_name:
            source_id = self.get_source_id(source_name)
            if source_id:
                query += " WHERE source_id = %s"
                params.append(source_id)
        
        result = self.execute(query, tuple(params) if params else None)
        return result[0]['count'] if result else 0
