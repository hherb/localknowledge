#!/usr/bin/env python3
"""
Script to compare HyDE vs direct semantic search.

This script:
1. Uses a question directly for semantic search
2. Uses HyDE to generate a hypothetical abstract and then search
3. Compares the results from both approaches
"""

import sys
import os
from pathlib import Path
import json
import time
from typing import List, Dict, Any, Optional, Tuple
import argparse
import ollama

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.ai.HyDE import generate_hypothetical_abstract, hyde_embedding_from_prompt
from localknowledge.embeddings.database import EmbeddingDatabaseManager
from localknowledge.db.medrxiv import MedRxivDatabaseManager


def get_embedding(text: str, model: str = "snowflake-arctic-embed2:latest") -> List[float]:
    """
    Get embedding for a text using the specified model.
    
    Args:
        text: Text to embed
        model: Model to use for embedding
        
    Returns:
        Vector embedding
    """
    response = ollama.embeddings(model=model, prompt=text)
    return response['embedding']


def get_top_titles(embedding: List[float], 
                  embedding_db: EmbeddingDatabaseManager,
                  medrxiv_db: MedRxivDatabaseManager,
                  top_n: int = 5,
                  threshold: float = 0.5) -> List[Dict[str, Any]]:
    """
    Get the top N titles for a given embedding.
    
    Args:
        embedding: Vector embedding
        embedding_db: Embedding database manager
        medrxiv_db: MedRxiv database manager
        top_n: Number of top results to return
        threshold: Similarity threshold
        
    Returns:
        List of dictionaries with title, doi, and similarity score
    """
    # Search for similar documents
    results = embedding_db.search_similar(
        query_embedding=embedding,
        limit=top_n,
        threshold=threshold,
        source_id='medrxiv'
    )
    
    # Get titles for the results
    titles = []
    for result in results:
        doi = result.get('document_id')
        similarity = result.get('similarity', 0)
        
        # Get the preprint to get the title
        preprint = medrxiv_db.get_preprint_by_doi(doi)
        if preprint:
            titles.append({
                'title': preprint.get('title', ''),
                'doi': doi,
                'similarity': similarity
            })
    
    return titles


