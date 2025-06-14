#!/usr/bin/env python3
"""
Simple HTTP Test Client for LocalKnowledge MCP Server

This script makes direct HTTP requests to test the MCP server endpoints.
It's simpler than the full MCP client and easier to debug.

Requirements:
- requests package: pip install requests
- Server running on localhost:8080

Usage:
    python simple_test_client.py
"""

import requests
import json
import time

class SimpleMCPClient:
    """Simple HTTP client for testing MCP server"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def call_tool(self, tool_name, arguments):
        """Call a tool on the MCP server"""
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/message",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def list_tools(self):
        """List available tools"""
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "tools/list"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/message",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

def test_server():
    """Test the MCP server functionality"""
    
    print("LocalKnowledge MCP Server - Simple Test Client")
    print("=" * 55)
    
    client = SimpleMCPClient()
    
    # Test server connection
    print("🔗 Testing server connection...")
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print(f"✓ Server is responding (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        print("\nMake sure the server is running:")
        print("  python localknowledge_mcp_server.py")
        return
    
    # List available tools
    print("\n📋 Listing available tools...")
    tools_response = client.list_tools()
    if "error" in tools_response:
        print(f"❌ Failed to list tools: {tools_response['error']}")
    else:
        if "result" in tools_response and "tools" in tools_response["result"]:
            tools = tools_response["result"]["tools"]
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        else:
            print("⚠️  Unexpected response format")
    
    print("\n" + "=" * 55)
    
    # Test 1: Search for documents
    print("\n🔍 Test 1: Searching for COVID vaccine papers...")
    search_response = client.call_tool(
        "search_pubmed_by_keywords",
        {"text": "covid & vaccine"}
    )
    
    test_doc_id = None
    if "error" in search_response:
        print(f"❌ Search failed: {search_response['error']}")
    elif "result" in search_response:
        result = search_response["result"]
        if "content" in result and result["content"]:
            try:
                # Parse the result content
                content = result["content"][0]["text"]
                if content.startswith('[') or content.startswith('{'):
                    results = json.loads(content)
                else:
                    results = content
                
                if isinstance(results, list) and results:
                    print(f"✓ Found {len(results)} documents")
                    for i, doc in enumerate(results[:3]):
                        print(f"  {i+1}. ID: {doc.get('document_id', 'N/A')}")
                        print(f"     DOI: {doc.get('doi', 'N/A')}")
                        print(f"     Title: {doc.get('title', 'N/A')[:80]}...")
                    test_doc_id = results[0].get('document_id')
                else:
                    print("⚠️  No results found or unexpected format")
                    print(f"Response: {results}")
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse search results: {e}")
                print(f"Raw content: {result.get('content', 'No content')}")
        else:
            print("❌ Search returned no content")
    else:
        print(f"❌ Unexpected response: {search_response}")
    
    # Test 2: Boolean search
    print("\n🔍 Test 2: Boolean search with operators...")
    search_response = client.call_tool(
        "search_pubmed_by_keywords",
        {"text": "(covid | coronavirus) & (vaccine | vaccination)"}
    )
    
    if "error" in search_response:
        print(f"❌ Boolean search failed: {search_response['error']}")
    elif "result" in search_response:
        result = search_response["result"]
        if "content" in result and result["content"]:
            try:
                content = result["content"][0]["text"]
                results = json.loads(content) if content.startswith('[') else content
                if isinstance(results, list):
                    print(f"✓ Boolean search found {len(results)} documents")
                else:
                    print(f"⚠️  Unexpected result format: {type(results)}")
            except json.JSONDecodeError:
                print("❌ Failed to parse boolean search results")
        else:
            print("❌ Boolean search returned no content")
    
    # Test 3: Get document details
    if test_doc_id:
        print(f"\n📄 Test 3: Getting details for document ID {test_doc_id}...")
        details_response = client.call_tool(
            "get_document_details",
            {"document_id": test_doc_id}
        )
        
        if "error" in details_response:
            print(f"❌ Get details failed: {details_response['error']}")
        elif "result" in details_response:
            result = details_response["result"]
            if "content" in result and result["content"]:
                try:
                    content = result["content"][0]["text"]
                    details = json.loads(content) if content.startswith('{') else content
                    if isinstance(details, dict):
                        print("✓ Document details retrieved:")
                        print(f"  Title: {details.get('title', 'N/A')}")
                        print(f"  DOI: {details.get('doi', 'N/A')}")
                        print(f"  PMID: {details.get('pmid', 'N/A')}")
                        print(f"  Authors: {details.get('authors', 'N/A')}")
                        print(f"  Journal: {details.get('journal', 'N/A')}")
                        print(f"  Publication Date: {details.get('publication_date', 'N/A')}")
                        abstract = details.get('abstract', '')
                        if abstract:
                            print(f"  Abstract: {abstract[:200]}...")
                    else:
                        print(f"⚠️  Unexpected details format: {type(details)}")
                except json.JSONDecodeError:
                    print("❌ Failed to parse document details")
            else:
                print("❌ Details request returned no content")
    else:
        print("\n📄 Test 3: Skipped (no document ID available)")
    
    # Test 4: Get full text
    if test_doc_id:
        print(f"\n📖 Test 4: Getting full text for document ID {test_doc_id}...")
        fulltext_response = client.call_tool(
            "get_full_text",
            {"document_id": test_doc_id, "only_md": True}
        )
        
        if "error" in fulltext_response:
            print(f"❌ Get full text failed: {fulltext_response['error']}")
        elif "result" in fulltext_response:
            result = fulltext_response["result"]
            if "content" in result and result["content"]:
                try:
                    content = result["content"][0]["text"]
                    fulltext = json.loads(content) if content.startswith('{') else content
                    if isinstance(fulltext, dict):
                        print("✓ Full text retrieved:")
                        markdown = fulltext.get('markdown', '')
                        print(f"  Markdown length: {len(markdown)} characters")
                        print(f"  PDF URL: {fulltext.get('pdf_url', 'N/A')}")
                        print(f"  PDF Path: {fulltext.get('pdf_path', 'N/A')}")
                        if markdown:
                            print(f"  First 200 chars: {markdown[:200]}...")
                        else:
                            print("  (No markdown content available)")
                    else:
                        print(f"⚠️  Unexpected fulltext format: {type(fulltext)}")
                except json.JSONDecodeError:
                    print("❌ Failed to parse full text")
            else:
                print("❌ Full text request returned no content")
    else:
        print("\n📖 Test 4: Skipped (no document ID available)")
    
    print("\n" + "=" * 55)
    print("🎉 Test completed!")

if __name__ == "__main__":
    try:
        test_server()
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
