#!/usr/bin/env python3
"""
Test script for PubMedBERT embeddings and semantic search.

This script takes a question as a command-line argument, embeds it using PubMedBERTEmbedder,
and performs a semantic search in the PostgreSQL database using the emb_768 table.
It uses direct psycopg2 connection rather than existing modules.

Usage:
    python test_pubmedbert_search.py "What is the role of ACE2 in COVID-19?"
"""

import os
import sys
import argparse
import logging
import warnings
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Suppress specific warnings
warnings.filterwarnings("ignore", message="No sentence-transformers model found with name.*Creating a new one with mean pooling.")

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set environment variables for offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def load_db_connection_params() -> Dict[str, Any]:
    """
    Load database connection parameters from environment variables.

    Returns:
        Dictionary of connection parameters
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get database connection parameters
    dbname = os.environ.get('POSTGRES_DB')
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    if not dbname:
        raise ValueError("POSTGRES_DB environment variable must be set")

    logger.info(f"Using database: {dbname}@{host}:{port}")

    return {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }

def embed_question(question: str, model_path: str = "~/.cache/huggingface/hub/models--microsoft--BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext") -> List[float]:
    """
    Embed a question using a pre-downloaded SentenceTransformer model.

    Args:
        question: The question to embed
        model_path: Path to the pre-downloaded model

    Returns:
        List of floats representing the embedding vector
    """
    # Expand the user path if it contains ~
    model_path = os.path.expanduser(model_path)

    logger.info(f"Loading model from local path: {model_path}")

    try:
        # Load the model from the local path
        model = SentenceTransformer(model_path)

        # Embed the question
        embedding = model.encode(question, show_progress_bar=False).tolist()

        logger.info(f"Successfully created embedding with dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"Error embedding question: {e}")
        # Try with a model name instead of path as fallback
        try:
            logger.info("Trying with model name instead of path...")
            model = SentenceTransformer("microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext")
            embedding = model.encode(question, show_progress_bar=False).tolist()
            logger.info(f"Successfully created embedding with dimension: {len(embedding)}")
            return embedding
        except Exception as inner_e:
            logger.error(f"Error with fallback approach: {inner_e}")
            raise

def semantic_search(embedding: List[float],
                   connection_params: Dict[str, Any],
                   table_name: str = "emb_768",
                   limit: int = 10,
                   threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Perform a semantic search using the embedding vector.

    Args:
        embedding: The embedding vector to search with
        connection_params: Database connection parameters
        table_name: The name of the embedding table to search in
        limit: Maximum number of results to return
        threshold: Similarity threshold (0-1)

    Returns:
        List of dictionaries containing search results
    """
    logger.info(f"Performing semantic search in table {table_name} with threshold {threshold}")

    # Connect to the database
    conn = None
    try:
        conn = psycopg2.connect(**connection_params)

        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Perform the search using cosine similarity
            query = f"""
            SELECT
                e.id as embedding_id,
                e.chunk_id,
                c.document_id,
                c.document_title,
                c.text,
                c.chunk_no,
                1 - (e.embedding <=> %s::vector) as similarity
            FROM
                {table_name} e
            JOIN
                chunks c ON e.chunk_id = c.id
            WHERE
                1 - (e.embedding <=> %s::vector) > %s
            ORDER BY
                similarity DESC
            LIMIT %s
            """

            cursor.execute(query, (embedding, embedding, threshold, limit))
            results = [dict(row) for row in cursor.fetchall()]

            logger.info(f"Found {len(results)} results with similarity > {threshold}")
            return results
    except Exception as e:
        logger.error(f"Error performing semantic search: {e}")
        raise
    finally:
        if conn:
            conn.close()

def main():
    """Main function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Test PubMedBERT embeddings and semantic search')
    parser.add_argument('question', type=str, help='The question to search for')
    parser.add_argument('--model-path', type=str,
                        default="~/.cache/huggingface/hub/models--microsoft--BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
                        help='Path to the pre-downloaded model')
    parser.add_argument('--limit', type=int, default=5,
                        help='Maximum number of results to return')
    parser.add_argument('--threshold', type=float, default=0.6,
                        help='Similarity threshold (0-1)')
    parser.add_argument('--table', type=str, default="emb_768",
                        help='Embedding table name')

    args = parser.parse_args()

    try:
        # Load database connection parameters
        connection_params = load_db_connection_params()

        # Embed the question using the local model
        embedding = embed_question(args.question, model_path=args.model_path)

        # Perform semantic search
        results = semantic_search(
            embedding=embedding,
            connection_params=connection_params,
            table_name=args.table,
            limit=args.limit,
            threshold=args.threshold
        )

        # Display results
        print(f"\nSearch results for: '{args.question}'\n")
        print(f"{'Similarity':<10} {'Document Title':<50} {'Chunk Text':<100}")
        print("-" * 160)

        for result in results:
            similarity = result['similarity']
            title = result['document_title']
            text = result['text']

            # Truncate text for display
            if len(text) > 97:
                text = text[:97] + "..."

            # Truncate title for display
            if len(title) > 47:
                title = title[:47] + "..."

            print(f"{similarity:<10.4f} {title:<50} {text:<100}")

        print("\nDetailed Results:")
        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Similarity: {result['similarity']:.4f}")
            print(f"Document ID: {result['document_id']}")
            print(f"Document Title: {result['document_title']}")
            print(f"Chunk ID: {result['chunk_id']} (Chunk #{result['chunk_no']})")
            print(f"Text: {result['text'][:500]}...")

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
