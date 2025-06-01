#!/usr/bin/env python3
"""
Example script demonstrating the LocalKnowledge AI agent.

This script shows how to use the pydantic-ai agent with Ollama models
and web search functionality.

Requirements:
- Ollama must be running locally
- A model must be available (e.g., gemma3:4b)

Usage:
    python agent_example.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from localknowledge.ai.agent import LocalKnowledgeAgent, AgentContext, ask_agent_sync, ask_agent_stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_agent():
    """Test basic agent functionality."""
    print("=" * 60)
    print("Testing Basic Agent Functionality")
    print("=" * 60)
    
    try:
        # Create an agent
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=True,
            enable_local_search=False  # Disable local search for this example
        )
        
        # Ask a simple question
        question = "What is the capital of France?"
        print(f"Question: {question}")
        print("Thinking...")
        
        result = await agent.run(question)
        
        print(f"Answer: {result.output.answer}")
        print(f"Sources: {len(result.output.sources)}")
        print(f"Search performed: {result.output.search_performed}")
        print(f"Confidence: {result.output.confidence}")
        
        # Close the agent
        agent.close()
        
    except Exception as e:
        logger.error(f"Basic agent test failed: {e}")
        print(f"Error: {e}")


async def test_web_search_agent():
    """Test agent with web search."""
    print("\n" + "=" * 60)
    print("Testing Agent with Web Search")
    print("=" * 60)
    
    try:
        # Create an agent with web search enabled
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=True,
            enable_local_search=False
        )
        
        # Ask a question that might require web search
        question = "What are the latest developments in AI research in 2024?"
        print(f"Question: {question}")
        print("Searching and thinking...")
        
        result = await agent.run(question)
        
        print(f"Answer: {result.output.answer}")
        print(f"Number of sources: {len(result.output.sources)}")
        print(f"Search performed: {result.output.search_performed}")
        print(f"Confidence: {result.output.confidence}")

        # Show sources if available
        if result.output.sources:
            print("\nSources:")
            for i, source in enumerate(result.output.sources[:3], 1):
                print(f"  {i}. {source.get('title', 'Unknown title')}")
                print(f"     URL: {source.get('url', 'No URL')}")
                print(f"     Snippet: {source.get('snippet', 'No snippet')[:100]}...")
        
        # Close the agent
        agent.close()
        
    except Exception as e:
        logger.error(f"Web search agent test failed: {e}")
        print(f"Error: {e}")


def test_sync_agent():
    """Test synchronous agent usage."""
    print("\n" + "=" * 60)
    print("Testing Synchronous Agent")
    print("=" * 60)
    
    try:
        # Use the convenience function
        question = "Explain quantum computing in simple terms."
        print(f"Question: {question}")
        print("Thinking...")
        
        response = ask_agent_sync(
            question=question,
            model_name="qwen3:8b",
            enable_web_search=False,  # Disable web search for faster response
            enable_local_search=False
        )
        
        print(f"Answer: {response.answer}")
        print(f"Sources: {len(response.sources)}")
        print(f"Search performed: {response.search_performed}")
        print(f"Confidence: {response.confidence}")
        
    except Exception as e:
        logger.error(f"Sync agent test failed: {e}")
        print(f"Error: {e}")


async def test_streaming_agent():
    """Test agent with streaming responses."""
    print("\n" + "=" * 60)
    print("Testing Streaming Agent")
    print("=" * 60)

    try:
        question = "Explain the benefits of renewable energy in 3 key points."
        print(f"Question: {question}")
        print("Streaming response:")
        print("-" * 40)

        # Use the streaming convenience function
        full_response = ""
        async for event in ask_agent_stream(
            question=question,
            model_name="qwen3:8b",
            enable_web_search=False,  # Disable for faster response
            enable_local_search=False
        ):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
                full_response += event.content
            elif event.event_type == "final_result":
                print("\n" + "-" * 40)
                print(f"Confidence: {event.metadata.get('confidence', 0.0)}")
                print(f"Search performed: {event.metadata.get('search_performed', False)}")
            elif event.event_type == "error":
                print(f"\nError: {event.content}")

    except Exception as e:
        logger.error(f"Streaming agent test failed: {e}")
        print(f"Error: {e}")


async def test_agent_with_context():
    """Test agent with custom context."""
    print("\n" + "=" * 60)
    print("Testing Agent with Custom Context")
    print("=" * 60)
    
    try:
        # Create an agent
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=True,
            enable_local_search=False
        )
        
        # Create custom context
        context = AgentContext(
            user_id=123,
            project_id=456,
            max_search_results=3,
            enable_web_search=True,
            enable_local_search=False
        )
        
        # Ask a question with context
        question = "What are the benefits of renewable energy?"
        print(f"Question: {question}")
        print("Thinking with custom context...")
        
        result = await agent.run(question, context)
        
        print(f"Answer: {result.output.answer}")
        print(f"Sources: {len(result.output.sources)}")
        print(f"Search performed: {result.output.search_performed}")
        print(f"Confidence: {result.output.confidence}")
        
        # Close the agent
        agent.close()
        
    except Exception as e:
        logger.error(f"Context agent test failed: {e}")
        print(f"Error: {e}")


def check_ollama_availability():
    """Check if Ollama is available."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"Ollama is running with {len(models)} models available")
            for model in models[:3]:  # Show first 3 models
                print(f"  - {model.get('name', 'Unknown')}")
            return True
        else:
            print("Ollama is running but returned an error")
            return False
    except Exception as e:
        print(f"Ollama is not available: {e}")
        print("Please start Ollama and ensure a model is available (e.g., 'ollama run qwen3:8b')")
        return False


async def main():
    """Main function to run all tests."""
    print("LocalKnowledge AI Agent Example")
    print("=" * 60)
    
    # Check if Ollama is available
    if not check_ollama_availability():
        print("\nPlease start Ollama and try again.")
        return
    
    # Run tests
    await test_basic_agent()
    await test_web_search_agent()
    test_sync_agent()
    await test_streaming_agent()
    await test_agent_with_context()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}")
        print(f"Error: {e}")
