#!/usr/bin/env python3
"""
MCP Server for access to local Pubmed and MedRxiv documents

This server provides access to the local publication database
using HTTP with Server-Sent Events,
supporting multiple concurrent clients and remote connections.

Run: python mcp_server.py --port 8080
"""

import argparse
import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

# Import database functionality
from localknowledge.db.connection_pool import get_cursor

# Initialize the FastMCP server using the official SDK
mcp = FastMCP("LocalPubmed Server")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ReferenceItem:
    document_id: int
    doi: str
    title: str
    abstract: str = ''

@dataclass  
class DocumentDetails:
    document_id: int
    doi: str
    pmid: int
    title: str
    abstract: str
    authors: list[str]
    journal: str
    publication_date: str
    url: str

@dataclass
class FullText:   
    markdown: str
    pdf_url: str
    pdf_path: str

@mcp.tool()
def search_pubmed_by_keywords(text: str) -> list[ReferenceItem] | None:
    """
    Searches pubmed with keywords passed as search string
    Syntax example: (keyword1 & keyword2) | "keyword 3"
    - & works as AND operator
    - | works as OR operator
    - () can be used to group keywords
    - "" can be used to search for exact phrase instead of single words

    Args:
        text (str): The search string with boolean operators

    Returns:
        list[ReferenceItem] | None: List of matching documents or None if error
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")

    if not text.strip():
        return []

    try:
        # Use PostgreSQL full-text search with the search_vector column
        query = """
        SELECT d.id, d.doi, d.title, d.abstract, d.external_id
        FROM document d
        WHERE d.search_vector @@ plainto_tsquery('english', %s)
        ORDER BY d.publication_date DESC NULLS LAST
        LIMIT 100
        """

        with get_cursor() as cursor:
            cursor.execute(query, (text,))
            results = cursor.fetchall()

            if not results:
                return []

            # Convert to ReferenceItem objects
            reference_items = []
            for row in results:
                # Handle potential None values
                doi = row[1] if row[1] else row[4]  # Use external_id if doi is None
                abstract = row[3] if row[3] else ""

                reference_items.append(ReferenceItem(
                    document_id=row[0],
                    doi=doi,
                    title=row[2] if row[2] else "",
                    abstract=abstract
                ))

            logger.info(f"Found {len(reference_items)} documents for search: {text}")
            return reference_items

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return None

@mcp.tool()
def get_document_details(document_id: int) -> DocumentDetails | None:
    """
    Returns available document details for a given document id

    Args:
        document_id (int): The internal database ID of the document

    Returns:
        DocumentDetails | None: Document details or None if not found
    """
    if not isinstance(document_id, int):
        raise ValueError("document_id must be integer")

    try:
        query = """
        SELECT d.id, d.doi, d.external_id, d.title, d.abstract,
               d.authors, d.publication, d.publication_date, d.url
        FROM document d
        WHERE d.id = %s
        """

        with get_cursor() as cursor:
            cursor.execute(query, (document_id,))
            result = cursor.fetchone()

            if not result:
                logger.warning(f"Document not found: {document_id}")
                return None

            # Extract PMID from external_id if available
            pmid = 0
            if result[2]:  # external_id
                try:
                    pmid = int(result[2])
                except (ValueError, TypeError):
                    pmid = 0

            # Handle potential None values and convert arrays to lists
            authors = result[5] if result[5] else []
            if isinstance(authors, str):
                # If authors is stored as a string, try to parse it
                authors = [authors]

            publication_date = str(result[7]) if result[7] else ""

            document_details = DocumentDetails(
                document_id=result[0],
                doi=result[1] if result[1] else result[2] if result[2] else "",
                pmid=pmid,
                title=result[3] if result[3] else "",
                abstract=result[4] if result[4] else "",
                authors=authors,
                journal=result[6] if result[6] else "",
                publication_date=publication_date,
                url=result[8] if result[8] else ""
            )

            logger.info(f"Retrieved document details for ID: {document_id}")
            return document_details

    except Exception as e:
        logger.error(f"Error retrieving document details: {e}")
        return None

@mcp.tool()
def get_full_text(document_id: int, only_md: bool = True) -> FullText | None:
    """
    Returns the full text for a given document id

    Args:
        document_id (int): The internal database ID of the document
        only_md (bool): If True, only return markdown text (default: True)

    Returns:
        FullText | None: Full text content or None if not found
    """
    if not isinstance(document_id, int):
        raise ValueError("document_id must be integer")

    try:
        query = """
        SELECT d.full_text, d.pdf_url, d.pdf_filename
        FROM document d
        WHERE d.id = %s
        """

        with get_cursor() as cursor:
            cursor.execute(query, (document_id,))
            result = cursor.fetchone()

            if not result:
                logger.warning(f"Document not found: {document_id}")
                return None

            full_text = result[0] if result[0] else ""
            pdf_url = result[1] if result[1] else ""
            pdf_path = result[2] if result[2] else ""

            # If no full text available, return empty result
            if not full_text and only_md:
                logger.info(f"No full text available for document ID: {document_id}")
                return FullText(
                    markdown="",
                    pdf_url=pdf_url,
                    pdf_path=pdf_path
                )

            full_text_obj = FullText(
                markdown=full_text,
                pdf_url=pdf_url,
                pdf_path=pdf_path
            )

            logger.info(f"Retrieved full text for document ID: {document_id}")
            return full_text_obj

    except Exception as e:
        logger.error(f"Error retrieving full text: {e}")
        return None

def main():
    """Main function to run the MCP server"""
    parser = argparse.ArgumentParser(description='LocalKnowledge MCP Server')
    parser.add_argument('--transport', type=str, default='stdio', choices=['stdio', 'sse'],
                       help='Transport type: stdio or sse (default: stdio)')
    parser.add_argument('--port', type=int, default=8080, help='Port for SSE transport (default: 8080)')
    parser.add_argument('--host', type=str, default='localhost', help='Host for SSE transport (default: localhost)')

    args = parser.parse_args()

    print("LocalKnowledge MCP Server", flush=True)
    print("Available tools:")
    print("- search_pubmed_by_keywords: Searches pubmed with keywords passed as search string")
    print("- get_document_details: Returns available document details for a given document id")
    print("- get_full_text: Returns the full text for a given document id")

    if args.transport == 'stdio':
        print("Using stdio transport", flush=True)
        mcp.run()
    else:
        print(f"Using SSE transport on http://{args.host}:{args.port}", flush=True)
        print("Server ready for multiple concurrent clients!")
        print("Press Ctrl+C to stop the server", flush=True)
        mcp.run(transport="sse")

if __name__ == "__main__":
    print("Calling main ..........", flush=True)
    main()