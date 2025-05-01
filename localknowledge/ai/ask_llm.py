import ollama
import json
from pydantic import BaseModel
from functools import lru_cache

thinking_model_series = ['qwen3', 'qwq']

@lru_cache(maxsize=100)
def is_thinking_model(model_name: str) -> bool:
    return any(model_name.startswith(series) for series in thinking_model_series)

def generate_answer(question: str, model_name: str = "gemma3:4b",
                    model_options: dict = None,
                    pydantic_model: BaseModel = None,
                    enable_thinking=False) -> str:
    """Generate an answer to a question using Ollama, depending on whether the model has a thinkng option or not."""

    if not model_options:
        model_options={}

    #if the model starts with any of the strings in thinking_model_series, add option "enable_thinking"
    if is_thinking_model(model_name):
        model_options["enable_thinking"] = enable_thinking
        if not enable_thinking:
            question = f"{question}</nothink>"

    response=ollama.generate(model=model_name,
                          prompt=question,
                          format=pydantic_model.model_json_schema() if pydantic_model else None,
                          options=model_options)
    if pydantic_model:
        return json.loads(response.response) #response.model_dump_json()

    return response.response

if __name__=="__main__":
    from pprint import pprint
    #import json

    class Answer(BaseModel):
        rating: int
        reason: str

    text = """Abstract
Systemic lupus erythematosus (SLE) is a rare, autoimmune disorder known to affect most organ sites.
Complicating clinical management is a poorly differentiated, heterogenous SLE disease state.
While some small molecule drugs and biologics are available for treatment, additional therapeutic options are needed.
Parsing complex biological signatures using powerful, yet human interpretable approaches is critical to advancing
our understanding of SLE etiology and identifying therapeutic repositioning opportunities.
To approach this goal, we developed a semi-supervised deep neural network pipeline for gene expression profiling of
SLE patients and subsequent characterization of individual gene features. Our pipeline performed exemplar multinomial
classification of SLE patients in independent balanced validation (F1=0.956) and unbalanced, under-powered testing
(F1=0.944) cohorts. A stacked autoencoder disambiguated individual feature representativeness by regenerating an
input-like(A ') feature matrix. A to A' comparisons suggest the top associated features to be key features in gene
expression profiling using neural nets."""

    prompt = """You are a medical expert. You are evaluating a text for its relevance to a research question.
Consider carefully how likely the provided text will contribute towards answering the question.
The research question is: {question}
The text is: {document}
Please rate the text on a scale of 0 to 3, where 0 means the document is not relevant at all,
1 means the document is somewhat relevant, tangentially related to the question.
2 means the document is very likely relevant to answer the question, it should not be missed.
3 means the document answers the question, it is essential and must be included in the reading list.
Provide a brief reason for your rating in no more than 3 brief sentences. Keep it short.
Answer in json format in the form of {{"rating": <rating>, "reason": "<reason>"}}.
"""
    models = ["gemma3:4b", "gemma3:12b-it-q8_0", "qwen3:1.7b-q8_0", "qwen3:4b", "qwen3:8b", "phi4:latest"]

    #now let's analyze performance of these models by running the question for each model 11 times,
    # discarding the results of the first run so as not to count model loading time.
    # - see how long it takes to generate an answer (min, max, avg, mean)
    # - see whether the rating is consistent (same answer all runs)
    # then printthe result in tabular form

    import time
    import statistics
    from tabulate import tabulate

    # Define the research question
    research_question = "is machine learning or AI superior to nurses in triaging patients?"

    # Prepare the formatted prompt
    formatted_prompt = prompt.format(question=research_question, document=text)

    # Number of runs per model (plus one warm-up run)
    num_runs = 11

    # Results storage
    results = []

    print(f"Analyzing performance of {len(models)} models with {num_runs-1} runs each (excluding warm-up run)...")

    for model_name in models:
        print(f"\nTesting model: {model_name}")

        # Performance metrics
        execution_times = []
        ratings = []

        # Warm-up run (discard result to avoid counting model loading time)
        print("  Performing warm-up run...")
        _ = generate_answer(
            question=formatted_prompt,
            model_name=model_name,
            enable_thinking=False,
            pydantic_model=Answer
        )

        # Actual test runs
        for i in range(1, num_runs):
            print(f"  Run {i}/{num_runs-1}...", end="", flush=True)

            # Measure execution time
            start_time = time.time()

            answer = generate_answer(
                question=formatted_prompt,
                model_name=model_name,
                enable_thinking=False,
                pydantic_model=Answer
            )

            end_time = time.time()
            execution_time = end_time - start_time
            execution_times.append(execution_time)

            # Store rating
            ratings.append(answer["rating"])

            print(f" completed in {execution_time:.2f}s (rating: {answer['rating']})")

        # Calculate statistics
        min_time = min(execution_times)
        max_time = max(execution_times)
        avg_time = sum(execution_times) / len(execution_times)
        median_time = statistics.median(execution_times)

        # Check rating consistency
        is_consistent = len(set(ratings)) == 1
        consistency = "Yes" if is_consistent else "No"
        rating_mode = statistics.mode(ratings)
        rating_distribution = {rating: ratings.count(rating) for rating in set(ratings)}

        # Store results for this model
        results.append([
            model_name,
            f"{min_time:.2f}s",
            f"{max_time:.2f}s",
            f"{avg_time:.2f}s",
            f"{median_time:.2f}s",
            consistency,
            rating_mode,
            str(rating_distribution)
        ])

    # Display results in tabular form
    headers = [
        "Model",
        "Min Time",
        "Max Time",
        "Avg Time",
        "Median Time",
        "Consistent Rating",
        "Most Common Rating",
        "Rating Distribution"
    ]

    # Sort results by average execution time (fastest first)
    results.sort(key=lambda x: float(x[3].rstrip('s')))

    print("\nPerformance Analysis Results (sorted by average execution time):")
    print(tabulate(results, headers=headers, tablefmt="grid"))

    # Add a summary of findings
    print("\nSummary of Findings:")

    # Find the fastest model
    fastest_model = results[0][0]
    fastest_time = results[0][3]
    print(f"- Fastest model (by average time): {fastest_model} ({fastest_time})")

    # Find the most consistent model in terms of execution time
    min_variance_model = min([(model, float(max_t.rstrip('s')) - float(min_t.rstrip('s')))
                             for model, min_t, max_t, *_ in results], key=lambda x: x[1])
    print(f"- Most consistent execution time: {min_variance_model[0]} (variance: {min_variance_model[1]:.2f}s)")

    # Check if all models agree on the rating
    ratings = [row[6] for row in results]
    if len(set(ratings)) == 1:
        print(f"- All models agree on the rating: {ratings[0]}")
    else:
        print(f"- Models disagree on ratings: {', '.join([f'{model}: {rating}' for model, *_, rating, _ in results])}")

    # Run one final example to show the full response
    print("\nExample full response from the fastest model (by average time):")
    fastest_model = results[0][0]  # We already sorted by average time

    final_answer = generate_answer(
        question=formatted_prompt,
        model_name=fastest_model,
        enable_thinking=False,
        pydantic_model=Answer
    )

    print(f"Model: {fastest_model}")
    print(f"Rating: {final_answer['rating']}")
    print(f"Reason: {final_answer['reason']}")

    # Show detailed reasoning from each model
    print("\nDetailed Reasoning from Each Model:")
    for model_name in [row[0] for row in results]:
        print(f"\n{model_name}:")
        model_answer = generate_answer(
            question=formatted_prompt,
            model_name=model_name,
            enable_thinking=False,
            pydantic_model=Answer
        )
        print(f"  Rating: {model_answer['rating']}")
        print(f"  Reason: {model_answer['reason']}")
