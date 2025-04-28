#!/usr/bin/env python3
"""
Chunk Abstracts Script

This script extracts abstracts from the document table, chunks them using
an overlapping text splitter, and stores the chunks in the chunks table.
"""

import os
import logging
import time
import argparse
from typing import List, Dict, Any, Tuple, Optional

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

from pubmedbert_experiment import get_cursor, load_environment

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 384  # Size for PubMedBERT chunks when splitting is needed
OVERLAP = 128     # Overlap between chunks to maintain context
SINGLE_CHUNK_THRESHOLD = 2000  # Maximum size for creating a single chunk (covers most abstracts)
CHUNKING_STRATEGY_ID = 1  # ID of the adaptive_splitter strategy in the database
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table


class AdaptiveTextChunker:
    """
    Adaptive text chunker for PubMedBERT that handles abstracts of different sizes efficiently.
    - Prepends document title to each chunk
    - Creates a single chunk for abstracts under a threshold
    - Chunks longer abstracts with proper sentence/paragraph boundaries
    """

    def __init__(self,
                 single_chunk_threshold: int = 2000,
                 max_chunk_size: int = CHUNK_SIZE,
                 overlap: int = OVERLAP,
                 min_chunk_size: int = 100):
        """
        Initialize the chunker.

        Args:
            single_chunk_threshold: Maximum size in characters for creating a single chunk
            max_chunk_size: Maximum size of each chunk in characters for longer texts
            overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size of a chunk to be considered valid
        """
        self.single_chunk_threshold = single_chunk_threshold
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(self, text: str, title: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Split text into chunks adaptively based on length, with title prepended.

        Args:
            text: The text to chunk
            title: The document title to prepend to each chunk

        Returns:
            List of tuples (chunk_text, metadata)
        """
        if not text or len(text.strip()) == 0:
            return []

        # Format title with tags
        formatted_title = f"<title>{title}</title>\n"
        title_length = len(formatted_title)

        # Adjust max chunk size to account for title
        effective_max_size = self.max_chunk_size - title_length

        # For short abstracts, create a single chunk
        if len(text) <= self.single_chunk_threshold:
            chunk_text = formatted_title + text.strip()
            metadata = {
                'chunk_number': 0,
                'start_char': 0,
                'end_char': len(text),
                'char_length': len(chunk_text),
                'is_complete_abstract': True,
                'title_included': True
            }
            return [(chunk_text, metadata)]

        # For longer abstracts, chunk with sentence boundaries
        logger.info(f"Chunking long abstract with {len(text)} characters")
        return self._chunk_with_boundaries(text, title, formatted_title, effective_max_size)

    def _find_sentence_end(self, text: str, start: int, end: int) -> int:
        """
        Find the end of a sentence within the specified range.

        Args:
            text: The text to search
            start: Start position
            end: End position

        Returns:
            Position of sentence end, or end if none found
        """
        # Look for sentence boundaries (., !, ?) followed by space or newline
        sentence_end = max(
            text.rfind('. ', start, end),
            text.rfind('! ', start, end),
            text.rfind('? ', start, end),
            text.rfind('.\n', start, end),
            text.rfind('!\n', start, end),
            text.rfind('?\n', start, end)
        )

        # If found a valid sentence end, include the period
        if sentence_end > start:
            return sentence_end + 1

        # If no sentence boundary, look for paragraph breaks
        paragraph_end = max(
            text.rfind('\n\n', start, end),
            text.rfind('\r\n\r\n', start, end)
        )

        if paragraph_end > start:
            return paragraph_end + 2  # Include the newline

        return end

    def _find_sentence_start(self, text: str, position: int, end: int) -> int:
        """
        Find the start of a sentence near the specified position.

        Args:
            text: The text to search
            position: Approximate position to find sentence start
            end: End boundary for search

        Returns:
            Position of sentence start, or position if none found
        """
        # Look backwards for end of previous sentence
        prev_end = max(
            text.rfind('. ', 0, position),
            text.rfind('! ', 0, position),
            text.rfind('? ', 0, position),
            text.rfind('.\n', 0, position),
            text.rfind('!\n', 0, position),
            text.rfind('?\n', 0, position)
        )

        # If found, start after that sentence
        if prev_end > 0:
            # Skip the period and any whitespace
            start = prev_end + 1
            while start < end and start < len(text) and text[start].isspace():
                start += 1
            return start

        # Look for paragraph breaks
        paragraph_start = max(
            text.rfind('\n\n', 0, position),
            text.rfind('\r\n\r\n', 0, position)
        )

        if paragraph_start > 0:
            # Skip the newlines
            start = paragraph_start + 2
            while start < end and start < len(text) and text[start].isspace():
                start += 1
            return start

        return position

    def _chunk_with_boundaries(self, text: str, title: str, formatted_title: str,
                              effective_max_size: int) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Split text into chunks with proper sentence/paragraph boundaries.

        Args:
            text: The text to chunk
            title: The document title (unused, kept for API consistency)
            formatted_title: The formatted title with tags
            effective_max_size: Maximum size of chunk content (excluding title)

        Returns:
            List of tuples (chunk_text, metadata)
        """
        chunks = []
        start = 0
        chunk_number = 0

        while start < len(text):
            # Calculate preliminary end position
            preliminary_end = min(start + effective_max_size, len(text))

            # If remaining text fits in one chunk, take it all
            if preliminary_end == len(text):
                end = len(text)
            else:
                # Find the end of a sentence before the preliminary end
                end = self._find_sentence_end(text, start, preliminary_end)

            # Extract the chunk text (without title yet)
            chunk_content = text[start:end].strip()

            # Create the full chunk with title
            full_chunk = formatted_title + chunk_content

            # Create metadata
            metadata = {
                'chunk_number': chunk_number,
                'start_char': start,
                'end_char': end,
                'char_length': len(full_chunk),
                'is_complete_abstract': (end == len(text) and start == 0),
                'title_included': True
            }

            # Add to chunks if not empty
            if chunk_content:
                chunks.append((full_chunk, metadata))
                chunk_number += 1

            # Calculate preliminary start of next chunk
            preliminary_start = end - self.overlap

            # Ensure we're not going backwards
            if preliminary_start <= start:
                # If we can't make progress, force advancement
                preliminary_start = start + 1

            # Handle special case for last small chunk
            remaining = len(text) - preliminary_start
            if 0 < remaining < self.overlap:
                # Extend the chunk to include the remaining text
                preliminary_start = max(0, len(text) - self.overlap * 2)

            # Find the nearest sentence/paragraph start
            if preliminary_start < len(text):
                start = self._find_sentence_start(text, preliminary_start, end)
            else:
                break

            # Safety check to prevent infinite loops
            if start >= end:
                start = end
                if start >= len(text):
                    break

        return chunks


def get_documents_without_chunks(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get documents that don't have chunks in the chunks table.

    Args:
        limit: Maximum number of documents to retrieve

    Returns:
        List of document dictionaries
    """
    documents = []

    try:
        with get_cursor() as cursor:
            # Check if the document table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'document'
                )
            """)
            if not cursor.fetchone()[0]:
                logger.error("Document table does not exist")
                return []

            # Find documents that don't have chunks
            query = """
            SELECT d.id, d.title, d.abstract
            FROM document d
            LEFT JOIN chunks c ON d.id = c.document_id
            WHERE c.id IS NULL
            AND d.abstract IS NOT NULL
            AND length(d.abstract) > 0
            LIMIT %s
            """

            cursor.execute(query, (limit,))
            documents = cursor.fetchall()
            logger.info(f"Found {len(documents)} documents without chunks")

    except Exception as e:
        logger.error(f"Error getting documents without chunks: {e}")

    return documents


def insert_chunks(chunks_data: List[Tuple]) -> int:
    """
    Insert chunks into the chunks table.

    Args:
        chunks_data: List of tuples (document_id, chunking_strategy_id, chunktype_id,
                                    document_title, text, chunklength, chunk_no, metadata)

    Returns:
        Number of chunks inserted
    """
    inserted = 0

    try:
        with get_cursor(commit=True) as cursor:
            # Insert chunks into chunks table
            query = """
            INSERT INTO chunks
            (document_id, chunking_strategy_id, chunktype_id, document_title, text, chunklength, chunk_no, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.executemany(query, chunks_data)
            inserted = cursor.rowcount
            logger.info(f"Inserted {inserted} chunks")

    except Exception as e:
        logger.error(f"Error inserting chunks: {e}")

    return inserted


def process_documents(documents: List[Dict[str, Any]], chunker: AdaptiveTextChunker) -> int:
    """
    Process documents and create chunks.

    Args:
        documents: List of document dictionaries
        chunker: Text chunker instance

    Returns:
        Number of chunks created
    """
    if not documents:
        logger.info("No documents to process")
        return 0

    chunks_data = []
    single_chunks = 0
    multi_chunks = 0

    for doc in documents:
        # Skip documents without abstracts
        if not doc['abstract'] or len(doc['abstract'].strip()) == 0:
            continue

        # Chunk the abstract with title
        abstract_length = len(doc['abstract'])
        chunks = chunker.chunk_text(doc['abstract'], doc['title'])

        # Track chunking statistics
        if len(chunks) == 1 and chunks[0][1].get('is_complete_abstract', False):
            single_chunks += 1
        else:
            multi_chunks += 1
            logger.info(f"Document {doc['id']} with {abstract_length} chars split into {len(chunks)} chunks")

        # Prepare data for insertion
        import json
        for chunk_number, (chunk_text, metadata) in enumerate(chunks):
            chunks_data.append((
                doc['id'],                  # document_id
                CHUNKING_STRATEGY_ID,       # chunking_strategy_id
                CHUNKTYPE_ID,               # chunktype_id
                doc['title'],               # document_title
                chunk_text,                 # text
                len(chunk_text),            # chunklength
                chunk_number,               # chunk_no
                json.dumps(metadata)        # metadata as JSON string
            ))

    # Log chunking statistics
    if single_chunks > 0 or multi_chunks > 0:
        logger.info(f"Chunking statistics: {single_chunks} single chunks, {multi_chunks} multi-chunk documents")

    # Insert chunks into database
    if chunks_data:
        return insert_chunks(chunks_data)

    return 0


def ensure_chunking_strategy_exists(single_chunk_threshold: int = SINGLE_CHUNK_THRESHOLD,
                              min_chunk_size: int = 100):
    """
    Ensure that the chunking strategy exists in the database.
    If not, create it.

    Args:
        single_chunk_threshold: Maximum size for creating a single chunk
        min_chunk_size: Minimum size of a chunk to be considered valid

    Returns:
        bool: True if strategy exists or was created, False otherwise
    """
    try:
        import json

        # Create parameters as JSON string
        parameters = json.dumps({
            "single_chunk_threshold": single_chunk_threshold,
            "chunk_size": CHUNK_SIZE,
            "overlap": OVERLAP,
            "min_chunk_size": min_chunk_size,
            "includes_title": True,
            "boundary_aware": True
        })

        with get_cursor(commit=True) as cursor:
            # Check if strategy exists
            cursor.execute(
                "SELECT COUNT(*) FROM chunking_strategies WHERE id = %s",
                (CHUNKING_STRATEGY_ID,)
            )
            if cursor.fetchone()[0] > 0:
                # Update the strategy parameters if it exists
                cursor.execute(
                    """
                    UPDATE chunking_strategies
                    SET strategy_name = %s, parameters = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        "boundary_aware_titled_splitter",
                        parameters,
                        CHUNKING_STRATEGY_ID
                    )
                )
                logger.info(f"Updated chunking strategy with ID {CHUNKING_STRATEGY_ID}")
                return True

            # Strategy doesn't exist, create it
            logger.info(f"Creating chunking strategy with ID {CHUNKING_STRATEGY_ID}")

            cursor.execute(
                """
                INSERT INTO chunking_strategies (id, strategy_name, parameters)
                VALUES (%s, %s, %s::jsonb)
                """,
                (
                    CHUNKING_STRATEGY_ID,
                    "boundary_aware_titled_splitter",
                    parameters
                )
            )
            logger.info(f"Created chunking strategy with ID {CHUNKING_STRATEGY_ID}")
            return True

    except Exception as e:
        logger.error(f"Error ensuring chunking strategy exists: {e}")
        return False


