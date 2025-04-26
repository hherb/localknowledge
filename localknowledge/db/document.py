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
            # Log the parameters for debugging
            logger.debug(f"Adding document with params: {params}")

            result = self.execute(query, params, commit=True)
            if result:
                document_id = result[0]['id']
                logger.debug(f"Document added with ID: {document_id}")

                # Process keywords if provided
                keywords = document_data.get('keywords', [])
                if keywords:
                    self._process_keywords(document_id, keywords)

                return document_id
            logger.error("No result returned from document insertion query")
            return None
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
                        offset: int = 0,
                        exclude_terms: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for documents using the all_keywords column with GIN index.

        This method uses the efficient array operators pattern with the all_keywords column
        that combines keywords, augmented_keywords, and mesh_terms into a single array.

        Args:
            search_text: Text to search for (comma-separated terms)
            source_name: Filter by source name (optional)
            limit: Maximum number of results to return
            offset: Number of results to skip
            exclude_terms: Terms to exclude from search results (optional)

        Returns:
            List of matching documents
        """
        logger.debug(f"DocumentDatabaseManager.search_documents: Starting search with text: {search_text}")
        logger.debug(f"DocumentDatabaseManager.search_documents: Source filter: {source_name}")
        logger.debug(f"DocumentDatabaseManager.search_documents: Limit: {limit}, Offset: {offset}")

        try:
            # Parse the search text into an array of terms
            include_terms = []

            # Handle quoted phrases and comma-separated terms
            remaining_text = search_text

            # Extract quoted phrases
            quote_start = remaining_text.find('"')
            while quote_start != -1:
                quote_end = remaining_text.find('"', quote_start + 1)
                if quote_end != -1:
                    quoted_term = remaining_text[quote_start + 1:quote_end].strip()
                    if quoted_term:
                        include_terms.append(quoted_term.lower())
                    remaining_text = remaining_text[:quote_start] + " " + remaining_text[quote_end + 1:]
                else:
                    break
                quote_start = remaining_text.find('"')

            # Split remaining text by commas
            for term in remaining_text.split(','):
                term = term.strip()
                if term.startswith('-'):
                    # This is an exclude term, skip it here
                    continue
                if term:
                    include_terms.append(term.lower())

            # If no terms were found, use the original search text
            if not include_terms:
                include_terms = [search_text.lower()]

            logger.debug(f"DocumentDatabaseManager.search_documents: Include terms: {include_terms}")

            # Check if all_keywords column exists
            result = self.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'document' AND column_name = 'all_keywords';
            """)

            has_all_keywords = bool(result)

            if has_all_keywords:
                # Use the all_keywords column with the efficient array operator pattern
                # Convert include_terms to a string representation for the ARRAY constructor
                include_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in include_terms) + "]"

                query = f"""
                SELECT d.*, s.name as source_name, c.name as category_name
                FROM document d
                JOIN sources s ON d.source_id = s.id
                LEFT JOIN categories c ON d.category_id = c.id
                WHERE d.all_keywords && {include_array_str}
                """

                # Add exclusion terms if provided
                if exclude_terms and len(exclude_terms) > 0:
                    logger.debug(f"DocumentDatabaseManager.search_documents: Exclude terms: {exclude_terms}")
                    exclude_terms = [term.lower() for term in exclude_terms]

                    # Convert exclude_terms to a string representation for the ARRAY constructor
                    exclude_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in exclude_terms) + "]"

                    query += f"""
                    AND NOT (d.all_keywords && {exclude_array_str})
                    """

                logger.debug(f"DocumentDatabaseManager.search_documents: Using all_keywords column with GIN index")
            else:
                # Fall back to the original pattern with keywords and mesh_terms
                # Convert include_terms to a string representation for the ARRAY constructor
                include_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in include_terms) + "]"

                query = f"""
                SELECT d.*, s.name as source_name, c.name as category_name
                FROM document d
                JOIN sources s ON d.source_id = s.id
                LEFT JOIN categories c ON d.category_id = c.id
                WHERE
                  (
                    (d.keywords && {include_array_str})
                    OR (d.mesh_terms && {include_array_str})
                  )
                """

                # Add exclusion terms if provided
                if exclude_terms and len(exclude_terms) > 0:
                    logger.debug(f"DocumentDatabaseManager.search_documents: Exclude terms: {exclude_terms}")
                    exclude_terms = [term.lower() for term in exclude_terms]

                    # Convert exclude_terms to a string representation for the ARRAY constructor
                    exclude_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in exclude_terms) + "]"

                    query += f"""
                    AND NOT (
                        (d.keywords && {exclude_array_str})
                        OR (d.mesh_terms && {exclude_array_str})
                    )
                    """

                logger.debug(f"DocumentDatabaseManager.search_documents: Using keywords and mesh_terms columns")

            # Add source filter if provided
            if source_name:
                source_id = self.get_source_id(source_name)
                logger.debug(f"DocumentDatabaseManager.search_documents: Source ID for {source_name}: {source_id}")
                if source_id:
                    query += f" AND d.source_id = {source_id}"

            # Add ordering and limit
            query += f" ORDER BY d.publication_date DESC NULLS LAST LIMIT {limit} OFFSET {offset}"

            logger.debug(f"DocumentDatabaseManager.search_documents: Executing array operator query")
            logger.debug(f"DocumentDatabaseManager.search_documents: SQL Query: {query}")

            # Execute the query with a longer timeout
            results = self.execute(query, (), timeout=30) or []
            logger.debug(f"DocumentDatabaseManager.search_documents: Array search completed, found {len(results)} results")

            # If we got results, return them
            if results:
                return results

            # If no results from array search, try a simple title search as fallback
            logger.debug("DocumentDatabaseManager.search_documents: No results from array search, trying title search")

            # Simple title search with ILIKE
            # Use the first term for the title search
            search_term = f"%{include_terms[0]}%"

            query = f"""
            SELECT d.*, s.name as source_name, c.name as category_name
            FROM document d
            JOIN sources s ON d.source_id = s.id
            LEFT JOIN categories c ON d.category_id = c.id
            WHERE d.title ILIKE '{search_term}'
            """

            # Add source filter if provided
            if source_name:
                source_id = self.get_source_id(source_name)
                if source_id:
                    query += f" AND d.source_id = {source_id}"

            # Add ordering and limit
            query += f" ORDER BY d.publication_date DESC NULLS LAST LIMIT {limit} OFFSET {offset}"

            logger.debug(f"DocumentDatabaseManager.search_documents: Executing title search fallback")

            # Execute with a longer timeout
            results = self.execute(query, (), timeout=15) or []
            logger.debug(f"DocumentDatabaseManager.search_documents: Title search completed, found {len(results)} results")

            return results

        except TimeoutError as e:
            logger.debug(f"DocumentDatabaseManager.search_documents: Search timed out: {e}")
            # Return an empty result set on timeout
            return []
        except Exception as e:
            logger.warning(f"DocumentDatabaseManager.search_documents: Error during search: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            return []

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

    def add_bookmark(self,
                    source_name: str,
                    external_id: str,
                    user_id: int,
                    bookmark_type: str,
                    project_id: Optional[int] = None) -> bool:
        """
        Add a bookmark to a document.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            user_id: User ID
            bookmark_type: Type of bookmark ('personal', 'project', or 'both')
            project_id: Project ID (required for 'project' or 'both' types)

        Returns:
            True if successful, False otherwise
        """
        # Validate bookmark type
        if bookmark_type not in ('personal', 'project', 'both'):
            logger.error(f"Invalid bookmark type: {bookmark_type}")
            return False

        # Validate project_id for project bookmarks
        if bookmark_type in ('project', 'both') and project_id is None:
            logger.error(f"Project ID is required for bookmark type: {bookmark_type}")
            return False

        # Get document ID
        document = self.get_document_by_external_id(source_name, external_id)
        if not document:
            logger.error(f"Document not found: {source_name}/{external_id}")
            return False

        document_id = document['id']

        # Add bookmark
        query = """
        INSERT INTO bookmarks (document_id, user_id, project_id, bookmark_type)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (document_id, user_id, project_id)
        DO UPDATE SET bookmark_type = %s, created_at = CURRENT_TIMESTAMP
        """

        try:
            self.execute(query, (document_id, user_id, project_id, bookmark_type, bookmark_type), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error adding bookmark: {e}")
            return False

    def remove_bookmark(self,
                       source_name: str,
                       external_id: str,
                       user_id: int,
                       project_id: Optional[int] = None) -> bool:
        """
        Remove a bookmark from a document.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            user_id: User ID
            project_id: Project ID (optional, if None removes personal bookmark)

        Returns:
            True if successful, False otherwise
        """
        # Get document ID
        document = self.get_document_by_external_id(source_name, external_id)
        if not document:
            logger.error(f"Document not found: {source_name}/{external_id}")
            return False

        document_id = document['id']

        # Remove bookmark
        query = """
        DELETE FROM bookmarks
        WHERE document_id = %s AND user_id = %s
        """

        params = [document_id, user_id]

        # Add project filter if provided
        if project_id is not None:
            query += " AND project_id = %s"
            params.append(project_id)
        else:
            query += " AND project_id IS NULL"

        try:
            self.execute(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"Error removing bookmark: {e}")
            return False

    def is_bookmarked(self,
                     source_name: str,
                     external_id: str,
                     user_id: int,
                     project_id: Optional[int] = None) -> Optional[str]:
        """
        Check if a document is bookmarked.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')
            external_id: External identifier (e.g., DOI, PMID)
            user_id: User ID
            project_id: Project ID (optional)

        Returns:
            Bookmark type ('personal', 'project', or 'both') if bookmarked, None otherwise
        """
        # Get document ID
        document = self.get_document_by_external_id(source_name, external_id)
        if not document:
            logger.error(f"Document not found: {source_name}/{external_id}")
            return None

        document_id = document['id']

        # Check for bookmark
        query = """
        SELECT bookmark_type
        FROM bookmarks
        WHERE document_id = %s AND user_id = %s
        """

        params = [document_id, user_id]

        # Add project filter if provided
        if project_id is not None:
            query += " AND project_id = %s"
            params.append(project_id)
        else:
            query += " AND project_id IS NULL"

        result = self.execute(query, tuple(params))
        return result[0]['bookmark_type'] if result else None

    def get_bookmarked_documents(self,
                                user_id: int,
                                project_id: Optional[int] = None,
                                limit: int = 100,
                                offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get bookmarked documents for a user or project.

        Args:
            user_id: User ID
            project_id: Project ID (optional)
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of bookmarked documents
        """
        query = """
        SELECT d.*, s.name as source_name, c.name as category_name, b.bookmark_type, b.created_at as bookmarked_at
        FROM bookmarks b
        JOIN document d ON b.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE b.user_id = %s
        """

        params = [user_id]

        # Add project filter if provided
        if project_id is not None:
            query += " AND b.project_id = %s"
            params.append(project_id)
        else:
            query += " AND b.project_id IS NULL"

        # Add ordering and limit
        query += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self.execute(query, tuple(params)) or []
