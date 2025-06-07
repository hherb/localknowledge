import psycopg2
import time

def get_connection():
    """gets a connectonfrom the connection pool"""
    return psycopg2.connect(
        dbname="knowledgebase",
        user="rwbadmin",
        password="rwb2025admin",
        host="localhost",
        port="5432"
    )


def count_missing_embeddings(dbconn,
                             chunktype_id : int = 1,
                             chunking_strategy_id : int = 2, 
                             model_id : int =1) -> int:
    """Counts the number of chunks that are missing embeddings
    Args:
        dbconn: database connection
        chunk_type_id: id of the chunk type
        chunking_strategy_id: id of the chunking strategy
        model_id: id of the embedding model

    Returns:
        number of chunks that are missing embeddings    
    """
    with dbconn.cursor() as cursor:
        cursor.execute("""
        SELECT COUNT(*) as count
        FROM public.chunks c
        LEFT JOIN public.emb_1024 e ON c.id = e.chunk_id AND e.model_id = %s
        WHERE c.chunktype_id = %s 
        AND c.chunking_strategy_id = %s
        AND e.chunk_id IS NULL
        """, (model_id, chunktype_id, chunking_strategy_id))
        count = cursor.fetchone()[0]
        return count
    
def fetch_chunks_missing_embeddings(dbconn,
                                  chunktype_id : int = 1,
                                  chunking_strategy_id : int = 2, 
                                  model_id : int =1,
                                  limit : int = 100,
                                  offset : int = 0) -> list[dict]:
    """Fetches chunks that are missing embeddings
    Args:
        dbconn: database connection
        chunk_type_id: id of the chunk type
        chunking_strategy_id: id of the chunking strategy
        model_id: id of the embedding model
        limit: number of chunks to fetch
        offset: offset for pagination

    Returns:
        list of chunks that are missing embeddings
    
    """
    with dbconn.cursor() as cursor:
        cursor.execute("""
        SELECT c.id, c.document_id, c.chunk_no, c.page_start, c.page_end,
               c.text, c.chunktype_id, d.title as document_title, d.abstract
        FROM public.chunks c
        JOIN public.chunktypes ct ON c.chunktype_id = ct.id
        JOIN public.document d ON c.document_id = d.id
        WHERE ct.chunktype = 'abstract'
        AND NOT EXISTS (
            SELECT 1 FROM public.emb_1024 e
            WHERE e.chunk_id = c.id AND e.model_id = %s
        )
        ORDER BY c.id
        LIMIT %s
        OFFSET %s
        """, (model_id, limit, offset))
        chunks = cursor.fetchall()
        return chunks


if __name__=="__main__":
    dbconn = get_connection()
    count = count_missing_embeddings(dbconn)
    print(f"Found {count} chunks without embeddings")