def ensure_chunktype_exists():
    """
    Ensure that the chunk type exists in the database.
    If not, create it.

    Returns:
        bool: True if chunk type exists or was created, False otherwise
    """
    try:
        with get_cursor(commit=True) as cursor:
            # Check if chunk type exists
            cursor.execute(
                "SELECT COUNT(*) FROM chunktypes WHERE id = %s",
                (CHUNKTYPE_ID,)
            )
            if cursor.fetchone()[0] > 0:
                logger.info(f"Chunk type with ID {CHUNKTYPE_ID} already exists")
                return True

            # Chunk type doesn't exist, create it
            logger.info(f"Creating chunk type with ID {CHUNKTYPE_ID}")

            cursor.execute(
                """
                INSERT INTO chunktypes (id, chunktype)
                VALUES (%s, %s)
                """,
                (CHUNKTYPE_ID, "abstract")
            )
            logger.info(f"Created chunk type with ID {CHUNKTYPE_ID}")
            return True

    except Exception as e:
        logger.error(f"Error ensuring chunk type exists: {e}")
        return False


def check_database_tables():
    """
    Check if the required database tables exist and have data.

    Returns:
        Dict with table counts
    """
    counts = {}

    try:
        with get_cursor() as cursor:
            # Check document table
            cursor.execute("SELECT COUNT(*) FROM document")
            counts['document'] = cursor.fetchone()[0]

            # Check chunks table
            cursor.execute("SELECT COUNT(*) FROM chunks")
            counts['chunks'] = cursor.fetchone()[0]

            # Check chunking_strategies table
            cursor.execute("SELECT COUNT(*) FROM chunking_strategies")
            counts['chunking_strategies'] = cursor.fetchone()[0]

            # Check chunktypes table
            cursor.execute("SELECT COUNT(*) FROM chunktypes")
            counts['chunktypes'] = cursor.fetchone()[0]

            logger.info(f"Database tables: {counts}")

    except Exception as e:
        logger.error(f"Error checking database tables: {e}")
        counts['error'] = str(e)

    return counts


