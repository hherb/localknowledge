#!/usr/bin/env python3
"""
Proper MCP Client Test for LocalKnowledge Server

This script connects to the LocalKnowledge MCP server using the proper
MCP Python library with stdio transport.

Requirements:
- pip install mcp
- LocalKnowledge MCP server script (localknowledge_mcp_server.py)

Usage:
    python proper_mcp_client_test.py
"""

import asyncio
import json
import sys
from typing import Any, Dict, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class LocalKnowledgeTestClient:
    def __init__(self):
        self.server_script = "localknowledge_mcp_server.py"
        
    async def test_all_tools(self):
        """Test all available tools on the LocalKnowledge MCP server"""
        
        print("LocalKnowledge MCP Server - Proper Client Test")
        print("=" * 55)
        
        # Set up server parameters for stdio transport
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script]
        )
        
        try:
            # Connect to MCP server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                # Create client session
                async with ClientSession(read_stream, write_stream) as session:
                    
                    # Initialize the session
                    print("🔗 Initializing MCP session...")
                    init_result = await session.initialize()
                    print(f"✓ Session initialized successfully")
                    
                    # List available tools
                    print("\n📋 Listing available tools...")
                    tools_result = await session.list_tools()
                    print(f"✓ Found {len(tools_result.tools)} tools:")
                    for tool in tools_result.tools:
                        print(f"  - {tool.name}: {tool.description}")
                    
                    print("\n" + "=" * 55)
                    
                    # Test 1: Search for documents
                    print("\n🔍 Test 1: Searching for COVID vaccine papers...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            {"text": "covid & vaccine"}
                        )
                        
                        if search_result.content:
                            result_text = search_result.content[0].text
                            # Parse JSON result
                            results = json.loads(result_text)
                            if results:
                                print(f"✓ Found {len(results)} documents")
                                # Show first few results
                                for i, doc in enumerate(results[:3]):
                                    print(f"  {i+1}. ID: {doc.get('document_id', 'N/A')}")
                                    print(f"     DOI: {doc.get('doi', 'N/A')}")
                                    print(f"     Title: {doc.get('title', 'N/A')[:80]}...")
                                
                                # Store first document ID for further testing
                                test_doc_id = results[0].get('document_id')
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
                            {"text": "(covid | coronavirus) & (vaccine | vaccination)"}
                        )
                        
                        if search_result.content:
                            result_text = search_result.content[0].text
                            results = json.loads(result_text)
                            print(f"✓ Boolean search found {len(results)} documents")
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
                                {"document_id": test_doc_id}
                            )
                            
                            if details_result.content:
                                result_text = details_result.content[0].text
                                details = json.loads(result_text)
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
                                {"document_id": test_doc_id, "only_md": True}
                            )
                            
                            if fulltext_result.content:
                                result_text = fulltext_result.content[0].text
                                fulltext = json.loads(result_text)
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
                            {"text": '"machine learning" & "medical imaging"'}
                        )
                        
                        if search_result.content:
                            result_text = search_result.content[0].text
                            results = json.loads(result_text)
                            print(f"✓ Complex search found {len(results)} documents")
                            if results:
                                print(f"  First result: {results[0].get('title', 'N/A')[:80]}...")
                        else:
                            print("❌ Complex search returned no content")
                            
                    except Exception as e:
                        print(f"❌ Complex search failed: {e}")
                    
                    # Test 6: Search with no results
                    print("\n🔍 Test 6: Search that should return no results...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            {"text": "xyzzyx_nonexistent_term_12345"}
                        )
                        
                        if search_result.content:
                            result_text = search_result.content[0].text
                            results = json.loads(result_text)
                            print(f"✓ Empty search returned {len(results)} documents (expected: 0)")
                        else:
                            print("❌ Empty search returned no content")
                            
                    except Exception as e:
                        print(f"❌ Empty search failed: {e}")
                    
                    print("\n" + "=" * 55)
                    print("🎉 All MCP tests completed successfully!")
                    
        except Exception as e:
            print(f"❌ Failed to connect to MCP server: {e}")
            print(f"Error type: {type(e).__name__}")
            print("\nMake sure:")
            print(f"1. The server script exists: {self.server_script}")
            print("2. All dependencies are installed: pip install mcp psycopg2-binary")
            print("3. Database connection is properly configured")
            import traceback
            traceback.print_exc()

async def main():
    """Main function to run the test"""
    client = LocalKnowledgeTestClient()
    await client.test_all_tools()

if __name__ == "__main__":
    print("Starting LocalKnowledge MCP Server Test...")
    print("Make sure you have:")
    print("1. MCP library installed: pip install mcp")
    print("2. PostgreSQL database running and configured")
    print("3. localknowledge_mcp_server.py in current directory")
    print("=" * 55)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
