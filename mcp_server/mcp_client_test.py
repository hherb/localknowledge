#!/usr/bin/env python3
"""
MCP Client Test using the official MCP Python library

This script uses the official MCP Python library to connect to and test
the LocalKnowledge MCP server.

Requirements:
- mcp package: pip install mcp
- Server running on localhost:8000

Usage:
    python mcp_client_test.py
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client
import httpx

async def test_mcp_server():
    """Test the MCP server using the official MCP library"""
    
    print("LocalKnowledge MCP Server - Official MCP Client Test")
    print("=" * 60)
    
    # Server URL for SSE transport
    server_url = "http://localhost:8000/sse"
    
    try:
        # Connect using SSE transport
        async with sse_client(server_url) as (read, write):
            # Create MCP session
            async with ClientSession(read, write) as session:

                # Initialize the session
                print("🔗 Initializing MCP session...")
                init_result = await session.initialize()
                print(f"✓ Session initialized: {init_result.protocol_version}")

                # List available tools
                print("\n📋 Listing available tools...")
                tools_result = await session.list_tools()
                print(f"✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                print("\n" + "=" * 60)
                    
                    # Test 1: Search for documents
                    print("\n🔍 Test 1: Searching for COVID vaccine papers...")
                    try:
                        search_result = await session.call_tool(
                            "search_pubmed_by_keywords",
                            arguments={"text": "covid & vaccine"}
                        )
                        
                        if search_result.content:
                            # The result should be in the content
                            content = search_result.content[0]
                            if hasattr(content, 'text'):
                                result_text = content.text
                                # Try to parse as JSON if it looks like JSON
                                if result_text.strip().startswith('['):
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
                                    print(f"✓ Search result: {result_text}")
                                    test_doc_id = None
                            else:
                                print(f"✓ Search completed: {content}")
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
                            content = search_result.content[0]
                            if hasattr(content, 'text'):
                                result_text = content.text
                                if result_text.strip().startswith('['):
                                    results = json.loads(result_text)
                                    print(f"✓ Boolean search found {len(results)} documents")
                                else:
                                    print(f"✓ Boolean search result: {result_text}")
                            else:
                                print(f"✓ Boolean search completed: {content}")
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
                                content = details_result.content[0]
                                if hasattr(content, 'text'):
                                    result_text = content.text
                                    if result_text.strip().startswith('{'):
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
                                        print(f"✓ Details result: {result_text}")
                                else:
                                    print(f"✓ Details completed: {content}")
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
                                content = fulltext_result.content[0]
                                if hasattr(content, 'text'):
                                    result_text = content.text
                                    if result_text.strip().startswith('{'):
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
                                        print(f"✓ Full text result: {result_text}")
                                else:
                                    print(f"✓ Full text completed: {content}")
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
                            content = search_result.content[0]
                            if hasattr(content, 'text'):
                                result_text = content.text
                                if result_text.strip().startswith('['):
                                    results = json.loads(result_text)
                                    print(f"✓ Complex search found {len(results)} documents")
                                    if results:
                                        print(f"  First result: {results[0].get('title', 'N/A')[:80]}...")
                                else:
                                    print(f"✓ Complex search result: {result_text}")
                            else:
                                print(f"✓ Complex search completed: {content}")
                        else:
                            print("❌ Complex search returned no content")
                            
                    except Exception as e:
                        print(f"❌ Complex search failed: {e}")
                    
                    print("\n" + "=" * 60)
                    print("🎉 MCP Client test completed!")
                    
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}")
        print(f"Error type: {type(e).__name__}")
        print("\nMake sure the MCP server is running:")
        print("  python localknowledge_mcp_server.py")
        import traceback
        traceback.print_exc()

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
