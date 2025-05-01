CREATE TABLE IF NOT EXISTS model_providers(
    id serial primary key,
    name text not null,
    description text,
    base_url text,
    requires_api_key boolean default false,
    api_key text,
    is_local boolean default true,
    created_at timestamp with time zone default current_timestamp,
    is_active boolean default true
);

CREATE TABLE IF NOT EXISTS models(
    id serial primary key,
    provider_id integer references model_providers(id) NOT NULL,
    name text not null,
    description text,
    params bigint,
    quantization text,
    context_length integer,
    embedding_length integer,
    is_free boolean default false,
    is_locally_available boolean default true,
    created_at timestamp with time zone default current_timestamp,
    is_active boolean default true
);

INSERT INTO model_providers(name, description, base_url, requires_api_key, is_local)
VALUES
('ollama', 'local ollama server', 'http://localhost:11434', false, true),  -- 1
('huggingface', 'huggingface api', 'https://api-inference.huggingface.co', true, false), -- 2
('openai', 'openai api', 'https://api.openai.com', true, false), -- 3
('anthropic', 'anthropic api', 'https://api.anthropic.com', true, false), -- 4
('deepseek', 'deepseek api', 'https://api.deepseek.com', true, false), -- 5
('cohere', 'cohere api', 'https://api.cohere.ai', true, false), -- 6
('mistral', 'mistral api', 'https://api.mistral.ai', true, false); -- 7


INSERT INTO models(provider_id, name, description, params, quantization, context_length, embedding_length, is_free, is_locally_available)
VALUES
(1, 'snowflake-arctic-embed2:latest', 'Snowflake Arctic Embedding Model', 566700000 , 'F16', 8192, 1024, true, true), -- 1
(2, 'microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext', 'PubMedBERT Model', 110000000, 'F16', 512, 768, false, false), -- 2
(1, 'gemma3:4b', 'Gemma Model', 4000000000, 'Q4_K_M', 131072, 2560, true, true), -- 3
(1, 'qwen3:4b', 'Qwen Model', 4000000000, 'Q4_K_M', 40960, 2560, true, true), -- 4
(1, 'phi4:latest', 'Phi Model', 4000000000, 'Q4_K_M', 16384, 5120, true, true); -- 5

CREATE TABLE IF NOT EXISTS model_capabilities(
    id serial primary key,
    name text not null,
    description text,
    created_at timestamp with time zone default current_timestamp
);

INSERT INTO model_capabilities(name, description)
VALUES
('completion', 'Model can be used for chat-style interactions'), --1
('reasoning', 'Model has reasoning capabilities'), --2
('instruct', 'Model follows instructions well'), --3
('tool_use', 'Model can use tools/functions'), --4
('vision', 'Model can process visual inputs'), --5
('embedding', 'Model can create embeddings'), --6
('reranker', 'Model can rerank search results'), --7
('stt', 'Speech-to-text capability'), --8
('tts', 'Text-to-speech capability'); --9

CREATE TABLE IF NOT EXISTS model_capability_junction(
    model_id integer references models(id) NOT NULL,
    capability_id integer references model_capabilities(id) NOT NULL,
    primary key (model_id, capability_id)
);

INSERT INTO model_capability_junction(model_id, capability_id)
VALUES
(1, 6), -- snowflake-arctic-embed2:latest, embeding
(2, 6), -- snowflake-arctic-embed2:latest, embedding
(3, 1), -- gemma3:4b, chat
(3, 3), -- gemma3:4b, instruct
(3, 5), -- gemma3:4b, vision
(4, 1), -- qwen3:4b, chat
(4, 2), -- qwen3:4b, reasoning
(4, 3), -- qwen3:4b, instruct
(4, 4); -- qwen3:4b, tool_use

CREATE TABLE IF NOT EXISTS prompts(
    id serial primary key,
    model_id integer references models(id) DEFAULT NULL, -- if it is specific for a model
    prompt text not null,
    purpose TEXT,
    created_at timestamp with time zone default current_timestamp,
    created_by integer references users(id) DEFAULT NULL
);

CREATE INDEX idx_models_provider_id ON models(provider_id);
CREATE INDEX idx_models_name ON models(name);
CREATE INDEX idx_model_cap_junction_model ON model_capability_junction(model_id);
CREATE INDEX idx_model_cap_junction_capability ON model_capability_junction(capability_id);
CREATE INDEX idx_prompts_model_id ON prompts(model_id);
