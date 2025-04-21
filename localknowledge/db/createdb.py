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
from localknowledge.db.reading_tracker import ReadingTrackerManager

# Import embedding database manager
try:
    from localknowledge.embeddings.database import EmbeddingDatabaseManager
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    logger.warning("Embeddings module not available. Skipping embedding tables.")
    EMBEDDINGS_AVAILABLE = False

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
        medrxiv_db.create_indices()
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
        pubmed_db.create_indices()
        managers.append(pubmed_db)
        logger.info("PubMed tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing PubMed tables: {e}")

    try:
        logger.info("Initializing Reading Tracker tables...")
        reading_tracker_db = ReadingTrackerManager()
        reading_tracker_db.create_tables()
        managers.append(reading_tracker_db)
        logger.info("Reading Tracker tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Reading Tracker tables: {e}")

    # Initialize Embedding tables if available
    if EMBEDDINGS_AVAILABLE:
        try:
            logger.info("Initializing Embedding tables...")
            embedding_db = EmbeddingDatabaseManager()
            embedding_db.create_tables()
            embedding_db.create_indices()
            managers.append(embedding_db)
            logger.info("Embedding tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Embedding tables: {e}")

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