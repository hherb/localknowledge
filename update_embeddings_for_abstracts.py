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
from concurrent.futures import TimeoutError as FuturesTimeoutError
import threading

import tqdm
import ollama
import backoff

from localknowledge.db.embeddings import get_embeddings_db
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk
from localknowledge.embeddings import OllamaEmbedder, PubMedBERTEmbedder
from localknowledge.db.connection_pool import initialize_pool, get_cursor, close_pool
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
    def __init__(self, embedder=OllamaEmbedder, model_name: str = "snowflake-arctic-embed2:latest",
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
        # Initialize connection pool if not already initialized
        initialize_pool(min_connections=2, max_connections=10)
        logger.info("Database connection pool initialized or reused")

        self.embeddings_db = get_embeddings_db()
        self.document_db = DocumentDatabaseManager()
        self.chunker_db = ChunkingDatabaseManager()

        # Initialize embedder with memory-saving parameters
        if embedder == PubMedBERTEmbedder:
            self.embedder = embedder(model_name, device=device, max_batch_size=max_batch_size)
        else:
            self.embedder = embedder(model_name)

        self.model_name = model_name
        self.vectorsize = self.embedder.get_vectorsize()
        self.db_timeout = db_timeout
        self.max_batch_size = max_batch_size
        self.memory_limit_percent = memory_limit_percent

        # Make sure we have a table for this vector size
        self.embeddings_db.ensure_table_for_vectorsize(self.vectorsize)
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
        """
        tablename = self.embeddings_db.get_tablename_for_vectorsize(self.vectorsize)

        # Check if the table exists
        check_table_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
        """
        table_exists = self.embeddings_db.execute(check_table_query, (tablename,))

        if not table_exists or not table_exists[0]['exists']:
            logger.info(f"Table '{tablename}' doesn't exist yet, skipping index creation")
            return

        # Create indices if they don't exist
        try:
            # Create all indices in a single transaction for better performance
            indices_queries = []

            # Index for the embedding table
            indices_queries.append(f"""
            CREATE INDEX IF NOT EXISTS {tablename}_chunk_model_idx
            ON {tablename} (chunk_id, model_id)
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
        """Count chunks without embeddings.

        Returns:
            Number of chunks without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_id = self.model_id
        tablename = self.embeddings_db.get_tablename_for_vectorsize(vector_size)

        # Use the cached table existence check
        if not hasattr(self, '_table_exists_cache'):
            check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
            """
            table_exists_result = self.embeddings_db.execute(check_table_query, (tablename,))
            self._table_exists_cache = table_exists_result[0]['exists'] if table_exists_result else False

        if not self._table_exists_cache:
            # If the table doesn't exist, all chunks need embeddings
            logger.info(f"Table '{tablename}' doesn't exist, counting all abstract chunks")
            query = """
            SELECT COUNT(*) as count
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE ct.chunktype = 'abstract'
            """
            params = []
        else:
            # Use a more efficient approach with NOT EXISTS
            # For counting, we can use an even more optimized query with LIMIT 1
            query = f"""
            SELECT COUNT(*) as count
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            WHERE ct.chunktype = 'abstract'
            AND NOT EXISTS (
                SELECT 1 FROM {tablename} e
                WHERE e.chunk_id = c.id AND e.model_id = %s
                LIMIT 1
            )
            """
            params = [model_id]

        try:
            # Use the instance's db_timeout value
            result = self.embeddings_db.execute(query, params, timeout=self.db_timeout)
            count = result[0]['count'] if result else 0
            return count
        except TimeoutError:
            logger.warning("Count query timed out. Using an estimate instead.")
            # Instead of returning a fixed large number, try to get an approximate count
            # by sampling a small portion of the data
            try:
                # Get the total number of abstract chunks
                total_query = """
                SELECT COUNT(*) as count
                FROM chunks c
                JOIN chunktypes ct ON c.chunktype_id = ct.id
                WHERE ct.chunktype = 'abstract'
                """
                total_result = self.embeddings_db.execute(total_query, timeout=30)
                total_count = total_result[0]['count'] if total_result else 0

                # Return 90% of total as an estimate (assuming most need embedding)
                return int(total_count * 0.9)
            except Exception:
                # If that fails too, return a large number
                return 1000000  # Just a large number to indicate there's work to do

    def get_chunks_without_embeddings(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Get chunks without embeddings.

        Args:
            limit: Maximum number of chunks to retrieve
            offset: Number of chunks to skip

        Returns:
            List of chunks without embeddings
        """
        vector_size = self.embedder.get_vectorsize()
        model_id = self.model_id
        tablename = self.embeddings_db.get_tablename_for_vectorsize(vector_size)

        # We only check if the table exists once during initialization
        # and cache the result for better performance
        if not hasattr(self, '_table_exists_cache'):
            check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
            """
            table_exists_result = self.embeddings_db.execute(check_table_query, (tablename,))
            self._table_exists_cache = table_exists_result[0]['exists'] if table_exists_result else False

        if not self._table_exists_cache:
            # If the table doesn't exist, all chunks need embeddings
            query = """
            SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
                   c.text, c.chunktype_id, d.title as document_title, d.abstract
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            JOIN document d ON c.document_id = d.id
            WHERE ct.chunktype = 'abstract'
            ORDER BY c.id
            """
            params = []
        else:
            # Use a more efficient approach with NOT EXISTS and select only needed columns
            query = f"""
            SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
                   c.text, c.chunktype_id, d.title as document_title, d.abstract
            FROM chunks c
            JOIN chunktypes ct ON c.chunktype_id = ct.id
            JOIN document d ON c.document_id = d.id
            WHERE ct.chunktype = 'abstract'
            AND NOT EXISTS (
                SELECT 1 FROM {tablename} e
                WHERE e.chunk_id = c.id AND e.model_id = %s
            )
            ORDER BY c.id
            """
            params = [model_id]

        # Add OFFSET and LIMIT clauses
        if offset > 0:
            query += f" OFFSET {offset}"

        if limit:
            query += f" LIMIT {limit}"

        # Use the instance's db_timeout value for this query
        try:
            chunks = self.embeddings_db.execute(query, params, timeout=self.db_timeout)
            logger.debug(f"Found {len(chunks)} abstract chunks without embeddings (offset: {offset}, limit: {limit})")
            return chunks or []
        except TimeoutError:
            # If it times out, try a more aggressive approach with a smaller batch
            logger.warning(f"Query timed out. Trying with a smaller batch size.")
            if limit and limit > 20:
                smaller_limit = max(20, limit // 2)  # Don't go below 20 for performance
                chunks = self.get_chunks_without_embeddings(limit=smaller_limit, offset=offset)
                return chunks or []
            else:
                # If we're already using a small limit, just return an empty list
                logger.error("Query timed out even with small batch size.")
                return []

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

        # Create a progress bar with additional metrics
        with tqdm.tqdm(total=total_to_process, desc=self.model_name[:20], disable=not show_progress) as pbar:
            offset = 0
            # Create a separate thread to update the progress bar continuously
            stop_event = threading.Event()
            
            def update_timer():
                while not stop_event.is_set():
                    # Refresh the display without updating progress
                    pbar.refresh()
                    time.sleep(0.5)  # Update every half second
                    
            # Start the timer thread
            timer_thread = threading.Thread(target=update_timer, daemon=True)
            timer_thread.start()
            
            try:
                while True:
                    try:
                        # Only check memory occasionally to maintain performance
                        if batch_count % 5 == 0:  # Check every 5 batches
                            if not self.check_memory_usage():
                                # If memory usage is too high, try to free some memory
                                self.cleanup_memory()

                                # If still too high after cleanup, reduce batch size
                                if not self.check_memory_usage() and batch_size > 10:
                                    new_batch_size = max(10, batch_size // 2)
                                    logger.warning(f"Memory usage high. Reducing batch size from {batch_size} to {new_batch_size}")
                                    batch_size = new_batch_size

                        # Get a batch of chunks
                        chunks = self.get_chunks_without_embeddings(limit=batch_size, offset=offset)
                        if not chunks:
                            logger.info("No more chunks to process")
                            break

                        # Reset consecutive errors counter on successful query
                        consecutive_errors = 0

                        batch_count += 1
                        #batch_start_time = time.time()

                        # Process chunks in parallel to create embeddings
                        embedding_data = []

                        # Use a fixed worker count for consistent performance
                        current_workers = workers

                        # Don't update progress bar during processing - we'll update it after the whole batch
                        batch_processed = 0
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=current_workers) as executor:
                            # Submit all chunks for processing
                            futures = [executor.submit(self.process_chunk, chunk, dry_run) for chunk in chunks]

                            # Collect results as they complete
                            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                                try:
                                    success, _, embedding = future.result()  # Ignore message

                                    if success and embedding:
                                        # Add to batch for database insertion
                                        embedding_data.append({
                                            'chunk_id': chunks[i]['id'],
                                            'embedding': embedding
                                        })
                                
                                    batch_processed += 1
                                except Exception as e:
                                    logger.error(f"Error processing chunk: {e}")

                        # Store all embeddings in a single batch operation
                        if embedding_data and not dry_run:
                            success_count = self.store_embeddings_batch(embedding_data, dry_run)
                            total_processed += success_count
                        elif dry_run:
                            # In dry run mode, count all successful embeddings
                            total_processed += len(embedding_data)
                        
                        # Now update the progress bar for the whole batch at once
                        pbar.update(batch_processed)
                        
                        # Calculate and update overall rate
                        elapsed_total = time.time() - overall_start_time
                        overall_rate = total_processed / elapsed_total if elapsed_total > 0 else 0
                        
                        # Update progress bar with overall rate
                        pbar.set_postfix({
                            'chunks/s': f'{overall_rate:.2f}',
                            'batch': batch_count,
                            'elapsed': f'{elapsed_total:.1f}s'
                        })

                        # Update offset for next batch
                        offset += len(chunks)  # Use actual number of chunks processed
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

                        # Skip this batch and continue with the next one
                        offset += batch_size

                        # Force garbage collection after error
                        self.cleanup_memory()

            finally:
                # Stop the timer thread
                stop_event.set()
                timer_thread.join(timeout=1.0)  # Wait for thread to finish

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

    def process_chunk(self, chunk: Dict[str, Any], dry_run: bool = False) -> Tuple[bool, str, List[float]]:
        """Process a single chunk to create its embedding.

        Args:
            chunk: Chunk data including id, text, document_id, etc.
            dry_run: If True, don't actually modify the database

        Returns:
            Tuple of (success, message, embedding)
        """
        chunk_id = chunk['id']
        document_id = chunk['document_id']
        text = chunk.get('text', '')
        # Get document title (for logging purposes if needed)
        _ = chunk.get('document_title', '')

        # If text is empty, try to use the abstract from the document
        if not text or text.strip() == '':
            text = chunk.get('abstract', '')

        # Skip if text is still empty
        if not text or text.strip() == '':
            return False, f"Skipping chunk {chunk_id} (document {document_id}) with empty text", []

        # Skip if model_id is not valid
        if self.model_id == -1:
            return False, f"Skipping chunk {chunk_id} (document {document_id}) - model not found in database", []

        try:
            # Measure embedding time
            start_time = time.time()

            # Create embedding - this will raise an exception if it fails
            embedding = self.create_embedding(text)

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
                # Get the table name for this vector size
                tablename = self.embeddings_db.get_tablename_for_vectorsize(self.vectorsize)

                # Prepare the query with ON CONFLICT for upsert
                upsert_query = f"""
                INSERT INTO {tablename} (chunk_id, model_id, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (chunk_id, model_id) DO UPDATE
                SET embedding = EXCLUDED.embedding
                """

                # Prepare all the data for batch execution
                batch_data = [(item['chunk_id'], self.model_id, item['embedding']) for item in embedding_data]

                try:
                    # Execute the query for all embeddings in a single batch
                    cursor.executemany(upsert_query, batch_data)
                    success_count = cursor.rowcount

                    # Record database operation time
                    db_time = time.time() - start_time
                    self.db_times.append(db_time)

                    logger.debug(f"Stored {success_count}/{len(embedding_data)} embeddings in {db_time:.3f}s")
                    return success_count
                except Exception as e:
                    logger.error(f"Error in batch embedding storage: {e}")

                    # Fall back to individual inserts if batch fails
                    logger.warning("Falling back to individual inserts")
                    success_count = 0

                    # Individual upsert query with RETURNING
                    individual_query = f"""
                    INSERT INTO {tablename} (chunk_id, model_id, embedding)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chunk_id, model_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding
                    RETURNING id
                    """

                    for item in embedding_data:
                        chunk_id = item['chunk_id']
                        embedding = item['embedding']

                        try:
                            cursor.execute(individual_query, (chunk_id, self.model_id, embedding))
                            result = cursor.fetchone()
                            if result and result['id']:
                                success_count += 1
                        except Exception as inner_e:
                            logger.error(f"Error storing embedding for chunk {chunk_id}: {inner_e}")

                    # Record database operation time
                    db_time = time.time() - start_time
                    self.db_times.append(db_time)

                    logger.debug(f"Stored {success_count}/{len(embedding_data)} embeddings individually in {db_time:.3f}s")
                    return success_count

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
    def create_embedding(self, text: str) -> List[float]:
        """Create an embedding for the given text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Use the embedder to create the embedding
            # No memory check here to maintain performance
            embedding = self.embedder.embed(text)

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
        initialize_pool(min_connections=args.min_connections, max_connections=args.max_connections)
        logger.info(f"Connection pool initialized with {args.min_connections}-{args.max_connections} connections")
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
        print(f"Table name: {updater.embeddings_db.get_tablename_for_vectorsize(updater.vectorsize)}")
        print(f"Database query timeout: {updater.db_timeout} seconds")

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
            chunks = updater.get_chunks_without_embeddings(limit=sample_size)

            print(f"\nSample of {len(chunks)} chunks that would be processed:")
            for chunk in chunks:
                chunk_id = chunk['id']
                document_id = chunk['document_id']
                document_title = chunk.get('document_title', 'No title')
                text = chunk.get('text', '')
                if not text:
                    text = chunk.get('abstract', '')
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
