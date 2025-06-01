#!/usr/bin/env python3
"""
Example script demonstrating streaming responses from the LocalKnowledge AI agent.

This script shows how to use the streaming capabilities to get faster time-to-first-token
and real-time response updates.

Requirements:
- Ollama must be running locally
- A model must be available (e.g., qwen3:8b)

Usage:
    python streaming_example.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from localknowledge.ai.agent import LocalKnowledgeAgent, ask_agent_stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_streaming():
    """Test basic streaming functionality."""
    print("=" * 60)
    print("Testing Basic Streaming")
    print("=" * 60)
    
    try:
        # Create an agent
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=False,  # Disable for faster response
            enable_local_search=False
        )
        
        question = "Explain quantum computing in simple terms."
        print(f"Question: {question}")
        print("Streaming response:")
        print("-" * 40)
        
        # Stream the response
        full_response = ""
        async for event in agent.stream_events(question):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
                full_response += event.content
            elif event.event_type == "final_result":
                print("\n" + "-" * 40)
                print(f"Final answer: {event.metadata.get('answer', 'No answer')}")
                print(f"Confidence: {event.metadata.get('confidence', 0.0)}")
                print(f"Search performed: {event.metadata.get('search_performed', False)}")
            elif event.event_type == "error":
                print(f"\nError: {event.content}")
        
        # Close the agent
        agent.close()
        
    except Exception as e:
        logger.error(f"Basic streaming test failed: {e}")
        print(f"Error: {e}")


async def test_streaming_with_search():
    """Test streaming with web search enabled."""
    print("\n" + "=" * 60)
    print("Testing Streaming with Web Search")
    print("=" * 60)
    
    try:
        question = "What are the latest developments in AI in 2024?"
        print(f"Question: {question}")
        print("Streaming response with search:")
        print("-" * 40)
        
        # Use the convenience function
        full_response = ""
        async for event in ask_agent_stream(
            question=question,
            model_name="qwen3:8b",
            enable_web_search=True,
            enable_local_search=False
        ):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
                full_response += event.content
            elif event.event_type == "final_result":
                print("\n" + "-" * 40)
                print(f"Final answer: {event.metadata.get('answer', 'No answer')}")
                print(f"Sources found: {len(event.metadata.get('sources', []))}")
                print(f"Search performed: {event.metadata.get('search_performed', False)}")
                print(f"Confidence: {event.metadata.get('confidence', 0.0)}")
                
                # Show sources if available
                sources = event.metadata.get('sources', [])
                if sources:
                    print("\nSources:")
                    for i, source in enumerate(sources[:3], 1):
                        print(f"  {i}. {source.get('title', 'Unknown title')}")
                        print(f"     URL: {source.get('url', 'No URL')}")
            elif event.event_type == "error":
                print(f"\nError: {event.content}")
        
    except Exception as e:
        logger.error(f"Streaming with search test failed: {e}")
        print(f"Error: {e}")


async def test_low_level_streaming():
    """Test low-level streaming using run_stream directly."""
    print("\n" + "=" * 60)
    print("Testing Low-Level Streaming")
    print("=" * 60)
    
    try:
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=False,
            enable_local_search=False
        )
        
        question = "What is machine learning?"
        print(f"Question: {question}")
        print("Low-level streaming response:")
        print("-" * 40)
        
        # Use the low-level text streaming interface
        async with agent.run_stream_text(question) as response:
            # Stream text chunks
            async for chunk in response.stream_text():
                print(chunk, end="", flush=True)

            # Get the final output
            final_output = await response.get_output()
            print("\n" + "-" * 40)
            print(f"Final output type: {type(final_output)}")
            print(f"Answer: {final_output}")
        
        agent.close()
        
    except Exception as e:
        logger.error(f"Low-level streaming test failed: {e}")
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
    """Main function to run all streaming tests."""
    print("LocalKnowledge AI Agent Streaming Example")
    print("=" * 60)
    
    # Check if Ollama is available
    if not check_ollama_availability():
        print("\nPlease start Ollama and try again.")
        return
    
    # Run streaming tests
    await test_basic_streaming()
    await test_streaming_with_search()
    await test_low_level_streaming()
    
    print("\n" + "=" * 60)
    print("All streaming tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStreaming example interrupted by user")
    except Exception as e:
        logger.error(f"Streaming example failed: {e}")
        print(f"Error: {e}")
