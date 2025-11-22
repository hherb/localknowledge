"""
MCP (Model Context Protocol) module for LocalKnowledge.

This module provides MCP server implementations for accessing the LocalKnowledge
PostgreSQL database, enabling AI assistants to query the knowledge base.

Components:
- mcp_postgres: FastMCP-based read-only PostgreSQL query server
- mcp_postgres_server: Class-based MCP server implementation
"""

# Note: The MCP servers are typically run as standalone processes,
# so we don't import them by default to avoid side effects.
# Import explicitly when needed:
#   from localknowledge.mcp.mcp_postgres import mcp, query_postgres
#   from localknowledge.mcp.mcp_postgres_server import PostgreSQLMCPServer

__all__ = [
    "mcp_postgres",
    "mcp_postgres_server",
]
