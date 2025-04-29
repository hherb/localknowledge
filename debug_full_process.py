#!/usr/bin/env python3
"""
Debug script to test the full chunking process with a single document.
"""

import sys
import time
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk as DBChunk
from localknowledge.textprocessing.chunking import AdaptiveTextChunker

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    # Get a single document to test chunking
    document_id = 62024974  # From the previous debug script
    
    # Chunking strategy ID
    strategy_id = 2  # This is the ID for adaptive_text_chunker_1500
    
    # Chunk type ID
    chunktype_id = 1  # ID for 'abstract' in the chunktypes table
    
    print(f"Testing full process for document {document_id}")
    
    try:
        # Create database manager
        db_manager = ChunkingDatabaseManager()
        
        # First, check if chunks already exist for this document and strategy
        with get_cursor() as cursor:
            check_query = """
            SELECT COUNT(*) as count
            FROM chunks
            WHERE document_id = %s
            AND chunking_strategy_id = %s
            """
            cursor.execute(check_query, (document_id, strategy_id))
            result = cursor.fetchone()
            existing_chunks = result['count'] if result else 0
            
            if existing_chunks > 0:
                print(f"Document {document_id} already has {existing_chunks} chunks for strategy {strategy_id}")
                
                # Delete existing chunks for testing
                print(f"Deleting existing chunks for document {document_id} and strategy {strategy_id}")
                delete_query = """
                DELETE FROM chunks
                WHERE document_id = %s
                AND chunking_strategy_id = %s
                """
                cursor.execute(delete_query, (document_id, strategy_id))
                print(f"Deleted {cursor.rowcount} chunks")
        
        # Get the document
        with get_cursor() as cursor:
            query = """
            SELECT d.id, d.title, d.abstract
            FROM document d
            WHERE d.id = %s
            """
            
            # Execute the query
            cursor.execute(query, (document_id,))
            
            # Fetch the document
            document = cursor.fetchone()
            
            if not document:
                print(f"Document {document_id} not found")
                return 1
            
            # Print document info
            print(f"Document ID: {document['id']}")
            print(f"Title: {document['title']}")
            print(f"Abstract length: {len(document['abstract'])} characters")
        
        # Initialize chunker
        chunker = AdaptiveTextChunker(
            max_chunk_size=1500,
            overlap=100,
            min_chunk_size=100
        )
        
        # Create metadata
        metadata = {
            'title': document['title'],
            'source': 'abstract',
            'document_id': document['id']
        }
        
        # Time the chunking process
        start_time = time.time()
        
        # Chunk the abstract
        chunks = chunker.chunk(document['abstract'], metadata=metadata)
        
        # Print chunking results
        print(f"Chunking completed in {time.time() - start_time:.4f} seconds")
        print(f"Created {len(chunks)} chunks")
        
        # Convert to database chunks
        db_chunks = []
        for i, chunk in enumerate(chunks):
            db_chunk = chunk.to_db_chunk(
                document_id=document_id,
                chunking_strategy_id=strategy_id,
                chunktype_id=chunktype_id,
                document_title=document['title'],
                chunk_no=i
            )
            db_chunks.append(db_chunk)
        
        # Time the insertion process
        start_time = time.time()
        
        # Insert chunks into database
        chunk_ids = db_manager.batch_insert_chunks(db_chunks)
        
        # Print insertion results
        print(f"Insertion completed in {time.time() - start_time:.4f} seconds")
        print(f"Inserted {len(chunk_ids)} chunks with IDs: {chunk_ids}")
        
        # Verify the chunks were inserted
        with get_cursor() as cursor:
            verify_query = """
            SELECT COUNT(*) as count
            FROM chunks
            WHERE document_id = %s
            AND chunking_strategy_id = %s
            """
            cursor.execute(verify_query, (document_id, strategy_id))
            result = cursor.fetchone()
            inserted_chunks = result['count'] if result else 0
            
            print(f"Verification: Document {document_id} now has {inserted_chunks} chunks for strategy {strategy_id}")
            
            # Clean up - delete the inserted chunks
            if chunk_ids:
                print(f"Cleaning up - deleting inserted chunks with IDs: {chunk_ids}")
                placeholders = ', '.join(['%s'] * len(chunk_ids))
                delete_query = f"""
                DELETE FROM chunks
                WHERE id IN ({placeholders})
                """
                cursor.execute(delete_query, chunk_ids)
                print(f"Deleted {cursor.rowcount} chunks")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
