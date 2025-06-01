"""
Pydantic-AI Agent module for LocalKnowledge.

This module provides a pydantic-ai agent that uses Ollama LLMs and includes
web search functionality using the official pydantic-ai DuckDuckGo search tool.
The agent can answer questions, perform web searches, and integrate with the
LocalKnowledge database.

Example usage:
    from localknowledge.ai.agent import LocalKnowledgeAgent

    agent = LocalKnowledgeAgent()
    result = await agent.run("What is the latest research on COVID-19 vaccines?")
    print(result.output)
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

from ..db.document import DocumentDatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

# Default models
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_EMBEDDING_MODEL = "snowflake-arctic-embed2:latest"

# Thinking model series that support reasoning
THINKING_MODEL_SERIES = ['qwen3', 'qwq', 'deepseek-r1']


class AgentResponse(BaseModel):
    """Response model for the LocalKnowledge agent."""

    answer: str = Field(description="The agent's answer to the user's question")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of sources used to answer the question"
    )
    search_performed: bool = Field(
        default=False,
        description="Whether a web search was performed"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score for the answer (0.0 to 1.0)"
    )


class StreamingEvent(BaseModel):
    """Event model for streaming responses."""

    event_type: str = Field(description="Type of streaming event")
    content: str = Field(default="", description="Content delta for text events")
    tool_name: Optional[str] = Field(default=None, description="Tool name for tool events")
    tool_args: Optional[Dict[str, Any]] = Field(default=None, description="Tool arguments")
    tool_result: Optional[str] = Field(default=None, description="Tool result")
    is_final: bool = Field(default=False, description="Whether this is the final event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


@dataclass
class AgentContext:
    """Context for the LocalKnowledge agent."""

    user_id: Optional[int] = None
    project_id: Optional[int] = None
    max_search_results: int = 5
    enable_web_search: bool = True
    enable_local_search: bool = True


def is_thinking_model(model_name: str) -> bool:
    """Check if the model supports thinking/reasoning capabilities."""
    return any(model_name.startswith(series) for series in THINKING_MODEL_SERIES)


def append_thinking_command(message: str, enable_thinking: bool, model_supports_thinking: bool) -> str:
    """
    Append thinking command to message for thinking-capable models.

    Args:
        message: The original message
        enable_thinking: Whether extended reasoning is enabled
        model_supports_thinking: Whether the model supports thinking

    Returns:
        Message with appropriate thinking command appended
    """
    if not model_supports_thinking:
        return message

    if enable_thinking:
        return f"{message} /think"
    else:
        return f"{message} /no_think"


class LocalKnowledgeAgent:
    """
    A pydantic-ai agent that uses Ollama LLMs and can perform web searches.

    This agent can:
    - Answer questions using Ollama models
    - Perform web searches using the official pydantic-ai DuckDuckGo tool
    - Search the local knowledge database
    - Provide structured responses with sources

    Attributes:
        model_name: The Ollama model to use for generation
        embedding_model: The model to use for embeddings
        enable_web_search: Whether web search is enabled
        enable_local_search: Whether local search is enabled
        db_manager: Database manager for local searches
        agent: The pydantic-ai agent instance
        text_agent: The pydantic-ai text agent for streaming
    """
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        ollama_host: str = "http://localhost:11434",
        enable_web_search: bool = True,
        enable_local_search: bool = True,
        enable_extended_reasoning: bool = False
    ):
        """
        Initialize the LocalKnowledge agent.

        Args:
            model_name: The Ollama model to use for generation
            embedding_model: The model to use for embeddings
            ollama_host: The Ollama server URL
            enable_web_search: Whether to enable web search functionality
            enable_local_search: Whether to enable local database search
            enable_extended_reasoning: Whether to enable extended reasoning by default
        """
        self.model_name = model_name
        self.embedding_model = embedding_model
        self.ollama_host = ollama_host
        self.enable_web_search = enable_web_search
        self.enable_local_search = enable_local_search
        self.enable_extended_reasoning = enable_extended_reasoning

        # Check if this model supports thinking
        self.supports_thinking = is_thinking_model(model_name)

        # Initialize tools
        self.db_manager = DocumentDatabaseManager() if enable_local_search else None

        # Initialize the Ollama model using OpenAI-compatible API
        self.model = OpenAIModel(
            model_name=model_name,
            provider=OpenAIProvider(
                base_url=f"{ollama_host}/v1",
                api_key="ollama"  # Mock API key for Ollama
            )
        )

        # Create the agent
        self._create_agent()

        # Create a text-only agent for streaming
        self._create_text_agent()

        logger.info(f"Initialized LocalKnowledge agent with model {model_name} (thinking support: {self.supports_thinking}, extended reasoning: {self.enable_extended_reasoning})")

    def extended_reasoning(self, enable: bool) -> None:
        """
        Toggle extended reasoning mode.

        Args:
            enable: True to enable extended reasoning, False to disable
        """
        self.enable_extended_reasoning = enable
        logger.info(f"Extended reasoning {'enabled' if enable else 'disabled'} for model {self.model_name}")

    def _get_system_prompt(self) -> str:
        """
        Get the standard system prompt.

        Returns:
            The system prompt for the agent
        """
        return """You are a helpful AI assistant for the LocalKnowledge system.

