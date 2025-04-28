#!/usr/bin/env python3
import psycopg2
from psycopg2.extras import DictCursor

def check_chunks():
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
            # Get a sample of chunks
            cursor.execute("""
            SELECT id, document_id, text
            FROM chunks
            LIMIT 5
            """)
            
            chunks = cursor.fetchall()
            
            for chunk in chunks:
                print(f"Chunk ID: {chunk['id']}")
                print(f"Document ID: {chunk['document_id']}")
                print(f"Text length: {len(chunk['text'])}")
                print(f"Text preview: {chunk['text'][:200]}...")
                print("-" * 80)
    finally:
        conn.close()

if __name__ == "__main__":
    check_chunks()
