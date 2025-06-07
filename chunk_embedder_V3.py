#!/usr/bin/env python3
"""
Efficient batch embedding processor for chunks using Ollama and PostgreSQL.
Processes chunks that haven't been embedded yet and stores results in emb_snowflake table.
"""

import logging
import time
import sys
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
import ollama
import os
from tqdm import tqdm

# Silence httpx (used by ollama) INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("ollama").setLevel(logging.WARNING)

__version__ = 0.1

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


class EmbeddingProcessor:
    """Handles batch processing of chunk embeddings"""
    
    def __init__(self, db_config: Dict[str, Any], embedding_config: EmbeddingConfig):
        self.db_config = db_config
        self.config = embedding_config
        self.logger = self._setup_logging()
        
        # Initialize connection pool
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            **db_config
        )
        
        self.logger.info("Ensuring embedding table exists...")
        self.ensure_embedding_table_exists()
        # Initialize Ollama client
        self.ollama_client = ollama.Client()
        
    def _setup_logging(self) -> logging.Logger:
        """Configure logging"""
        logging.basicConfig(
            level=logging.WARNING,  # Change from INFO to WARNING to reduce console output
            format='%(asctime)s - %(levelname)s - %(message)s',
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
                        
                        # Optional: HNSW index for vector similarity if using pgvector
                        # Uncomment if you need vector similarity searches
                        # cur.execute(f"""
                        #     CREATE INDEX idx_{table_name}_embedding_hnsw 
                        #     ON public.{table_name} 
                        #     USING hnsw (embedding vector_cosine_ops);
                        # """)
                        
                        conn.commit()
                        self.logger.info(f"Successfully created table {table_name} with indexes")
                        
                    else:
                        self.logger.info(f"Embedding table {table_name} already exists")
                        
                        # Verify essential indexes exist and create if missing
                        self._ensure_indexes_exist(cur, table_name)
                        conn.commit()
                        
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Failed to create/verify embedding table: {e}")
                    raise
    
    def _ensure_indexes_exist(self, cursor, table_name: str) -> None:
        """Ensure all necessary indexes exist on the embedding table"""
        
        # Check and create composite index on (chunk_id, model_id)
        index_name = f"idx_{table_name}_chunk_model"
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_class c 
                JOIN pg_namespace n ON n.oid = c.relnamespace 
                WHERE c.relname = %s AND n.nspname = 'public'
            );
        """, (index_name,))
        
        if not cursor.fetchone()[0]:
            self.logger.info(f"Creating missing index: {index_name}")
            cursor.execute(f"""
                CREATE INDEX {index_name} 
                ON public.{table_name} (chunk_id, model_id);
            """)
        
        # Check and create chunk_id index
        index_name = f"idx_{table_name}_chunk_id"
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_class c 
                JOIN pg_namespace n ON n.oid = c.relnamespace 
                WHERE c.relname = %s AND n.nspname = 'public'
            );
        """, (index_name,))
        
        if not cursor.fetchone()[0]:
            self.logger.info(f"Creating missing index: {index_name}")
            cursor.execute(f"""
                CREATE INDEX {index_name} 
                ON public.{table_name} (chunk_id);
            """)
        
        # Check and create model_id index
        index_name = f"idx_{table_name}_model_id"
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_class c 
                JOIN pg_namespace n ON n.oid = c.relnamespace 
                WHERE c.relname = %s AND n.nspname = 'public'
            );
        """, (index_name,))
        
        if not cursor.fetchone()[0]:
            self.logger.info(f"Creating missing index: {index_name}")
            cursor.execute(f"""
                CREATE INDEX {index_name} 
                ON public.{table_name} (model_id);
            """)
    
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
    
    def get_unembedded_chunks_cursor(self):
        """Get a cursor for iterating through unembedded chunks efficiently"""
        query = f"""
        SELECT c.id, c.text
        FROM public.chunks c
        LEFT JOIN public.{self.config.embedding_table} e ON c.id = e.chunk_id AND e.model_id = %s
        WHERE c.chunktype_id = %s 
          AND c.chunking_strategy_id = %s
          AND e.chunk_id IS NULL
        ORDER BY c.id
        """
        
        conn = self.pool.getconn()
        # Use a named cursor for server-side cursor (memory efficient)
        cursor = conn.cursor(name='unembedded_chunks_cursor')
        cursor.itersize = self.config.batch_size  # Fetch batch_size rows at a time
        
        try:
            cursor.execute(query, (
                self.config.model_id,
                self.config.chunktype_id,
                self.config.chunking_strategy_id
            ))
            return conn, cursor
        except Exception as e:
            cursor.close()
            self.pool.putconn(conn)
            raise e
    
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
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts using Ollama"""
        embeddings = []
        
        for text in texts:
            for attempt in range(self.config.max_retries):
                try:
                    response = self.ollama_client.embeddings(
                        model=self.config.ollama_model,
                        prompt=text
                    )
                    embeddings.append(response['embedding'])
                    break
                    
                except Exception as e:
                    self.logger.warning(
                        f"Embedding attempt {attempt + 1} failed for chunk: {e}"
                    )
                    if attempt == self.config.max_retries - 1:
                        self.logger.error(f"Failed to generate embedding after {self.config.max_retries} attempts")
                        raise
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
        
        return embeddings
    
    def store_embeddings(self, chunk_embeddings: List[Tuple[int, List[float]]]) -> None:
        """Store embeddings in the database"""
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
                        template=None, page_size=self.config.batch_size
                    )
                conn.commit()
                # Use debug level instead of info to reduce console output
                self.logger.debug(f"Successfully stored {len(chunk_embeddings)} embeddings")
                
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to store embeddings: {e}")
                raise
    
    def process_batch(self, chunks: List[Tuple], pbar: Optional[tqdm] = None) -> int:
        """Process a batch of chunks"""
        if not chunks:
            return 0
        
        chunk_ids = [chunk[0] for chunk in chunks]
        texts = [chunk[1] for chunk in chunks]
        
        # Use tqdm.write for logging to avoid interfering with progress bar
        if pbar:
            pbar.set_description(f"Processing chunks {chunk_ids[0]}-{chunk_ids[-1]}")
        else:
            self.logger.info(f"Processing batch of {len(chunks)} chunks (IDs: {chunk_ids[0]}-{chunk_ids[-1]})")
        
        try:
            # Generate embeddings
            start_time = time.time()
            embeddings = self.generate_embeddings(texts)
            embedding_time = time.time() - start_time
            
            # Store embeddings
            chunk_embeddings = list(zip(chunk_ids, embeddings))
            self.store_embeddings(chunk_embeddings)
            
            total_time = time.time() - start_time
            
            # Log completion but use tqdm.write if progress bar is active
            if pbar:
                if len(chunks) > 5:  # Only log for larger batches
                    tqdm.write(
                        f"Batch completed in {total_time:.2f}s "
                        f"(embedding: {embedding_time:.2f}s, avg: {embedding_time/len(chunks):.3f}s/chunk)"
                    )
            else:
                self.logger.info(
                    f"Batch completed in {total_time:.2f}s "
                    f"(embedding: {embedding_time:.2f}s, avg: {embedding_time/len(chunks):.3f}s/chunk)"
                )
            
            return len(chunks)
            
        except Exception as e:
            if pbar:
                tqdm.write(f"Batch processing failed: {e}")
            self.logger.error(f"Batch processing failed: {e}")
            raise
    
    def run(self, max_chunks: Optional[int] = None) -> None:
        """Main processing loop using server-side cursor for efficiency"""
        self.logger.info(f"Starting embedding processor (version {__version__})")
        self.logger.info(f"Config: chunktype_id={self.config.chunktype_id}, "
                        f"chunking_strategy_id={self.config.chunking_strategy_id}, "
                        f"model_id={self.config.model_id}, "
                        f"embedding_table={self.config.embedding_table}, "
                        f"batch_size={self.config.batch_size}")
        
        try:
            # Test Ollama connection
            self.ollama_client.list()
            self.logger.info("Ollama connection successful")
            
            # Get total count for progress tracking
            total_count = self.get_unembedded_chunks_count()
            
            if max_chunks:
                total_count = min(total_count, max_chunks)
            
            self.logger.info(f"Found {total_count} chunks to process")
            
            if total_count == 0:
                self.logger.info("No chunks to process. Exiting.")
                return
            
            # Get cursor for streaming results (executes expensive query only once)
            self.logger.info("Executing query for unembedded chunks...")
            conn, cursor = self.get_unembedded_chunks_cursor()
            
            try:
                processed_count = 0
                start_time = time.time()
                
                # Create progress bar
                with tqdm(total=total_count, desc="Embedding chunks", unit="chunk") as pbar:
                    # Stream results in batches
                    while processed_count < total_count:
                        # Fetch next batch using server-side cursor
                        batch = cursor.fetchmany(self.config.batch_size)
                        
                        if not batch:
                            break
                        
                        # Limit to max_chunks if specified
                        if max_chunks and processed_count + len(batch) > max_chunks:
                            batch = batch[:max_chunks - processed_count]
                        
                        try:
                            # Extract chunk IDs and texts
                            chunk_ids = [chunk[0] for chunk in batch]
                            texts = [chunk[1] for chunk in batch]
                            
                            # Update progress bar description
                            pbar.set_description(f"Processing {chunk_ids[0]}-{chunk_ids[-1]}")
                            
                            # Generate embeddings
                            embeddings = self.generate_embeddings(texts)
                            
                            # Store embeddings
                            chunk_embeddings = list(zip(chunk_ids, embeddings))
                            self.store_embeddings(chunk_embeddings)
                            
                            # Update counters and progress bar
                            batch_size = len(batch)
                            processed_count += batch_size
                            pbar.update(batch_size)
                            
                            # Calculate overall rate based on total time since start
                            current_time = time.time()
                            total_elapsed = current_time - start_time
                            overall_rate = processed_count / total_elapsed if total_elapsed > 0 else 0
                            
                            # Calculate ETA based on overall rate
                            remaining_chunks = total_count - processed_count
                            eta_seconds = remaining_chunks / overall_rate if overall_rate > 0 else 0
                            
                            # Format time nicely
                            if eta_seconds < 60:
                                eta_str = f"{eta_seconds:.0f}s"
                            elif eta_seconds < 3600:
                                eta_str = f"{eta_seconds/60:.1f}min"
                            else:
                                eta_str = f"{eta_seconds/3600:.1f}h"
                            
                            # Update progress bar with rate and ETA
                            pbar.set_postfix({
                                'rate': f"{overall_rate:.2f} chunks/s",
                                'eta': eta_str
                            })
                            
                            # Break if we've reached max_chunks
                            if max_chunks and processed_count >= max_chunks:
                                break
                            
                        except Exception as e:
                            tqdm.write(f"Batch failed, continuing with next batch: {str(e)}")
                            self.logger.error(f"Batch failed, continuing with next batch: {e}")
                            continue
                
                # Final stats after completion
                total_time = time.time() - start_time
                avg_rate = processed_count / total_time if total_time > 0 else 0
                
                tqdm.write(f"Processing completed: {processed_count}/{total_count} chunks in {total_time:.2f}s (avg: {avg_rate:.2f} chunks/sec)")
                
            finally:
                # Always clean up cursor and connection
                cursor.close()
                self.pool.putconn(conn)
            
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
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Efficient batch embedding processor for chunks")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="Number of chunks to process in each batch (default: 200)")
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
    
    # Embedding configuration
    embedding_config = EmbeddingConfig(
        chunktype_id=1,
        chunking_strategy_id=2,
        model_id=1,
        embedding_table="emb_snowflake",  # Configurable table name
        embedding_dim=1024,          # Vector dimension
        batch_size=args.batch_size,  # Use command line argument
        ollama_model="snowflake-arctic-embed2:latest"
    )
    
    # Create and run processor
    processor = EmbeddingProcessor(db_config, embedding_config)
    
    # Optional: Check progress before starting
    stats = processor.get_progress_stats()
    print(f"Progress Stats: {stats}")
    
    # Run the processor
    processor.run()


if __name__ == "__main__":
    main()
