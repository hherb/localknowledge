"""
Tools for the LocalKnowledge AI agent.

This module provides various tools that can be used by the pydantic-ai agent.
The web search functionality now uses the official pydantic-ai DuckDuckGo tool.
This module contains additional utilities like URL content fetching.
"""

import logging
import requests
from typing import Dict, Any
from bs4 import BeautifulSoup
import re

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logging.warning("aiohttp not available. URL fetching will use synchronous requests.")

# Configure logging
logger = logging.getLogger(__name__)


# Note: WebSearchTool has been replaced by the official pydantic-ai DuckDuckGo tool
# Use: from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool


class URLFetchTool:
    """
    A tool for fetching and extracting content from URLs.

    This tool can fetch web pages and extract their main content,
    which can be useful for getting more details from search results.
    """

    def __init__(self, timeout: int = 10):
        """
        Initialize the URL fetch tool.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        logger.info("Initialized URLFetchTool")

    async def fetch_content(self, url: str, max_length: int = 5000) -> Dict[str, Any]:
        """
        Fetch and extract content from a URL.

        Args:
            url: The URL to fetch
            max_length: Maximum length of extracted content

        Returns:
            Dictionary with title, content, and metadata
        """
        if not AIOHTTP_AVAILABLE:
            # Fallback to synchronous fetch
            return self._fetch_content_sync(url, max_length)

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
                async with session.get(url, headers={"User-Agent": self.user_agent}) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content_from_html(html, url, max_length)
                    else:
                        return {
                            "title": "",
                            "content": "",
                            "url": url,
                            "status": f"error_http_{response.status}"
                        }

        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return {
                "title": "",
                "content": "",
                "url": url,
                "status": f"error_{type(e).__name__}"
            }

    def _fetch_content_sync(self, url: str, max_length: int = 5000) -> Dict[str, Any]:
        """Synchronous fallback for fetching content when aiohttp is not available."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return self._extract_content_from_html(response.text, url, max_length)
            else:
                return {
                    "title": "",
                    "content": "",
                    "url": url,
                    "status": f"error_http_{response.status_code}"
                }
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return {
                "title": "",
                "content": "",
                "url": url,
                "status": f"error_{type(e).__name__}"
            }

    def _extract_content_from_html(self, html: str, url: str, max_length: int) -> Dict[str, Any]:
        """Extract content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        title = ""
        title_elem = soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Extract main content
        content = ""

        # Try to find main content areas
        content_selectors = [
            'article',
            'main',
            '.content',
            '.main-content',
            '.post-content',
            '.entry-content'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = content_elem.get_text(strip=True)
                break

        # Fallback to body if no specific content area found
        if not content:
            body = soup.find('body')
            if body:
                # Remove script and style elements
                for script in soup.find_all(["script", "style"]):
                    script.decompose()
                content = body.get_text(strip=True)

        # Truncate content if too long
        if len(content) > max_length:
            content = content[:max_length] + "..."

        return {
            "title": title,
            "content": content,
            "url": url,
            "status": "success"
        }
    
    def close(self) -> None:
        """Close the session and cleanup resources."""
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("URLFetchTool closed")


# Utility functions
def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: The text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might cause issues
    text = re.sub(r'[^\w\s\-.,!?;:()\[\]{}"\']', '', text)
    
    return text.strip()


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: The URL to extract domain from
        
    Returns:
        Domain name
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""
