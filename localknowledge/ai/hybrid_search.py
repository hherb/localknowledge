"""
Hybrid search module that combines results from multiple search methods.

This module provides functions to perform hybrid searches that combine results from
different search methods (semantic, HyDE, etc.), remove duplicates, and optionally
re-rank the combined results.
"""

from typing import List, Dict, Any, Optional, Callable, Union
import logging
import traceback

from localknowledge.db.connection_pool import get_cursor
from localknowledge.embeddings.multiembeddings import EmbeddingManager
from localknowledge.ai.HyDE import generate_hypothetical_abstract

# Configure logging
logger = logging.getLogger(__name__)


def perform_semantic_search(
    embedding_manager: EmbeddingManager,
    query: str,
    max_results: int = 10,
    threshold: float = 0.3,
    model_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Perform a semantic search using the embedding manager.

    Args:
        embedding_manager: The embedding manager to use
        query: The search query
        max_results: Maximum number of results to return
        threshold: Similarity threshold
        model_name: Model name to use (defaults to embedding_manager's model_name)

    Returns:
        List of search results
    """
    try:
        # Create embedding for the query
        query_embedding = embedding_manager.create_embedding(query)

        # Use the model name from the embedding manager if not specified
        if model_name is None:
            model_name = embedding_manager.model_name

        # Get the embedding source ID
        from localknowledge.db.embedding_source import get_embedding_source_by_name

        results = []
        with get_cursor() as cursor:
            # Get the embedding source ID
            embed_source_record = get_embedding_source_by_name(cursor, 'abstract')

            if not embed_source_record:
                logger.error("Embedding source 'abstract' not found")
                return []

            embed_source_id = embed_source_record['id']

            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(query_embedding)

            query_sql = """
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.id, d.title, d.abstract, d.source_id, d.authors
            FROM unified_multiembeddings e
            JOIN embedding_source s ON e.embed_source_id = s.id
            JOIN document d ON e.document_id = d.id
            WHERE e.embed_source_id = %s
            AND e.model_name = %s
            AND 1 - (e.embedding <=> vector(%s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
            """

            cursor.execute(
                query_sql,
                (embedding_str, embedding_str, embed_source_id, model_name, embedding_str, threshold, max_results)
            )

            results = [dict(row) for row in cursor.fetchall()]

        return results
    except Exception as e:
        logger.error(f"Error in semantic search: {e}\n{traceback.format_exc()}")
        return []


def perform_hyde_search(
    embedding_manager: EmbeddingManager,
    query: str,
    max_results: int = 10,
    threshold: float = 0.3,
    hyde_model: str = 'gemma3:4b',
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform a HyDE search using the embedding manager.

    Args:
        embedding_manager: The embedding manager to use
        query: The search query
        max_results: Maximum number of results to return
        threshold: Similarity threshold
        hyde_model: Model to use for generating hypothetical abstracts
        model_name: Model name to use (defaults to embedding_manager's model_name)

    Returns:
        Dictionary with results and abstract
    """
    try:
        # First get the hypothetical abstract
        hypothetical_abstract = generate_hypothetical_abstract(
            question=query,
            model=hyde_model
        )

        # Create embedding of the hypothetical abstract
        if not hypothetical_abstract:
            return {
                'results': [],
                'abstract': "Failed to generate hypothetical abstract."
            }

        # Use the model name from the embedding manager if not specified
        if model_name is None:
            model_name = embedding_manager.model_name

        # Create a direct embedding of the hypothetical abstract
        try:
            hyde_embedding = embedding_manager.create_embedding(hypothetical_abstract)
        except Exception as e:
            logger.error(f"Error creating HyDE embedding: {e}")
            return {
                'results': [],
                'abstract': hypothetical_abstract
            }

        # Get the embedding source ID
        from localknowledge.db.embedding_source import get_embedding_source_by_name

        results = []
        with get_cursor() as cursor:
            # Get the embedding source ID
            embed_source_record = get_embedding_source_by_name(cursor, 'abstract')

            if not embed_source_record:
                logger.error("Embedding source 'abstract' not found")
                return {
                    'results': [],
                    'abstract': hypothetical_abstract
                }

            embed_source_id = embed_source_record['id']

            # Convert the embedding list to a PostgreSQL vector
            # For pgvector, we need to pass the embedding as a string in the format '[0.1, 0.2, ...]'
            embedding_str = str(hyde_embedding)

            query_sql = """
            SELECT e.*, s.name as embed_source,
                   (e.embedding <=> vector(%s)) as distance,
                   1 - (e.embedding <=> vector(%s)) as similarity,
                   d.id, d.title, d.abstract, d.source_id, d.authors
            FROM unified_multiembeddings e
            JOIN embedding_source s ON e.embed_source_id = s.id
            JOIN document d ON e.document_id = d.id
            WHERE e.embed_source_id = %s
            AND e.model_name = %s
            AND 1 - (e.embedding <=> vector(%s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
            """

            cursor.execute(
                query_sql,
                (embedding_str, embedding_str, embed_source_id, model_name, embedding_str, threshold, max_results)
            )

            results = [dict(row) for row in cursor.fetchall()]

        return {
            'results': results,
            'abstract': hypothetical_abstract
        }
    except Exception as e:
        logger.error(f"Error in HyDE search: {e}\n{traceback.format_exc()}")
        return {
            'results': [],
            'abstract': None
        }


def deduplicate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate documents from a list of search results.

    Args:
        results: List of search results

    Returns:
        Deduplicated list of search results
    """
    # Use a dictionary to track seen document IDs
    seen_ids = {}
    unique_results = []

    for result in results:
        doc_id = result.get('id')

        # Skip if we've already seen this document ID
        if doc_id in seen_ids:
            continue

        # Mark this document ID as seen and add to unique results
        seen_ids[doc_id] = True
        unique_results.append(result)

    return unique_results


def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    reranker_model: str = 'BAAI/bge-reranker-base'
) -> List[Dict[str, Any]]:
    """
    Rerank search results using a reranker model.

    Args:
        query: The original search query
        results: List of search results to rerank
        reranker_model: Name of the reranker model to use

    Returns:
        Reranked list of search results
    """
    try:
        # Import in a safer way
        try:
            from localknowledge.ai.rerankers import get_reranker
            reranker = get_reranker(reranker_model)

            if reranker and results:
                # Limit the number of documents to rerank to avoid memory issues
                max_rerank = min(len(results), 50)  # Rerank up to 50 documents
                to_rerank = results[:max_rerank]

                # Rerank the limited set
                reranked = reranker.rerank(query, to_rerank)

                # Combine with any remaining results
                if max_rerank < len(results):
                    return reranked + results[max_rerank:]
                else:
                    return reranked

            # Return original results if no reranker or no results
            return results
        except ImportError:
            logger.warning("Rerankers module not available")
            return results
    except Exception as e:
        logger.error(f"Error during reranking: {e}\n{traceback.format_exc()}")
        # Continue with original results if reranking fails
        return results


def perform_hybrid_search(
    embedding_manager: EmbeddingManager,
    query: str,
    max_results: int = 10,
    threshold: float = 0.3,
    use_reranker: bool = False,
    reranker_model: str = 'BAAI/bge-reranker-base',
    hyde_model: str = 'gemma3:4b',
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform a hybrid search that combines semantic and HyDE search results.

    Args:
        embedding_manager: The embedding manager to use
        query: The search query
        max_results: Maximum number of results to return
        threshold: Similarity threshold
        use_reranker: Whether to use reranking
        reranker_model: Reranker model to use
        hyde_model: Model to use for generating hypothetical abstracts
        model_name: Model name to use (defaults to embedding_manager's model_name)

    Returns:
        Dictionary with combined results and HyDE abstract
    """
    try:
        # Calculate how many results to get from each method
        # We'll get max_results from each method and then combine them
        method_max_results = max(max_results, 20)  # Get at least 20 from each method

        # Perform semantic search
        semantic_results = perform_semantic_search(
            embedding_manager=embedding_manager,
            query=query,
            max_results=method_max_results,
            threshold=threshold,
            model_name=model_name
        )

        # Perform HyDE search
        hyde_result = perform_hyde_search(
            embedding_manager=embedding_manager,
            query=query,
            max_results=method_max_results,
            threshold=threshold,
            hyde_model=hyde_model,
            model_name=model_name
        )

        hyde_results = hyde_result.get('results', [])
        hypothetical_abstract = hyde_result.get('abstract')

        # Mark results with their source method
        for result in semantic_results:
            result['search_source'] = 'semantic'

        for result in hyde_results:
            result['search_source'] = 'hyde'

        # Combine results
        combined_results = semantic_results + hyde_results

        # Deduplicate results, keeping track of which methods found each document
        seen_ids = {}
        unique_results = []

        for result in combined_results:
            doc_id = result.get('id')
            search_source = result.get('search_source', '')

            if doc_id in seen_ids:
                # If we've seen this document before, update its search_source
                # to indicate it was found by multiple methods
                for unique_result in unique_results:
                    if unique_result.get('id') == doc_id:
                        current_source = unique_result.get('search_source', '')
                        if search_source and search_source not in current_source:
                            if current_source:
                                unique_result['search_source'] = f"{current_source}+{search_source}"
                            else:
                                unique_result['search_source'] = search_source
                        break
            else:
                # Mark this document ID as seen and add to unique results
                seen_ids[doc_id] = True
                unique_results.append(result)

        # Apply reranking if requested
        if use_reranker and unique_results:
            reranked_results = rerank_results(
                query=query,
                results=unique_results,
                reranker_model=reranker_model
            )

            # Limit to max_results
            final_results = reranked_results[:max_results]
        else:
            # Sort by similarity (highest first)
            sorted_results = sorted(
                unique_results,
                key=lambda x: x.get('similarity', 0),
                reverse=True
            )

            # Limit to max_results
            final_results = sorted_results[:max_results]

        return {
            'results': final_results,
            'abstract': hypothetical_abstract
        }
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}\n{traceback.format_exc()}")
        return {
            'results': [],
            'abstract': None
        }
