CREATE TABLE IF NOT EXISTS chunking_strategies (
    id SERIAL PRIMARY KEY,
    strategy_name text NOT NULL,
    modelname text,
    parameters jsonb
);

CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id integer,
    chunking_strategy_id integer,
    chunktype_id integer,
    document_title text,
    text text,
    chunklength integer,
    chunk_no integer NOT NULL,
    page_start integer DEFAULT 0,
    page_end integer DEFAULT 0,
    metadata jsonb
);

CREATE TABLE IF NOT EXISTS chunktypes (
    id SERIAL PRIMARY KEY,
    chunktype text NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_base (
    id SERIAL PRIMARY KEY,
    chunk_id integer NOT NULL,
    model_id integer
);

CREATE TABLE IF NOT EXISTS emb_768 (
    embedding public.vector(768)
)
INHERITS (embedding_base);

CREATE TABLE IF NOT EXISTS emb_1024 (
    embedding vector(1024)
)
INHERITS (embedding_base);

CREATE TABLE IF NOT EXISTS embedding_models (
    id SERIAL NOT NULL,
    provider_id integer,
    model_name text NOT NULL,
    model_description text,
    model_parameters jsonb
);

CREATE TABLE IF NOT EXISTS embedding_provider (
    id SERIAL NOT NULL,
    provider_name text NOT NULL,
    base_url text
);

INSERT INTO embedding_provider (provider_name, base_url)
VALUES 
('ollama', 'http://localhost:11434'),
('huggingface', 'https://api-inference.huggingface.co');

insert into embedding_models (provider_id, model_name)
VALUES 
(1, 'snowflake-arctic-embed2:latest'),
(2, 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext'),
(2, 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb');

-- GIN index for title ILIKE %pattern%
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_document_title_trgm ON public.document USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_document_all_keywords ON public.document USING gin (all_keywords);

CREATE OR REPLACE FUNCTION trim_text_array(input text[], max_bytes integer)
RETURNS text[] LANGUAGE plpgsql AS $$
DECLARE
    output text[] := '{}';
    total_bytes integer := 0;
    elem text;
BEGIN
    FOREACH elem IN ARRAY input LOOP
        total_bytes := total_bytes + length(elem)::integer;  -- length() gives byte count in PostgreSQL
        IF total_bytes > max_bytes THEN
            RETURN output;
        END IF;
        output := array_append(output, elem);
    END LOOP;
    RETURN output;
END;
$$;

UPDATE document
SET all_keywords = trim_text_array(all_keywords, 2000)
WHERE cardinality(all_keywords) > 0;

