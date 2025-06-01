"""
Unit tests for the LocalKnowledge AI agent.

These tests verify the functionality of the pydantic-ai agent,
including web search capabilities and local database integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

from localknowledge.ai.agent import (
    LocalKnowledgeAgent,
    AgentResponse,
    AgentContext,
    ask_agent,
    ask_agent_sync,
    DEFAULT_MODEL,
    DEFAULT_EMBEDDING_MODEL
)
from localknowledge.ai.tools import WebSearchTool, URLFetchTool


class TestAgentResponse:
    """Test the AgentResponse model."""
    
    def test_agent_response_creation(self):
        """Test creating an AgentResponse."""
        response = AgentResponse(
            answer="This is a test answer",
            sources=[{"title": "Test", "url": "http://example.com"}],
            search_performed=True,
            confidence=0.8
        )
        
        assert response.answer == "This is a test answer"
        assert len(response.sources) == 1
        assert response.search_performed is True
        assert response.confidence == 0.8
    
    def test_agent_response_defaults(self):
        """Test AgentResponse with default values."""
        response = AgentResponse(answer="Test answer")
        
        assert response.answer == "Test answer"
        assert response.sources == []
        assert response.search_performed is False
        assert response.confidence == 0.0


class TestAgentContext:
    """Test the AgentContext dataclass."""
    
    def test_agent_context_creation(self):
        """Test creating an AgentContext."""
        context = AgentContext(
            user_id=123,
            project_id=456,
            max_search_results=10,
            enable_web_search=True,
            enable_local_search=False
        )
        
        assert context.user_id == 123
        assert context.project_id == 456
        assert context.max_search_results == 10
        assert context.enable_web_search is True
        assert context.enable_local_search is False
    
    def test_agent_context_defaults(self):
        """Test AgentContext with default values."""
        context = AgentContext()
        
        assert context.user_id is None
        assert context.project_id is None
        assert context.max_search_results == 5
        assert context.enable_web_search is True
        assert context.enable_local_search is True


class TestLocalKnowledgeAgent:
    """Test the LocalKnowledgeAgent class."""
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.OpenAIProvider')
    @patch('localknowledge.ai.agent.Agent')
    def test_agent_initialization(self, mock_agent, mock_provider, mock_openai, mock_db, mock_web_search):
        """Test agent initialization."""
        agent = LocalKnowledgeAgent(
            model_name="test-model",
            embedding_model="test-embedding",
            enable_web_search=True,
            enable_local_search=True
        )
        
        assert agent.model_name == "test-model"
        assert agent.embedding_model == "test-embedding"
        assert agent.enable_web_search is True
        assert agent.enable_local_search is True
        
        # Verify tools were initialized
        mock_web_search.assert_called_once()
        mock_db.assert_called_once()
        mock_openai.assert_called_once()
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.OpenAIProvider')
    @patch('localknowledge.ai.agent.Agent')
    def test_agent_initialization_disabled_tools(self, mock_agent, mock_provider, mock_openai, mock_db, mock_web_search):
        """Test agent initialization with disabled tools."""
        agent = LocalKnowledgeAgent(
            enable_web_search=False,
            enable_local_search=False
        )
        
        assert agent.web_search_tool is None
        assert agent.db_manager is None
        
        # Verify tools were not initialized
        mock_web_search.assert_not_called()
        mock_db.assert_not_called()
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.Agent')
    def test_agent_run(self, mock_agent_class, mock_openai, mock_db, mock_web_search):
        """Test running the agent."""
        # Setup mocks
        mock_agent_instance = Mock()
        mock_agent_class.return_value = mock_agent_instance
        mock_result = Mock()
        mock_result.output = AgentResponse(answer="Test answer")
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        
        agent = LocalKnowledgeAgent()
        
        # Test async run
        async def test_async():
            result = await agent.run("Test question")
            assert result.output.answer == "Test answer"
            mock_agent_instance.run.assert_called_once()

        asyncio.run(test_async())
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.Agent')
    def test_agent_run_sync(self, mock_agent_class, mock_openai, mock_db, mock_web_search):
        """Test running the agent synchronously."""
        # Setup mocks
        mock_agent_instance = Mock()
        mock_agent_class.return_value = mock_agent_instance
        mock_result = Mock()
        mock_result.output = AgentResponse(answer="Test answer")
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        
        agent = LocalKnowledgeAgent()
        
        # Test sync run
        result = agent.run_sync("Test question")
        assert result.output.answer == "Test answer"
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.OpenAIProvider')
    @patch('localknowledge.ai.agent.Agent')
    def test_agent_close(self, mock_agent, mock_provider, mock_openai, mock_db, mock_web_search):
        """Test closing the agent."""
        mock_db_instance = Mock()
        mock_web_search_instance = Mock()
        mock_db.return_value = mock_db_instance
        mock_web_search.return_value = mock_web_search_instance
        
        agent = LocalKnowledgeAgent()
        agent.close()
        
        # Verify cleanup methods were called
        mock_db_instance.close.assert_called_once()
        mock_web_search_instance.close.assert_called_once()
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    async def test_web_search_wrapper(self, mock_openai, mock_db, mock_web_search):
        """Test the web search wrapper method."""
        mock_web_search_instance = Mock()
        mock_web_search_instance.search = AsyncMock(return_value=[
            {"title": "Test", "url": "http://example.com", "snippet": "Test snippet"}
        ])
        mock_web_search.return_value = mock_web_search_instance
        
        agent = LocalKnowledgeAgent()
        context = AgentContext()
        
        results = await agent._web_search_wrapper(context, "test query", 5)
        
        assert len(results) == 1
        assert results[0]["title"] == "Test"
        mock_web_search_instance.search.assert_called_once_with("test query", 5)
    
    @patch('localknowledge.ai.agent.WebSearchTool')
    @patch('localknowledge.ai.agent.DocumentDatabaseManager')
    @patch('localknowledge.ai.agent.OpenAIModel')
    @patch('localknowledge.ai.agent.DocumentSearchManager')
    async def test_local_search_wrapper(self, mock_search_manager_class, mock_openai, mock_db, mock_web_search):
        """Test the local search wrapper method."""
        mock_search_manager = Mock()
        mock_search_manager.semantic.return_value = [
            {"title": "Local Doc", "content": "Test content"}
        ]
        mock_search_manager_class.return_value = mock_search_manager
        
        agent = LocalKnowledgeAgent()
        context = AgentContext()
        
        results = await agent._local_search_wrapper(context, "test query", 5, 0.5)
        
        assert len(results) == 1
        assert results[0]["title"] == "Local Doc"


class TestConvenienceFunctions:
    """Test the convenience functions."""
    
    @patch('localknowledge.ai.agent.LocalKnowledgeAgent')
    async def test_ask_agent(self, mock_agent_class):
        """Test the ask_agent convenience function."""
        mock_agent = Mock()
        mock_result = Mock()
        mock_result.data = AgentResponse(answer="Test answer")
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent
        
        result = await ask_agent("Test question")
        
        assert result.answer == "Test answer"
        mock_agent.close.assert_called_once()
    
    @patch('localknowledge.ai.agent.LocalKnowledgeAgent')
    def test_ask_agent_sync(self, mock_agent_class):
        """Test the ask_agent_sync convenience function."""
        mock_agent = Mock()
        mock_result = Mock()
        mock_result.data = AgentResponse(answer="Test answer")
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent
        
        result = ask_agent_sync("Test question")
        
        assert result.answer == "Test answer"
        mock_agent.close.assert_called_once()


class TestWebSearchTool:
    """Test the WebSearchTool class."""
    
    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization."""
        tool = WebSearchTool(
            search_engine="duckduckgo",
            timeout=15,
            max_retries=5
        )
        
        assert tool.search_engine == "duckduckgo"
        assert tool.timeout == 15
        assert tool.max_retries == 5
    
    @patch('aiohttp.ClientSession')
    async def test_duckduckgo_search(self, mock_session_class):
        """Test DuckDuckGo search functionality."""
        # Mock the aiohttp session and response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "AbstractText": "Test abstract",
            "Heading": "Test heading",
            "AbstractURL": "http://example.com"
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session
        
        tool = WebSearchTool(search_engine="duckduckgo")
        results = await tool.search("test query", max_results=5)
        
        assert len(results) >= 1
        assert results[0]["title"] == "Test heading"
        assert results[0]["url"] == "http://example.com"
        assert results[0]["snippet"] == "Test abstract"
    
    def test_web_search_tool_close(self):
        """Test WebSearchTool cleanup."""
        tool = WebSearchTool()
        tool.close()  # Should not raise any exceptions


class TestURLFetchTool:
    """Test the URLFetchTool class."""
    
    def test_url_fetch_tool_initialization(self):
        """Test URLFetchTool initialization."""
        tool = URLFetchTool(timeout=15)
        assert tool.timeout == 15
    
    @patch('aiohttp.ClientSession')
    async def test_fetch_content(self, mock_session_class):
        """Test fetching content from a URL."""
        # Mock the aiohttp session and response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "<html><head><title>Test Title</title></head><body><p>Test content</p></body></html>"
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session
        
        tool = URLFetchTool()
        result = await tool.fetch_content("http://example.com")
        
        assert result["title"] == "Test Title"
        assert "Test content" in result["content"]
        assert result["url"] == "http://example.com"
        assert result["status"] == "success"
    
    def test_url_fetch_tool_close(self):
        """Test URLFetchTool cleanup."""
        tool = URLFetchTool()
        tool.close()  # Should not raise any exceptions


if __name__ == "__main__":
    pytest.main([__file__])
