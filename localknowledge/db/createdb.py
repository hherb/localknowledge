"""
Database initialization module for the LocalKnowledge library.

This module coordinates the creation of all database tables and indexes across different
database modules. When a new database module is added, its create_tables function
should be called here.
"""

import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database managers
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.user import UserDatabaseManager
from localknowledge.db.pubmed import PubMedDatabaseManager
# Import additional database managers here as they are added

def create_all_tables() -> None:
    """Create all tables across all database modules."""
    logger.info("Initializing database tables...")
    
    # List of database managers to initialize
    managers = []
    
    try:
        logger.info("Initializing MedRxiv tables...")
        medrxiv_db = MedRxivDatabaseManager()
        medrxiv_db.create_tables()
        managers.append(medrxiv_db)
        logger.info("MedRxiv tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing MedRxiv tables: {e}")
    
    try:
        logger.info("Initializing User tables...")
        user_db = UserDatabaseManager()
        user_db.create_tables()
        managers.append(user_db)
        logger.info("User tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing User tables: {e}")
    
    try:
        logger.info("Initializing PubMed tables...")
        pubmed_db = PubMedDatabaseManager()
        pubmed_db.create_tables()
        managers.append(pubmed_db)
        logger.info("PubMed tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing PubMed tables: {e}")
    
    # Add calls to additional database modules' create_tables methods here
    
    # Close all connections
    for manager in managers:
        try:
            manager.close()
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
    
    logger.info("Database initialization complete")

def main():
    """Main function to execute when run as a script."""
    create_all_tables()

if __name__ == "__main__":
    main()