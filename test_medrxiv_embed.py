#!/usr/bin/env python3
import os
import ollama
import time
import logging
from dotenv import load_dotenv

# Import the necessary classes from the codebase
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.embeddings.database import EmbeddingDatabaseManager

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_abstract_sample(limit=2):
    """Get a sample of abstracts from the database."""
    db = MedRxivDatabaseManager()

    try:
        query = """
        SELECT doi, title, abstract
        FROM preprints
        WHERE abstract IS NOT NULL AND abstract != ''
        LIMIT %s
        """
        results = db.execute(query, (limit,))
        return results or []
    except Exception as e:
        logger.error(f"Error fetching abstracts: {e}")
        return []
    finally:
        db.close()

def create_embedding(text):
    """Create an embedding for the given text."""
    start_time = time.time()
    response = ollama.embeddings(model="snowflake-arctic-embed2:latest", prompt=text)
    end_time = time.time()

    embedding = response.get('embedding', [])
    logger.info(f"Embedding created in {end_time - start_time:.2f} seconds, length: {len(embedding)}")
    return embedding

def main():
    """Main function."""
    # Get sample abstracts
    abstracts = get_abstract_sample(limit=2)
    logger.info(f"Retrieved {len(abstracts)} abstracts")

    if not abstracts:
        logger.error("No abstracts found. Check database connection.")
        return

    # Process each abstract
    for i, abstract in enumerate(abstracts):
        doi = abstract['doi']
        abstract_text = abstract['abstract']

        logger.info(f"Processing abstract {i+1}/{len(abstracts)}: {doi}")
        logger.info(f"Abstract length: {len(abstract_text)} characters")

        # Create embedding
        start_time = time.time()
        embedding = create_embedding(abstract_text)
        end_time = time.time()

        logger.info(f"Total time for abstract {i+1}: {end_time - start_time:.2f} seconds")

        # Store the embedding in the database
        if embedding:
            db = EmbeddingDatabaseManager()
            try:
                start_time = time.time()
                db.store_embedding(
                    source_id='medrxiv',
                    document_id=doi,
                    chunk_no=0,
                    page_no=None,
                    text=abstract_text,
                    embedding=embedding,
                    model_name="snowflake-arctic-embed2:latest"
                )
                end_time = time.time()
                logger.info(f"Embedding stored in database in {end_time - start_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Error storing embedding: {e}")
            finally:
                db.close()

if __name__ == "__main__":
    main()
