#!/usr/bin/env python3
"""
Test script to verify the DuckDuckGo search tool integration.
"""

import asyncio
import logging
from localknowledge.ai.agent import LocalKnowledgeAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_duckduckgo_search():
    """Test the DuckDuckGo search integration."""
    print("Testing DuckDuckGo search integration...")
    
    try:
        # Create an agent with web search enabled
        agent = LocalKnowledgeAgent(
            model_name="qwen3:8b",
            enable_web_search=True,
            enable_local_search=False  # Disable local search for this test
        )
        
        # Test a simple question that should trigger web search
        question = "What is the current weather in New York?"
        print(f"Question: {question}")
        print("Searching...")
        
        result = await agent.run(question)
        
        print(f"Answer: {result.output.answer}")
        print(f"Sources: {len(result.output.sources)}")
        print(f"Search performed: {result.output.search_performed}")
        print(f"Confidence: {result.output.confidence}")
        
        # Close the agent
        agent.close()
        
        print("✅ DuckDuckGo search integration test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_duckduckgo_search())
