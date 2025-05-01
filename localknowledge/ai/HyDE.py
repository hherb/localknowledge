#!/usr/bin/env python3
"""
Hypothetical Document Embeddings (HyDE) module for semantic search enhancement.

This module implements the HyDE technique, which improves semantic search by generating
a hypothetical document that answers a query, then using that document's embedding
for search instead of directly embedding the query.

Reference:
Gao, L., Ma, X., Lin, J., & Callan, J. (2022). Precise Zero-Shot Dense Retrieval without Relevance Labels.
https://arxiv.org/abs/2212.10496
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union

import ollama

# Configure logging
logger = logging.getLogger(__name__)

# Template for generating hypothetical abstracts
HYDE_PROMPT_TEMPLATE = """Generate a hypothetical PubMed abstract section that answers a medical question.
Example:
<example> Question: What is the cut-off for ultrasound optic nerve sheath diameter (ONSD) for diagnosing raised intracranial pressure (ICP) in adults?

Hypothetical Abstract:

Objective: To determine the optimal cut-off value for optic nerve sheath diameter (ONSD) measured by ultrasound in identifying elevated intracranial pressure (ICP) among adult patients.
Methods: In this prospective study, adult patients with suspected increased ICP underwent bedside ultrasound to measure ONSD, which was then compared to invasive ICP measurements.
Results: The study identified an ONSD threshold of 5.7 mm as the most accurate cut-off for detecting ICP levels exceeding 20 mmHg, yielding a sensitivity of 90% and specificity of 85%.
Conclusion: Ultrasound-measured ONSD is a reliable, non-invasive tool for screening raised ICP in adults, with 5.7 mm as the recommended diagnostic cut-off.
</example>
here is the question - answer in the style of the example provided and with nothing else.
<question>{question}</question>. """


def format_hyde_prompt(question: str) -> str:
    """
    Format the HyDE prompt with the given question.

    Args:
        question: The medical question to generate a hypothetical abstract for

    Returns:
        Formatted prompt string
    """
    return HYDE_PROMPT_TEMPLATE.format(question=question)


def generate_hypothetical_abstract(question: str, model: str = "gemma3:4b") -> str:
    """
    Generate a hypothetical abstract that answers the given question.

    Args:
        question: The medical question to generate a hypothetical abstract for
        model: The Ollama model to use for generation (default: gemma3:4b)

    Returns:
        Generated hypothetical abstract as a string
    """
    prompt = format_hyde_prompt(question)
    try:
        response = ollama.generate(model=model, prompt=prompt)
        logger.debug(f"Generated abstract with model {model} ({len(response.response)} chars)")
        return response.response
    except Exception as e:
        logger.error(f"Error generating abstract with model {model}: {e}")
        return ""


def get_embedding_from_text(text: str, model: str = "snowflake-arctic-embed2:latest") -> List[float]:
    """
    Get embedding vector for the given text using the specified model.

    Args:
        text: The text to embed
        model: The model to use for embedding (default: snowflake-arctic-embed2:latest)

    Returns:
        Embedding vector as a list of floats
    """
    try:
        # Get the provider for the model
        from localknowledge.db.embeddings import get_embeddings_db
        embeddings_db = get_embeddings_db()

        # Query for the provider
        query = """
        SELECT p.provider_name
        FROM embedding_models m
        JOIN embedding_provider p ON m.provider_id = p.id
        WHERE m.model_name = %s
        """
        result = embeddings_db.execute(query, (model,))

        provider = "unknown"
        if result and len(result) > 0:
            provider = result[0]['provider_name']

        # Use the appropriate embedder based on the provider
        if provider == "ollama":
            # Use Ollama embedder
            from localknowledge.embeddings.ollama_embedder import OllamaEmbedder
            embedder = OllamaEmbedder(model_name=model)
            return embedder.embed(text)
        elif provider.startswith("pubmedbert"):
            # Use PubMedBERT embedder
            from localknowledge.embeddings.pubmed_embedder import PubMedBERTEmbedder
            embedder = PubMedBERTEmbedder(model_name=model)
            return embedder.embed(text)
        else:
            # Default to Ollama embedder
            logger.warning(f"Unknown provider '{provider}' for model '{model}', defaulting to Ollama embedder")
            response = ollama.embeddings(model=model, prompt=text)

            # Handle the response based on its type
            if hasattr(response, 'embedding'):
                # New Ollama client returns a Pydantic model
                return response.embedding
            elif isinstance(response, dict) and 'embedding' in response:
                # Old Ollama client returns a dictionary
                return response['embedding']
            else:
                logger.error(f"Unexpected response format from Ollama: {type(response)}")
                return []
    except Exception as e:
        logger.error(f"Error getting embedding with model {model}: {e}")
        return []


def generate_hyde_embedding(question: str,
                           generation_model: str = "gemma3:4b",
                           embedding_model: str = "snowflake-arctic-embed2:latest") -> List[float]:
    """
    Generate a HyDE embedding for the given question.

    This is the main function that implements the HyDE technique:
    1. Generate a hypothetical abstract that answers the question
    2. Get the embedding of that abstract

    Args:
        question: The medical question to generate a HyDE embedding for
        generation_model: The model to use for generating the abstract (default: gemma3:4b)
        embedding_model: The model to use for embedding (default: snowflake-arctic-embed2:latest)

    Returns:
        HyDE embedding vector as a list of floats
    """
    # Generate hypothetical abstract
    hydetext = generate_hypothetical_abstract(question, model=generation_model)
    if not hydetext:
        logger.warning(f"Failed to generate abstract for question: {question}")
        return []

    # Get embedding
    return get_embedding_from_text(hydetext, model=embedding_model)


@dataclass
class BenchmarkItem:
    """
    Data class for storing benchmark results.

    Attributes:
        generated_text: The generated hypothetical abstract
        embedding: The embedding vector
        model: The model used for generation
        embedding_model: The model used for embedding
        time: The time taken in seconds
    """
    generated_text: str
    embedding: List[float]
    model: str
    embedding_model: str
    time: float


def run_benchmark(question: str,
                 rounds: int = 10,
                 models: List[str] = None,
                 embedding_model: str = "snowflake-arctic-embed2:latest") -> List[BenchmarkItem]:
    """
    Run a benchmark test for HyDE with different models.

    Args:
        question: The question to use for benchmarking
        rounds: Number of rounds to run for each model (default: 10)
        models: List of models to benchmark (default: ["gemma3:4b"])
        embedding_model: The model to use for embedding (default: snowflake-arctic-embed2:latest)

    Returns:
        List of benchmark results
    """
    from tqdm import tqdm

    if models is None:
        models = ["gemma3:4b"]

    results = []
    for model in models:
        logger.info(f"Benchmarking model {model}...")
        for _ in tqdm(range(rounds), desc=f"Model: {model}"):
            start_time = time.time()
            hydetext = generate_hypothetical_abstract(question, model=model)
            embedding = get_embedding_from_text(hydetext, model=embedding_model)
            end_time = time.time()
            benchmark = BenchmarkItem(
                generated_text=hydetext,
                embedding=embedding,
                model=model,
                embedding_model=embedding_model,
                time=end_time-start_time
            )
            results.append(benchmark)

    return results


def save_benchmark_results(results: List[BenchmarkItem], filename: str = "hyde_benchmarks.json") -> None:
    """
    Save benchmark results to a JSON file.

    Args:
        results: List of benchmark results
        filename: Name of the file to save to (default: "hyde_benchmarks.json")
    """
    # Convert results to serializable format
    serializable_results = [
        {
            "generated_text": item.generated_text,
            "model": item.model,
            "embedding_model": item.embedding_model,
            "time": item.time,
            # Don't include the full embedding vector in the JSON file
            "embedding_length": len(item.embedding) if item.embedding else 0
        }
        for item in results
    ]

    try:
        with open(filename, "w") as f:
            json.dump(serializable_results, f, indent=4)
        logger.info(f"Benchmark results saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving benchmark results: {e}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Define the test question
    QUESTION = """What is the cut-off for ultrasound optic nerve sheath diameter (ONSD) for diagnosing raised intracranial pressure (ICP) in adults?"""

    # Define models to benchmark
    models = [
        "gemma3:4b",
        "llama3.2:3b-instruct-q8_0",
        "qwen2.5:3b-instruct-q8_0"
    ]

    print(f"Benchmarking {len(models)} models: {models}")

    # Run benchmark
    start_time = time.time()
    results = run_benchmark(QUESTION, rounds=3, models=models)
    end_time = time.time()

    # Calculate statistics
    total_time = end_time - start_time
    avg_time_per_abstract = total_time / len(results) if results else 0

    print(f"Time taken: {total_time:.2f} seconds for {len(results)} embedded HyDE abstracts")
    print(f"Average time per abstract: {avg_time_per_abstract:.2f} seconds")

    # Save results to file
    save_benchmark_results(results)