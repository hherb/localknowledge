"""
Migration 004: Reading Suggestions

This migration adds tables for reading suggestions and evaluators.
"""

import logging
from typing import Optional, Callable

from localknowledge.db.migrations_system import MigrationsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.

    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 004: Reading Suggestions")

    # Create evaluators table
    logger.info("Creating evaluators table")
    db_manager.execute("""
    CREATE TABLE IF NOT EXISTS evaluators (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        user_id INTEGER REFERENCES users(id),
        model_id TEXT,
        parameters JSONB,
        prompt TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    );
    """, commit=True)

    # Create reading_suggestions table
    logger.info("Creating reading_suggestions table")
    db_manager.execute("""
    CREATE TABLE IF NOT EXISTS reading_suggestions (
        id SERIAL PRIMARY KEY,
        document_id INTEGER NOT NULL REFERENCES document(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        evaluator_id INTEGER NOT NULL REFERENCES evaluators(id),
        recommendation_strength INTEGER CHECK (recommendation_strength >= 0 AND recommendation_strength <= 5),
        confidence_level FLOAT,
        comment TEXT,
        user_agreement BOOLEAN,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    );
    """, commit=True)

    # Add indexes for performance
    logger.info("Creating indexes")
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_reading_suggestions_document_id ON reading_suggestions(document_id);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_reading_suggestions_user_id ON reading_suggestions(user_id);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_reading_suggestions_evaluator_id ON reading_suggestions(evaluator_id);
    """, commit=True)
    
    db_manager.execute("""
    CREATE INDEX IF NOT EXISTS idx_reading_suggestions_recommendation_strength ON reading_suggestions(recommendation_strength);
    """, commit=True)

    # Add a unique constraint to prevent duplicate suggestions
    logger.info("Creating unique constraint")
    db_manager.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_suggestions_unique 
    ON reading_suggestions(document_id, user_id, evaluator_id);
    """, commit=True)

    logger.info("Migration 004 completed successfully")
