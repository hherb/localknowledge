#!/usr/bin/env python3
"""
Simple test script for the LocalKnowledge AI agent.

This script performs a basic test to verify the agent works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from localknowledge.ai.agent import LocalKnowledgeAgent


async def simple_test():
    """Simple test of the agent functionality."""
    print("Testing LocalKnowledge AI Agent...")
    
    try:
        # Create an agent with minimal configuration
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",  # Use a model suitable for tool use
            enable_web_search=False,  # Disable web search for simplicity
            enable_local_search=False  # Disable local search for simplicity
        )
        
        print("Agent created successfully!")
        
        # Ask a simple question
        question = "What is 2 + 2?"
        print(f"Question: {question}")
        
        result = await agent.run(question)
        
        print(f"Answer: {result.output.answer}")
        print(f"Confidence: {result.output.confidence}")
        
        # Close the agent
        agent.close()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        print("Make sure Ollama is running and has the qwen3:8b model available.")
        print("You can install it with: ollama pull qwen3:8b")


if __name__ == "__main__":
    asyncio.run(simple_test())
