#!/usr/bin/env python3
"""
High-performance multi-threaded embedding processor for chunks using Ollama and PostgreSQL.
Optimized with concurrent processing, connection pooling, and efficient batching.
"""

import logging
import time
import sys
import threading
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import queue

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
import ollama
import os
from tqdm import tqdm

# Silence httpx (used by ollama) INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("ollama").setLevel(logging.WARNING)

__version__ = 0.4

@dataclass
class EmbeddingConfig:
    """Configuration for embedding processing"""
    chunktype_id: int
    chunking_strategy_id: int
    model_id: int
    embedding_table: str = "emb_snowflake"
    embedding_dim: int = 1024
    batch_size: int = 50
    ollama_model: str = "snowflake-arctic-embed2:latest"
    max_retries: int = 3
    retry_delay: float = 1.0
    # New optimization parameters
    num_workers: int = 4  # Number of concurrent embedding workers
    db_pool_size: int = 8  # Database connection pool size
    prefetch_batches: int = 3  # Number of batches to prefetch
    use_concurrent_embeddings: bool = True  # Enable concurrent embedding generation


class BatchQueue:
    """Thread-safe queue for managing batches between producer and consumers"""
    
    def __init__(self, maxsize: int = 0):
        self.queue = Queue(maxsize=maxsize)
        self._finished = threading.Event()
    
    def put(self, item, block=True, timeout=None):
        return self.queue.put(item, block, timeout)
    
    def get(self, block=True, timeout=None):
        return self.queue.get(block, timeout)
    
    def task_done(self):
        return self.queue.task_done()
    
    def empty(self):
        return self.queue.empty()
    
    def qsize(self):
        return self.queue.qsize()
    
    def mark_finished(self):
        """Signal that no more items will be added"""
        self._finished.set()
    
    def is_finished(self):
        """Check if producer is finished and queue is empty"""
        return self._finished.is_set() and self.queue.empty()