def main(total_limit: int = 1000,
         batch_size: int = 100,
         check_only: bool = False,
         single_chunk_threshold: int = SINGLE_CHUNK_THRESHOLD,
         chunk_size: int = CHUNK_SIZE,
         overlap: int = OVERLAP,
         min_chunk_size: int = 100):
    """
    Main function to chunk abstracts.

    Args:
        total_limit: Maximum number of documents to process in total
        batch_size: Number of documents to process in each batch
        check_only: If True, only check database status without processing
        single_chunk_threshold: Maximum size for creating a single chunk
        chunk_size: Maximum size of each chunk for longer texts
        overlap: Overlap between chunks
        min_chunk_size: Minimum size of a chunk to be considered valid
    """
    logger.info(f"Starting abstract chunking with adaptive strategy:")
    logger.info(f"  - Single chunk threshold: {single_chunk_threshold} chars")
    logger.info(f"  - Chunk size for long texts: {chunk_size} chars")
    logger.info(f"  - Overlap: {overlap} chars")
    logger.info(f"  - Minimum chunk size: {min_chunk_size} chars")

    # Check database tables
    table_counts = check_database_tables()

    # If there's an error or no documents, exit
    if 'error' in table_counts:
        logger.error("Database check failed, exiting")
        return

    if table_counts.get('document', 0) == 0:
        logger.warning("No documents found in document table, exiting")
        return

    # Ensure chunking strategy and chunk type exist
    if not ensure_chunking_strategy_exists(single_chunk_threshold, min_chunk_size) or not ensure_chunktype_exists():
        logger.error("Failed to ensure chunking strategy or chunk type, exiting")
        return

    # If check_only, exit after diagnostics
    if check_only:
        logger.info("Check-only mode, exiting without processing")
        return

    # Initialize chunker
    chunker = AdaptiveTextChunker(
        single_chunk_threshold=single_chunk_threshold,
        max_chunk_size=chunk_size,
        overlap=overlap,
        min_chunk_size=min_chunk_size
    )

    # Process documents in batches
    processed_total = 0
    chunks_total = 0
    start_time = time.time()

    while processed_total < total_limit:
        # Get documents without chunks
        remaining = total_limit - processed_total
        current_batch_size = min(batch_size, remaining)
        documents = get_documents_without_chunks(limit=current_batch_size)

        if not documents:
            logger.info("No more documents to process")
            break

        # Process the batch
        batch_start_time = time.time()
        processed = process_documents(documents, chunker)
        batch_end_time = time.time()

        if processed == 0:
            logger.warning("Failed to process batch, stopping")
            break

        # Update counters and log progress
        processed_total += len(documents)
        chunks_total += processed
        batch_time = batch_end_time - batch_start_time
        logger.info(f"Processed batch of {len(documents)} documents in {batch_time:.2f}s " +
                   f"({len(documents)/batch_time:.2f} docs/s)")
        logger.info(f"Created {processed} chunks for {len(documents)} documents")
        logger.info(f"Total processed: {processed_total}/{total_limit}")

    # Log summary
    total_time = time.time() - start_time
    logger.info(f"Completed abstract chunking: {processed_total} documents in {total_time:.2f}s")
    logger.info(f"Created a total of {chunks_total} chunks")
    if processed_total > 0:
        logger.info(f"Average processing speed: {processed_total/total_time:.2f} docs/s")
        logger.info(f"Average chunks per document: {chunks_total/processed_total:.2f}")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Chunk abstracts for PubMedBERT embeddings")
    parser.add_argument("--limit", type=int, default=1000,
                        help="Maximum number of documents to process")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Number of documents to process in each batch")
    parser.add_argument("--check-only", action="store_true",
                        help="Only check database status without processing")
    parser.add_argument("--single-chunk-threshold", type=int, default=SINGLE_CHUNK_THRESHOLD,
                        help=f"Maximum size for creating a single chunk (default: {SINGLE_CHUNK_THRESHOLD})")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help=f"Size of each chunk for longer texts (default: {CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=OVERLAP,
                        help=f"Overlap between chunks in characters (default: {OVERLAP})")
    parser.add_argument("--min-chunk-size", type=int, default=100,
                        help="Minimum size of a chunk to be considered valid (default: 100)")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze abstract lengths in the database without chunking")
    args = parser.parse_args()

    # Load environment variables
    load_environment()

    # If analyze mode, analyze abstract lengths
    if args.analyze:
        try:
            with get_cursor() as cursor:
                # Get abstract length statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_abstracts,
                        MIN(LENGTH(abstract)) as min_length,
                        MAX(LENGTH(abstract)) as max_length,
                        AVG(LENGTH(abstract)) as avg_length,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LENGTH(abstract)) as median_length
                    FROM document
                    WHERE abstract IS NOT NULL
                """)
                stats = cursor.fetchone()

                logger.info("Abstract length statistics:")
                logger.info(f"  - Total abstracts: {stats['total_abstracts']}")
                logger.info(f"  - Min length: {stats['min_length']} chars")
                logger.info(f"  - Max length: {stats['max_length']} chars")
                logger.info(f"  - Average length: {stats['avg_length']:.2f} chars")
                logger.info(f"  - Median length: {stats['median_length']:.2f} chars")

                # Get distribution of abstract lengths
                cursor.execute("""
                    SELECT
                        CASE
                            WHEN LENGTH(abstract) <= 500 THEN '0-500'
                            WHEN LENGTH(abstract) <= 1000 THEN '501-1000'
                            WHEN LENGTH(abstract) <= 1500 THEN '1001-1500'
                            WHEN LENGTH(abstract) <= 2000 THEN '1501-2000'
                            WHEN LENGTH(abstract) <= 3000 THEN '2001-3000'
                            WHEN LENGTH(abstract) <= 5000 THEN '3001-5000'
                            WHEN LENGTH(abstract) <= 10000 THEN '5001-10000'
                            ELSE '10001+'
                        END as length_range,
                        COUNT(*) as count
                    FROM document
                    WHERE abstract IS NOT NULL
                    GROUP BY length_range
                    ORDER BY length_range
                """)

                logger.info("Abstract length distribution:")
                for row in cursor.fetchall():
                    logger.info(f"  - {row['length_range']} chars: {row['count']} abstracts")

        except Exception as e:
            logger.error(f"Error analyzing abstract lengths: {e}")

        exit(0)

    # Run the main function
    main(
        total_limit=args.limit,
        batch_size=args.batch_size,
        check_only=args.check_only,
        single_chunk_threshold=args.single_chunk_threshold,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        min_chunk_size=args.min_chunk_size
    )