def compare_search_methods(question: str, 
                          hyde_model: str = "gemma3:4b",
                          embedding_model: str = "snowflake-arctic-embed2:latest",
                          top_n: int = 5,
                          threshold: float = 0.5) -> Dict[str, Any]:
    """
    Compare HyDE vs direct semantic search.
    
    Args:
        question: Question to search for
        hyde_model: Model to use for HyDE
        embedding_model: Model to use for embeddings
        top_n: Number of top results to return
        threshold: Similarity threshold
        
    Returns:
        Dictionary with comparison results
    """
    embedding_db = EmbeddingDatabaseManager()
    medrxiv_db = MedRxivDatabaseManager()
    
    results = {}
    
    print(f"Comparing search methods for question: {question}")
    
    # Method 1: Direct semantic search
    print("\nMethod 1: Direct semantic search")
    start_time = time.time()
    
    # Get embedding for the question
    direct_embedding = get_embedding(question, model=embedding_model)
    
    # Get top titles
    direct_titles = get_top_titles(
        embedding=direct_embedding,
        embedding_db=embedding_db,
        medrxiv_db=medrxiv_db,
        top_n=top_n,
        threshold=threshold
    )
    
    direct_time = time.time() - start_time
    
    # Print titles
    print(f"Top {len(direct_titles)} titles (took {direct_time:.2f} seconds):")
    for i, title_info in enumerate(direct_titles):
        print(f"{i+1}. {title_info['title']} (similarity: {title_info['similarity']:.4f})")
    
    # Method 2: HyDE
    print("\nMethod 2: HyDE")
    start_time = time.time()
    
    # Generate hypothetical abstract
    hypothetical_abstract = generate_hypothetical_abstract(question, model=hyde_model)
    print(f"Generated abstract ({len(hypothetical_abstract)} chars)")
    print("---")
    print(hypothetical_abstract[:300] + "..." if len(hypothetical_abstract) > 300 else hypothetical_abstract)
    print("---")
    
    # Generate embedding
    hyde_embedding = hyde_embedding_from_prompt(hypothetical_abstract, embedding_model=embedding_model)
    
    # Get top titles
    hyde_titles = get_top_titles(
        embedding=hyde_embedding,
        embedding_db=embedding_db,
        medrxiv_db=medrxiv_db,
        top_n=top_n,
        threshold=threshold
    )
    
    hyde_time = time.time() - start_time
    
    # Print titles
    print(f"Top {len(hyde_titles)} titles (took {hyde_time:.2f} seconds):")
    for i, title_info in enumerate(hyde_titles):
        print(f"{i+1}. {title_info['title']} (similarity: {title_info['similarity']:.4f})")
    
    # Compare results
    print("\nComparison:")
    
    # Find common titles
    common_dois = set([t['doi'] for t in direct_titles]) & set([t['doi'] for t in hyde_titles])
    common_titles = [t for t in direct_titles if t['doi'] in common_dois]
    
    print(f"Common titles: {len(common_titles)}")
    for title in common_titles:
        direct_similarity = next((t['similarity'] for t in direct_titles if t['doi'] == title['doi']), 0)
        hyde_similarity = next((t['similarity'] for t in hyde_titles if t['doi'] == title['doi']), 0)
        print(f"- {title['title']}")
        print(f"  Direct: {direct_similarity:.4f}, HyDE: {hyde_similarity:.4f}")
    
    # Store results
    results = {
        'question': question,
        'direct_search': {
            'titles': direct_titles,
            'time_taken': direct_time
        },
        'hyde_search': {
            'model': hyde_model,
            'hypothetical_abstract': hypothetical_abstract,
            'titles': hyde_titles,
            'time_taken': hyde_time
        },
        'common_titles': [
            {
                'title': t['title'],
                'doi': t['doi'],
                'direct_similarity': next((d['similarity'] for d in direct_titles if d['doi'] == t['doi']), 0),
                'hyde_similarity': next((h['similarity'] for h in hyde_titles if h['doi'] == t['doi']), 0)
            }
            for t in common_titles
        ]
    }
    
    # Close database connections
    embedding_db.close()
    medrxiv_db.close()
    
    return results


def main():
    """Run the comparison."""
    parser = argparse.ArgumentParser(description='Compare HyDE vs direct semantic search')
    parser.add_argument('--question', type=str, 
                        default="What is the cut-off for ultrasound optic nerve sheath diameter (ONSD) for diagnosing raised intracranial pressure (ICP) in adults?",
                        help='Question to search for')
    parser.add_argument('--hyde-model', type=str, default="gemma3:4b",
                        help='Model to use for HyDE')
    parser.add_argument('--embedding-model', type=str, 
                        default="snowflake-arctic-embed2:latest",
                        help='Model to use for embeddings')
    parser.add_argument('--top-n', type=int, default=5,
                        help='Number of top results to return')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Similarity threshold')
    parser.add_argument('--output', type=str, default="hyde_vs_direct_search.json",
                        help='Output file for comparison results')
    
    args = parser.parse_args()
    
    # Run comparison
    results = compare_search_methods(
        question=args.question,
        hyde_model=args.hyde_model,
        embedding_model=args.embedding_model,
        top_n=args.top_n,
        threshold=args.threshold
    )
    
    # Save results to file
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")
    
    # Print summary
    print("\nSummary:")
    print(f"Direct search: {len(results['direct_search']['titles'])} titles in {results['direct_search']['time_taken']:.2f} seconds")
    print(f"HyDE search: {len(results['hyde_search']['titles'])} titles in {results['hyde_search']['time_taken']:.2f} seconds")
    print(f"Common titles: {len(results['common_titles'])}")
    
    # Calculate average similarity
    if results['direct_search']['titles']:
        direct_avg = sum(t['similarity'] for t in results['direct_search']['titles']) / len(results['direct_search']['titles'])
        print(f"Direct search average similarity: {direct_avg:.4f}")
    
    if results['hyde_search']['titles']:
        hyde_avg = sum(t['similarity'] for t in results['hyde_search']['titles']) / len(results['hyde_search']['titles'])
        print(f"HyDE search average similarity: {hyde_avg:.4f}")


if __name__ == "__main__":
    main()
