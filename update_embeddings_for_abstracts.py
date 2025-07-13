#!/usr/bin/env python3
"""
Update abstract embeddings for documents without embeddings.

This module creates embeddings for abstracts in the document table that don't have
embeddings yet, using either Ollama API or PubMedBERT. It shows progress with tqdm and
handles errors gracefully.

Performance optimizations:
- Uses connection pooling for database operations
- Processes embeddings in batches for better database performance
- Monitors performance metrics to identify bottlenecks
- Implements memory management to prevent memory leaks and segmentation faults
- Supports configurable batch sizes and worker counts
"""

import argparse
import logging
from typing import List, Dict, Any, Optional, Tuple
import sys
import concurrent.futures
import time
import statistics
import gc
import os
import psutil
# from concurrent.futures import TimeoutError as FuturesTimeoutError  # Unused import
import threading

import tqdm
# import ollama  # Unused import
import backoff

from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkingDatabaseManager
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder
from localknowledge.db.connection_pool import initialize_pool, get_cursor, close_pool, get_pool_status, get_raw_connection, put_raw_connection
# Use Python's built-in TimeoutError

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and higher levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence httpx (used by ollama) INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)


class AbstractEmbeddingUpdater:
    """Class for updating abstract embeddings for chunks without embeddings."""
    def __init__(self, embedder=None, model_name: str = "snowflake-arctic-embed2:latest",
                 db_timeout: int = 120, max_batch_size: int = 100, memory_limit_percent: float = 80.0,
                 device: Optional[str] = None):
        """
        Initialize the abstract embedding updater.

        Args:
            embedder: Embedder class to use (OllamaEmbedder or PubMedBERTEmbedder)
            model_name: Name of the model to use
            db_timeout: Database query timeout in seconds
            max_batch_size: Maximum batch size for embedding to prevent memory issues
            memory_limit_percent: Memory usage limit as percentage of total system memory
            device: Device to use for computation (None for auto-detection)
        """
        # Don't initialize connection pool here - let main() handle it with proper arguments
        # This ensures we use the command-line specified connection counts
        logger.info("Database connection pool initialized or reused")

        self.embeddings_db = get_embeddings_db()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkingDatabaseManager()

        # Initialize embedder with memory-saving parameters
        if embedder is None:
            embedder = OllamaEmbedder

        if embedder == PubMedBERTEmbedder:
            self.embedder = embedder(model_name)
        else:
            self.embedder = embedder(model_name)

        # Create multiple embedder instances for concurrent processing
        self.embedders = [embedder(model_name) for _ in range(4)]

        self.model_name = model_name
        self.vectorsize = self.embedder.get_vectorsize()
        self.db_timeout = db_timeout
        self.max_batch_size = max_batch_size
        self.memory_limit_percent = memory_limit_percent

        # Make sure we have a table for this vector size - this guarantees the table exists
        self.tablename = self.embeddings_db.ensure_table_for_vectorsize(self.vectorsize)
        logger.info(f"Using embedding table: {self.tablename}")

        # Get the model ID
        self.model_id = self.embeddings_db.get_model_id(model_name)
        if self.model_id == -1:
            logger.warning(f"Model {model_name} not found in embedding_models table. Embeddings will not be stored.")

        # Ensure we have the necessary indices for efficient queries
        self.ensure_indices()

        # Performance metrics
        self.embedding_times = []
        self.db_times = []
        self.memory_usage = []

        # Log initial memory usage (force log at INFO level)
        self.log_memory_usage(force_log=True)

    def ensure_indices(self):
        """Ensure that necessary indices exist for efficient queries.
        This is only called once during initialization.
        Since ensure_table_for_vectorsize() was already called, we know the table exists.
        """
        # Create indices if they don't exist
        try:
            # Create all indices in a single transaction for better performance
            indices_queries = []

            # Index for the embedding table
            indices_queries.append(f"""
            CREATE INDEX IF NOT EXISTS {self.tablename}_chunk_model_idx
            ON {self.tablename} (chunk_id, model_id)
            """)

            # Index for the chunks table to speed up chunktype filtering
            indices_queries.append("""
            CREATE INDEX IF NOT EXISTS chunks_chunktype_id_idx
            ON chunks (chunktype_id)
            """)

            # Index for the chunks table to speed up document_id filtering
            indices_queries.append("""
            CREATE INDEX IF NOT EXISTS chunks_document_id_idx
            ON chunks (document_id)
            """)

            # Execute all index creation queries in a single transaction
            with get_cursor(commit=True) as cursor:
                for query in indices_queries:
                    cursor.execute(query)

            logger.info(f"All necessary indices created or verified successfully")

        except Exception as e:
            logger.warning(f"Error creating indices: {e}")

    def count_chunks_without_embeddings(self) -> int:
        """Count chunks without embeddings using an optimized approach.

        Returns:
            Number of chunks without embeddings
        """
        # Use a more efficient approach: get chunktype_id first to avoid join
        try:
            # First get the chunktype_id for 'abstract'
            chunktype_query = "SELECT id FROM chunktypes WHERE chunktype = 'abstract'"
            chunktype_result = self.embeddings_db.execute(chunktype_query, (), timeout=30)
            if not chunktype_result:
                logger.error("Could not find chunktype 'abstract'")
                return 0

            chunktype_id = chunktype_result[0]['id']

            # Use LEFT JOIN instead of NOT EXISTS for better performance
            query = f"""
            SELECT COUNT(*) as count
            FROM chunks c
            LEFT JOIN {self.tablename} e ON c.id = e.chunk_id AND e.model_id = %s
            WHERE c.chunktype_id = %s
            AND e.chunk_id IS NULL
            """
            params = (self.model_id, chunktype_id)

            result = self.embeddings_db.execute(query, params, timeout=self.db_timeout)
            count = result[0]['count'] if result else 0
            return count

        except TimeoutError:
            logger.warning("Count query timed out. Using an estimate instead.")
            # Try a simpler approach with sampling
            try:
                # Get the chunktype_id for 'abstract'
                chunktype_query = "SELECT id FROM chunktypes WHERE chunktype = 'abstract'"
                chunktype_result = self.embeddings_db.execute(chunktype_query, (), timeout=max(10, self.db_timeout // 4))
                if not chunktype_result:
                    return 1000000  # Large estimate

                chunktype_id = chunktype_result[0]['id']

                # Get total abstract chunks count (should be fast with index)
                total_query = "SELECT COUNT(*) as count FROM chunks WHERE chunktype_id = %s"
                total_result = self.embeddings_db.execute(total_query, (chunktype_id,), timeout=max(30, self.db_timeout // 2))
                total_count = total_result[0]['count'] if total_result else 0

                # Return 90% of total as an estimate (assuming most need embedding)
                return int(total_count * 0.9)
            except Exception:
                # If that fails too, return a large number
                return 1000000  # Just a large number to indicate there's work to do

    def get_unembedded_chunks_cursor(self):
        """Get a server-side cursor for efficiently iterating through unembedded chunks.

        This executes the expensive query only once and returns a cursor that can be used
        to fetch batches of results efficiently.

        Returns:
            Tuple of (connection, cursor) - caller is responsible for closing both
        """
        # Cache the chunktype_id to avoid repeated lookups
        if not hasattr(self, '_abstract_chunktype_id'):
            try:
                chunktype_query = "SELECT id FROM chunktypes WHERE chunktype = 'abstract'"
                chunktype_result = self.embeddings_db.execute(chunktype_query, (), timeout=max(30, self.db_timeout // 2))
                if not chunktype_result:
                    logger.error("Could not find chunktype 'abstract'")
                    raise ValueError("Could not find chunktype 'abstract'")
                self._abstract_chunktype_id = chunktype_result[0]['id']
            except Exception as e:
                logger.error(f"Error getting chunktype_id: {e}")
                raise

        # Use LEFT JOIN instead of NOT EXISTS for better performance
        # Also avoid the chunktypes join by using the cached chunktype_id
        # No need to JOIN with document table since chunks already contain document_title
        # and abstract chunks contain the abstract text in c.text
        query = f"""
        SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
               c.text, c.chunktype_id, c.document_title
        FROM chunks c
        LEFT JOIN {self.tablename} e ON c.id = e.chunk_id AND e.model_id = %s
        WHERE c.chunktype_id = %s
        AND e.chunk_id IS NULL
        ORDER BY c.id
        """

        params = (self.model_id, self._abstract_chunktype_id)

        # Get a raw connection from the pool and create a named cursor for server-side processing
        conn = get_raw_connection()
        cursor = conn.cursor(name='unembedded_chunks_cursor')
        cursor.itersize = 100  # Fetch 100 rows at a time from server

        try:
            cursor.execute(query, params)
            logger.info("Executed query for unembedded chunks using server-side cursor")
            return conn, cursor
        except Exception as e:
            cursor.close()
            put_raw_connection(conn)
            logger.error(f"Error executing cursor query: {e}")
            raise

    def update_abstract_embeddings(self, limit: Optional[int] = None, batch_size: int = 50, workers: int = 4,
                              dry_run: bool = False, show_progress: bool = True) -> int:
        """Update abstract embeddings for chunks without embeddings.

        Args:
            limit: Maximum number of chunks to process
            batch_size: Number of chunks to process in each batch (default: 50)
            workers: Number of worker threads to use for parallel processing
            dry_run: If True, don't actually modify the database
            show_progress: If True, show the progress bar (default: True)

        Returns:
            Number of chunks successfully processed
        """
        total_processed = 0
        total_to_process = self.count_chunks_without_embeddings()
        start_time = time.time()
        batch_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        # Track overall progress metrics
        overall_start_time = time.time()

        # Use a smaller batch size for PubMedBERT to prevent memory issues
        if isinstance(self.embedder, PubMedBERTEmbedder):
            original_workers = workers
            workers = min(workers, 4)  # Limit to 4 workers for PubMedBERT
            if workers < original_workers:
                logger.info(f"Adjusted workers from {original_workers} to {workers} for PubMedBERT")

        if limit:
            total_to_process = min(total_to_process, limit)

        # Get cursor for streaming results (executes expensive query only once)
        logger.info("Executing query for unembedded chunks using server-side cursor...")
        conn, cursor = self.get_unembedded_chunks_cursor()

        # Create a progress bar with additional metrics
        with tqdm.tqdm(total=total_to_process, desc=self.model_name[:20], disable=not show_progress) as pbar:
            # Create a separate thread to update the progress bar continuously
            stop_event = threading.Event()

            def update_timer():
                while not stop_event.is_set():
                    # Refresh the display without updating progress
                    pbar.refresh()
                    time.sleep(2.0)  # Update every 2 seconds to reduce overhead

            # Start the timer thread
            timer_thread = threading.Thread(target=update_timer, daemon=True)
            timer_thread.start()

            try:
                while True:
                    try:
                        # Only check memory occasionally to maintain performance
                        if batch_count % 20 == 0:  # Check every 20 batches to reduce overhead
                            if not self.check_memory_usage():
                                # If memory usage is too high, try to free some memory
                                self.cleanup_memory()

                                # If still too high after cleanup, reduce batch size
                                if not self.check_memory_usage() and batch_size > 10:
                                    new_batch_size = max(10, batch_size // 2)
                                    logger.warning(f"Memory usage high. Reducing batch size from {batch_size} to {new_batch_size}")
                                    batch_size = new_batch_size

                        # Get a batch of chunks using the server-side cursor
                        batch = cursor.fetchmany(batch_size)
                        if not batch:
                            logger.info("No more chunks to process")
                            break

                        # Convert batch tuples to dictionaries for compatibility
                        chunks = []
                        for row in batch:
                            chunks.append({
                                'id': row[0],
                                'document_id': row[1],
                                'chunk_no': row[2],
                                'page_start': row[3],
                                'page_end': row[4],
                                'text': row[5],
                                'chunktype_id': row[6],
                                'document_title': row[7]
                            })

                        # Reset consecutive errors counter on successful query
                        consecutive_errors = 0

                        batch_count += 1
                        #batch_start_time = time.time()

                        # Process chunks in parallel to create embeddings
                        embedding_data = []

                        # Use a fixed worker count for consistent performance
                        current_workers = workers

                        # Track chunks that were successfully processed and stored
                        batch_processed = 0
                        batch_stored = 0

                        with concurrent.futures.ThreadPoolExecutor(max_workers=current_workers) as executor:
                            # Submit all chunks for processing with chunk info and worker ID attached
                            future_to_chunk = {}
                            for i, chunk in enumerate(chunks):
                                worker_id = i % current_workers
                                future_to_chunk[executor.submit(self.process_chunk, chunk, dry_run, worker_id)] = chunk

                            # Collect results as they complete
                            for future in concurrent.futures.as_completed(future_to_chunk):
                                chunk = future_to_chunk[future]
                                try:
                                    success, _, embedding = future.result()  # Ignore message

                                    if success and embedding:
                                        # Add to batch for database insertion
                                        embedding_data.append({
                                            'chunk_id': chunk['id'],
                                            'embedding': embedding
                                        })

                                    batch_processed += 1

                                    # Update progress bar less frequently to reduce overhead
                                    # Only update every 25% of batch or every 10 items, whichever is larger
                                    update_interval = max(10, len(chunks) // 4)
                                    if batch_processed % update_interval == 0:
                                        elapsed_total = time.time() - overall_start_time
                                        current_rate = total_processed / elapsed_total if elapsed_total > 0 else 0
                                        pbar.set_postfix({
                                            'stored/s': f'{current_rate:.2f}',
                                            'batch': batch_count,
                                            'processing': f'{batch_processed}/{len(chunks)}',
                                            'elapsed': f'{elapsed_total:.1f}s'
                                        })
                                        pbar.refresh()

                                except Exception as e:
                                    logger.error(f"Error processing chunk {chunk['id']}: {e}")
                                    batch_processed += 1  # Count failed chunks too for progress tracking

                        # Store all embeddings in a single batch operation for optimal performance
                        if embedding_data and not dry_run:
                            batch_stored = self.store_embeddings_batch(embedding_data, dry_run)
                            total_processed += batch_stored
                        elif dry_run:
                            # In dry run mode, count all successful embeddings
                            batch_stored = len(embedding_data)
                            total_processed += batch_stored

                        # Update progress bar with the number of chunks actually stored/processed successfully
                        # This makes the progress bar consistent with the final count
                        pbar.update(batch_stored)
                        
                        # Calculate and update overall rate
                        elapsed_total = time.time() - overall_start_time
                        overall_rate = total_processed / elapsed_total if elapsed_total > 0 else 0

                        # Update progress bar with detailed metrics
                        pbar.set_postfix({
                            'stored/s': f'{overall_rate:.2f}',
                            'batch': batch_count,
                            'stored': f'{batch_stored}/{len(chunks)}',
                            'elapsed': f'{elapsed_total:.1f}s'
                        })

                        # Don't update offset since successfully processed chunks are removed from the result set
                        # The next query will automatically get the next batch of unprocessed chunks
                        # offset += len(chunks)  # REMOVED: This was causing chunks to be skipped
                        if limit and total_processed >= limit:
                            logger.info(f"Reached processing limit of {limit} chunks")
                            break

                        # Only do garbage collection occasionally to maintain performance
                        if batch_count % 10 == 0:  # Every 10 batches
                            self.cleanup_memory()

                    except TimeoutError as e:
                        consecutive_errors += 1
                        logger.warning(f"Timeout error in batch {batch_count}: {e}")

                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping processing.")
                            break

                        # Try with a smaller batch size
                        new_batch_size = max(1, batch_size // 2)
                        logger.info(f"Reducing batch size from {batch_size} to {new_batch_size}")
                        batch_size = new_batch_size

                        # Don't update offset, retry with same offset but smaller batch

                        # Force garbage collection after error
                        self.cleanup_memory()

                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"Error in batch {batch_count}: {e}")

                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping processing.")
                            break

                        # Don't update offset on error - let the next iteration try the same chunks again
                        # offset += batch_size  # REMOVED: This could skip chunks that failed to process

                        # Force garbage collection after error
                        self.cleanup_memory()

            finally:
                # Stop the timer thread
                stop_event.set()
                timer_thread.join(timeout=1.0)  # Wait for thread to finish

                # Always clean up cursor and connection
                try:
                    cursor.close()
                    put_raw_connection(conn)
                    logger.debug("Cursor and connection cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning up cursor/connection: {e}")

        # Calculate and display overall statistics
        total_time = time.time() - start_time
        avg_time_per_item = total_time / total_processed if total_processed > 0 else 0

        # Calculate average embedding and database times
        if self.embedding_times:
            avg_embedding_time = sum(self.embedding_times) / len(self.embedding_times)
            median_embedding_time = statistics.median(self.embedding_times)
        else:
            avg_embedding_time = 0
            median_embedding_time = 0

        if self.db_times:
            avg_db_time = sum(self.db_times) / len(self.db_times)
            median_db_time = statistics.median(self.db_times)
        else:
            avg_db_time = 0
            median_db_time = 0

        logger.info(f"Total processing time: {total_time:.2f}s for {total_processed} items")
        logger.info(f"Average time per item: {avg_time_per_item:.4f}s")
        logger.info(f"Embedding time (avg/median): {avg_embedding_time:.4f}s / {median_embedding_time:.4f}s")
        logger.info(f"Database time (avg/median): {avg_db_time:.4f}s / {median_db_time:.4f}s")

        return total_processed

    def get_sample_chunks(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get a small sample of chunks for dry run testing.

        Args:
            limit: Maximum number of chunks to retrieve

        Returns:
            List of sample chunks
        """
        try:
            conn, cursor = self.get_unembedded_chunks_cursor()
            try:
                batch = cursor.fetchmany(limit)
                chunks = []
                for row in batch:
                    chunks.append({
                        'id': row[0],
                        'document_id': row[1],
                        'chunk_no': row[2],
                        'page_start': row[3],
                        'page_end': row[4],
                        'text': row[5],
                        'chunktype_id': row[6],
                        'document_title': row[7]
                    })
                return chunks
            finally:
                cursor.close()
                put_raw_connection(conn)
        except Exception as e:
            logger.error(f"Error getting sample chunks: {e}")
            return []

    def process_chunk(self, chunk: Dict[str, Any], dry_run: bool = False, worker_id: int = 0) -> Tuple[bool, str, List[float]]:
        """Process a single chunk to create its embedding.

        Args:
            chunk: Chunk data including id, text, document_id, etc.
            dry_run: If True, don't actually modify the database
            worker_id: ID of the worker thread for selecting embedder instance

        Returns:
            Tuple of (success, message, embedding)
        """
        chunk_id = chunk['id']
        document_id = chunk['document_id']
        text = chunk.get('text', '')
        # Get document title (for logging purposes if needed)
        _ = chunk.get('document_title', '')

        # For abstract chunks, the text should already contain the abstract content
        # No need to fallback to separate abstract field

        # Skip if text is still empty
        if not text or text.strip() == '':
            return False, f"Skipping chunk {chunk_id} (document {document_id}) with empty text", []

        # Skip if model_id is not valid
        if self.model_id == -1:
            return False, f"Skipping chunk {chunk_id} (document {document_id}) - model not found in database", []

        try:
            # Measure embedding time
            start_time = time.time()

            # Create embedding using worker-specific embedder - this will raise an exception if it fails
            embedding = self.create_embedding(text, worker_id)

            # Record embedding time
            embedding_time = time.time() - start_time
            self.embedding_times.append(embedding_time)

            if dry_run:
                # In dry run mode, just log what would happen
                logger.info(f"DRY RUN: Would add embedding for chunk {chunk_id} (document {document_id})")
                return True, f"DRY RUN: Would add embedding for chunk {chunk_id} (document {document_id})", embedding

            return True, f"Created embedding for chunk {chunk_id} (document {document_id})", embedding

        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id} (document {document_id}): {e}")
            return False, f"Error: {str(e)}", []



    def store_embeddings_batch(self, embedding_data: List[Dict[str, Any]], dry_run: bool = False) -> int:
        """Store a batch of embeddings in the database.

        Args:
            embedding_data: List of dictionaries with chunk_id, embedding
            dry_run: If True, don't actually modify the database

        Returns:
            Number of embeddings successfully stored
        """
        if dry_run:
            logger.info(f"DRY RUN: Would store {len(embedding_data)} embeddings")
            return len(embedding_data)

        if not embedding_data:
            return 0

        # Measure database operation time
        start_time = time.time()

        try:
            # Use the connection pool to get a cursor
            with get_cursor(commit=True) as cursor:
                # Prepare the query with ON CONFLICT for upsert
                upsert_query = f"""
                INSERT INTO {self.tablename} (chunk_id, model_id, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (chunk_id, model_id) DO UPDATE
                SET embedding = EXCLUDED.embedding
                """

                # Prepare all the data for batch execution
                batch_data = [(item['chunk_id'], self.model_id, item['embedding']) for item in embedding_data]

                try:
                    # Execute the query for all embeddings in a single batch
                    cursor.executemany(upsert_query, batch_data)

                    # Record database operation time
                    db_time = time.time() - start_time
                    self.db_times.append(db_time)

                    # Return the number of items we attempted to store
                    return len(embedding_data)
                except Exception as e:
                    logger.error(f"Error in batch embedding storage: {e}")
                    # Record database operation time even for failures
                    db_time = time.time() - start_time
                    self.db_times.append(db_time)
                    return 0

        except Exception as e:
            logger.error(f"Error in batch embedding storage: {e}")
            db_time = time.time() - start_time
            self.db_times.append(db_time)
            return 0

    def log_memory_usage(self, force_log=False):
        """
        Log current memory usage.

        Args:
            force_log: If True, log at INFO level regardless of threshold
                      If False, only log at DEBUG level unless memory usage is high
        """
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Convert to MB for easier reading
            rss_mb = memory_info.rss / (1024 * 1024)

            # Store memory usage for tracking (but limit the size to avoid memory growth)
            if len(self.memory_usage) > 100:
                self.memory_usage = self.memory_usage[-50:]
            self.memory_usage.append(memory_percent)

            # Only log at WARNING level if memory usage is high
            # This ensures it will show up but won't interrupt the progress bar too much
            if memory_percent > self.memory_limit_percent * 0.8:
                logger.warning(f"High memory usage: {rss_mb:.2f} MB ({memory_percent:.2f}%)")
            elif force_log:
                # Use DEBUG level for normal logging to avoid cluttering the output
                logger.debug(f"Memory usage: {rss_mb:.2f} MB ({memory_percent:.2f}%)")

            return memory_percent
        except Exception as e:
            logger.warning(f"Error getting memory usage: {e}")
            return 0.0

    def check_memory_usage(self) -> bool:
        """
        Check if memory usage is below the limit.

        Returns:
            True if memory usage is OK, False if it's too high
        """
        try:
            # Only check memory every 10 calls to reduce performance impact
            if not hasattr(self, '_memory_check_counter'):
                self._memory_check_counter = 0

            self._memory_check_counter += 1
            if self._memory_check_counter % 10 != 0:
                return True  # Skip most checks to improve performance

            # Check memory usage without forcing logs
            memory_percent = self.log_memory_usage(force_log=False)
            if memory_percent > self.memory_limit_percent:
                logger.warning(f"Memory usage too high: {memory_percent:.2f}% > {self.memory_limit_percent:.2f}%")
                return False
            return True
        except Exception as e:
            logger.warning(f"Error checking memory usage: {e}")
            return True  # Assume it's OK if we can't check

    def cleanup_memory(self):
        """Force garbage collection to free memory."""
        try:
            # Only do full garbage collection when memory is high
            # This is a performance optimization
            if hasattr(self, '_memory_check_counter') and self._memory_check_counter % 20 == 0:
                # Force garbage collection
                collected = gc.collect()
                logger.debug(f"Garbage collection: collected {collected} objects")
        except Exception as e:
            logger.warning(f"Error during memory cleanup: {e}")

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str, worker_id: int = 0) -> List[float]:
        """Create an embedding for the given text.

        Args:
            text: Text to embed
            worker_id: ID of the worker thread for selecting embedder instance

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Use the worker-specific embedder to create the embedding for better concurrency
            # No memory check here to maintain performance
            embedder = self.embedders[worker_id % len(self.embedders)]
            embedding = embedder.embed(text)

            if not embedding or len(embedding) == 0:
                logger.error("Embedding creation failed - empty result")
                raise ValueError("Embedding creation failed - empty result")

            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise


def main():
    """Main function to update abstract embeddings."""
    parser = argparse.ArgumentParser(description='Update abstract embeddings for documents without embeddings.')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of documents to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of documents to process in each batch (default: 50)')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads to use for parallel processing')
    parser.add_argument('--model', type=str, default="snowflake-arctic-embed2:latest", help='Name of the embedding model to use')
    parser.add_argument('--embedder', type=str, default="ollama", choices=["ollama", "pubmedbert"], help='Type of embedder to use')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without modifying the database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information about each document processed')
    parser.add_argument('--min-connections', type=int, default=2, help='Minimum number of database connections in the pool')
    parser.add_argument('--max-connections', type=int, default=10, help='Maximum number of database connections in the pool')
    parser.add_argument('--no-progress', action='store_true', help='Hide progress bar and only show batch information')
    parser.add_argument('--timeout', type=int, default=120, help='Database query timeout in seconds (default: 120)')
    parser.add_argument('--optimize-query', action='store_true', help='Use optimized query strategy (default: True)')
    parser.add_argument('--no-optimize-query', action='store_false', dest='optimize_query', help='Disable optimized query strategy')
    parser.add_argument('--max-batch-size', type=int, default=100, help='Maximum batch size for embedding to prevent memory issues (default: 32)')
    parser.add_argument('--memory-limit', type=float, default=80.0, help='Memory usage limit as percentage of total system memory (default: 80.0)')
    parser.add_argument('--device', type=str, default=None, choices=['cpu', 'cuda', 'mps'], help='Device to use for computation (default: auto-detect)')
    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.embeddings").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.base").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.INFO)
        logging.getLogger("localknowledge.db.connection_pool").setLevel(logging.INFO)
    else:
        # Silence INFO logs from various modules
        logging.getLogger("localknowledge.db.embeddings").setLevel(logging.WARNING)
        logging.getLogger("localknowledge.db.base").setLevel(logging.WARNING)
        logging.getLogger("localknowledge.db.basic_infrastructure").setLevel(logging.WARNING)
        logging.getLogger("localknowledge.db.connection_pool").setLevel(logging.WARNING)

    # Initialize the connection pool
    try:
        # Close any existing pool first to ensure we use the new settings
        close_pool()
        initialize_pool(min_connections=args.min_connections, max_connections=args.max_connections)
        logger.info(f"Connection pool initialized with {args.min_connections}-{args.max_connections} connections")
        print(f"Connection pool: {args.min_connections}-{args.max_connections} connections")
    except Exception as e:
        logger.error(f"Error initializing connection pool: {e}")
        sys.exit(1)

    try:
        # Define default models for each embedder type
        default_models = {
            "ollama": "snowflake-arctic-embed2:latest",
            "pubmedbert": "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
        }

        # Choose the embedder based on the argument
        if args.embedder == "ollama":
            embedder_class = OllamaEmbedder
            # Use default model if none specified or if using the default from command line
            model_name = args.model
        elif args.embedder == "pubmedbert":
            embedder_class = PubMedBERTEmbedder
            # Use default model if none specified or if using the default from command line
            if args.model == "snowflake-arctic-embed2:latest":  # This is the default from argparse
                model_name = default_models["pubmedbert"]
            else:
                model_name = args.model
        else:
            logger.error(f"Unknown embedder type: {args.embedder}")
            sys.exit(1)

        print(f"Using embedder: {args.embedder}")
        print(f"Using model: {model_name}")
        print(f"Using batch size: {args.batch_size}")
        print(f"Using {args.workers} worker threads")
        print(f"Using connection pool with {args.min_connections}-{args.max_connections} connections")

        # Create the updater with memory management parameters
        updater = AbstractEmbeddingUpdater(
            embedder=embedder_class,
            model_name=model_name,
            db_timeout=args.timeout,
            max_batch_size=args.max_batch_size,
            memory_limit_percent=args.memory_limit,
            device=args.device
        )
        print(f"Model ID: {updater.model_id}")
        print(f"Vector size: {updater.vectorsize}")
        print(f"Table name: {updater.tablename}")
        print(f"Database query timeout: {updater.db_timeout} seconds")

        # Show connection pool status
        pool_status = get_pool_status()
        print(f"Connection pool status: {pool_status}")

        # Count chunks without embeddings
        count = updater.count_chunks_without_embeddings()
        print(f"Found {count} chunks without embeddings")

        if count == 0:
            print("No chunks to process")
            return

        if args.dry_run:
            print("Performing dry run - no database modifications will be made")
            # Get a sample of chunks to process
            sample_size = min(5, count)
            chunks = updater.get_sample_chunks(limit=sample_size)

            print(f"\nSample of {len(chunks)} chunks that would be processed:")
            for chunk in chunks:
                chunk_id = chunk['id']
                document_id = chunk['document_id']
                document_title = chunk.get('document_title', 'No title')
                text = chunk.get('text', '')
                # For abstract chunks, text should already contain the abstract content
                text_length = len(text) if text else 0

                print(f"\nChunk ID: {chunk_id}")
                print(f"Document ID: {document_id}")
                print(f"Document Title: {document_title}")
                print(f"Text length: {text_length} characters")

                # Create embedding for demonstration
                if text_length > 0:
                    try:
                        embedding = updater.create_embedding(text)
                        print(f"Successfully created embedding with {len(embedding)} dimensions")

                        # Show a sample of the embedding vector
                        if len(embedding) > 0:
                            sample = embedding[:3] + ['.....'] + embedding[-3:]
                            print(f"Embedding sample: {sample}")
                    except Exception as e:
                        print(f"Error creating embedding: {e}")

            print("\nDry run completed. No changes were made to the database.")
        else:
            # Process chunks
            processed = updater.update_abstract_embeddings(
                limit=args.limit,
                batch_size=args.batch_size,
                workers=args.workers,
                dry_run=args.dry_run,
                show_progress=not args.no_progress
            )

            print(f"Successfully processed {processed} chunks")
    finally:
        # Always close the connection pool
        close_pool()
        logger.info("Connection pool closed")


if __name__ == "__main__":
    print("Embedder V0.3 - with threded timer")
    main()
