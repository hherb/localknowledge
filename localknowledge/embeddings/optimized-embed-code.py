import psycopg2
from psycopg2.extras import execute_values, DictCursor
from tqdm import tqdm
import requests
import json
import time
import logging
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
import os
import pickle
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

class OllamaEmbedder:
    """Class to handle batch embeddings with Ollama"""
    
    def __init__(self, model='snowflake-arctic-embed2:latest', batch_size=50, ollama_host="http://localhost:11434"):
        self.model = model
        self.batch_size = batch_size
        self.api_url = f"{ollama_host}/api/embeddings"
        
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts"""
        if not texts:
            return []
            
        payload = {
            "model": self.model,
            "prompt": texts  # Ollama API accepts a list for batch processing
        }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()
                
                # Extract embeddings from the response
                if "embeddings" in result:
                    return [item["embedding"] for item in result["embeddings"]]
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return []
            except requests.exceptions.RequestException as e:
                logger.warning(f"Embedding request failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to get embeddings after {max_retries} attempts")
                    return []

def save_checkpoint(checkpoint_path: Path, last_id: int, processed_count: int) -> None:
    """Save a checkpoint for resuming later"""
    try:
        checkpoint_data = {
            'last_id': last_id,
            'processed_count': processed_count,
            'timestamp': time.time()
        }
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)
        logger.info(f"Checkpoint saved: last_id={last_id}, processed={processed_count:,}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")

def generate_and_store_embeddings(
    db_params: Dict[str, str],
    batch_size: int = 50,
    embedding_model: str = 'snowflake-arctic-embed2:latest',
    embed_source_id: int = 1,
    worker_threads: int = 4,
    commit_frequency: int = 5,
    checkpoint_file: str = "embedding_checkpoint.pkl",
    resume: bool = True
):
    """
    Generate and store embeddings for documents in batches with checkpoint recovery
    
    Args:
        db_params: Database connection parameters
        batch_size: Number of documents to process in each batch
        embedding_model: Name of the embedding model to use
        embed_source_id: ID of the embedding source
        worker_threads: Number of concurrent workers for database operations
        commit_frequency: How many batches to process before committing
        checkpoint_file: File to store progress information for recovery
        resume: Whether to attempt to resume from checkpoint if available
    """
    # Create checkpoint directory if it doesn't exist
    checkpoint_dir = Path("checkpoints")
    checkpoint_dir.mkdir(exist_ok=True)
    checkpoint_path = checkpoint_dir / checkpoint_file
    
    # Initialize state variables for recovery
    last_processed_id = None
    processed_count = 0
    conn = None
    
    # Setup graceful shutdown handling
    shutdown_requested = False
    
    # Store original signal handlers to restore later
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    original_sigterm_handler = signal.getsignal(signal.SIGTERM)
    
    def handle_shutdown_signal(sig, frame):
        nonlocal shutdown_requested
        logger.info(f"Shutdown signal received ({sig}). Finishing current batch and saving checkpoint...")
        shutdown_requested = True
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    
    # Try to load checkpoint if resume is enabled
    if resume and checkpoint_path.exists():
        try:
            with open(checkpoint_path, 'rb') as f:
                checkpoint_data = pickle.load(f)
                last_processed_id = checkpoint_data.get('last_id')
                processed_count = checkpoint_data.get('processed_count', 0)
                logger.info(f"Resuming from checkpoint: last_id={last_processed_id}, "
                           f"processed={processed_count:,} documents")
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}. Starting from scratch.")
            last_processed_id = None
            processed_count = 0
    
    try:
        start_time = time.time()
        embedder = OllamaEmbedder(model=embedding_model, batch_size=batch_size)
        
        # Set up connection with appropriate parameters
        conn_params = db_params.copy()
        if 'options' not in conn_params:
            conn_params['options'] = '-c statement_timeout=0'  # Prevent timeouts for long operations
        
        conn = psycopg2.connect(**conn_params)
        conn.set_session(autocommit=False)
        
        # Count total documents needing embeddings
        try:
            with conn.cursor() as count_cur:
                if last_processed_id is not None:
                    count_query = """
                        SELECT COUNT(*)
                        FROM public.document d
                        LEFT JOIN public.unified_multiembeddings ume
                            ON d.id = ume.document_id
                            AND ume.embed_source_id = %s
                        WHERE d.abstract IS NOT NULL
                            AND ume.id IS NULL
                            AND d.id > %s
                    """
                    count_cur.execute(count_query, (embed_source_id, last_processed_id))
                else:
                    count_query = """
                        SELECT COUNT(*)
                        FROM public.document d
                        LEFT JOIN public.unified_multiembeddings ume
                            ON d.id = ume.document_id
                            AND ume.embed_source_id = %s
                        WHERE d.abstract IS NOT NULL
                            AND ume.id IS NULL
                    """
                    count_cur.execute(count_query, (embed_source_id,))
                
                total_docs = count_cur.fetchone()[0]
            
            if total_docs == 0:
                logger.info("All embeddings are up to date.")
                return
            
            logger.info(f"Found {total_docs:,} documents that need embeddings")
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            raise
        
        # Define insert query
        insert_query = """
            INSERT INTO public.unified_multiembeddings 
            (document_id, embed_source_id, chunk_no, page_no, text, embedding, model_name)
            VALUES %s
            ON CONFLICT (document_id, embed_source_id, chunk_no, page_no, model_name) DO NOTHING
        """
        
        # Process in larger external batches for database efficiency
        db_batch_size = batch_size * 10
        batch_count = 0
        last_checkpoint_time = time.time()
        
        # Initialize progress bar
        with tqdm(total=total_docs, 
                  desc="Embedding abstracts", 
                  unit="doc", 
                  initial=0) as progress_bar:
            
            try:
                with conn.cursor(name='doc_cursor', cursor_factory=DictCursor) as fetch_cur:
                    # Set cursor fetch size for memory efficiency
                    fetch_cur.itersize = db_batch_size
                    
                    # Execute query with appropriate parameters
                    if last_processed_id is not None:
                        fetch_query = """
                            SELECT d.id AS document_id, d.abstract
                            FROM public.document d
                            LEFT JOIN public.unified_multiembeddings ume
                                ON d.id = ume.document_id
                                AND ume.embed_source_id = %s
                            WHERE d.abstract IS NOT NULL
                                AND ume.id IS NULL
                                AND d.id > %s
                            ORDER BY d.id
                        """
                        fetch_cur.execute(fetch_query, (embed_source_id, last_processed_id))
                    else:
                        fetch_query = """
                            SELECT d.id AS document_id, d.abstract
                            FROM public.document d
                            LEFT JOIN public.unified_multiembeddings ume
                                ON d.id = ume.document_id
                                AND ume.embed_source_id = %s
                            WHERE d.abstract IS NOT NULL
                                AND ume.id IS NULL
                            ORDER BY d.id
                        """
                        fetch_cur.execute(fetch_query, (embed_source_id,))
                    
                    while True:
                        if shutdown_requested:
                            logger.info("Shutdown requested - finishing current batch and exiting")
                            break
                            
                        db_batch = fetch_cur.fetchmany(db_batch_size)
                        if not db_batch:
                            break
                        
                        # Process this database batch in smaller chunks for the embedding API
                        for i in range(0, len(db_batch), batch_size):
                            if shutdown_requested:
                                break
                                
                            current_batch = db_batch[i:i+batch_size]
                            doc_ids = [row['document_id'] for row in current_batch]
                            abstracts = [row['abstract'] for row in current_batch]
                            
                            # Skip empty abstracts
                            valid_indices = [i for i, abstract in enumerate(abstracts) if abstract and len(abstract.strip()) > 0]
                            if not valid_indices:
                                progress_bar.update(len(current_batch))
                                continue
                                
                            valid_abstracts = [abstracts[i] for i in valid_indices]
                            valid_doc_ids = [doc_ids[i] for i in valid_indices]
                            
                            # Get embeddings in batch
                            embeddings = embedder.get_embeddings(valid_abstracts)
                            
                            if len(embeddings) != len(valid_abstracts):
                                logger.warning(f"Expected {len(valid_abstracts)} embeddings but got {len(embeddings)}")
                                progress_bar.update(len(current_batch))
                                continue
                            
                            # Prepare insert data
                            insert_data = [
                                (doc_id, embed_source_id, 0, 0, abstract, embedding, embedding_model)
                                for doc_id, abstract, embedding in zip(valid_doc_ids, valid_abstracts, embeddings)
                            ]
                            
                            # Bulk insert
                            try:
                                with conn.cursor() as insert_cur:
                                    execute_values(insert_cur, insert_query, insert_data)
                                batch_count += 1
                                
                                # Commit periodically to avoid transaction bloat
                                if batch_count % commit_frequency == 0:
                                    conn.commit()
                                    # Update the last processed ID for checkpointing
                                    last_processed_id = max(doc_ids) if doc_ids else last_processed_id
                                    logger.debug(f"Committed {batch_count} batches")
                                    
                                    # Create checkpoint every 10 minutes or after significant progress
                                    current_time = time.time()
                                    if current_time - last_checkpoint_time > 600:  # 10 minutes
                                        save_checkpoint(checkpoint_path, last_processed_id, processed_count)
                                        last_checkpoint_time = current_time
                            except Exception as e:
                                conn.rollback()
                                logger.error(f"Batch insert failed: {e}")
                            
                            processed_count += len(current_batch)
                            progress_bar.update(len(current_batch))
                            
                            # Report progress periodically
                            if processed_count % (batch_size * 20) == 0:
                                elapsed = time.time() - start_time
                                docs_per_sec = processed_count / elapsed if elapsed > 0 else 0
                                est_remaining = (total_docs - processed_count) / docs_per_sec if docs_per_sec > 0 else 0
                                logger.info(f"Progress: {processed_count:,}/{total_docs:,} docs "
                                           f"({docs_per_sec:.1f} docs/sec, ~{est_remaining/3600:.1f} hours remaining)")
                    
                    # Final commit for any remaining transactions
                    if conn and not conn.closed:
                        conn.commit()
                    
                    # Create final checkpoint
                    if last_processed_id is not None:
                        save_checkpoint(checkpoint_path, last_processed_id, processed_count)
            except Exception as e:
                logger.error(f"Error during document processing: {e}")
                if conn and not conn.closed:
                    conn.rollback()
                raise
    except Exception as e:
        logger.exception(f"Error in embedding process: {e}")
        # Create checkpoint on error if we have processed any documents
        if last_processed_id is not None:
            save_checkpoint(checkpoint_path, last_processed_id, processed_count)
    finally:
        # Clean up resources
        if conn and not conn.closed:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
                
        # Restore original signal handlers
        signal.signal(signal.SIGINT, original_sigint_handler)
        signal.signal(signal.SIGTERM, original_sigterm_handler)
    
    if shutdown_requested:
        logger.info("Process was gracefully shutdown. Run again with the same parameters to resume.")
        return
    
    total_time = time.time() - start_time
    logger.info(f"Embedding process completed in {total_time/3600:.2f} hours. "
               f"Processed {processed_count:,} documents at {processed_count/total_time:.1f} docs/sec")
    
    # Remove checkpoint file on successful completion
    if checkpoint_path.exists():
        try:
            checkpoint_path.unlink()
            logger.info("Checkpoint file removed after successful completion")
        except Exception as e:
            logger.warning(f"Failed to remove checkpoint file: {e}")

if __name__ == "__main__":
    load_dotenv()
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate and store embeddings for documents")
    parser.add_argument("--batch-size", type=int, default=50, 
                        help="Number of documents to embed in each API call")
    parser.add_argument("--model", type=str, default="snowflake-arctic-embed2:latest",
                        help="Embedding model to use")
    parser.add_argument("--embed-source-id", type=int, default=1,
                        help="ID of the embedding source")
    parser.add_argument("--commit-frequency", type=int, default=5,
                        help="Commit every N batches")
    parser.add_argument("--worker-threads", type=int, default=4,
                        help="Number of worker threads for concurrent operations")
    parser.add_argument("--checkpoint-file", type=str, default="embedding_checkpoint.pkl",
                        help="File to store checkpoint information")
    parser.add_argument("--no-resume", action="store_true",
                        help="Don't resume from checkpoint even if available")
    
    args = parser.parse_args()
    
    db_params = {
        'dbname': os.getenv('POSTGRES_DB'),
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD'),
        'host': os.getenv('POSTGRES_HOST'),
        'port': os.getenv('POSTGRES_PORT')
    }
    
    # Configuration from command line arguments
    config = {
        'batch_size': args.batch_size,
        'embedding_model': args.model,
        'embed_source_id': args.embed_source_id,
        'worker_threads': args.worker_threads,
        'commit_frequency': args.commit_frequency,
        'checkpoint_file': args.checkpoint_file,
        'resume': not args.no_resume
    }
    
    logger.info(f"Starting embedding pipeline with parameters: {config}")
    generate_and_store_embeddings(
        db_params=db_params,
        **config
    )
