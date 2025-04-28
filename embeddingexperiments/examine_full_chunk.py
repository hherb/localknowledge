#!/usr/bin/env python3
import psycopg2
from psycopg2.extras import DictCursor

def examine_full_chunk():
    # Connect directly to the database
    conn = psycopg2.connect(
        dbname="rwb",
        user="rwbadmin",
        password="rwb2025admin",
        host="localhost",
        port="5432"
    )
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Get a sample chunk
            cursor.execute("""
            SELECT c.id, c.document_id, c.text, d.abstract
            FROM chunks c
            JOIN document d ON c.document_id = d.id
            LIMIT 10
            """)
            
            chunks = cursor.fetchall()
            
            for chunk in chunks:
                print(f"Chunk ID: {chunk['id']}")
                print(f"Document ID: {chunk['document_id']}")
                print(f"Chunk text length: {len(chunk['text'])}")
                print(f"Original abstract length: {len(chunk['abstract'])}")
                print("\nChunk text:")
                print("-" * 80)
                print(chunk['text'])
                print("-" * 80)
                print("\nOriginal abstract:")
                print("-" * 80)
                print(chunk['abstract'])
                print("-" * 80)
                
                # Check if abstract is in chunk text
                if chunk['abstract'] in chunk['text']:
                    print("\nThe abstract is fully contained in the chunk text.")
                else:
                    # Check if abstract is in chunk text without whitespace differences
                    if chunk['abstract'].strip() in chunk['text']:
                        print("\nThe abstract (without whitespace differences) is contained in the chunk text.")
                    else:
                        print("\nThe abstract is NOT contained in the chunk text.")
            else:
                print("No chunks found in the database.")
    finally:
        conn.close()

if __name__ == "__main__":
    examine_full_chunk()
