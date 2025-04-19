"""
Database functionality for tracking user reading activity.

This module provides a database manager for tracking which articles users have read,
along with metadata such as tags, ratings, and notes.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger()

class ReadingTrackerManager(DatabaseManager):
    """Database manager for tracking user reading activity."""
    
    def __init__(self):
        """Initialize the reading tracker manager."""
        super().__init__()
        self.create_tables()
    
    def create_tables(self) -> None:
        """Create reading tracker tables if they don't exist."""
        # Create tags table
        self.execute("""
        CREATE TABLE IF NOT EXISTS reading_tags (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
        """, commit=True)
        
        # Create reading_records table
        self.execute("""
        CREATE TABLE IF NOT EXISTS reading_records (
            id SERIAL PRIMARY KEY,
            source_type TEXT NOT NULL,
            content_id TEXT NOT NULL,
            user_id INTEGER,
            read_timestamp TIMESTAMP,
            rating INTEGER,
            notes TEXT,
            UNIQUE(source_type, content_id, user_id)
        )
        """, commit=True)
        
        # Create linking table for many-to-many relationship between records and tags
        self.execute("""
        CREATE TABLE IF NOT EXISTS reading_records_tags (
            record_id INTEGER REFERENCES reading_records(id) ON DELETE CASCADE,
            tag_id INTEGER REFERENCES reading_tags(id) ON DELETE CASCADE,
            PRIMARY KEY (record_id, tag_id)
        )
        """, commit=True)
        
        # Create indexes for better performance
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_reading_records_content_id ON reading_records(content_id)
        """, commit=True)
        
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_reading_records_source_type ON reading_records(source_type)
        """, commit=True)
        
        self.execute("""
        CREATE INDEX IF NOT EXISTS idx_reading_records_read_timestamp ON reading_records(read_timestamp)
        """, commit=True)
        
        logger.info("Reading tracker tables created or verified")
    
    def get_or_create_tag(self, tag_name: str) -> int:
        """
        Get or create a tag with the specified name.
        
        Args:
            tag_name: The name of the tag
            
        Returns:
            The ID of the tag
        """
        # First try to get the existing tag
        query = "SELECT id FROM reading_tags WHERE name = %s"
        result = self.execute(query, (tag_name,))
        
        if result:
            return result[0]['id']
        
        # If it doesn't exist, create it
        insert_query = "INSERT INTO reading_tags (name) VALUES (%s) RETURNING id"
        result = self.execute(insert_query, (tag_name,))
        
        return result[0]['id']
    
    def mark_as_read(self, 
                   source_type: str, 
                   content_id: str, 
                   user_id: Optional[int] = None,
                   rating: Optional[int] = None,
                   notes: Optional[str] = None,
                   tags: Optional[List[str]] = None) -> int:
        """
        Mark content as read or update an existing reading record.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            user_id: Optional user ID (for multi-user systems)
            rating: Optional rating (1-5)
            notes: Optional notes about the content
            tags: Optional list of tags to associate with the content
            
        Returns:
            ID of the reading record
        """
        try:
            # Check if a record already exists
            query = """
            SELECT id FROM reading_records 
            WHERE source_type = %s AND content_id = %s AND 
            (user_id = %s OR (user_id IS NULL AND %s IS NULL))
            """
            result = self.execute(query, (source_type, content_id, user_id, user_id))
            
            if result:
                # Update existing record
                record_id = result[0]['id']
                update_query = """
                UPDATE reading_records 
                SET read_timestamp = %s, 
                    rating = COALESCE(%s, rating),
                    notes = COALESCE(%s, notes)
                WHERE id = %s
                """
                self.execute(update_query, 
                           (datetime.now(), rating, notes, record_id),
                           commit=True)
            else:
                # Create new record
                insert_query = """
                INSERT INTO reading_records 
                (source_type, content_id, user_id, read_timestamp, rating, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """
                result = self.execute(
                    insert_query, 
                    (source_type, content_id, user_id, datetime.now(), rating, notes),
                    commit=True
                )
                
                if result and len(result) > 0:
                    record_id = result[0]['id']
                else:
                    # Fallback: Get the ID of the record we just inserted
                    fallback_query = """
                    SELECT id FROM reading_records 
                    WHERE source_type = %s AND content_id = %s AND 
                    (user_id = %s OR (user_id IS NULL AND %s IS NULL))
                    ORDER BY read_timestamp DESC LIMIT 1
                    """
                    fallback_result = self.execute(fallback_query, (source_type, content_id, user_id, user_id))
                    if fallback_result and len(fallback_result) > 0:
                        record_id = fallback_result[0]['id']
                    else:
                        # If all else fails, just return a placeholder ID
                        # The tags won't be associated but at least the read status will be recorded
                        logger.error(f"Failed to get ID for newly inserted reading record")
                        return 0
            
            # Update tags if provided
            if tags:
                # First remove existing tags
                self.execute(
                    "DELETE FROM reading_records_tags WHERE record_id = %s",
                    (record_id,),
                    commit=True
                )
                
                # Add the new tags
                for tag_name in tags:
                    tag_id = self.get_or_create_tag(tag_name)
                    self.execute(
                        "INSERT INTO reading_records_tags (record_id, tag_id) VALUES (%s, %s)",
                        (record_id, tag_id),
                        commit=True
                    )
            
            return record_id
            
        except Exception as e:
            logger.error(f"Error marking content as read: {e}")
            self.connection.rollback()
            raise
    
    def is_read(self, source_type: str, content_id: str, user_id: Optional[int] = None) -> bool:
        """
        Check if content has been read.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            user_id: Optional user ID (for multi-user systems)
            
        Returns:
            Boolean indicating if the content has been read
        """
        query = """
        SELECT 1 FROM reading_records 
        WHERE source_type = %s AND content_id = %s AND 
        (user_id = %s OR (user_id IS NULL AND %s IS NULL)) AND
        read_timestamp IS NOT NULL
        """
        result = self.execute(query, (source_type, content_id, user_id, user_id))
        
        return len(result) > 0
    
    def get_reading_record(self, source_type: str, content_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get a reading record for the specified content.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            user_id: Optional user ID (for multi-user systems)
            
        Returns:
            Reading record or None if not found
        """
        # Get the basic record
        query = """
        SELECT id, read_timestamp, rating, notes 
        FROM reading_records 
        WHERE source_type = %s AND content_id = %s AND 
        (user_id = %s OR (user_id IS NULL AND %s IS NULL))
        """
        result = self.execute(query, (source_type, content_id, user_id, user_id))
        
        if not result:
            return None
        
        record = result[0]
        
        # Get the tags for this record
        tags_query = """
        SELECT t.name 
        FROM reading_tags t
        JOIN reading_records_tags rt ON t.id = rt.tag_id
        WHERE rt.record_id = %s
        ORDER BY t.name
        """
        tags_result = self.execute(tags_query, (record['id'],))
        
        # Add tags to the record
        record['tags'] = [row['name'] for row in tags_result]
        
        return record
    
    def get_all_tags(self) -> List[str]:
        """
        Get all available tags.
        
        Returns:
            List of tag names
        """
        query = "SELECT name FROM reading_tags ORDER BY name"
        result = self.execute(query)
        
        return [row['name'] for row in result]
    
    def get_records_by_tag(self, tag_name: str, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all records that have a specific tag.
        
        Args:
            tag_name: Name of the tag to filter by
            user_id: Optional user ID (for multi-user systems)
            
        Returns:
            List of reading records with the specified tag
        """
        query = """
        SELECT r.id, r.source_type, r.content_id, r.read_timestamp, r.rating, r.notes
        FROM reading_records r
        JOIN reading_records_tags rt ON r.id = rt.record_id
        JOIN reading_tags t ON rt.tag_id = t.id
        WHERE t.name = %s AND (r.user_id = %s OR (r.user_id IS NULL AND %s IS NULL))
        ORDER BY r.read_timestamp DESC
        """
        result = self.execute(query, (tag_name, user_id, user_id))
        
        # Get tags for each record
        for record in result:
            tags_query = """
            SELECT t.name 
            FROM reading_tags t
            JOIN reading_records_tags rt ON t.id = rt.tag_id
            WHERE rt.record_id = %s
            ORDER BY t.name
            """
            tags_result = self.execute(tags_query, (record['id'],))
            record['tags'] = [row['name'] for row in tags_result]
        
        return result
    
    def get_recent_reads(self, 
                       limit: int = 50, 
                       source_type: Optional[str] = None,
                       user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recently read content.
        
        Args:
            limit: Maximum number of records to return
            source_type: Optional filter by source type
            user_id: Optional user ID (for multi-user systems)
            
        Returns:
            List of recent reading records
        """
        # Build the query based on filters
        query_parts = ["SELECT id, source_type, content_id, read_timestamp, rating, notes FROM reading_records"]
        where_clauses = []
        params = []
        
        # Add source type filter if specified
        if source_type:
            where_clauses.append("source_type = %s")
            params.append(source_type)
        
        # Add user filter
        where_clauses.append("(user_id = %s OR (user_id IS NULL AND %s IS NULL))")
        params.extend([user_id, user_id])
        
        # Add where clause if needed
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Add ordering and limit
        query_parts.append("ORDER BY read_timestamp DESC")
        query_parts.append("LIMIT %s")
        params.append(limit)
        
        # Execute the query
        query = " ".join(query_parts)
        result = self.execute(query, tuple(params))
        
        # Get tags for each record
        for record in result:
            tags_query = """
            SELECT t.name 
            FROM reading_tags t
            JOIN reading_records_tags rt ON t.id = rt.tag_id
            WHERE rt.record_id = %s
            ORDER BY t.name
            """
            tags_result = self.execute(tags_query, (record['id'],))
            record['tags'] = [row['name'] for row in tags_result]
        
        return result
    
    def add_tag_to_record(self, record_id: int, tag_name: str) -> None:
        """
        Add a tag to a reading record.
        
        Args:
            record_id: ID of the reading record
            tag_name: Name of the tag to add
        """
        try:
            # Get or create the tag
            tag_id = self.get_or_create_tag(tag_name)
            
            # Add the tag to the record if it's not already there
            self.execute(
                """
                INSERT INTO reading_records_tags (record_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT (record_id, tag_id) DO NOTHING
                """,
                (record_id, tag_id),
                commit=True
            )
        except Exception as e:
            logger.error(f"Error adding tag to record: {e}")
            self.connection.rollback()
            raise
    
    def remove_tag_from_record(self, record_id: int, tag_name: str) -> None:
        """
        Remove a tag from a reading record.
        
        Args:
            record_id: ID of the reading record
            tag_name: Name of the tag to remove
        """
        try:
            # Get the tag ID
            query = "SELECT id FROM reading_tags WHERE name = %s"
            result = self.execute(query, (tag_name,))
            
            if not result:
                # Tag doesn't exist, nothing to do
                return
                
            tag_id = result[0]['id']
            
            # Remove the tag from the record
            self.execute(
                "DELETE FROM reading_records_tags WHERE record_id = %s AND tag_id = %s",
                (record_id, tag_id),
                commit=True
            )
        except Exception as e:
            logger.error(f"Error removing tag from record: {e}")
            self.connection.rollback()
            raise
    
    def update_record_notes(self, source_type: str, content_id: str, notes: str, user_id: Optional[int] = None) -> None:
        """
        Update the notes for a reading record.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            notes: New notes to save
            user_id: Optional user ID (for multi-user systems)
        """
        try:
            # Check if a record exists
            query = """
            SELECT id FROM reading_records 
            WHERE source_type = %s AND content_id = %s AND 
            (user_id = %s OR (user_id IS NULL AND %s IS NULL))
            """
            result = self.execute(query, (source_type, content_id, user_id, user_id))
            
            if result:
                # Update existing record
                record_id = result[0]['id']
                self.execute(
                    "UPDATE reading_records SET notes = %s WHERE id = %s",
                    (notes, record_id),
                    commit=True
                )
            else:
                # Create a new record with just the notes
                self.mark_as_read(
                    source_type=source_type,
                    content_id=content_id,
                    user_id=user_id,
                    notes=notes
                )
        except Exception as e:
            logger.error(f"Error updating record notes: {e}")
            self.connection.rollback()
            raise
    
    def update_record_rating(self, source_type: str, content_id: str, rating: int, user_id: Optional[int] = None) -> None:
        """
        Update the rating for a reading record.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            rating: New rating (typically 1-5)
            user_id: Optional user ID (for multi-user systems)
        """
        try:
            # Check if a record exists
            query = """
            SELECT id FROM reading_records 
            WHERE source_type = %s AND content_id = %s AND 
            (user_id = %s OR (user_id IS NULL AND %s IS NULL))
            """
            result = self.execute(query, (source_type, content_id, user_id, user_id))
            
            if result:
                # Update existing record
                record_id = result[0]['id']
                self.execute(
                    "UPDATE reading_records SET rating = %s WHERE id = %s",
                    (rating, record_id),
                    commit=True
                )
            else:
                # Create a new record with just the rating
                self.mark_as_read(
                    source_type=source_type,
                    content_id=content_id,
                    user_id=user_id,
                    rating=rating
                )
        except Exception as e:
            logger.error(f"Error updating record rating: {e}")
            self.connection.rollback()
            raise
    
    def delete_reading_record(self, source_type: str, content_id: str, user_id: Optional[int] = None) -> bool:
        """
        Delete a reading record.
        
        Args:
            source_type: Type of content ('pubmed', 'medrxiv', etc.)
            content_id: Identifier for the content (PMID, DOI, etc.)
            user_id: Optional user ID (for multi-user systems)
            
        Returns:
            Boolean indicating if a record was deleted
        """
        try:
            query = """
            DELETE FROM reading_records 
            WHERE source_type = %s AND content_id = %s AND 
            (user_id = %s OR (user_id IS NULL AND %s IS NULL))
            """
            result = self.execute(query, (source_type, content_id, user_id, user_id), commit=True)
            
            # Return True if a record was deleted
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting reading record: {e}")
            self.connection.rollback()
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about reading records.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        # Total records
        result = self.execute("SELECT COUNT(*) AS total FROM reading_records")
        stats['total_records'] = result[0]['total'] if result else 0
        
        # Records by source type
        result = self.execute(
            "SELECT source_type, COUNT(*) AS count FROM reading_records GROUP BY source_type"
        )
        stats['by_source_type'] = {row['source_type']: row['count'] for row in result} if result else {}
        
        # Records with ratings
        result = self.execute("SELECT COUNT(*) AS count FROM reading_records WHERE rating IS NOT NULL")
        stats['with_ratings'] = result[0]['count'] if result else 0
        
        # Records with notes
        result = self.execute("SELECT COUNT(*) AS count FROM reading_records WHERE notes IS NOT NULL")
        stats['with_notes'] = result[0]['count'] if result else 0
        
        # Records with tags
        result = self.execute("""
            SELECT COUNT(DISTINCT record_id) AS count 
            FROM reading_records_tags
        """)
        stats['with_tags'] = result[0]['count'] if result else 0
        
        # Tag counts
        result = self.execute("""
            SELECT t.name, COUNT(rt.record_id) AS count
            FROM reading_tags t
            JOIN reading_records_tags rt ON t.id = rt.tag_id
            GROUP BY t.name
            ORDER BY count DESC
        """)
        stats['tag_counts'] = {row['name']: row['count'] for row in result} if result else {}
        
        # Recent activity - records per day over the last week
        result = self.execute("""
            SELECT DATE(read_timestamp) AS date, COUNT(*) AS count
            FROM reading_records
            WHERE read_timestamp >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(read_timestamp)
            ORDER BY date
        """)
        stats['recent_activity'] = {str(row['date']): row['count'] for row in result} if result else {}
        
        return stats
