"""Fix for reading_tracker.py to handle NoneType result issue in delete_reading_record"""
import traceback
from typing import Optional

def delete_reading_record(self, source_type: str, content_id: str, user_id: Optional[int] = None) -> bool:
    """
    Delete a reading record from the database.
    
    Args:
        source_type: Type of content ('pubmed', 'medrxiv', etc.)
        content_id: Unique identifier for the content
        user_id: Optional user ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Build query with conditionals
        query = """
        DELETE FROM reading_tracker
        WHERE source_type = %s AND content_id = %s
        """
        
        params = [source_type, content_id]
        
        # Add user_id condition if provided
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        
        # Execute the query
        result = self.execute(query, tuple(params))
        
        # Check if result is None (might happen if there's no connection or other DB issues)
        if result is None:
            print("Warning: execute() returned None in delete_reading_record")
            return False
            
        # Return True if at least one row was affected
        return result.rowcount > 0
        
    except Exception as e:
        print(f"Error deleting reading record: {str(e)}")
        traceback.print_exc()
        return False
