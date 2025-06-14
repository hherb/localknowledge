#!/usr/bin/env python3
"""
Simple MCP Client Test Script

This script connects to the LocalKnowledge MCP server and tests all available tools.
It demonstrates how to use the MCP client to interact with the server.

Requirements:
- mcp package: pip install mcp
- Server running on localhost:8080

Usage:
    python test_client.py
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import httpx

async def test_mcp_server():
    """Test the MCP server by calling all available tools"""
    
    print("LocalKnowledge MCP Server Test Client")
    print("=" * 50)
    
    # Connect to the server using SSE transport
    server_url = "http://localhost:8000"
    
    try:
        async with httpx.AsyncClient() as http_client:
            async with sse_client(server_url, http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    
                    # Initialize the session
                    await session.initialize()
                    
                    print(f"✓ Connected to MCP server at {server_url}")
                    
                    # List available tools
                    tools = await session.list_tools()
                    print(f"\n📋 Available tools: {len(tools.tools)}")
                    for tool in tools.tools:
                        print(f"  - {tool.name}: {tool.description}")
                    
                    print("\n" + "=" * 50)
                    
                    # Test 1: Search for documents
                    print("\n🔍 Test 1: Searching for COVID vaccine papers...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            arguments={"text": "covid & vaccine"}
                        )
                        
                        if search_result.content:
                            results = json.loads(search_result.content[0].text)
                            if results:
                                print(f"✓ Found {len(results)} documents")
                                
                                # Show first few results
                                for i, doc in enumerate(results[:3]):
                                    print(f"  {i+1}. ID: {doc['document_id']}")
                                    print(f"     DOI: {doc['doi']}")
                                    print(f"     Title: {doc['title'][:80]}...")
                                
                                # Store first document ID for further testing
                                test_doc_id = results[0]['document_id']
                            else:
                                print("⚠️  No results found")
                                test_doc_id = None
                        else:
                            print("❌ Search returned no content")
                            test_doc_id = None
                            
                    except Exception as e:
                        print(f"❌ Search failed: {e}")
                        test_doc_id = None
                    
                    # Test 2: Boolean search
                    print("\n🔍 Test 2: Boolean search with operators...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            arguments={"text": "(covid | coronavirus) & (vaccine | vaccination)"}
                        )
                        
                        if search_result.content:
                            results = json.loads(search_result.content[0].text)
                            if results:
                                print(f"✓ Boolean search found {len(results)} documents")
                            else:
                                print("⚠️  Boolean search returned no results")
                        else:
                            print("❌ Boolean search returned no content")
                            
                    except Exception as e:
                        print(f"❌ Boolean search failed: {e}")
                    
                    # Test 3: Get document details
                    if test_doc_id:
                        print(f"\n📄 Test 3: Getting details for document ID {test_doc_id}...")
                        try:
                            details_result = await session.call_tool(
                                "get_document_details",
                                arguments={"document_id": test_doc_id}
                            )
                            
                            if details_result.content:
                                details = json.loads(details_result.content[0].text)
                                if details:
                                    print("✓ Document details retrieved:")
                                    print(f"  Title: {details['title']}")
                                    print(f"  DOI: {details['doi']}")
                                    print(f"  PMID: {details['pmid']}")
                                    print(f"  Authors: {details['authors']}")
                                    print(f"  Journal: {details['journal']}")
                                    print(f"  Publication Date: {details['publication_date']}")
                                    print(f"  Abstract: {details['abstract'][:200]}...")
                                else:
                                    print("⚠️  No details found")
                            else:
                                print("❌ Details request returned no content")
                                
                        except Exception as e:
                            print(f"❌ Get details failed: {e}")
                    else:
                        print("\n📄 Test 3: Skipped (no document ID available)")
                    
                    # Test 4: Get full text
                    if test_doc_id:
                        print(f"\n📖 Test 4: Getting full text for document ID {test_doc_id}...")
                        try:
                            fulltext_result = await session.call_tool(
                                "get_full_text",
                                arguments={"document_id": test_doc_id, "only_md": True}
                            )
                            
                            if fulltext_result.content:
                                fulltext = json.loads(fulltext_result.content[0].text)
                                if fulltext:
                                    print("✓ Full text retrieved:")
                                    print(f"  Markdown length: {len(fulltext['markdown'])} characters")
                                    print(f"  PDF URL: {fulltext['pdf_url']}")
                                    print(f"  PDF Path: {fulltext['pdf_path']}")
                                    if fulltext['markdown']:
                                        print(f"  First 200 chars: {fulltext['markdown'][:200]}...")
                                    else:
                                        print("  (No markdown content available)")
                                else:
                                    print("⚠️  No full text found")
                            else:
                                print("❌ Full text request returned no content")
                                
                        except Exception as e:
                            print(f"❌ Get full text failed: {e}")
                    else:
                        print("\n📖 Test 4: Skipped (no document ID available)")
                    
                    # Test 5: Complex search query
                    print("\n🔍 Test 5: Complex search with exact phrases...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            arguments={"text": '"machine learning" & "medical imaging"'}
                        )
                        
                        if search_result.content:
                            results = json.loads(search_result.content[0].text)
                            if results:
                                print(f"✓ Complex search found {len(results)} documents")
                                if results:
                                    print(f"  First result: {results[0]['title'][:80]}...")
                            else:
                                print("⚠️  Complex search returned no results")
                        else:
                            print("❌ Complex search returned no content")
                            
                    except Exception as e:
                        print(f"❌ Complex search failed: {e}")
                    
                    print("\n" + "=" * 50)
                    print("🎉 Test completed!")
                    
    except Exception as e:
        print(f"❌ Failed to connect to server: {e}")
        print("\nMake sure the MCP server is running:")
        print("  python localknowledge_mcp_server.py")

def main():
    """Main function to run the async test"""
    try:
        asyncio.run(test_mcp_server())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
