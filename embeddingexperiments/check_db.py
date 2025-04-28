#!/usr/bin/env python3
from pubmedbert_experiment import get_cursor

def check_tables():
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunks_count = cursor.fetchone()[0]
        print(f"Chunks in database: {chunks_count}")
        
        cursor.execute("SELECT COUNT(*) FROM emb_768")
        embeddings_count = cursor.fetchone()[0]
        print(f"Embeddings in database: {embeddings_count}")
        
        if chunks_count > 0:
            cursor.execute("SELECT id, document_id, text FROM chunks LIMIT 1")
            chunk = cursor.fetchone()
            print(f"Sample chunk: ID={chunk['id']}, Document ID={chunk['document_id']}, Text length={len(chunk['text'])}")

if __name__ == "__main__":
    check_tables()
