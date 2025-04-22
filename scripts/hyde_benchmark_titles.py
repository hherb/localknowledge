#!/usr/bin/env python3
"""
Script to benchmark HyDE on legacy embeddings for preprint abstracts.

This script:
1. Uses HyDE to generate hypothetical abstracts for a medical question
2. Creates embeddings for each hypothetical abstract using different models
3. Retrieves the top 3 titles for each model's embedding
4. Compares which model yielded the best results
"""

import sys
import os
from pathlib import Path
import json
import time
from typing import List, Dict, Any, Optional, Tuple
import argparse

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from localknowledge.ai.HyDE import generate_hypothetical_abstract, hyde_embedding_from_prompt
from localknowledge.embeddings.database import EmbeddingDatabaseManager
from localknowledge.db.medrxiv import MedRxivDatabaseManager


def get_top_titles(embedding: List[float], 
                  embedding_db: EmbeddingDatabaseManager,
                  medrxiv_db: MedRxivDatabaseManager,
                  top_n: int = 3,
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


def benchmark_hyde_models(question: str, 
                         models: List[str],
                         embedding_model: str = "snowflake-arctic-embed2:latest",
                         top_n: int = 3,
                         threshold: float = 0.5) -> Dict[str, Any]:
    """
    Benchmark different models for HyDE.
    
    Args:
        question: Medical question to use for HyDE
        models: List of models to benchmark
        embedding_model: Model to use for embeddings
        top_n: Number of top results to return
        threshold: Similarity threshold
        
    Returns:
        Dictionary with benchmark results
    """
    embedding_db = EmbeddingDatabaseManager()
    medrxiv_db = MedRxivDatabaseManager()
    
    results = {}
    
    print(f"Benchmarking {len(models)} models for question: {question}")
    
    for model in models:
        print(f"\nModel: {model}")
        
        # Generate hypothetical abstract
        start_time = time.time()
        hypothetical_abstract = generate_hypothetical_abstract(question, model=model)
        print(f"Generated abstract ({len(hypothetical_abstract)} chars)")
        print("---")
        print(hypothetical_abstract[:300] + "..." if len(hypothetical_abstract) > 300 else hypothetical_abstract)
        print("---")
        
        # Generate embedding
        embedding = hyde_embedding_from_prompt(hypothetical_abstract, embedding_model=embedding_model)
        
        # Get top titles
        titles = get_top_titles(
            embedding=embedding,
            embedding_db=embedding_db,
            medrxiv_db=medrxiv_db,
            top_n=top_n,
            threshold=threshold
        )
        
        end_time = time.time()
        
        # Store results
        results[model] = {
            'hypothetical_abstract': hypothetical_abstract,
            'titles': titles,
            'time_taken': end_time - start_time
        }
        
        # Print titles
        print(f"Top {len(titles)} titles:")
        for i, title_info in enumerate(titles):
            print(f"{i+1}. {title_info['title']} (similarity: {title_info['similarity']:.4f})")
    
    # Close database connections
    embedding_db.close()
    medrxiv_db.close()
    
    return results


def main():
    """Run the benchmark."""
    parser = argparse.ArgumentParser(description='Benchmark HyDE on legacy embeddings')
    parser.add_argument('--question', type=str, 
                        default="What is the effectiveness of mRNA vaccines against COVID-19 variants?",
                        help='Medical question to use for HyDE')
    parser.add_argument('--models', type=str, nargs='+',
                        default=["gemma3:4b", "llama3.2:3b-instruct-q8_0", "qwen2.5:3b-instruct-q8_0"],
                        help='Models to benchmark')
    parser.add_argument('--embedding-model', type=str, 
                        default="snowflake-arctic-embed2:latest",
                        help='Model to use for embeddings')
    parser.add_argument('--top-n', type=int, default=3,
                        help='Number of top results to return')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Similarity threshold')
    parser.add_argument('--output', type=str, default="hyde_benchmark_titles.json",
                        help='Output file for benchmark results')
    
    args = parser.parse_args()
    
    # Run benchmark
    results = benchmark_hyde_models(
        question=args.question,
        models=args.models,
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
    for model, result in results.items():
        titles_count = len(result['titles'])
        time_taken = result['time_taken']
        print(f"{model}: {titles_count} titles in {time_taken:.2f} seconds")


if __name__ == "__main__":
    main()
