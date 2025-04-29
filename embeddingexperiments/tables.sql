CREATE extension IF NOT EXISTS vector;
-- DROP TABLE IF EXISTS chunking_strategies;
CREATE TABLE chunking_strategies (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    modelname TEXT DEFAULT NULL,
    parameters JSONB
);

INSERT INTO chunking_strategies(strategy_name, parameters)
VALUES ('simple_splitter', '{"chunksize": 500, "overlap": 50}');


-- DROP TABLE IF EXISTS chunktypes;
CREATE TABLE chunktypes (
    id SERIAL PRIMARY KEY,
    chunktype TEXT NOT NULL
);

INSERT INTO chunktypes (chunktype)
VALUES 
('abstract'),
('fulltext'),
('summary'),
('HyDE'),
('synth QA');

-- DROP TABLE IF EXISTS chunks;
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document(id),
    chunking_strategy_id INTEGER REFERENCES chunking_strategies(id),
    chunktype_id INTEGER REFERENCES chunktypes(id),
    document_title TEXT,
    text TEXT,
    chunklength INTEGER,
    chunk_no INTEGER NOT NULL,
    page_start INTEGER DEFAULT 0,
    page_end INTEGER DEFAULT 0,
    metadata JSONB
);

-- DROP TABLE IF EXISTS embedding_provider;
CREATE TABLE embedding_provider (
    id SERIAL PRIMARY KEY,
    provider_name TEXT NOT NULL,
    base_url TEXT
);

INSERT INTO embedding_provider (provider_name, base_url)
VALUES 
('ollama', 'http://localhost:11434'),
('huggingface', 'https://api-inference.huggingface.co');

-- DROP TABLE IF EXISTS embedding_models;
CREATE TABLE embedding_models (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES embedding_provider(id),
    model_name TEXT NOT NULL,
    model_description TEXT,
    model_parameters JSONB
);

insert into embedding_models (provider_id, model_name)
VALUES (1, 'snowflake-arctic-embed2:latest');

insert into embedding_models (provider_id, model_name)
VALUES (2, 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext');

insert into embedding_models (provider_id, model_name)
VALUES (2, 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb');

-- DROP TABLE IF EXISTS embedding_base;
CREATE TABLE embedding_base (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    model_id INTEGER REFERENCES embedding_models(id)
);

-- DROP TABLE IF EXISTS emb_pubmedbert;
CREATE TABLE IF NOT EXISTS emb_pubmedbert(
	embedding vector(768)
) INHERITS (embedding_base);

