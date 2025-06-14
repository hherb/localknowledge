#!/bin/bash

# Environment setup script for LocalKnowledge MCP Server
# This script sets up the required environment variables for database connection

echo "Setting up environment variables for LocalKnowledge MCP Server..."

# Database configuration - adjust these values for your setup
export POSTGRES_DB="localknowledge"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD=""
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"

echo "Environment variables set:"
echo "  POSTGRES_DB=$POSTGRES_DB"
echo "  POSTGRES_USER=$POSTGRES_USER"
echo "  POSTGRES_HOST=$POSTGRES_HOST"
echo "  POSTGRES_PORT=$POSTGRES_PORT"
echo "  POSTGRES_PASSWORD=[hidden]"

echo ""
echo "You can now run the MCP server or tests:"
echo "  python localknowledge_mcp_server.py"
echo "  python proper_mcp_client_test.py"
echo "  python test_with_env.py"

# Keep the environment active for this shell session
echo ""
echo "Environment is now set for this shell session."
echo "Run 'source setup_env.sh' to set these variables in your current shell."
