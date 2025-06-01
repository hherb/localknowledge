#!/usr/bin/env python3
"""
Test script for the extended reasoning functionality in LocalKnowledge AI agent.

This script demonstrates how to use the extended reasoning mode
with the LocalKnowledge agent.
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to the path so we can import localknowledge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from localknowledge.ai.agent import LocalKnowledgeAgent, ask_agent_sync, append_thinking_command, is_thinking_model

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_append_thinking_command():
    """Test the append_thinking_command function."""
    print("=" * 60)
    print("Testing append_thinking_command function")
    print("=" * 60)

    test_cases = [
        ("What is AI?", False, True, "What is AI? /no_think"),
        ("What is AI?", True, True, "What is AI? /think"),
        ("What is AI?", False, False, "What is AI?"),
        ("What is AI?", True, False, "What is AI?"),
    ]

    for message, enable_thinking, model_supports, expected in test_cases:
        result = append_thinking_command(message, enable_thinking, model_supports)
        status = "✓" if result == expected else "✗"
        print(f"{status} Message: '{message}', thinking={enable_thinking}, supports={model_supports}")
        print(f"    Expected: '{expected}'")
        print(f"    Got:      '{result}'")
        print()


async def test_agent_extended_reasoning():
    """Test the agent with extended reasoning modes."""
    print("=" * 60)
    print("Testing LocalKnowledge Agent with Extended Reasoning")
    print("=" * 60)

    # Test with extended reasoning disabled (default)
    print("\n1. Testing with extended reasoning DISABLED (default)")
    agent1 = LocalKnowledgeAgent(
        model_name="qwen3:8b",  # Use a thinking-capable model
        enable_web_search=False,  # Disable web search for faster testing
        enable_local_search=False,  # Disable local search for faster testing
        enable_extended_reasoning=False  # Default
    )

    try:
        result = await agent1.run("What is 2+2?")
        print(f"Answer: {result.output.answer}")
        print(f"Confidence: {result.output.confidence}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent1.close()

    print("-" * 40)

    # Test with extended reasoning enabled
    print("\n2. Testing with extended reasoning ENABLED")
    agent2 = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=False,
        enable_local_search=False,
        enable_extended_reasoning=True  # Enable extended reasoning
    )

    try:
        result = await agent2.run("What is 2+2?")
        print(f"Answer: {result.output.answer}")
        print(f"Confidence: {result.output.confidence}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent2.close()

    print("-" * 40)

    # Test toggling extended reasoning
    print("\n3. Testing toggling extended reasoning")
    agent3 = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=False,
        enable_local_search=False,
        enable_extended_reasoning=False
    )

    try:
        # First with extended reasoning disabled
        result1 = await agent3.run("Explain photosynthesis")
        print(f"Without extended reasoning: {result1.output.answer[:100]}...")

        # Toggle to enable extended reasoning
        agent3.extended_reasoning(True)
        result2 = await agent3.run("Explain photosynthesis")
        print(f"With extended reasoning: {result2.output.answer[:100]}...")

        # Toggle back to disable
        agent3.extended_reasoning(False)
        result3 = await agent3.run("Explain photosynthesis")
        print(f"Back to fast mode: {result3.output.answer[:100]}...")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent3.close()


def test_sync_convenience_function():
    """Test the synchronous convenience function."""
    print("=" * 60)
    print("Testing Synchronous Convenience Function")
    print("=" * 60)

    # Test with extended reasoning disabled
    print("\n1. Testing sync function with extended reasoning DISABLED")
    try:
        result1 = ask_agent_sync(
            question="What is the square root of 16?",
            model_name="qwen3:8b",
            enable_web_search=False,
            enable_local_search=False,
            enable_extended_reasoning=False
        )
        print(f"Answer: {result1.answer}")
        print(f"Confidence: {result1.confidence}")
    except Exception as e:
        print(f"Error: {e}")

    print("-" * 40)

    # Test with extended reasoning enabled
    print("\n2. Testing sync function with extended reasoning ENABLED")
    try:
        result2 = ask_agent_sync(
            question="What is the square root of 16?",
            model_name="qwen3:8b",
            enable_web_search=False,
            enable_local_search=False,
            enable_extended_reasoning=True
        )
        print(f"Answer: {result2.answer}")
        print(f"Confidence: {result2.confidence}")
    except Exception as e:
        print(f"Error: {e}")


async def test_streaming_with_extended_reasoning():
    """Test streaming functionality with extended reasoning modes."""
    print("=" * 60)
    print("Testing Streaming with Extended Reasoning")
    print("=" * 60)

    # Test streaming without extended reasoning
    print("\n1. Streaming WITHOUT extended reasoning")
    agent1 = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=False,
        enable_local_search=False,
        enable_extended_reasoning=False
    )

    try:
        print("Question: Explain photosynthesis briefly")
        print("Streaming response:")
        print("-" * 20)

        async for event in agent1.stream_events("Explain photosynthesis briefly"):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
            elif event.event_type == "final_result":
                print("\n" + "-" * 20)
                print("Stream completed")
                break
            elif event.event_type == "error":
                print(f"\nError: {event.content}")
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent1.close()

    print("\n" + "=" * 40)

    # Test streaming with extended reasoning
    print("\n2. Streaming WITH extended reasoning")
    agent2 = LocalKnowledgeAgent(
        model_name="qwen3:8b",
        enable_web_search=False,
        enable_local_search=False,
        enable_extended_reasoning=True
    )

    try:
        print("Question: Explain photosynthesis step by step")
        print("Streaming response:")
        print("-" * 20)

        async for event in agent2.stream_events("Explain photosynthesis step by step"):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
            elif event.event_type == "final_result":
                print("\n" + "-" * 20)
                print("Stream completed")
                break
            elif event.event_type == "error":
                print(f"\nError: {event.content}")
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent2.close()


async def main():
    """Main test function."""
    print("LocalKnowledge AI Agent - Extended Reasoning Test")
    print("=" * 60)

    # Test 1: Append thinking command function
    test_append_thinking_command()

    # Test 2: Model compatibility
    print("\nTesting model compatibility...")
    models = ['qwen3:8b', 'gemma3:4b', 'qwq:latest', 'deepseek-r1:latest', 'llama3:8b']
    for model in models:
        supports = is_thinking_model(model)
        print(f"Model: {model} -> Supports extended reasoning: {supports}")

    # Test 3: Agent with extended reasoning modes
    print("\nTesting agent with extended reasoning modes...")
    await test_agent_extended_reasoning()

    # Test 4: Synchronous convenience function
    print("\nTesting synchronous convenience function...")
    test_sync_convenience_function()

    # Test 5: Streaming with extended reasoning
    print("\nTesting streaming with extended reasoning...")
    await test_streaming_with_extended_reasoning()

    print("\n" + "=" * 60)
    print("All tests completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
