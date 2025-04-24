"""
Migration 002: add_all_keywords_column

This migration script adds the all_keywords column to the document table,
creates a trigger to maintain it, and creates a GIN index for efficient searching.
"""

import logging
from typing import Callable, Optional
from localknowledge.db.migrations_system.manager import MigrationsManager

# Configure logging
logger = logging.getLogger(__name__)

def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.

    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 002: add_all_keywords_column")

    # Step 1: Check if the all_keywords column already exists
    logger.info("Checking if all_keywords column already exists")
    result = db_manager.execute_without_timeout("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'document' AND column_name = 'all_keywords';
    """)

    if not result:
        # Column doesn't exist, add it
        logger.info("Adding all_keywords column to document table")
        db_manager.execute_without_timeout("""
        ALTER TABLE public.document
        ADD COLUMN all_keywords text[];
        """, commit=True)

        if progress_callback:
            progress_callback(1, 4, "Added all_keywords column")
    else:
        logger.info("all_keywords column already exists in document table")
        if progress_callback:
            progress_callback(1, 4, "all_keywords column already exists")

    # Step 2: Create the trigger function if it doesn't exist
    logger.info("Creating or replacing update_all_keywords_trigger function")
    db_manager.execute_without_timeout("""
    CREATE OR REPLACE FUNCTION update_all_keywords_trigger()
    RETURNS TRIGGER AS $$
    BEGIN
      -- Combine, lowercase, and de-duplicate
      NEW.all_keywords := (
        SELECT ARRAY(
          SELECT DISTINCT LOWER(element)
          FROM unnest(
            coalesce(NEW.keywords, '{}') ||
            coalesce(NEW.augmented_keywords, '{}') ||
            coalesce(NEW.mesh_terms, '{}')
          ) AS element
          WHERE element IS NOT NULL
        )
      );

      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """, commit=True)

    if progress_callback:
        progress_callback(2, 4, "Created trigger function")

    # Step 3: Create the trigger if it doesn't exist
    logger.info("Checking if trigger already exists")
    result = db_manager.execute_without_timeout("""
    SELECT tgname
    FROM pg_trigger
    WHERE tgname = 'update_all_keywords_before_ins_upd';
    """)

    if not result:
        logger.info("Creating trigger on document table")
        db_manager.execute_without_timeout("""
        CREATE TRIGGER update_all_keywords_before_ins_upd
        BEFORE INSERT OR UPDATE ON public.document
        FOR EACH ROW
        EXECUTE FUNCTION update_all_keywords_trigger();
        """, commit=True)

        if progress_callback:
            progress_callback(3, 4, "Created trigger")
    else:
        logger.info("Trigger already exists")
        if progress_callback:
            progress_callback(3, 4, "Trigger already exists")

    # Step 4: Backfill the new column with existing data
    logger.info("Backfilling all_keywords column with existing data")

    # Get the total number of documents
    result = db_manager.execute_without_timeout("SELECT COUNT(*) FROM public.document;")
    total_documents = result[0]['count'] if result else 0
    logger.info(f"Total documents to process: {total_documents}")

    if total_documents > 0:
        # Process in batches of 1,000 documents
        batch_size = 1000
        num_batches = (total_documents + batch_size - 1) // batch_size

        logger.info(f"Processing in {num_batches} batches of {batch_size} documents")

        for batch in range(num_batches):
            start_id = batch * batch_size
            end_id = min((batch + 1) * batch_size, total_documents)

            logger.info(f"Processing batch {batch + 1}/{num_batches} (documents {start_id} to {end_id})")

            # Update documents in this batch with no timeout
            db_manager.execute_without_timeout(f"""
            UPDATE public.document
            SET all_keywords = (
              SELECT ARRAY(
                SELECT DISTINCT LOWER(element)
                FROM unnest(
                  coalesce(keywords, '{{}}') ||
                  coalesce(augmented_keywords, '{{}}') ||
                  coalesce(mesh_terms, '{{}}')
                ) AS element
                WHERE element IS NOT NULL
              )
            )
            WHERE id IN (
                SELECT id FROM public.document
                WHERE all_keywords IS NULL
                ORDER BY id
                LIMIT {batch_size} OFFSET {start_id}
            );
            """, commit=True)

            if progress_callback:
                progress_callback(4, 5, f"Backfilled batch {batch + 1}/{num_batches}")
    else:
        logger.info("No documents to process")

    if progress_callback:
        progress_callback(4, 5, "Backfilled all_keywords column")

    # Step 5: Create the GIN index if it doesn't exist
    logger.info("Checking if GIN index already exists")
    result = db_manager.execute_without_timeout("""
    SELECT indexname
    FROM pg_indexes
    WHERE indexname = 'idx_document_all_keywords_gin';
    """)

    if not result:
        logger.info("Creating GIN index on all_keywords column")
        db_manager.execute_without_timeout("""
        CREATE INDEX idx_document_all_keywords_gin ON public.document USING GIN (all_keywords);
        """, commit=True)

        if progress_callback:
            progress_callback(5, 5, "Created GIN index")
    else:
        logger.info("GIN index already exists")
        if progress_callback:
            progress_callback(5, 5, "GIN index already exists")

    logger.info("Migration 002 completed successfully")