class OptimizedEmbeddingProcessor:
    """High-performance multi-threaded embedding processor"""
    
    def __init__(self, db_config: Dict[str, Any], embedding_config: EmbeddingConfig):
        self.db_config = db_config
        self.config = embedding_config
        self.logger = self._setup_logging()
        
        # Initialize larger connection pool for concurrent operations
        self.pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=self.config.db_pool_size,
            **db_config
        )
        
        self.logger.info("Ensuring embedding table exists...")
        self.ensure_embedding_table_exists()
        
        # Initialize multiple Ollama clients for concurrent processing
        self.ollama_clients = [ollama.Client() for _ in range(self.config.num_workers)]
        
        # Threading coordination
        self.batch_queue = BatchQueue(maxsize=self.config.prefetch_batches)
        self.results_queue = Queue()
        self.stats_lock = threading.Lock()
        self.processed_count = 0
        
    def _setup_logging(self) -> logging.Logger:
        """Configure logging with thread safety"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(threadName)-10s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('embedding_processor.log')
            ]
        )
        
        return logging.getLogger(__name__)
    
    def ensure_embedding_table_exists(self) -> None:
        """Check if embedding table exists, create it if not, and ensure proper indexes"""
        table_name = self.config.embedding_table
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Check if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        );
                    """, (table_name,))
                    
                    table_exists = cur.fetchone()[0]
                    
                    if not table_exists:
                        self.logger.info(f"Creating embedding table: {table_name}")
                        
                        # Create table inheriting from embedding_base
                        create_table_sql = f"""
                        CREATE TABLE public.{table_name} (
                            embedding public.vector({self.config.embedding_dim})
                        ) INHERITS (public.embedding_base);
                        """
                        cur.execute(create_table_sql)
                        
                        # Create indexes for performance
                        self.logger.info(f"Creating indexes for table: {table_name}")
                        
                        # Primary key index on id (inherited from embedding_base)
                        cur.execute(f"""
                            ALTER TABLE public.{table_name} 
                            ADD CONSTRAINT {table_name}_pkey PRIMARY KEY (id);
                        """)
                        
                        # Composite index on (chunk_id, model_id) for efficient lookups
                        cur.execute(f"""
                            CREATE INDEX idx_{table_name}_chunk_model 
                            ON public.{table_name} (chunk_id, model_id);
                        """)
                        
                        # Index on chunk_id for joins
                        cur.execute(f"""
                            CREATE INDEX idx_{table_name}_chunk_id 
                            ON public.{table_name} (chunk_id);
                        """)
                        
                        # Index on model_id for filtering
                        cur.execute(f"""
                            CREATE INDEX idx_{table_name}_model_id 
                            ON public.{table_name} (model_id);
                        """)
                        
                        conn.commit()
                        self.logger.info(f"Successfully created table {table_name} with indexes")
                        
                    else:
                        self.logger.info(f"Embedding table {table_name} already exists")
                        self._ensure_indexes_exist(cur, table_name)
                        conn.commit()
                        
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Failed to create/verify embedding table: {e}")
                    raise
    
    def _ensure_indexes_exist(self, cursor, table_name: str) -> None:
        """Ensure all necessary indexes exist on the embedding table"""
        
        indexes_to_check = [
            (f"idx_{table_name}_chunk_model", f"ON public.{table_name} (chunk_id, model_id)"),
            (f"idx_{table_name}_chunk_id", f"ON public.{table_name} (chunk_id)"),
            (f"idx_{table_name}_model_id", f"ON public.{table_name} (model_id)")
        ]
        
        for index_name, index_def in indexes_to_check:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_class c 
                    JOIN pg_namespace n ON n.oid = c.relnamespace 
                    WHERE c.relname = %s AND n.nspname = 'public'
                );
            """, (index_name,))
            
            if not cursor.fetchone()[0]:
                self.logger.info(f"Creating missing index: {index_name}")
                cursor.execute(f"CREATE INDEX {index_name} {index_def};")
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def get_unembedded_chunks_count(self) -> int:
        """Get count of chunks that haven't been embedded yet"""
        query = f"""
        SELECT COUNT(*)
        FROM public.chunks c
        LEFT JOIN public.{self.config.embedding_table} e ON c.id = e.chunk_id AND e.model_id = %s
        WHERE c.chunktype_id = %s 
          AND c.chunking_strategy_id = %s
          AND e.chunk_id IS NULL
        """
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    self.config.model_id,
                    self.config.chunktype_id,
                    self.config.chunking_strategy_id
                ))
                return cur.fetchone()[0]
    
    def batch_producer(self, max_chunks: Optional[int] = None) -> None:
        """Producer thread that fetches batches of chunks and queues them for processing"""
        query = f"""
        SELECT c.id, c.text
        FROM public.chunks c
        LEFT JOIN public.{self.config.embedding_table} e ON c.id = e.chunk_id AND e.model_id = %s
        WHERE c.chunktype_id = %s 
          AND c.chunking_strategy_id = %s
          AND e.chunk_id IS NULL
        ORDER BY c.id
        """
        
        conn = None
        cursor = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor(name='batch_producer_cursor')
            cursor.itersize = self.config.batch_size * 2  # Fetch more rows per round-trip
            
            cursor.execute(query, (
                self.config.model_id,
                self.config.chunktype_id,
                self.config.chunking_strategy_id
            ))
            
            fetched_count = 0
            while True:
                batch = cursor.fetchmany(self.config.batch_size)
                if not batch:
                    break
                
                # Respect max_chunks limit
                if max_chunks and fetched_count + len(batch) > max_chunks:
                    batch = batch[:max_chunks - fetched_count]
                
                # Put batch in queue (this will block if queue is full)
                self.batch_queue.put(batch)
                fetched_count += len(batch)
                
                if max_chunks and fetched_count >= max_chunks:
                    break
            
        except Exception as e:
            self.logger.error(f"Batch producer failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.pool.putconn(conn)
            
            # Signal that no more batches will be produced
            self.batch_queue.mark_finished()
            self.logger.info(f"Batch producer finished. Queued {fetched_count} chunks for processing.")
    
    def generate_embeddings_concurrent(self, texts: List[str], client_id: int) -> List[List[float]]:
        """Generate embeddings for a batch of texts using assigned Ollama client"""
        client = self.ollama_clients[client_id % len(self.ollama_clients)]
        embeddings = []
        
        if self.config.use_concurrent_embeddings and len(texts) > 1:
            # Process multiple texts concurrently within the batch
            with ThreadPoolExecutor(max_workers=min(4, len(texts))) as executor:
                future_to_idx = {
                    executor.submit(self._generate_single_embedding, text, client): idx
                    for idx, text in enumerate(texts)
                }
                
                # Initialize embeddings list with correct size
                embeddings = [None] * len(texts)
                
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        embeddings[idx] = future.result()
                    except Exception as e:
                        self.logger.error(f"Failed to generate embedding for text at index {idx}: {e}")
                        raise
        else:
            # Sequential processing for smaller batches
            for text in texts:
                embedding = self._generate_single_embedding(text, client)
                embeddings.append(embedding)
        
        return embeddings
    
    def _generate_single_embedding(self, text: str, client: ollama.Client) -> List[float]:
        """Generate embedding for a single text with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                response = client.embeddings(
                    model=self.config.ollama_model,
                    prompt=text
                )
                return response['embedding']
                
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    self.logger.error(f"Failed to generate embedding after {self.config.max_retries} attempts: {e}")
                    raise
                time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
    
    def store_embeddings_batch(self, chunk_embeddings: List[Tuple[int, List[float]]]) -> None:
        """Store embeddings in the database with optimized batch insert"""
        if not chunk_embeddings:
            return
        
        insert_query = f"""
        INSERT INTO public.{self.config.embedding_table} (chunk_id, model_id, embedding)
        VALUES %s
        """
        
        # Prepare data for batch insert
        values = [
            (chunk_id, self.config.model_id, embedding)
            for chunk_id, embedding in chunk_embeddings
        ]
        
        with self.get_db_connection() as conn:
            try:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_values(
                        cur, insert_query, values,
                        template=None, 
                        page_size=min(1000, len(values))  # Optimize page size
                    )
                conn.commit()
                
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to store {len(chunk_embeddings)} embeddings: {e}")
                raise
    
    def embedding_worker(self, worker_id: int, pbar: tqdm) -> None:
        """Worker thread that processes batches from the queue"""
        processed_batches = 0
        
        try:
            while True:
                try:
                    # Get batch from queue with timeout
                    batch = self.batch_queue.get(timeout=5.0)
                except Empty:
                    # Check if producer is finished and queue is empty
                    if self.batch_queue.is_finished():
                        break
                    continue
                
                try:
                    # Process the batch
                    chunk_ids = [chunk[0] for chunk in batch]
                    texts = [chunk[1] for chunk in batch]
                    
                    # Generate embeddings
                    start_time = time.time()
                    embeddings = self.generate_embeddings_concurrent(texts, worker_id)
                    embedding_time = time.time() - start_time
                    
                    # Store embeddings
                    chunk_embeddings = list(zip(chunk_ids, embeddings))
                    self.store_embeddings_batch(chunk_embeddings)
                    
                    # Update progress
                    with self.stats_lock:
                        self.processed_count += len(batch)
                        pbar.update(len(batch))
                        
                        # Update progress bar with performance info
                        if len(batch) > 0:
                            avg_time_per_chunk = embedding_time / len(batch)
                            pbar.set_postfix({
                                f'worker-{worker_id}': f'{avg_time_per_chunk:.3f}s/chunk',
                                'queue': self.batch_queue.qsize()
                            })
                    
                    processed_batches += 1
                    
                except Exception as e:
                    self.logger.error(f"Worker {worker_id} failed to process batch: {e}")
                finally:
                    self.batch_queue.task_done()
                    
        except Exception as e:
            self.logger.error(f"Worker {worker_id} encountered fatal error: {e}")
        finally:
            self.logger.info(f"Worker {worker_id} finished after processing {processed_batches} batches")
    
    def run(self, max_chunks: Optional[int] = None) -> None:
        """Main processing loop with multi-threading"""
        self.logger.info(f"Starting optimized embedding processor (version {__version__})")
        self.logger.info(f"Config: chunktype_id={self.config.chunktype_id}, "
                        f"chunking_strategy_id={self.config.chunking_strategy_id}, "
                        f"model_id={self.config.model_id}, "
                        f"embedding_table={self.config.embedding_table}, "
                        f"batch_size={self.config.batch_size}, "
                        f"num_workers={self.config.num_workers}")
        
        try:
            # Test Ollama connections
            for i, client in enumerate(self.ollama_clients):
                client.list()
            self.logger.info(f"All {len(self.ollama_clients)} Ollama clients connected successfully")
            
            # Get total count for progress tracking
            total_count = self.get_unembedded_chunks_count()
            
            if max_chunks:
                total_count = min(total_count, max_chunks)
            
            self.logger.info(f"Found {total_count} chunks to process")
            
            if total_count == 0:
                self.logger.info("No chunks to process. Exiting.")
                return
            
            start_time = time.time()
            
            # Create progress bar
            with tqdm(total=total_count, desc="Embedding chunks", unit="chunk") as pbar:
                # Start producer thread
                producer_thread = threading.Thread(
                    target=self.batch_producer,
                    args=(max_chunks,),
                    name="BatchProducer"
                )
                producer_thread.start()
                
                # Start worker threads
                worker_threads = []
                for i in range(self.config.num_workers):
                    thread = threading.Thread(
                        target=self.embedding_worker,
                        args=(i, pbar),
                        name=f"EmbeddingWorker-{i}"
                    )
                    thread.start()
                    worker_threads.append(thread)
                
                # Wait for producer to finish
                producer_thread.join()
                self.logger.info("Batch producer completed")
                
                # Wait for all workers to finish
                for thread in worker_threads:
                    thread.join()
                
                # Final statistics
                total_time = time.time() - start_time
                avg_rate = self.processed_count / total_time if total_time > 0 else 0
                
                self.logger.info(f"Processing completed: {self.processed_count}/{total_count} chunks "
                               f"in {total_time:.2f}s (avg: {avg_rate:.2f} chunks/sec)")
                
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise
        
        finally:
            if hasattr(self, 'pool'):
                self.pool.closeall()
    
    def get_progress_stats(self) -> Dict[str, int]:
        """Get current progress statistics"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Total chunks matching criteria
                cur.execute("""
                    SELECT COUNT(*) FROM public.chunks 
                    WHERE chunktype_id = %s AND chunking_strategy_id = %s
                """, (self.config.chunktype_id, self.config.chunking_strategy_id))
                total_chunks = cur.fetchone()[0]
                
                # Already embedded chunks
                cur.execute(f"""
                    SELECT COUNT(*) FROM public.chunks c
                    JOIN public.{self.config.embedding_table} e ON c.id = e.chunk_id
                    WHERE c.chunktype_id = %s 
                      AND c.chunking_strategy_id = %s 
                      AND e.model_id = %s
                """, (self.config.chunktype_id, self.config.chunking_strategy_id, self.config.model_id))
                embedded_chunks = cur.fetchone()[0]
                
                return {
                    'total_chunks': total_chunks,
                    'embedded_chunks': embedded_chunks,
                    'remaining_chunks': total_chunks - embedded_chunks,
                    'progress_percent': (embedded_chunks / total_chunks * 100) if total_chunks > 0 else 0
                }


def main():
    from dotenv import load_dotenv
    import argparse
    """Main entry point with enhanced argument parsing"""
    print(f"Starting optimized embedding processor (version {__version__})")
    parser = argparse.ArgumentParser(description="High-performance multi-threaded embedding processor")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Number of chunks to process in each batch (default: 50)")
    parser.add_argument("--num-workers", type=int, default=4,
                        help="Number of concurrent embedding workers (default: 4)")
    parser.add_argument("--db-pool-size", type=int, default=8,
                        help="Database connection pool size (default: 8)")
    parser.add_argument("--prefetch-batches", type=int, default=3,
                        help="Number of batches to prefetch (default: 3)")
    parser.add_argument("--max-chunks", type=int, default=None,
                        help="Maximum number of chunks to process (for testing)")
    parser.add_argument("--disable-concurrent-embeddings", action="store_true",
                        help="Disable concurrent embedding generation within batches")
    
    args = parser.parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Database configuration from environment variables
    db_config = {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'dbname': os.environ.get('POSTGRES_DB'),
        'user': os.environ.get('POSTGRES_USER'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
        'port': int(os.environ.get('POSTGRES_PORT', '5432'))
    }
    
    # Embedding configuration with command line overrides
    embedding_config = EmbeddingConfig(
        chunktype_id=1,
        chunking_strategy_id=2,
        model_id=1,
        embedding_table="emb_snowflake",
        embedding_dim=1024,
        batch_size=args.batch_size,
        ollama_model="snowflake-arctic-embed2:latest",
        num_workers=args.num_workers,
        db_pool_size=args.db_pool_size,
        prefetch_batches=args.prefetch_batches,
        use_concurrent_embeddings=not args.disable_concurrent_embeddings
    )
    
    # Create and run processor
    processor = OptimizedEmbeddingProcessor(db_config, embedding_config)
    
    # Optional: Check progress before starting
    stats = processor.get_progress_stats()
    print(f"Progress Stats: {stats}")
    
    # Run the processor
    processor.run(max_chunks=args.max_chunks)


if __name__ == "__main__":
    main()
