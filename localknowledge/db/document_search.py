"""
Document search functionality for the LocalKnowledge library.

This module provides specialized search functions for documents using the unified document table.
It focuses on using the all_keywords column for keyword searches and will be expanded to include
other search methods like fulltext, semantic, HyDE, and hybrid searches.
"""

import logging
import time
import threading
import concurrent.futures
import ollama
import backoff
from psycopg2.extras import DictCursor
from typing import List, Dict, Any, Optional, Generator, Tuple, Union, Callable

from localknowledge.db.base import DatabaseManager
from localknowledge.db.connection_pool import get_connection
from localknowledge.db.embeddings import get_embeddings_db, EmbeddingsDatabaseManager
from localknowledge.db.embedding_source import get_embedding_source_db
from localknowledge.ai.HyDE import generate_hypothetical_abstract, get_embedding_from_text

# Configure logging
logger = logging.getLogger(__name__)


class DocumentSearchManager(DatabaseManager):
    """Database manager for document search operations."""

    def __init__(self):
        """Initialize the document search manager."""
        super().__init__()
        self.embedding_model = "snowflake-arctic-embed2:latest"
        self.embeddings_db = get_embeddings_db()

    def _get_model_provider(self, model_name: str) -> str:
        """
        Get the provider for a model.

        Args:
            model_name: Name of the model

        Returns:
            Provider name or "unknown" if not found
        """
        query = """
        SELECT p.provider_name
        FROM embedding_models m
        JOIN embedding_provider p ON m.provider_id = p.id
        WHERE m.model_name = %s
        """
        result = self.execute(query, (model_name,))

        if result and len(result) > 0:
            return result[0]['provider_name']

        logger.warning(f"Provider not found for model: {model_name}")
        return "unknown"

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for the given text using the appropriate embedder.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as a list of floats
        """
        try:
            # Get the provider for the model
            provider = self._get_model_provider(self.embedding_model)

            # Use the appropriate embedder based on the provider
            if provider == "ollama":
                # Use Ollama embedder
                from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
                embedder = OllamaEmbedder(model_name=self.embedding_model)
                return embedder.embed(text)
            elif provider.startswith("pubmedbert"):
                # Use PubMedBERT embedder
                from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder
                embedder = PubMedBERTEmbedder(model_name=self.embedding_model)
                return embedder.embed(text)
            else:
                # Default to Ollama embedder
                logger.warning(f"Unknown provider '{provider}', defaulting to Ollama embedder")
                response = ollama.embeddings(model=self.embedding_model, prompt=text)

                # Handle the response based on its type
                if hasattr(response, 'embedding'):
                    # New Ollama client returns a Pydantic model
                    embedding = response.embedding
                elif isinstance(response, dict) and 'embedding' in response:
                    # Old Ollama client returns a dictionary
                    embedding = response['embedding']
                else:
                    logger.error(f"Unexpected response format from Ollama: {type(response)}")
                    return []

                return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise

    def keywords(self,
                included: List[str],
                excluded: Optional[List[str]] = None,
                source_name: Optional[str] = None,
                limit: int = 100,
                offset: int = 0,
                batch_size: int = 100,
                timeout: Optional[int] = 30,
                async_mode: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        Search for documents using the all_keywords column with GIN index.

        This method uses the efficient array operators pattern with the all_keywords column
        that combines keywords, augmented_keywords, and mesh_terms into a single array.

        The results are returned as a generator that yields documents in batches to avoid
        loading all results into memory at once, which is useful for large result sets.

        This method is threadsafe and can be run in asynchronous mode for long-running queries.

        Args:
            included: List of keywords to include in the search
            excluded: List of keywords to exclude from the search (optional)
            source_name: Filter by source name (optional)
            limit: Maximum number of results to return (use 0 for no limit)
            offset: Number of results to skip
            batch_size: Number of results to fetch in each database query
            timeout: Query timeout in seconds (default: 30, None for no timeout)
            async_mode: Whether to run the query in asynchronous mode (default: False)

        Returns:
            Generator yielding matching documents
        """
        # Normalize keywords to lowercase
        included = [term.lower() for term in included if term]

        if not included:
            logger.warning("No include terms provided for keyword search")
            return

        logger.debug(f"DocumentSearchManager.keywords: Include terms: {included}")

        # Convert include_terms to a string representation for the ARRAY constructor
        include_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in included) + "]"

        # Build the base query without LIMIT/OFFSET
        query = f"""
        SELECT d.*, s.name as source_name, c.name as category_name
        FROM document d
        JOIN sources s ON d.source_id = s.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.all_keywords && {include_array_str}
        """

        # Add exclusion terms if provided
        if excluded and len(excluded) > 0:
            excluded = [term.lower() for term in excluded]
            logger.debug(f"DocumentSearchManager.keywords: Exclude terms: {excluded}")

            # Convert exclude_terms to a string representation for the ARRAY constructor
            exclude_array_str = "ARRAY[" + ", ".join(f"'{term}'" for term in excluded) + "]"

            query += f"""
            AND NOT (d.all_keywords && {exclude_array_str})
            """

        # Add source filter if provided
        if source_name:
            source_id = self.get_source_id(source_name)
            if source_id:
                query += f" AND d.source_id = {source_id}"

        # Add ordering
        query += f" ORDER BY d.publication_date DESC NULLS LAST"

        # Create a result queue for asynchronous mode
        result_queue = []
        stop_event = threading.Event()
        error_info = [None]

        # Define the batch fetching function that will run in a separate thread
        def fetch_batches():
            try:
                # Use a separate connection for thread safety
                with get_connection() as conn:
                    # Set statement timeout if specified
                    if timeout is not None:
                        with conn.cursor() as timeout_cursor:
                            timeout_cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # Convert to milliseconds

                    # Initialize counters
                    current_offset = offset
                    total_fetched = 0

                    # Fetch results in batches
                    while not stop_event.is_set():
                        # Add LIMIT and OFFSET for this batch
                        current_batch_size = min(batch_size, limit - total_fetched) if limit > 0 else batch_size
                        if current_batch_size <= 0:
                            break

                        batch_query = f"{query} LIMIT {current_batch_size} OFFSET {current_offset}"

                        logger.debug(f"DocumentSearchManager.keywords: Executing batch query (offset={current_offset}, limit={current_batch_size})")
                        logger.debug(f"DocumentSearchManager.keywords: SQL Query: {batch_query}")

                        # Execute the query directly with cursor to avoid loading all results at once
                        with conn.cursor(cursor_factory=DictCursor) as cursor:
                            start_time = time.time()
                            cursor.execute(batch_query, ())
                            execution_time = time.time() - start_time
                            logger.debug(f"Batch query executed in {execution_time:.2f} seconds")

                            # Get the number of rows in this batch
                            row_count = cursor.rowcount
                            logger.debug(f"DocumentSearchManager.keywords: Batch returned {row_count} results")

                            # No more results
                            if row_count == 0:
                                break

                            # Add each row to the result queue
                            batch_results = [dict(row) for row in cursor]
                            result_queue.extend(batch_results)
                            total_fetched += len(batch_results)

                            # Update offset for next batch
                            current_offset += row_count

                            # If we got fewer rows than requested, we've reached the end
                            if row_count < current_batch_size or (limit > 0 and total_fetched >= limit):
                                break

                    logger.debug(f"DocumentSearchManager.keywords: Search completed, fetched {total_fetched} results")

            except Exception as e:
                logger.error(f"DocumentSearchManager.keywords: Error during search: {e}")
                import traceback
                error_info[0] = (e, traceback.format_exc())
                logger.error(traceback.format_exc())
            finally:
                # Signal that we're done fetching
                stop_event.set()

        # If running in asynchronous mode, start a separate thread for fetching
        if async_mode:
            fetch_thread = threading.Thread(target=fetch_batches, daemon=True)
            fetch_thread.start()

            # Yield results as they become available
            last_index = 0
            while True:
                # Check if there are new results
                if last_index < len(result_queue):
                    # Yield all new results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                # Check if we're done
                if stop_event.is_set():
                    # Yield any remaining results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                    # Check if there was an error
                    if error_info[0] is not None:
                        e, traceback_str = error_info[0]
                        logger.error(f"Async search error: {e}")
                        logger.error(traceback_str)
                        # Don't raise the exception, just log it and stop yielding

                    break

                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)
        else:
            # In synchronous mode, just run the fetch function directly
            try:
                fetch_batches()

                # Yield all results
                for result in result_queue:
                    yield result

                # Check if there was an error
                if error_info[0] is not None:
                    e, traceback_str = error_info[0]
                    raise e

            except Exception as e:
                logger.error(f"DocumentSearchManager.keywords: Error during search: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return

    def semantic(self,
                question: str,
                similarity_threshold: float = 0.5,
                max_results: int = 50,
                source_name: Optional[str] = None,
                embed_source: str = 'abstract',
                timeout: Optional[int] = 30,
                async_mode: bool = False,
                reranker: Optional[Callable] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Perform semantic search using embeddings.

        This method creates an embedding for the question and searches for similar documents
        in the database. It returns a generator that yields documents in order of similarity.

        Args:
            question: The question or query to search for
            similarity_threshold: Minimum similarity score (0-1) for results
            max_results: Maximum number of results to return
            source_name: Filter by source name (optional)
            embed_source: Embedding source to search (default: 'abstract')
            timeout: Query timeout in seconds (default: 30, None for no timeout)
            async_mode: Whether to run the query in asynchronous mode (default: False)
            reranker: Optional function to rerank results (takes question and results as input)

        Returns:
            Generator yielding matching documents with similarity scores
        """
        logger.debug(f"DocumentSearchManager.semantic: Query: {question}")

        # Create a result queue for asynchronous mode
        result_queue = []
        stop_event = threading.Event()
        error_info = [None]

        # Define the search function that will run in a separate thread
        def perform_search():
            try:
                # Get the embeddings database manager
                embeddings_db = get_embeddings_db()

                # Get the embedding source database manager
                embedding_source_db = get_embedding_source_db()

                # Create embedding for the question
                query_embedding = self.create_embedding(question)

                if not query_embedding:
                    logger.error("Failed to create query embedding")
                    error_info[0] = (ValueError("Failed to create query embedding"), "")
                    return

                # Get source_id if source_name is provided
                source_id = None
                if source_name:
                    source_id = self.get_source_id(source_name)
                    if not source_id:
                        logger.warning(f"Source '{source_name}' not found")

                # Set statement timeout if specified
                if timeout is not None:
                    with embeddings_db.connection.cursor() as timeout_cursor:
                        timeout_cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # Convert to milliseconds

                # Search for similar documents
                logger.debug(f"Searching for similar documents with threshold={similarity_threshold}")

                # Get the embed_source_id
                embed_source_record = embedding_source_db.get_embedding_source_by_name(embed_source)
                if not embed_source_record:
                    logger.error(f"Embedding source '{embed_source}' not found")
                    error_info[0] = (ValueError(f"Embedding source '{embed_source}' not found"), "")
                    return

                embed_source_id = embed_source_record['id']

                # Perform the search
                search_results = embeddings_db.search_similar(
                    embedding=query_embedding,
                    embed_source=embed_source_id,
                    model_name=self.embedding_model,
                    limit=max_results,
                    threshold=similarity_threshold
                )

                logger.debug(f"Search returned {len(search_results)} results")

                # Apply reranking if provided
                if reranker and search_results:
                    try:
                        search_results = reranker(question, search_results)
                        logger.debug(f"Reranking applied, now have {len(search_results)} results")
                    except Exception as e:
                        logger.error(f"Error during reranking: {e}")

                # Filter by source if needed
                if source_id:
                    search_results = [r for r in search_results if r.get('source_id') == source_id]
                    logger.debug(f"After source filtering: {len(search_results)} results")

                # Add results to the queue
                result_queue.extend(search_results)

            except Exception as e:
                logger.error(f"DocumentSearchManager.semantic: Error during search: {e}")
                import traceback
                error_info[0] = (e, traceback.format_exc())
                logger.error(traceback.format_exc())
            finally:
                # Signal that we're done searching
                stop_event.set()

        # If running in asynchronous mode, start a separate thread for searching
        if async_mode:
            search_thread = threading.Thread(target=perform_search, daemon=True)
            search_thread.start()

            # Yield results as they become available
            last_index = 0
            while True:
                # Check if there are new results
                if last_index < len(result_queue):
                    # Yield all new results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                # Check if we're done
                if stop_event.is_set():
                    # Yield any remaining results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                    # Check if there was an error
                    if error_info[0] is not None:
                        e, traceback_str = error_info[0]
                        logger.error(f"Async search error: {e}")
                        logger.error(traceback_str)
                        # Don't raise the exception, just log it and stop yielding

                    break

                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)
        else:
            # In synchronous mode, just run the search function directly
            try:
                perform_search()

                # Yield all results
                for result in result_queue:
                    yield result

                # Check if there was an error
                if error_info[0] is not None:
                    e, traceback_str = error_info[0]
                    raise e

            except Exception as e:
                logger.error(f"DocumentSearchManager.semantic: Error during search: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return

    def hyde(self,
                question: str,
                similarity_threshold: float = 0.5,
                max_results: int = 50,
                source_name: Optional[str] = None,
                embed_source: str = 'abstract',
                timeout: Optional[int] = 30,
                async_mode: bool = False,
                reranker: Optional[Callable] = None,
                hydeprompt: Optional[str] = None,
                model_name: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Perform semantic search using Hypothetical Document Embeddings (HyDE).

        This method generates a hypothetical document that answers the question,
        creates an embedding for that document, and then searches for similar documents.
        It returns a generator that yields documents in order of similarity.

        Args:
            question: The question or query to search for
            similarity_threshold: Minimum similarity score (0-1) for results
            max_results: Maximum number of results to return
            source_name: Filter by source name (optional)
            embed_source: Embedding source to search (default: 'abstract')
            timeout: Query timeout in seconds (default: 30, None for no timeout)
            async_mode: Whether to run the query in asynchronous mode (default: False)
            reranker: Optional function to rerank results (takes question and results as input)
            hydeprompt: Optional pre-generated hypothetical document (if None, one will be generated)
            model_name: Model to use for generating the hypothetical document (default: gemma3:4b)

        Returns:
            Generator yielding matching documents with similarity scores
        """
        logger.debug(f"DocumentSearchManager.hyde: Query: {question}")

        # Create a result queue for asynchronous mode
        result_queue = []
        stop_event = threading.Event()
        error_info = [None]

        # Define the search function that will run in a separate thread
        def perform_search():
            try:
                # Get the embeddings database manager
                embeddings_db = get_embeddings_db()

                # Get the embedding source database manager
                embedding_source_db = get_embedding_source_db()

                # Generate or use the provided hypothetical document
                if hydeprompt is None:
                    # Use default model if none specified
                    generation_model = model_name or "gemma3:4b"
                    logger.debug(f"Generating hypothetical document using model: {generation_model}")

                    # Generate the hypothetical document
                    hypothetical_doc = generate_hypothetical_abstract(question, model=generation_model)

                    if not hypothetical_doc:
                        logger.error("Failed to generate hypothetical document")
                        error_info[0] = (ValueError("Failed to generate hypothetical document"), "")
                        return

                    logger.debug(f"Generated hypothetical document ({len(hypothetical_doc)} chars)")
                else:
                    # Use the provided hypothetical document
                    hypothetical_doc = hydeprompt
                    logger.debug(f"Using provided hypothetical document ({len(hypothetical_doc)} chars)")

                # Create embedding for the hypothetical document
                embedding_model = self.embedding_model
                logger.debug(f"Creating embedding using model: {embedding_model}")

                hyde_embedding = get_embedding_from_text(hypothetical_doc, model=embedding_model)

                if not hyde_embedding:
                    logger.error("Failed to create embedding for hypothetical document")
                    error_info[0] = (ValueError("Failed to create embedding for hypothetical document"), "")
                    return

                # Get source_id if source_name is provided
                source_id = None
                if source_name:
                    source_id = self.get_source_id(source_name)
                    if not source_id:
                        logger.warning(f"Source '{source_name}' not found")

                # Set statement timeout if specified
                if timeout is not None:
                    with embeddings_db.connection.cursor() as timeout_cursor:
                        timeout_cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # Convert to milliseconds

                # Search for similar documents
                logger.debug(f"Searching for similar documents with threshold={similarity_threshold}")

                # Get the embed_source_id
                embed_source_record = embedding_source_db.get_embedding_source_by_name(embed_source)
                if not embed_source_record:
                    logger.error(f"Embedding source '{embed_source}' not found")
                    error_info[0] = (ValueError(f"Embedding source '{embed_source}' not found"), "")
                    return

                embed_source_id = embed_source_record['id']

                # Perform the search
                search_results = embeddings_db.search_similar(
                    embedding=hyde_embedding,
                    embed_source=embed_source_id,
                    model_name=embedding_model,
                    limit=max_results,
                    threshold=similarity_threshold
                )

                logger.debug(f"Search returned {len(search_results)} results")

                # Add the hypothetical document to the results for reference
                for result in search_results:
                    result['hyde_document'] = hypothetical_doc

                # Apply reranking if provided
                if reranker and search_results:
                    try:
                        search_results = reranker(question, search_results)
                        logger.debug(f"Reranking applied, now have {len(search_results)} results")
                    except Exception as e:
                        logger.error(f"Error during reranking: {e}")

                # Filter by source if needed
                if source_id:
                    search_results = [r for r in search_results if r.get('source_id') == source_id]
                    logger.debug(f"After source filtering: {len(search_results)} results")

                # Add results to the queue
                result_queue.extend(search_results)

            except Exception as e:
                logger.error(f"DocumentSearchManager.hyde: Error during search: {e}")
                import traceback
                error_info[0] = (e, traceback.format_exc())
                logger.error(traceback.format_exc())
            finally:
                # Signal that we're done searching
                stop_event.set()

        # If running in asynchronous mode, start a separate thread for searching
        if async_mode:
            search_thread = threading.Thread(target=perform_search, daemon=True)
            search_thread.start()

            # Yield results as they become available
            last_index = 0
            while True:
                # Check if there are new results
                if last_index < len(result_queue):
                    # Yield all new results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                # Check if we're done
                if stop_event.is_set():
                    # Yield any remaining results
                    while last_index < len(result_queue):
                        yield result_queue[last_index]
                        last_index += 1

                    # Check if there was an error
                    if error_info[0] is not None:
                        e, traceback_str = error_info[0]
                        logger.error(f"Async search error: {e}")
                        logger.error(traceback_str)
                        # Don't raise the exception, just log it and stop yielding

                    break

                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)
        else:
            # In synchronous mode, just run the search function directly
            try:
                perform_search()

                # Yield all results
                for result in result_queue:
                    yield result

                # Check if there was an error
                if error_info[0] is not None:
                    e, traceback_str = error_info[0]
                    raise e

            except Exception as e:
                logger.error(f"DocumentSearchManager.hyde: Error during search: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return

    def get_source_id(self, source_name: str) -> Optional[int]:
        """
        Get the ID for a source by name.

        Args:
            source_name: Name of the source (e.g., 'pubmed', 'medrxiv')

        Returns:
            Source ID or None if not found
        """
        query = "SELECT id FROM sources WHERE name = %s"
        result = self.execute(query, (source_name,))
        return result[0]['id'] if result else None
