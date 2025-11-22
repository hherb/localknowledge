"""
AI module for LocalKnowledge.

This module provides AI-powered features for search, evaluation, summarization,
and agent-based interactions with the knowledge base.

Key components:
- LocalKnowledgeAgent: Pydantic-AI agent with web search capabilities
- DocumentEvaluator: AI-powered document relevance evaluation
- NewsFinder: Discovery of relevant new publications
- HyDE: Hypothetical Document Embeddings for improved search
- Summarizer: Document summarization
- QAFinder: Question extraction and answering
"""

from localknowledge.ai.agent import LocalKnowledgeAgent, AgentResponse
from localknowledge.ai.document_evaluator import (
    DocumentEvaluator,
    EvaluationResponse,
    DocumentOfInterest,
)
from localknowledge.ai.newsfinder import NewsFinder, NewsItem
from localknowledge.ai.ask_llm import generate_answer, is_thinking_model
from localknowledge.ai.qafinder import find_questions
from localknowledge.ai.summarizer import summarize_interesting_text
from localknowledge.ai.HyDE import generate_hypothetical_abstract
from localknowledge.ai.hybrid_search import (
    perform_semantic_search,
    perform_hyde_search,
    perform_hybrid_search,
)

__all__ = [
    # Agent
    "LocalKnowledgeAgent",
    "AgentResponse",
    # Document evaluation
    "DocumentEvaluator",
    "EvaluationResponse",
    "DocumentOfInterest",
    # News discovery
    "NewsFinder",
    "NewsItem",
    # LLM utilities
    "generate_answer",
    "is_thinking_model",
    # QA functionality
    "find_questions",
    # Summarization
    "summarize_interesting_text",
    # HyDE search
    "generate_hypothetical_abstract",
    # Hybrid search
    "perform_semantic_search",
    "perform_hyde_search",
    "perform_hybrid_search",
]
