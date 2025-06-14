#!/bin/bash

# Test script for LocalKnowledge MCP Server using curl
# This script tests the MCP server endpoints using curl commands
#
# Requirements:
# - curl command available
# - jq for JSON formatting (optional, for pretty output)
# - Server running on localhost:8080
#
# Usage:
#   chmod +x test_with_curl.sh
#   ./test_with_curl.sh

SERVER_URL="http://localhost:8000"
CONTENT_TYPE="Content-Type: application/json"

echo "LocalKnowledge MCP Server - Curl Test Script"
echo "============================================="

# Check if server is running
echo ""
echo "🔗 Testing server connection..."
if curl -s --connect-timeout 5 "$SERVER_URL" > /dev/null; then
    echo "✓ Server is responding"
else
    echo "❌ Cannot connect to server at $SERVER_URL"
    echo "Make sure the server is running:"
    echo "  python localknowledge_mcp_server.py"
    exit 1
fi

# Function to make MCP tool calls
call_tool() {
    local tool_name="$1"
    local arguments="$2"
    local id=$(date +%s)
    
    local payload=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "id": $id,
    "method": "tools/call",
    "params": {
        "name": "$tool_name",
        "arguments": $arguments
    }
}
EOF
)
    
    echo "Calling tool: $tool_name"
    echo "Arguments: $arguments"
    echo ""
    
    if command -v jq > /dev/null; then
        curl -s -X POST "$SERVER_URL/message" \
             -H "$CONTENT_TYPE" \
             -d "$payload" | jq '.'
    else
        curl -s -X POST "$SERVER_URL/message" \
             -H "$CONTENT_TYPE" \
             -d "$payload"
    fi
    echo ""
}

# Function to list tools
list_tools() {
    local id=$(date +%s)
    
    local payload=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "id": $id,
    "method": "tools/list"
}
EOF
)
    
    echo "📋 Listing available tools..."
    echo ""
    
    if command -v jq > /dev/null; then
        curl -s -X POST "$SERVER_URL/message" \
             -H "$CONTENT_TYPE" \
             -d "$payload" | jq '.result.tools[] | {name: .name, description: .description}'
    else
        curl -s -X POST "$SERVER_URL/message" \
             -H "$CONTENT_TYPE" \
             -d "$payload"
    fi
    echo ""
}

echo ""
echo "============================================="

# List available tools
list_tools

echo "============================================="

# Test 1: Search for documents
echo ""
echo "🔍 Test 1: Searching for COVID vaccine papers..."
echo ""
call_tool "search_pubmed_by_keywords" '{"text": "covid & vaccine"}'

echo "============================================="

# Test 2: Boolean search
echo ""
echo "🔍 Test 2: Boolean search with operators..."
echo ""
call_tool "search_pubmed_by_keywords" '{"text": "(covid | coronavirus) & (vaccine | vaccination)"}'

echo "============================================="

# Test 3: Get document details (using a sample document ID)
echo ""
echo "📄 Test 3: Getting document details (using document ID 1)..."
echo ""
call_tool "get_document_details" '{"document_id": 1}'

echo "============================================="

# Test 4: Get full text (using a sample document ID)
echo ""
echo "📖 Test 4: Getting full text (using document ID 1)..."
echo ""
call_tool "get_full_text" '{"document_id": 1, "only_md": true}'

echo "============================================="

# Test 5: Complex search with exact phrases
echo ""
echo "🔍 Test 5: Complex search with exact phrases..."
echo ""
call_tool "search_pubmed_by_keywords" '{"text": "\"machine learning\" & \"medical imaging\""}'

echo "============================================="
echo ""
echo "🎉 Test completed!"
echo ""
echo "Note: Some tests may show errors if:"
echo "- No documents match the search criteria"
echo "- Document ID 1 doesn't exist in your database"
echo "- The database is empty"
echo ""
echo "This is normal for testing purposes."
