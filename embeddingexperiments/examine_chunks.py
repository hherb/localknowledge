#!/usr/bin/env python3
from pubmedbert_experiment import get_cursor
import json

def examine_chunks():
    with get_cursor() as cursor:
        # Get a sample of chunks
        cursor.execute("""
        SELECT id, document_id, text, metadata
        FROM chunks
        LIMIT 25
        """)
        
        chunks = cursor.fetchall()
        
        for chunk in chunks:
            print(f"Chunk ID: {chunk['id']}")
            print(f"Document ID: {chunk['document_id']}")
            print(f"Text length: {len(chunk['text'])}")
            print(f"Text preview: {chunk['text'][:200]}...")
            
            # Parse metadata
            if chunk['metadata']:
                metadata = json.loads(chunk['metadata'])
                print(f"Metadata: {metadata}")
            
            print("-" * 80)

if __name__ == "__main__":
    examine_chunks()
