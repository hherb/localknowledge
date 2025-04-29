CREATE TABLE public.chunking_strategies (
    id integer NOT NULL,
    strategy_name text NOT NULL,
    modelname text,
    parameters jsonb
);


CREATE TABLE public.chunks (
    id integer NOT NULL,
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

CREATE TABLE public.chunktypes (
    id integer NOT NULL,
    chunktype text NOT NULL
);


CREATE TABLE public.embedding_base (
    id integer NOT NULL,
    chunk_id integer NOT NULL,
    model_id integer
);

CREATE TABLE public.emb_768 (
    embedding public.vector(768)
)
INHERITS (public.embedding_base);

CREATE TABLE public.emb_1024 (
    embedding public.vector(1024)
)
INHERITS (public.embedding_base);

CREATE TABLE public.embedding_models (
    id integer NOT NULL,
    provider_id integer,
    model_name text NOT NULL,
    model_description text,
    model_parameters jsonb
);

CREATE TABLE public.embedding_provider (
    id integer NOT NULL,
    provider_name text NOT NULL,
    base_url text
);

INSERT INTO embedding_provider (provider_name, base_url)
VALUES 
('ollama', 'http://localhost:11434'),
('huggingface', 'https://api-inference.huggingface.co');

insert into embedding_models (provider_id, model_name)
VALUES (1, 'snowflake-arctic-embed2:latest');

insert into embedding_models (provider_id, model_name)
VALUES (2, 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext');

insert into embedding_models (provider_id, model_name)
VALUES (2, 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb');

- GIN index for title ILIKE %pattern%
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_document_title_trgm ON public.document USING gin (title gin_trgm_ops);
CREATE INDEX idx_document_all_keywords ON public.document USING gin (all_keywords);



