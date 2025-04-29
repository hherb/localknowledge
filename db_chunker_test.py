#!/usr/bin/env python3
"""
Test script for inserting chunks into the database.
"""

import logging
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNKING_STRATEGY_ID = 2  # Use a different ID for testing
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table
TEST_LIMIT = 2  # Number of abstracts to test

def get_test_documents():
    """
    Get a few documents for testing.
    """
    # Use hardcoded test documents instead of querying the database
    return [
        {
            "id": 1,
            "title": "Short Abstract Test",
            "abstract": "This is a short abstract that should fit in a single chunk."
        },
        {
            "id": 2,
            "title": "Medium Abstract Test",
            "abstract": """This is a medium-length abstract that might be split into multiple chunks.
            It contains multiple sentences and should demonstrate the sentence boundary detection.
            The chunker should try to split at sentence boundaries when possible.
            This abstract is still relatively short but might be split depending on the chunk size."""
        }
    ]

def ensure_test_chunking_strategy_exists():
    """
    Ensure that the test chunking strategy exists in the database.
    """
    try:
        db_manager = ChunkingDatabaseManager()

        # Create parameters
        parameters = {
            "chunk_size": 384,
            "overlap": 128,
            "min_chunk_size": 100,
            "includes_title": True,
            "boundary_aware": True,
            "test_strategy": True
        }

        # Check if strategy exists
        strategies = db_manager.list_chunking_strategies()
        strategy_exists = any(s['id'] == CHUNKING_STRATEGY_ID for s in strategies)

        if strategy_exists:
            logger.info(f"Test chunking strategy with ID {CHUNKING_STRATEGY_ID} already exists")
        else:
            # Create the strategy
            strategy_id = db_manager.get_or_create_chunking_strategy(
                strategy_name="test_adaptive_chunker",
                parameters=parameters
            )
            logger.info(f"Created test chunking strategy with ID {strategy_id}")

        return True
    except Exception as e:
        logger.error(f"Error ensuring test chunking strategy exists: {e}")
        return False

def process_documents():
    """
    Process documents and insert chunks into the database.
    """
    # Ensure the test chunking strategy exists
    if not ensure_test_chunking_strategy_exists():
        logger.error("Failed to ensure test chunking strategy, exiting")
        return

    # Initialize chunker
    chunker = AdaptiveTextChunker(
        max_chunk_size=384,
        overlap=128,
        min_chunk_size=100
    )

    # Get test documents
    documents = get_test_documents()

    if not documents:
        logger.error("No documents found, exiting")
        return

    # Create database manager
    db_manager = ChunkingDatabaseManager()

    # Process each document
    for doc in documents:
        doc_id = doc['id']
        title = doc['title']
        abstract = doc['abstract']

        logger.info(f"Processing document {doc_id}: '{title[:50]}...' ({len(abstract)} chars)")

        # Create metadata with title
        metadata = {
            'title': title,
            'source': 'abstract',
            'document_id': doc_id
        }

        # Chunk the abstract
        chunks = chunker.chunk(abstract, metadata=metadata)

        logger.info(f"Created {len(chunks)} chunks for document {doc_id}")

        # Convert to database chunks
        db_chunks = []
        for i, chunk in enumerate(chunks):
            db_chunk = chunk.to_db_chunk(
                document_id=doc_id,
                chunking_strategy_id=CHUNKING_STRATEGY_ID,
                chunktype_id=CHUNKTYPE_ID,
                document_title=title,
                chunk_no=i
            )
            db_chunks.append(db_chunk)

        # Insert chunks into database
        chunk_ids = db_manager.batch_insert_chunks(db_chunks)

        logger.info(f"Inserted {len(chunk_ids)} chunks for document {doc_id}")

    logger.info(f"Processed {len(documents)} documents")

def display_chunks():
    """
    Display chunks from the database.
    """
    try:
        with get_cursor() as cursor:
            # Get statistics about the test chunks
            query = """
            SELECT
                d.id as document_id,
                d.title as document_title,
                length(d.abstract) as abstract_length,
                count(c.id) as chunk_count,
                min(c.chunklength) as min_chunk_length,
                max(c.chunklength) as max_chunk_length,
                avg(c.chunklength) as avg_chunk_length
            FROM document d
            JOIN chunks c ON d.id = c.document_id
            WHERE c.chunking_strategy_id = %s
            GROUP BY d.id, d.title, d.abstract
            ORDER BY length(d.abstract) DESC
            """

            cursor.execute(query, (CHUNKING_STRATEGY_ID,))
            results = cursor.fetchall()

            if not results:
                logger.info("No chunks found in the database")
                return

            # Display results
            print("\n===== Chunks in Database =====")
            print(f"{'Document ID':<12} {'Abstract Length':<16} {'Chunks':<8} {'Min Length':<12} {'Max Length':<12} {'Avg Length':<12} {'Title':<40}")
            print("-" * 120)

            for row in results:
                print(f"{row['document_id']:<12} {row['abstract_length']:<16} {row['chunk_count']:<8} {row['min_chunk_length']:<12} {row['max_chunk_length']:<12} {row['avg_chunk_length']:<12.1f} {row['document_title'][:40]}")

            # Get a sample of chunks to display
            print("\n===== Sample Chunks =====")
            sample_query = """
            SELECT
                c.id as chunk_id,
                c.document_id,
                c.chunk_no,
                c.chunklength,
                c.text,
                c.metadata
            FROM chunks c
            WHERE c.chunking_strategy_id = %s
            ORDER BY c.document_id, c.chunk_no
            LIMIT 5
            """

            cursor.execute(sample_query, (CHUNKING_STRATEGY_ID,))
            samples = cursor.fetchall()

            for row in samples:
                print(f"\nChunk ID: {row['chunk_id']}")
                print(f"Document ID: {row['document_id']}, Chunk #: {row['chunk_no']}, Length: {row['chunklength']}")
                print(f"Metadata: {row['metadata']}")
                print(f"Text: {row['text'][:200]}...")

    except Exception as e:
        logger.error(f"Error displaying chunks: {e}")

def main():
    """
    Main function.
    """
    # Load environment variables
    load_environment()

    # Process documents and insert chunks
    process_documents()

    # Display chunks
    display_chunks()

if __name__ == "__main__":
    main()