You can search the web for current information and access a local knowledge database
containing medical and scientific literature.

When answering questions:
1. Use web search for current events, recent developments, or information not in the local database
2. Use local search for established medical/scientific knowledge and research papers
3. Combine information from multiple sources when helpful
4. Always cite your sources and indicate confidence levels
5. Be clear about the recency and reliability of information

Note: Extended reasoning mode is controlled by /think and /no_think commands appended to messages."""

    def _create_agent(self) -> None:
        """Create the pydantic-ai agent with tools and system prompt."""

        # Use standard system prompt
        system_prompt = self._get_system_prompt()
        system_prompt += """

Always structure your responses clearly and include relevant sources."""

        # Prepare tools list
        tools = []
        if self.enable_web_search:
            tools.append(duckduckgo_search_tool())

        # Create the agent with AgentContext as deps type
        self.agent = Agent(
            model=self.model,
            output_type=AgentResponse,
            system_prompt=system_prompt,
            deps_type=AgentContext,
            tools=tools
        )

        # Register local search tool if available
        if self.db_manager:
            self.agent.tool(self._local_search_wrapper)

    def _create_text_agent(self) -> None:
        """Create a text-only agent for true streaming."""

        # Use standard system prompt
        system_prompt = self._get_system_prompt()
        system_prompt += """

Provide clear, concise answers in plain text."""

        # Prepare tools list
        tools = []
        if self.enable_web_search:
            tools.append(duckduckgo_search_tool())

        # Create a text-only agent (no structured output)
        self.text_agent = Agent(
            model=self.model,
            output_type=str,  # Text output for streaming
            system_prompt=system_prompt,
            deps_type=AgentContext,
            tools=tools
        )

        # Register local search tool if available
        if self.db_manager:
            self.text_agent.tool(self._local_search_wrapper)

    async def _local_search_wrapper(
        self,
        _ctx: RunContext[AgentContext],
        query: str,
        max_results: int = 5,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search the local knowledge database.
        
        Args:
            ctx: The run context
            query: The search query
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of documents from the local database
        """
        if not self.db_manager:
            return []
        
        try:
            # Use the document search functionality
            from ..db.document_search import DocumentSearchManager
            
            search_manager = DocumentSearchManager()
            search_manager.embedding_model = self.embedding_model
            
            # Perform semantic search
            results = list(search_manager.semantic(
                question=query,
                similarity_threshold=similarity_threshold,
                max_results=max_results
            ))
            
            logger.info(f"Local search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Local search failed: {e}")
            return []
    
    async def run(
        self,
        user_input: str,
        context: Optional[AgentContext] = None
    ) -> Any:
        """
        Run the agent with user input.

        Args:
            user_input: The user's question or request
            context: Optional context for the agent

        Returns:
            The agent's response
        """
        if context is None:
            context = AgentContext()

        # Append thinking command based on current setting
        processed_input = append_thinking_command(
            user_input,
            self.enable_extended_reasoning,
            self.supports_thinking
        )

        # Log extended reasoning mode if model supports it
        if self.supports_thinking:
            mode = "extended reasoning" if self.enable_extended_reasoning else "fast mode"
            logger.info(f"Running in {mode} for input: {user_input[:50]}...")

        try:
            result = await self.agent.run(processed_input, message_history=[], deps=context)
            logger.info(f"Agent completed successfully for input: {user_input[:50]}...")
            return result
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            raise

    def run_stream(
        self,
        user_input: str,
        context: Optional[AgentContext] = None
    ):
        """
        Run the agent with streaming output.

        Args:
            user_input: The user's question or request
            context: Optional context for the agent

        Returns:
            StreamedRunResult context manager for streaming the response
        """
        if context is None:
            context = AgentContext()

        # Append thinking command based on current setting
        processed_input = append_thinking_command(
            user_input,
            self.enable_extended_reasoning,
            self.supports_thinking
        )

        # Log extended reasoning mode if model supports it
        if self.supports_thinking:
            mode = "extended reasoning" if self.enable_extended_reasoning else "fast mode"
            logger.info(f"Streaming in {mode} for input: {user_input[:50]}...")

        try:
            logger.info(f"Agent streaming started for input: {user_input[:50]}...")
            return self.agent.run_stream(processed_input, message_history=[], deps=context)
        except Exception as e:
            logger.error(f"Agent streaming failed: {e}")
            raise

    def run_stream_text(
        self,
        user_input: str,
        context: Optional[AgentContext] = None
    ):
        """
        Run the text agent with streaming output for true text streaming.

        Args:
            user_input: The user's question or request
            context: Optional context for the agent

        Returns:
            StreamedRunResult context manager for streaming text responses
        """
        if context is None:
            context = AgentContext()

        # Append thinking command based on current setting
        processed_input = append_thinking_command(
            user_input,
            self.enable_extended_reasoning,
            self.supports_thinking
        )

        # Log extended reasoning mode if model supports it
        if self.supports_thinking:
            mode = "extended reasoning" if self.enable_extended_reasoning else "fast mode"
            logger.info(f"Text streaming in {mode} for input: {user_input[:50]}...")

        try:
            logger.info(f"Agent text streaming started for input: {user_input[:50]}...")
            return self.text_agent.run_stream(processed_input, message_history=[], deps=context)
        except Exception as e:
            logger.error(f"Agent text streaming failed: {e}")
            raise

    async def stream_events(
        self,
        user_input: str,
        context: Optional[AgentContext] = None
    ) -> AsyncIterator[StreamingEvent]:
        """
        Stream events from the agent run with a simplified interface.

        Args:
            user_input: The user's question or request
            context: Optional context for the agent

        Yields:
            StreamingEvent objects with simplified event information
        """
        if context is None:
            context = AgentContext()

        try:
            # Use the text agent for true streaming (thinking mode is handled in run_stream_text)
            async with self.run_stream_text(user_input, context) as response:
                collected_text = ""

                # Stream text chunks
                async for chunk in response.stream_text():
                    collected_text += chunk
                    yield StreamingEvent(
                        event_type="text_delta",
                        content=chunk,
                        is_final=False
                    )

                # Get the final result (which is just a string for text agent)
                final_result = await response.get_output()

                yield StreamingEvent(
                    event_type="final_result",
                    content="",
                    is_final=True,
                    metadata={
                        "answer": final_result,
                        "sources": [],  # Text agent doesn't track sources separately
                        "search_performed": True,  # Assume search was available
                        "confidence": 1.0  # Text agent doesn't provide confidence
                    }
                )
        except Exception as e:
            logger.error(f"Agent streaming events failed: {e}")
            yield StreamingEvent(
                event_type="error",
                content=str(e),
                is_final=True
            )

    def run_sync(
        self,
        user_input: str,
        context: Optional[AgentContext] = None
    ) -> Any:
        """
        Run the agent synchronously.
        
        Args:
            user_input: The user's question or request
            context: Optional context for the agent
            
        Returns:
            The agent's response
        """
        return asyncio.run(self.run(user_input, context))
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.db_manager:
            self.db_manager.close()

        logger.info("LocalKnowledge agent closed")


