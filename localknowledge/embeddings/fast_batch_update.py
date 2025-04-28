import psycopg2
from psycopg2.extras import execute_values, DictCursor
from tqdm import tqdm
import ollama
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("ollama").setLevel(logging.WARNING)

def generate_and_store_embeddings(
    db_params,
    batch_size=1000,
    embedding_model='snowflake-arctic-embed2:latest',
    embed_source_id=1
):
    conn = psycopg2.connect(**db_params)
    count_cur = conn.cursor()

    # Count total documents needing embeddings
    count_query = """
        SELECT COUNT(*)
        FROM public.document d
        LEFT JOIN public.unified_multiembeddings ume
            ON d.id = ume.document_id
            AND ume.embed_source_id = %s
        WHERE d.abstract IS NOT NULL
            AND ume.id IS NULL
    """
    count_cur.execute(count_query, (embed_source_id))
    total_docs = count_cur.fetchone()[0]
    count_cur.close()

    if total_docs == 0:
        print("All embeddings are up to date.")
        conn.close()
        return

    cur = conn.cursor(name='document_cursor', cursor_factory=DictCursor)
    cur.execute(count_query.replace("SELECT COUNT(*)", "SELECT d.id AS document_id, d.abstract"), 
                (embed_source_id, embedding_model))

    ollama_client = ollama.Client()

    insert_query = """
        INSERT INTO public.unified_multiembeddings 
        (document_id, embed_source_id, chunk_no, page_no, text, embedding, model_name)
        VALUES %s
        ON CONFLICT (document_id, embed_source_id, chunk_no, page_no, model_name) DO NOTHING
    """

    with tqdm(total=total_docs, desc="Embedding abstracts", unit="doc") as pbar:
        while True:
            batch = cur.fetchmany(batch_size)
            if not batch:
                break

            insert_data = []

            for row in batch:
                doc_id = row['document_id']
                abstract = row['abstract']

                # Generate embedding for one abstract at a time
                response = ollama_client.embeddings(model=embedding_model, prompt=abstract)
                embedding = response['embedding']

                insert_data.append((doc_id, embed_source_id, 0, 0, abstract, embedding, embedding_model))

                pbar.update(1)

            # Bulk insert for this batch
            try:
                with conn.cursor() as insert_cur:
                    execute_values(insert_cur, insert_query, insert_data)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Batch insert failed: {e}")

    cur.close()
    conn.close()



if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    db_params = {
        'dbname': os.getenv('POSTGRES_DB'),
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD'),
        'host': os.getenv('POSTGRES_HOST'),
        'port': os.getenv('POSTGRES_PORT')
    }

print(f"Generating and storing embeddings for abstracts with dbparams= {db_params}...")
generate_and_store_embeddings(db_params=db_params)