#!/usr/bin/env python3
"""
Example usage of the embedding module.

This script demonstrates how to use the embedding module to create and search
vector embeddings for documents.
"""

import os
import sys
import logging
from pprint import pprint

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.embeddings import EmbeddingManager
from localknowledge.db.medrxiv import MedRxivDatabaseManager
from localknowledge.db.pubmed import PubMedDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def embed_medrxiv_document(doi: str):
    """
    Embed a medRxiv document.
    
    Args:
        doi: DOI of the document
    """
    # Get the document from the database
    db = MedRxivDatabaseManager()
    document = db.get_preprint_by_doi(doi)
    db.close()
    
    if not document:
        logger.error(f"Document with DOI {doi} not found")
        return
    
    # Create an embedding manager
    embedding_manager = EmbeddingManager()
    
    # Process the document
    text = document.get('abstract', '') + '\n\n' + document.get('full_text', '')
    if not text.strip():
        logger.error(f"Document with DOI {doi} has no text")
        return
    
    # Process the document
    chunks = embedding_manager.process_document(
        source_id='medrxiv',
        document_id=doi,
        text=text
    )
    
    logger.info(f"Processed {chunks} chunks for document {doi}")
    embedding_manager.close()

def embed_pubmed_document(pmid: str):
    """
    Embed a PubMed document.
    
    Args:
        pmid: PMID of the document
    """
    # Get the document from the database
    db = PubMedDatabaseManager()
    document = db.get_article_by_pmid(pmid)
    db.close()
    
    if not document:
        logger.error(f"Document with PMID {pmid} not found")
        return
    
    # Create an embedding manager
    embedding_manager = EmbeddingManager()
    
    # Process the document
    text = document.get('abstract', '')
    if not text.strip():
        logger.error(f"Document with PMID {pmid} has no text")
        return
    
    # Process the document
    chunks = embedding_manager.process_document(
        source_id='pubmed',
        document_id=pmid,
        text=text
    )
    
    logger.info(f"Processed {chunks} chunks for document {pmid}")
    embedding_manager.close()

def search_embeddings(query: str, limit: int = 5):
    """
    Search for similar documents using semantic search.
    
    Args:
        query: Search query
        limit: Maximum number of results to return
    """
    # Create an embedding manager
    embedding_manager = EmbeddingManager()
    
    # Search for similar documents
    results = embedding_manager.search(query, limit=limit)
    
    logger.info(f"Found {len(results)} results for query: {query}")
    for i, result in enumerate(results):
        print(f"\nResult {i+1} (similarity: {result['similarity']:.4f}):")
        print(f"Source: {result['source_id']}, Document: {result['document_id']}")
        print(f"Text: {result['text'][:200]}...")
    
    embedding_manager.close()

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Embedding example')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Embed medRxiv document
    medrxiv_parser = subparsers.add_parser('medrxiv', help='Embed a medRxiv document')
    medrxiv_parser.add_argument('doi', help='DOI of the document')
    
    # Embed PubMed document
    pubmed_parser = subparsers.add_parser('pubmed', help='Embed a PubMed document')
    pubmed_parser.add_argument('pmid', help='PMID of the document')
    
    # Search embeddings
    search_parser = subparsers.add_parser('search', help='Search for similar documents')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=5, help='Maximum number of results to return')
    
    args = parser.parse_args()
    
    if args.command == 'medrxiv':
        embed_medrxiv_document(args.doi)
    elif args.command == 'pubmed':
        embed_pubmed_document(args.pmid)
    elif args.command == 'search':
        search_embeddings(args.query, args.limit)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
