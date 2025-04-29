#!/usr/bin/env python3
"""
Adaptive Text Chunker

This module provides an adaptive text chunker that handles abstracts and other text
of different sizes efficiently, with proper sentence/paragraph boundaries.
"""

import logging
import time
import argparse
import json
from typing import List, Dict, Any, Tuple, Iterator, Optional

from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.db.chunker import Chunk as DBChunk
from localknowledge.textprocessing.chunking.base import Chunk, BaseChunker

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 384  # Size for PubMedBERT chunks when splitting is needed
OVERLAP = 128     # Overlap between chunks to maintain context
CHUNKING_STRATEGY_ID = 1  # ID of the adaptive_splitter strategy in the database
CHUNKTYPE_ID = 1  # ID for 'abstract' in the chunktypes table


class AdaptiveTextChunker(BaseChunker):
    """
    Adaptive text chunker for PubMedBERT that handles abstracts of different sizes efficiently.
    - Prepends document title to each chunk
    - Creates a single chunk for abstracts that fit within max_chunk_size
    - Chunks longer abstracts with proper sentence/paragraph boundaries
    """

    def __init__(self,
                 max_chunk_size: int = CHUNK_SIZE,
                 overlap: int = OVERLAP,
                 min_chunk_size: int = 100,
                 **kwargs):
        """
        Initialize the chunker.

        Args:
            max_chunk_size: Maximum size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size of a chunk to be considered valid
            **kwargs: Additional parameters passed to BaseChunker
        """
        super().__init__(**kwargs)
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Chunk]:
        """
        Split text into chunks adaptively based on length, with title prepended if available.

        Args:
            text: The text to chunk
            metadata: Dictionary with contextual information about the text (e.g., title)
            **kwargs: Additional parameters (can override chunk_size and overlap)

        Returns:
            List of Chunk objects
        """
        if not text or len(text.strip()) == 0:
            return []

        # Initialize metadata if None
        if metadata is None:
            metadata = {}

        # Override parameters if provided
        max_chunk_size = kwargs.get('max_chunk_size', self.max_chunk_size)
        overlap = kwargs.get('overlap', self.overlap)
        min_chunk_size = kwargs.get('min_chunk_size', self.min_chunk_size)

        # Get title from metadata if available
        title = metadata.get('title', '')

        # Format title with tags if available
        formatted_title = f"<title>{title}</title>\n" if title else ""
        title_length = len(formatted_title)

        # Adjust max chunk size to account for title
        effective_max_size = max_chunk_size - title_length

        # For short texts, create a single chunk
        if len(text) <= max_chunk_size:
            chunk_text = formatted_title + text.strip()
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_number': 0,
                'start_char': 0,
                'end_char': len(text),
                'char_length': len(chunk_text),
                'is_complete_text': True,
                'title_included': bool(title)
            })
            return [Chunk(text=chunk_text, metadata=chunk_metadata)]

        # For longer texts, chunk with sentence boundaries
        logger.info(f"Chunking long text with {len(text)} characters")
        raw_chunks = self._chunk_with_boundaries(text, title, formatted_title, effective_max_size)

        # Convert to Chunk objects
        chunks = []
        for i, (chunk_text, chunk_metadata) in enumerate(raw_chunks):
            # Create a copy of the base metadata and enhance it with chunk-specific info
            combined_metadata = metadata.copy()
            combined_metadata.update(chunk_metadata)
            combined_metadata['chunk_number'] = i

            chunks.append(Chunk(text=chunk_text, metadata=combined_metadata))

        return chunks

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
        sentence_markers = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
        sentence_end = -1

        for marker in sentence_markers:
            pos = text.rfind(marker, start, end)
            if pos > sentence_end:
                sentence_end = pos

        # If found a valid sentence end, include the period
        if sentence_end > start:
            return sentence_end + 1

        # If no sentence boundary, look for paragraph breaks
        paragraph_markers = ['\n\n', '\r\n\r\n']
        paragraph_end = -1

        for marker in paragraph_markers:
            pos = text.rfind(marker, start, end)
            if pos > paragraph_end:
                paragraph_end = pos

        if paragraph_end > start:
            return paragraph_end + 2  # Include the newline

        return end

    def chunk_text(self, text: str, title: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Legacy method for backward compatibility.
        Uses the new chunk method internally.

        Args:
            text: The text to chunk
            title: The document title to prepend to each chunk

        Returns:
            List of tuples (chunk_text, metadata)
        """
        # Create metadata with title
        metadata = {'title': title}

        # Use the new chunk method
        chunks = self.chunk(text, metadata=metadata)

        # Convert Chunk objects back to tuples for backward compatibility
        result = []
        for chunk in chunks:
            result.append((chunk.text, chunk.metadata))

        return result

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
        # Limit the search to a reasonable window before the position
        # This prevents inefficient searches in very long texts
        search_start = max(0, position - 200)  # Look back at most 200 chars

        # Look backwards for end of previous sentence
        sentence_markers = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
        prev_end = -1

        for marker in sentence_markers:
            pos = text.rfind(marker, search_start, position)
            if pos > prev_end:
                prev_end = pos

        # If found, start after that sentence
        if prev_end > 0:
            # Skip the period and any whitespace
            start = prev_end + 1
            while start < end and start < len(text) and text[start].isspace():
                start += 1
            return start

        # Look for paragraph breaks within a limited window
        paragraph_markers = ['\n\n', '\r\n\r\n']
        paragraph_start = -1

        for marker in paragraph_markers:
            pos = text.rfind(marker, search_start, position)
            if pos > paragraph_start:
                paragraph_start = pos

        if paragraph_start > 0:
            # Skip the newlines
            start = paragraph_start + 2
            while start < end and start < len(text) and text[start].isspace():
                start += 1
            return start

        # If no sentence or paragraph boundary found, just use the position
        return position

    def _chunk_with_boundaries(self, text: str, _: str, formatted_title: str,
                              effective_max_size: int) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Split text into chunks with proper sentence/paragraph boundaries.

        Args:
            text: The text to chunk
            _: The document title (unused, kept for API consistency)
            formatted_title: The formatted title with tags
            effective_max_size: Maximum size of chunk content (excluding title)

        Returns:
            List of tuples (chunk_text, metadata)
        """
        logger.debug(f"Starting _chunk_with_boundaries: text length={len(text)}, effective_max_size={effective_max_size}")

        # For very short texts, just return a single chunk
        if len(text) <= effective_max_size:
            logger.debug("Text fits in a single chunk, returning immediately")
            chunk_content = text.strip()
            full_chunk = formatted_title + chunk_content
            metadata = {
                'chunk_number': 0,
                'start_char': 0,
                'end_char': len(text),
                'char_length': len(full_chunk),
                'is_complete_text': True,
                'title_included': bool(formatted_title),
                'chunk_type': 'text'
            }
            return [(full_chunk, metadata)]

        # Split text into sentences first
        sentences = []
        current_pos = 0

        # Simple sentence splitting - not perfect but good enough for this purpose
        while current_pos < len(text):
            # Find the next sentence end
            next_end = -1
            for marker in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                pos = text.find(marker, current_pos)
                if pos != -1 and (next_end == -1 or pos < next_end):
                    next_end = pos + 1  # Include the period

            # If no sentence end found, take the rest of the text
            if next_end == -1:
                sentences.append(text[current_pos:])
                break
            else:
                # Add one more character to include the space after the period
                end_pos = min(next_end + 1, len(text))
                sentences.append(text[current_pos:end_pos])
                current_pos = end_pos

        # Now group sentences into chunks
        chunks = []
        current_chunk = ""
        chunk_start = 0
        chunk_number = 0

        for sentence in sentences:
            # If adding this sentence would exceed the max size, create a new chunk
            if len(current_chunk) + len(sentence) > effective_max_size and current_chunk:
                # Create metadata for the current chunk
                chunk_end = chunk_start + len(current_chunk)
                full_chunk = formatted_title + current_chunk

                metadata = {
                    'chunk_number': chunk_number,
                    'start_char': chunk_start,
                    'end_char': chunk_end,
                    'char_length': len(full_chunk),
                    'is_complete_text': False,
                    'title_included': bool(formatted_title),
                    'chunk_type': 'text'
                }

                # Add the chunk
                chunks.append((full_chunk, metadata))
                chunk_number += 1

                # Start a new chunk with overlap
                overlap_start = max(0, chunk_end - self.overlap)

                # Find a good sentence start in the overlap region
                current_chunk = sentence
                chunk_start = text.find(sentence, overlap_start)
            else:
                # Add the sentence to the current chunk
                current_chunk += sentence
                if not current_chunk.strip():
                    chunk_start = text.find(sentence)

        # Add the last chunk if there's anything left
        if current_chunk.strip():
            chunk_end = chunk_start + len(current_chunk)
            full_chunk = formatted_title + current_chunk

            metadata = {
                'chunk_number': chunk_number,
                'start_char': chunk_start,
                'end_char': chunk_end,
                'char_length': len(full_chunk),
                'is_complete_text': False,
                'title_included': bool(formatted_title),
                'chunk_type': 'text'
            }

            chunks.append((full_chunk, metadata))

        # Special case: if we couldn't split into sentences properly, fall back to a simpler approach
        if not chunks:
            # Just split the text into chunks of effective_max_size
            for i in range(0, len(text), effective_max_size):
                chunk_start = i
                chunk_end = min(i + effective_max_size, len(text))
                chunk_content = text[chunk_start:chunk_end].strip()

                if chunk_content:
                    full_chunk = formatted_title + chunk_content
                    metadata = {
                        'chunk_number': i // effective_max_size,
                        'start_char': chunk_start,
                        'end_char': chunk_end,
                        'char_length': len(full_chunk),
                        'is_complete_text': (i == 0 and chunk_end == len(text)),
                        'title_included': bool(formatted_title),
                        'chunk_type': 'text'
                    }
                    chunks.append((full_chunk, metadata))

        logger.debug(f"Created {len(chunks)} chunks")
        return chunks


def get_documents_without_chunks(limit: int = 100) -> Iterator[Dict[str, Any]]:
    """
    Get documents that don't have chunks in the chunks table.

    Args:
        limit: Maximum number of documents to retrieve

    Returns:
        Iterator of document dictionaries
    """
    try:
        with get_cursor() as cursor:
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

            # Count for logging
            count = 0

            # Yield each document as it's fetched
            for document in cursor:
                count += 1
                yield document

            logger.info(f"Found {count} documents without chunks")

    except Exception as e:
        logger.error(f"Error getting documents without chunks: {e}")
        # Generator should not return anything else in case of error


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


def process_documents(documents: Iterator[Dict[str, Any]], chunker: AdaptiveTextChunker) -> Tuple[int, int]:
    """
    Process documents and create chunks.

    Args:
        documents: Iterator of document dictionaries
        chunker: Text chunker instance

    Returns:
        Tuple of (number of chunks created, number of documents processed)
    """
    chunks_data = []
    single_chunks = 0
    multi_chunks = 0
    doc_count = 0

    # We'll use the ChunkingDatabaseManager through the Chunk class

    for doc in documents:
        doc_count += 1
        # Skip documents without abstracts
        if not doc['abstract'] or len(doc['abstract'].strip()) == 0:
            continue

        # Chunk the abstract with title
        abstract_length = len(doc['abstract'])

        # Create metadata with title
        metadata = {
            'title': doc['title'],
            'source': 'abstract',
            'document_id': doc['id']
        }

        # Use the new chunk method
        chunks = chunker.chunk(doc['abstract'], metadata=metadata)

        # Track chunking statistics
        if len(chunks) == 1 and chunks[0].metadata.get('is_complete_text', False):
            single_chunks += 1
        else:
            multi_chunks += 1
            logger.info(f"Document {doc['id']} with {abstract_length} chars split into {len(chunks)} chunks")

        # Convert to database chunks and prepare for insertion
        for i, chunk in enumerate(chunks):
            # Convert to database chunk
            db_chunk = chunk.to_db_chunk(
                document_id=doc['id'],
                chunking_strategy_id=CHUNKING_STRATEGY_ID,
                chunktype_id=CHUNKTYPE_ID,
                document_title=doc['title'],
                chunk_no=i
            )

            # Add to chunks data for batch insertion
            chunks_data.append((
                db_chunk.document_id,           # document_id
                db_chunk.chunking_strategy_id,  # chunking_strategy_id
                db_chunk.chunktype_id,          # chunktype_id
                db_chunk.document_title,        # document_title
                db_chunk.text,                  # text
                db_chunk.chunklength,           # chunklength
                db_chunk.chunk_no,              # chunk_no
                json.dumps(db_chunk.metadata)   # metadata as JSON string
            ))

    # Log chunking statistics
    if doc_count == 0:
        logger.info("No documents to process")
        return 0, 0

    if single_chunks > 0 or multi_chunks > 0:
        logger.info(f"Chunking statistics: {single_chunks} single chunks, {multi_chunks} multi-chunk documents")

    # Insert chunks into database
    chunks_inserted = 0
    if chunks_data:
        chunks_inserted = insert_chunks(chunks_data)

    return chunks_inserted, doc_count


def ensure_chunking_strategy_exists(chunk_size: int = CHUNK_SIZE,
                              min_chunk_size: int = 100):
    """
    Ensure that the chunking strategy exists in the database.
    If not, create it.

    Args:
        chunk_size: Maximum size of each chunk in characters
        min_chunk_size: Minimum size of a chunk to be considered valid

    Returns:
        bool: True if strategy exists or was created, False otherwise
    """
    try:
        # Create parameters as JSON string
        parameters = json.dumps({
            "chunk_size": chunk_size,
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
         chunk_size: int = CHUNK_SIZE,
         overlap: int = OVERLAP,
         min_chunk_size: int = 100):
    """
    Main function to chunk abstracts.

    Args:
        total_limit: Maximum number of documents to process in total
        batch_size: Number of documents to process in each batch
        check_only: If True, only check database status without processing
        chunk_size: Maximum size of each chunk in characters
        overlap: Overlap between chunks
        min_chunk_size: Minimum size of a chunk to be considered valid
    """
    logger.info(f"Starting abstract chunking with adaptive strategy:")
    logger.info(f"  - Chunk size: {chunk_size} chars")
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
    if not ensure_chunking_strategy_exists(chunk_size, min_chunk_size) or not ensure_chunktype_exists():
        logger.error("Failed to ensure chunking strategy or chunk type, exiting")
        return

    # If check_only, exit after diagnostics
    if check_only:
        logger.info("Check-only mode, exiting without processing")
        return

    # Initialize chunker with BaseChunker interface
    chunker = AdaptiveTextChunker(
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

        # Get iterator for documents without chunks
        documents_iterator = get_documents_without_chunks(limit=current_batch_size)

        # Process the batch
        batch_start_time = time.time()
        chunks_processed, docs_processed = process_documents(documents_iterator, chunker)
        batch_end_time = time.time()

        # If no documents were processed, we're done
        if docs_processed == 0:
            logger.warning("No documents processed in this batch, stopping")
            break

        # Update counters and log progress
        processed_total += docs_processed
        chunks_total += chunks_processed
        batch_time = batch_end_time - batch_start_time

        # Log progress
        if batch_time > 0:
            logger.info(f"Processed batch of {docs_processed} documents in {batch_time:.2f}s " +
                       f"({docs_processed/batch_time:.2f} docs/s)")
        else:
            logger.info(f"Processed batch of {docs_processed} documents")

        logger.info(f"Created {chunks_processed} chunks in this batch")
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
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help=f"Maximum size of each chunk in characters (default: {CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=OVERLAP,
                        help=f"Overlap between chunks in characters (default: {OVERLAP})")
    parser.add_argument("--min-chunk-size", type=int, default=100,
                        help="Minimum size of a chunk to be considered valid (default: 100)")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze abstract lengths in the database without chunking")
    parser.add_argument("--log-level", type=str, default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level")
    args = parser.parse_args()

    # Load environment variables
    load_environment()

    # Set logging level based on argument
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    logger.info(f"Log level set to {args.log_level}")

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
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        min_chunk_size=args.min_chunk_size
    )
