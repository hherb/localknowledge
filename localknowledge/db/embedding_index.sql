-- Index: emb_768_chunk_model_idx

-- DROP INDEX IF EXISTS emb_768_chunk_model_idx;

CREATE INDEX IF NOT EXISTS emb_768_chunk_model_idx
    ON emb_768 USING btree
    (chunk_id ASC NULLS LAST, model_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Index: emb_1024_chunk_model_idx

-- DROP INDEX IF EXISTS public.emb_1024_chunk_model_idx;

CREATE INDEX IF NOT EXISTS emb_1024_chunk_model_idx
    ON public.emb_1024 USING btree
    (chunk_id ASC NULLS LAST, model_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Index: emb_1024_embedding_idx

-- DROP INDEX IF EXISTS public.emb_1024_embedding_idx;

CREATE INDEX IF NOT EXISTS emb_1024_embedding_idx
    ON public.emb_1024 USING ivfflat
    (embedding vector_cosine_ops)
    TABLESPACE pg_default;

