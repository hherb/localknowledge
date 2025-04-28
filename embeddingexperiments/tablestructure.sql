CREATE TABLE public.categories (
    id integer NOT NULL,
    name text NOT NULL,
    description text
);

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


CREATE TABLE public.document (
    id integer NOT NULL,
    source_id integer,
    external_id text NOT NULL,
    doi text,
    title text,
    abstract text,
    category_id integer,
    keywords text[],
    augmented_keywords text[],
    mesh_terms text[],
    authors text[],
    publication text,
    publication_date date,
    url text,
    pdf_url text,
    pdf_filename text,
    full_text text,
    added_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    withdrawn_date timestamp without time zone,
    withdrawn_reason text,
    all_keywords text[]
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


CREATE TABLE public.sources (
    id integer NOT NULL,
    name text NOT NULL,
    url text,
    is_reputable boolean DEFAULT false,
    is_free boolean DEFAULT true
);

CREATE TABLE public.summaries (
    id integer NOT NULL,
    summary text,
    evaluation boolean,
    reason text,
    interests text[],
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    document_id integer NOT NULL
);