# Convenience function for quick usage
async def ask_agent(
    question: str,
    model_name: str = DEFAULT_MODEL,
    enable_web_search: bool = True,
    enable_local_search: bool = True,
    enable_extended_reasoning: bool = False
) -> AgentResponse:
    """
    Convenience function to quickly ask a question using the agent.

    Args:
        question: The question to ask
        model_name: The Ollama model to use
        enable_web_search: Whether to enable web search
        enable_local_search: Whether to enable local search
        enable_extended_reasoning: Whether to enable extended reasoning mode

    Returns:
        The agent's response
    """
    agent = LocalKnowledgeAgent(
        model_name=model_name,
        enable_web_search=enable_web_search,
        enable_local_search=enable_local_search,
        enable_extended_reasoning=enable_extended_reasoning
    )

    try:
        result = await agent.run(question)
        return result.output
    finally:
        agent.close()


def ask_agent_sync(
    question: str,
    model_name: str = DEFAULT_MODEL,
    enable_web_search: bool = True,
    enable_local_search: bool = True,
    enable_extended_reasoning: bool = False
) -> AgentResponse:
    """
    Synchronous version of ask_agent.

    Args:
        question: The question to ask
        model_name: The Ollama model to use
        enable_web_search: Whether to enable web search
        enable_local_search: Whether to enable local search
        enable_extended_reasoning: Whether to enable extended reasoning mode

    Returns:
        The agent's response
    """
    return asyncio.run(ask_agent(
        question=question,
        model_name=model_name,
        enable_web_search=enable_web_search,
        enable_local_search=enable_local_search,
        enable_extended_reasoning=enable_extended_reasoning
    ))


# Streaming convenience functions
async def ask_agent_stream(
    question: str,
    model_name: str = DEFAULT_MODEL,
    enable_web_search: bool = True,
    enable_local_search: bool = True,
    enable_extended_reasoning: bool = False
) -> AsyncIterator[StreamingEvent]:
    """
    Convenience function to stream a question using the agent.

    Args:
        question: The question to ask
        model_name: The Ollama model to use
        enable_web_search: Whether to enable web search
        enable_local_search: Whether to enable local search
        enable_extended_reasoning: Whether to enable extended reasoning mode

    Yields:
        StreamingEvent objects with response chunks and final result
    """
    agent = LocalKnowledgeAgent(
        model_name=model_name,
        enable_web_search=enable_web_search,
        enable_local_search=enable_local_search,
        enable_extended_reasoning=enable_extended_reasoning
    )

    try:
        async for event in agent.stream_events(question):
            yield event
    finally:
        agent.close()
