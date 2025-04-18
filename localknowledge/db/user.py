"""
User and interests database functionality for the LocalKnowledge library.

This module provides database operations specific to user data and interests.
"""
from typing import List, Dict, Any, Optional, Tuple
import bcrypt
from localknowledge.db.base import DatabaseManager


class UserDatabaseManager(DatabaseManager):
    """Database manager for user data and interests."""
    
    def __init__(self):
        """Initialize the user database manager."""
        super().__init__()
        self.create_tables()
    
    def create_tables(self) -> None:
        """Create user-related tables if they don't exist."""
        # Create users table
        self.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            firstname TEXT,
            surname TEXT,
            email TEXT UNIQUE NOT NULL,
            pwdhash TEXT NOT NULL
        )
        """, commit=True)
        
        # Create user_interests table
        self.execute("""
        CREATE TABLE IF NOT EXISTS user_interests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            interest TEXT NOT NULL,
            UNIQUE (user_id, interest)
        )
        """, commit=True)
        
        # Create index for user interests
        self.execute("CREATE INDEX IF NOT EXISTS idx_user_interests_user_id ON user_interests(user_id)", commit=True)
    
    def create_user(self, username: str, firstname: str, surname: str, 
                   email: str, password: str) -> Optional[int]:
        """
        Create a new user in the database.
        
        Args:
            username: Unique username
            firstname: First name
            surname: Last name
            email: Email address
            password: Plain text password (will be hashed)
            
        Returns:
            User ID if successful, None if failed
        """
        try:
            # Hash the password
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            query = """
            INSERT INTO users (username, firstname, surname, email, pwdhash)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """
            result = self.execute(query, (username, firstname, surname, email, hashed.decode('utf-8')), commit=True)
            
            if result and len(result) > 0:
                return result[0]['id']
            return None
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username/password.
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            User data if authentication successful, None otherwise
        """
        try:
            # Check if username is actually an email
            if '@' in username:
                query = "SELECT * FROM users WHERE email = %s"
            else:
                query = "SELECT * FROM users WHERE username = %s"
                
            result = self.execute(query, (username,))
            
            if result and len(result) > 0:
                user = result[0]
                stored_hash = user['pwdhash'].encode('utf-8')
                
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    # Don't return the password hash to the caller
                    del user['pwdhash']
                    return user
            
            return None
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User data if found, None otherwise
        """
        query = "SELECT id, username, firstname, surname, email FROM users WHERE id = %s"
        result = self.execute(query, (user_id,))
        
        if result and len(result) > 0:
            return result[0]
        return None
    
    def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        """
        Update user data.
        
        Args:
            user_id: User ID
            data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            allowed_fields = ['firstname', 'surname', 'email']
            update_fields = []
            params = []
            
            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    params.append(data[field])
            
            # Handle password separately
            if 'password' in data:
                hashed = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
                update_fields.append("pwdhash = %s")
                params.append(hashed.decode('utf-8'))
            
            if not update_fields:
                return False
            
            query = f"""
            UPDATE users
            SET {", ".join(update_fields)}
            WHERE id = %s
            """
            params.append(user_id)
            
            self.execute(query, tuple(params), commit=True)
            return True
        except Exception as e:
            print(f"Error updating user: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute("DELETE FROM users WHERE id = %s", (user_id,), commit=True)
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False
    
    def add_interest(self, user_id: int, interest: str) -> bool:
        """
        Add an interest for a user.
        
        Args:
            user_id: User ID
            interest: Interest string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT INTO user_interests (user_id, interest)
            VALUES (%s, %s)
            ON CONFLICT (user_id, interest) DO NOTHING
            """
            self.execute(query, (user_id, interest), commit=True)
            return True
        except Exception as e:
            print(f"Error adding interest: {e}")
            return False
    
    def remove_interest(self, user_id: int, interest: str) -> bool:
        """
        Remove an interest for a user.
        
        Args:
            user_id: User ID
            interest: Interest string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                "DELETE FROM user_interests WHERE user_id = %s AND interest = %s",
                (user_id, interest),
                commit=True
            )
            return True
        except Exception as e:
            print(f"Error removing interest: {e}")
            return False
    
    def get_user_interests(self, user_id: int) -> List[str]:
        """
        Get all interests for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of interest strings
        """
        query = "SELECT interest FROM user_interests WHERE user_id = %s"
        results = self.execute(query, (user_id,))
        
        if results:
            return [row['interest'] for row in results]
        return []
    
    def get_users_by_interest(self, interest: str) -> List[Dict[str, Any]]:
        """
        Get all users with a specific interest.
        
        Args:
            interest: Interest string
            
        Returns:
            List of user data dictionaries
        """
        query = """
        SELECT u.id, u.username, u.firstname, u.surname, u.email
        FROM users u
        INNER JOIN user_interests ui ON u.id = ui.user_id
        WHERE ui.interest = %s
        """
        return self.execute(query, (interest,)) or []
